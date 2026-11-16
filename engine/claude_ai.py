"""The Claude calls: reviewing one section of a project and answering in chat, through Anthropic's Messages API.

The same jobs as ai.py does with Gemini, with the same prompts, skills and schema. Drawings are sent inline
(base64), so nothing is stored on Anthropic's side between requests. Claude Opus 5.5 is used unless
NORMA_CLAUDE_MODEL names another; if it declines a request, the API passes it to a fallback model.
"""
import base64
import json
import os

import anthropic

from ai import CHAT_SYSTEM, SEARCH_DESCRIPTION, page_records, search
from errors import ReviewError
import pdf_tools
import sections
from settings import read_key

MODEL = os.environ.get('NORMA_CLAUDE_MODEL') or 'claude-opus-5-5'
BETAS = ['server-side-fallback-2026-07-01']
FALLBACKS = 'default'              # the API picks the fallback model by the kind of refusal
MAX_PDF_BYTES = 20 * 1000 * 1000   # a request is at most 32 MB, and base64 adds a third
MAX_PAGES = 600
REVIEW_TOKENS = 128000             # thinking counts too, and a big section has many results
CHAT_TOKENS = 16000
TOOLS = [{
    'name': 'search_regulation',
    'description': SEARCH_DESCRIPTION,
    'input_schema': {'type': 'object', 'additionalProperties': False, 'required': ['query'], 'properties': {'query': {'type': 'string'}}},
    'strict': True,
    'eager_input_streaming': True,   # inputs arrive as they are written; search() checks them
}]


def client():
    return anthropic.Anthropic(api_key=read_key('claude'), max_retries=2)


def api_error(error):
    """Maps API failures to messages the user can act on. Anthropic's own words go along as the detail."""
    text = str(error)[:400]
    if isinstance(error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return ReviewError('ai_key_rejected', text)
    if isinstance(error, anthropic.RequestTooLargeError):
        return ReviewError('pdf_too_large', text)
    if isinstance(error, (anthropic.RateLimitError, anthropic.OverloadedError, anthropic.ServiceUnavailableError, anthropic.InternalServerError)):
        return ReviewError('ai_busy', text)
    if isinstance(error, anthropic.APIConnectionError):
        return ReviewError('ai_unreachable', text)
    if isinstance(error, anthropic.BadRequestError) and 'credit balance' in text.lower():
        return ReviewError('ai_no_credit', text)
    if isinstance(error, anthropic.APIStatusError) and error.status_code >= 500:
        return ReviewError('ai_busy', text)
    return ReviewError('ai_failed', text)


def strict(schema):
    """The schema as structured outputs take it: a nullable type becomes anyOf."""
    if isinstance(schema, dict):
        if isinstance(schema.get('type'), list):
            kinds = schema['type']
            rest = {k: strict(v) for k, v in schema.items() if k != 'type'}
            return {'anyOf': [dict(rest, type=kind) if kind != 'null' else {'type': 'null'} for kind in kinds]}
        return {k: strict(v) for k, v in schema.items()}
    if isinstance(schema, list):
        return [strict(item) for item in schema]
    return schema


def pdf_block(path, cached=False):
    block = {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': base64.standard_b64encode(path.read_bytes()).decode()}}
    return dict(block, cache_control={'type': 'ephemeral'}) if cached else block


def content(folder, request):
    """One section's request as Claude takes it: the sheets, close-ups of sheets without text, the notes, the text items."""
    path = pdf_tools.for_model(request['pdf'], folder / f'model-claude-{request["key"]}.pdf', MAX_PDF_BYTES, sections.by_importance(request['pages']))
    if path is None:
        raise ReviewError('pdf_too_large')
    blocks = [pdf_block(path)]
    for number, tiles in request['tiles']:
        blocks.append({'type': 'text', 'text': f'Close-up tiles of page {number}, left to right, top to bottom:'})
        blocks += [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.standard_b64encode(tile).decode()}} for tile in tiles]
    blocks += [{'type': 'text', 'text': note} for note in request['notes']]
    blocks.append({'type': 'text', 'text': request['listing']})
    return blocks


