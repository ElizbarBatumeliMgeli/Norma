"""Claude end to end. Anthropic's API is a local HTTP stand-in, so requests go through the real SDK:
a wrong field name fails here. Anthropic's own responses are not covered."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

import anthropic

import claude_ai
from errors import ReviewError
import pdf_tools
from rulebook import RULES
import server
import settings
from test_engine import review

SAMPLE = Path(__file__).parent / 'demo' / 'sample.pdf'


def message(*blocks, stop='end_turn'):
    """A streamed message: text blocks are strings, a tool call is a (name, input) pair."""
    events = [dict(type='message_start', message=dict(id='msg_1', type='message', role='assistant', model='claude-opus-5-5', content=[],
                                                      stop_reason=None, stop_sequence=None, usage=dict(input_tokens=10, output_tokens=1)))]
    for index, block in enumerate(blocks):
        if isinstance(block, str):
            events += [dict(type='content_block_start', index=index, content_block=dict(type='text', text='')),
                       dict(type='content_block_delta', index=index, delta=dict(type='text_delta', text=block))]
        else:
            name, arguments = block
            events += [dict(type='content_block_start', index=index, content_block=dict(type='tool_use', id=f'tu_{index}', name=name, input={})),
                       dict(type='content_block_delta', index=index, delta=dict(type='input_json_delta', partial_json=json.dumps(arguments)))]
        events.append(dict(type='content_block_stop', index=index))
    events += [dict(type='message_delta', delta=dict(stop_reason=stop, stop_sequence=None), usage=dict(output_tokens=5)), dict(type='message_stop')]
    return events


def failure(status, kind, text='x'):
    return status, dict(type='error', error=dict(type=kind, message=text))


class StandIn(BaseHTTPRequestHandler):
    """Plays Anthropic's Messages endpoint: each reply is a list of events, or (status, body)."""
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(dict(body=body, path=self.path, beta=self.headers.get('anthropic-beta', '')))
        reply = self.server.replies.pop(0)
        if isinstance(reply, tuple):
            data = json.dumps(reply[1]).encode()
            self.send_response(reply[0])
            self.send_header('Content-Type', 'application/json')
        else:
            data = ''.join(f'event: {e["type"]}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n' for e in reply).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


class ClaudeCase(unittest.TestCase):
    def setUp(self):
        self.claude = ThreadingHTTPServer(('127.0.0.1', 0), StandIn)
        self.claude.requests, self.claude.replies = [], []
        threading.Thread(target=self.claude.serve_forever, daemon=True).start()
        self.addCleanup(self.claude.server_close)
        self.addCleanup(self.claude.shutdown)
        url = f'http://127.0.0.1:{self.claude.server_port}'
        patch = mock.patch.object(claude_ai, 'client', lambda: anthropic.Anthropic(api_key='sk-ant-test', base_url=url, max_retries=0))
        patch.start()
        self.addCleanup(patch.stop)

    def folder(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / 'drawing.pdf').write_bytes(SAMPLE.read_bytes())
        return folder


class ReviewTest(ClaudeCase):
    def run_review(self):
        return claude_ai.review(self.folder(), pdf_tools.page_sizes(SAMPLE), pdf_tools.anchors(SAMPLE))

    def test_sends_the_drawing_and_the_schema_and_parses_the_answer(self):
        self.claude.replies.append(message(json.dumps(review())))
        self.assertEqual(len(self.run_review()['checks']), len(RULES))
        sent = self.claude.requests[0]
        body = sent['body']
        self.assertEqual((body['model'], body['fallbacks']), ('claude-opus-5-5', 'default'))
        self.assertIn('server-side-fallback-2026-07-01', sent['beta'])
        self.assertTrue(sent['path'].startswith('/v1/messages'))
        self.assertEqual(body['output_config']['effort'], 'high')
        schema = body['output_config']['format']['schema']
        self.assertEqual(body['output_config']['format']['type'], 'json_schema')
        page = schema['properties']['checks']['items']['properties']['page']
        self.assertEqual(page, {'anyOf': [{'type': 'integer'}, {'type': 'null'}]})
        self.assertNotIn('thinking', body)   # adaptive by default; effort sets the depth
        content = body['messages'][0]['content']
        self.assertEqual((content[0]['type'], content[0]['source']['media_type']), ('document', 'application/pdf'))
        self.assertIn('კიბე 2', content[-1]['text'])
        self.assertEqual(body['system'][0]['cache_control'], {'type': 'ephemeral'})
        self.assertIn('Architecture review', body['system'][0]['text'])   # every skill, for a set with no disciplines

    def test_failures_are_named(self):
        for reply, code in ((failure(401, 'authentication_error'), 'ai_key_rejected'),
                            (failure(529, 'overloaded_error'), 'ai_busy'),
                            (failure(429, 'rate_limit_error'), 'ai_busy'),
                            (failure(400, 'invalid_request_error', 'Your credit balance is too low to access the Anthropic API.'), 'ai_no_credit'),
                            (message('{"building": {', stop='max_tokens'), 'ai_truncated'),
                            (message('', stop='refusal'), 'ai_refused'),
                            (message('not json'), 'ai_failed')):
            self.claude.replies.append(reply)
            with self.assertRaises(ReviewError, msg=code) as raised:
                self.run_review()
            self.assertEqual(raised.exception.code, code)