def ask(folder, request):
    """One section's review by Claude: the parsed answer to the request's schema."""
    if len(request['pages']) > MAX_PAGES:
        raise ReviewError('too_many_pages')
    blocks = content(folder, request)
    try:
        fast = bool(request.get('fast'))   # reading the building data: a light pass
        with client().beta.messages.stream(
            model=MODEL, max_tokens=CHAT_TOKENS if fast else REVIEW_TOKENS, betas=BETAS, fallbacks=FALLBACKS,
            system=[{'type': 'text', 'text': request['system'], 'cache_control': {'type': 'ephemeral'}}],
            messages=[{'role': 'user', 'content': blocks}],
            output_config={'effort': 'low' if fast else 'high', 'format': {'type': 'json_schema', 'schema': strict(request['schema'])}},
        ) as stream:
            message = stream.get_final_message()
    except anthropic.APIError as error:
        raise api_error(error)
    if message.stop_reason == 'refusal':
        raise ReviewError('ai_refused', getattr(message.stop_details, 'explanation', '') or '')
    text = ''.join(block.text for block in message.content if block.type == 'text')
    if message.stop_reason == 'max_tokens':
        raise ReviewError('ai_truncated', f'{len(text)} characters before the limit')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ReviewError('ai_failed', text[:200])


def review(folder, sizes, anchors, measured=None, progress=lambda done, total: None, facts_note=None):
    """The whole project reviewed by Claude, one section at a time."""
    return sections.review(folder, sizes, anchors, ask, measured, progress, facts_note)


# ---------- Chat ----------

def chat_context(folder, summary):
    """What chat is told about an open report: the drawing and the results of the check. Cached, since every turn repeats it."""
    path = pdf_tools.for_model(folder / 'drawing.pdf', folder / 'model-claude.pdf', MAX_PDF_BYTES, sections.by_importance(page_records(folder)))
    if path is None:
        raise ReviewError('pdf_too_large')
    return [pdf_block(path, cached=True), {'type': 'text', 'text': f'Report of the check:\n{summary}'}]


def conversation(question, context, state):
    """The messages of a chat so far. Earlier answers go back as text, the same each turn, so the history
    stays append-only and the cached prefix (the drawing) keeps being reused."""
    said = state.get('messages', [])
    first = said[0]['text'] if said else question
    messages = [{'role': 'user', 'content': context() + [{'type': 'text', 'text': first}]}]
    messages += [{'role': m['role'], 'content': m['text'] or '…'} for m in said[1:]]
    if said:
        messages.append({'role': 'user', 'content': question})
    return messages


def chat_turn(question, context, state):
    """Streams one answer, running regulation searches as Claude asks for them."""
    try:
        messages = conversation(question, context, state)
    except ReviewError as error:
        yield dict(type='error', code=error.code)
        return
    claude, wrote = client(), False
    while True:
        try:
            with claude.beta.messages.stream(
                model=MODEL, max_tokens=CHAT_TOKENS, betas=BETAS, fallbacks=FALLBACKS,
                system=[{'type': 'text', 'text': CHAT_SYSTEM, 'cache_control': {'type': 'ephemeral'}}],
                tools=TOOLS, messages=messages, output_config={'effort': 'medium'}, cache_control={'type': 'ephemeral'},
            ) as stream:
                for text in stream.text_stream:
                    wrote = True
                    yield dict(type='text', text=text)
                message = stream.get_final_message()
        except anthropic.APIError as error:
            yield dict(type='error', code=api_error(error).code)
            return
        if message.stop_reason == 'refusal' and not wrote:
            yield dict(type='error', code='ai_refused')
            return
        calls = [block for block in message.content if block.type == 'tool_use']
        if message.stop_reason != 'tool_use' or not calls:
            if not wrote:
                yield dict(type='error', code='ai_failed')
            return
        yield dict(type='searching')
        # The assistant's turn goes back unchanged, thinking included; then every result in one message.
        messages.append({'role': 'assistant', 'content': message.content})
        results = []
        for call in calls:
            text, is_error = search(call.input)
            results.append({'type': 'tool_result', 'tool_use_id': call.id, 'content': text, **({'is_error': True} if is_error else {})})
        messages.append({'role': 'user', 'content': results})