class ChatTest(ClaudeCase):
    def test_runs_the_search_tool_and_sends_the_turn_back_unchanged(self):
        self.claude.replies += [message('ვეძებ.', ('search_regulation', dict(query='1018.4')), stop='tool_use'), message('ჩიხი 6,0 მ-ია.')]
        events = list(claude_ai.chat_turn('რა არის ჩიხის ლიმიტი?', list, dict(messages=[])))
        self.assertEqual([e['type'] for e in events], ['text', 'searching', 'text'])
        second = self.claude.requests[1]['body']['messages']
        self.assertEqual([m['role'] for m in second], ['user', 'assistant', 'user'])
        self.assertEqual([b['type'] for b in second[1]['content']], ['text', 'tool_use'])
        result = second[2]['content'][0]
        self.assertEqual((result['type'], result['tool_use_id']), ('tool_result', 'tu_1'))
        self.assertIn('1018.4', result['content'])
        tool = self.claude.requests[0]['body']['tools'][0]
        self.assertEqual((tool['name'], tool['strict'], tool['eager_input_streaming']), ('search_regulation', True, True))

    def test_a_bad_tool_input_is_reported_to_the_model(self):
        self.claude.replies += [message(('search_regulation', dict(query='')), stop='tool_use'), message('ok')]
        list(claude_ai.chat_turn('?', list, dict(messages=[])))
        self.assertTrue(self.claude.requests[1]['body']['messages'][2]['content'][0]['is_error'])

    def test_later_turns_repeat_the_same_beginning(self):
        context = lambda: [dict(type='text', text='report')]
        said = dict(messages=[dict(role='user', text='first'), dict(role='assistant', text='answer')])
        self.claude.replies.append(message('second answer'))
        list(claude_ai.chat_turn('second', context, said))
        sent = self.claude.requests[0]['body']['messages']
        self.assertEqual(sent[0]['content'], [dict(type='text', text='report'), dict(type='text', text='first')])
        self.assertEqual(sent[1:], [dict(role='assistant', content='answer'), dict(role='user', content='second')])


class ServerTest(ClaudeCase):
    def setUp(self):
        super().setUp()
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        for patch in (mock.patch.object(settings, 'REPORTS', folder / 'reports'), mock.patch.object(settings, 'CONFIG', folder / 'config.json'),
                      mock.patch.object(settings, 'HOME', folder), mock.patch.object(server, 'SAMPLE_PAUSE', 0),
                      mock.patch.object(server, 'building_data', lambda *_: None),
                      mock.patch.dict('os.environ', GEMINI_API_KEY='', GOOGLE_API_KEY='', ANTHROPIC_API_KEY='', NORMA_VERTEX_PROJECT='')):
            patch.start()
            self.addCleanup(patch.stop)
        self.app = server.app.test_client()

    def test_a_claude_key_is_kept_beside_gemini_and_used_first(self):
        self.app.post('/api/key', json=dict(key='AIza-gemini'))
        self.assertEqual(self.app.post('/api/key', json=dict(key='sk-ant-api03-x')).json['provider'], 'claude')
        status = self.app.get('/api/status').json
        self.assertEqual((status['provider'], status['keys']), ('claude', dict(claude=True, vertex=False, gemini=True)))
        self.app.delete('/api/key?provider=claude')
        self.assertEqual(self.app.get('/api/status').json['provider'], 'gemini')

    def test_a_project_is_checked_by_claude_section_by_section(self):
        report_id = self.app.post('/api/reports', json=dict(name='Plan')).json['id']
        for name, discipline in (('arch.pdf', 'architecture'), ('fire.pdf', 'fire')):
            self.app.post(f'/api/reports/{report_id}/files', data=dict(file=(io.BytesIO(SAMPLE.read_bytes()), name), discipline=discipline),
                          content_type='multipart/form-data')
        self.app.post('/api/key', json=dict(key='sk-ant-api03-x'))
        self.claude.replies += [message(json.dumps(review())), message(json.dumps(review()))]
        self.assertEqual(self.app.post(f'/api/reports/{report_id}/check').status_code, 200)
        for _ in range(1500):
            stage = self.app.get(f'/api/reports/{report_id}/stage').json
            if stage['stage'] in ('done', 'failed'):
                break
            time.sleep(0.02)
        self.assertEqual(stage['stage'], 'done', stage)
        first, second = (r['body'] for r in self.claude.requests)
        self.assertIn('only the architecture drawings', first['system'][0]['text'])
        self.assertIn('only the fire protection drawings', second['system'][0]['text'])
        self.assertTrue(any('architecture review' in b.get('text', '') for b in second['messages'][0]['content']))
        report = self.app.get(f'/api/reports/{report_id}').json
        self.assertEqual(report['ai_provider'], 'claude')
        self.assertEqual({s['key']: s['status'] for s in report['sections']}['fire'], 'done')


if __name__ == '__main__':
    unittest.main()
