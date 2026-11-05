"""NORMA's local engine. The desktop window starts it with --port and talks to it over 127.0.0.1.

Each check lives in its own folder under settings.REPORTS: the project's files until they are read,
then all their sheets as one PDF, its text items, the report and the chat. Nothing leaves the machine
except the requests to Gemini (the sheets during a check, and in chat when a report is attached).
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import threading
import time
import uuid

from flask import Flask, Response, abort, jsonify, request, send_file, stream_with_context

import ai
import pdf_tools
import project
import regulation
from report import assemble
from rulebook import CATEGORY_KEYS, RULES
import settings

ALLOWED_ORIGINS = ('tauri://localhost', 'http://tauri.localhost', 'https://tauri.localhost',
                   'http://localhost:1440', 'http://127.0.0.1:1440')
SAMPLE = Path(__file__).parent / 'demo'
SAMPLE_PAUSE = 1.4   # seconds per stage, so the sample plays like a real check
MAX_UPLOAD = 200 * 1024 * 1024

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD
stages = {}          # report id → dict(stage=…, error=…, detail=…) while a check runs
general_chat = dict(messages=[])    # the conversation when no report is open; gone when the app quits


def fail(code, status=400, detail=''):
    return jsonify(error=code, detail=detail), status


@app.after_request
def allow_app_window(response):
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.errorhandler(413)
def too_large(_):
    return fail('pdf_too_large', 413)


def folder(report_id):
    if not re.fullmatch(r'[0-9a-f]{32}|sample', report_id) or not (settings.REPORTS / report_id).is_dir():
        abort(404)
    return settings.REPORTS / report_id


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


@app.get('/api/health')
def health():
    return jsonify(ok=True)


@app.get('/api/status')
def status():
    amendments = regulation.amendments()
    counts = {key: sum(r['category'] == key for r in RULES) for key in CATEGORY_KEYS}
    return jsonify(ai=bool(settings.read_key()), rules=len(RULES), counts=counts, amendments=len(amendments), latest=amendments[-1])


@app.post('/api/key')
def save_key():
    key = str((request.get_json(silent=True) or {}).get('key', '')).strip()
    if not key:
        return fail('ai_key_empty')
    settings.save_key(key)
    return jsonify(ok=True)


@app.delete('/api/key')
def forget_key():
    settings.forget_key()
    return jsonify(ok=True)


def new_report(source, name, demo=False, report_id=None):
    report_id = report_id or uuid.uuid4().hex
    target = settings.REPORTS / report_id
    shutil.rmtree(target, ignore_errors=True)
    (target / 'pages').mkdir(parents=True)
    shutil.copyfile(source, target / 'drawing.pdf')
    sizes = pdf_tools.page_sizes(target / 'drawing.pdf')
    write_json(target / 'meta.json', dict(id=report_id, name=name, pages=sizes, demo=demo, created=datetime.now().isoformat(timespec='seconds')))
    return report_id, sizes


@app.post('/api/reports')
def create_project():
    name = str((request.get_json(silent=True) or {}).get('name', '')).strip()[:200]
    if not name:
        return fail('no_files')
    report_id = uuid.uuid4().hex
    target = settings.REPORTS / report_id
    (target / 'pages').mkdir(parents=True)
    (target / 'sources').mkdir()
    write_json(target / 'meta.json', dict(id=report_id, name=name, pages=[], files=[], demo=False, created=datetime.now().isoformat(timespec='seconds')))
    return jsonify(id=report_id)


@app.post('/api/reports/<report_id>/files')
def add_file(report_id):
    target = folder(report_id)
    file = request.files.get('file')
    suffix = Path(file.filename).suffix.lower() if file else ''
    if suffix not in project.ALLOWED_TYPES:
        return fail('bad_file_type')
    meta = read_json(target / 'meta.json')
    stored = f'{len(meta["files"])}{suffix}'
    file.save(target / 'sources' / stored)
    if suffix == '.pdf':
        try:
            pdf_tools.page_sizes(target / 'sources' / stored)
        except pdf_tools.UnreadablePdf as error:
            (target / 'sources' / stored).unlink()
            return fail('unreadable_pdf', 422, f'{file.filename}: {error}')
    discipline = request.form.get('discipline')
    meta['files'].append(dict(name=Path(file.filename).name, stored=stored, discipline=discipline if discipline in project.DISCIPLINES else 'other'))
    write_json(target / 'meta.json', meta)
    return jsonify(ok=True)


@app.post('/api/sample')
def sample():
    report_id, _ = new_report(SAMPLE / 'sample.pdf', 'ნიმუში — საცხოვრებელი კორპუსი.pdf', demo=True, report_id='sample')
    return jsonify(id=report_id)


def read_project(target, meta, state):
    """Reads the project's files into one drawing set, once. The text items are returned."""
    if not meta.get('files') or meta['pages']:
        return pdf_tools.anchors(target / 'drawing.pdf')
    pages, anchors, measured, files = project.build(target, meta, lambda done, total: state.update(done=done, total=total))
    meta.update(pages=pages, files=files, measured=measured)
    write_json(target / 'meta.json', meta)
    if not pages:
        reasons = sorted({f.get('error', '') for f in files})
        raise ai.ReviewError(reasons[0] if len(reasons) == 1 and reasons[0] else 'no_sheets')
    return anchors


def has_cad(meta):
    return any(Path(f['name']).suffix.lower() in project.CAD_TYPES for f in meta.get('files', []))


def run_check(report_id):
    """Runs in a thread. The app follows `stages` and reads the report when it is done."""
    target = settings.REPORTS / report_id
    meta = read_json(target / 'meta.json')
    state = stages[report_id]
    try:
        state.update(stage='reading')
        anchors = read_project(target, meta, state)
        write_json(target / 'anchors.json', anchors)
        if meta['demo']:
            time.sleep(SAMPLE_PAUSE)
        state.update(stage='checking', done=None)
        review, problem = None, None
        if meta['demo']:
            time.sleep(SAMPLE_PAUSE * 2)
            review = read_json(SAMPLE / 'review.json')
        elif settings.read_key():
            try:
                review = ai.review(target, meta['pages'], anchors, meta.get('measured'))
            except ai.ReviewError as error:
                # What was measured stands without the AI, so a busy model does not cost the whole check.
                if not meta.get('measured'):
                    raise
                problem = error.code
        state.update(stage='writing')
        write_json(target / 'report.json', dict(assemble(review, anchors, meta['pages'], meta.get('measured'), meta['name']), **meta, ai_error=problem))
        if meta['demo']:
            time.sleep(SAMPLE_PAUSE / 2)
        state.update(stage='done')
    except ai.ReviewError as error:
        state.update(stage='failed', error=error.code, detail=error.detail)
    except Exception as error:
        app.logger.exception('Check failed for %s', report_id)
        state.update(stage='failed', error='check_failed', detail=str(error))


@app.post('/api/reports/<report_id>/check')
def start_check(report_id):
    meta = read_json(folder(report_id) / 'meta.json')
    if not meta['demo'] and not settings.read_key() and not has_cad(meta):
        return fail('ai_not_connected', 409)
    stages[report_id] = dict(stage='reading')
    threading.Thread(target=run_check, args=(report_id,), daemon=True).start()
    return jsonify(ok=True)


@app.get('/api/reports/<report_id>/stage')
def check_stage(report_id):
    return jsonify(stages.get(report_id) or dict(stage='failed', error='check_failed'))


@app.get('/api/reports')
def recent():
    reports = [read_json(path) for path in settings.REPORTS.glob('*/report.json')] if settings.REPORTS.exists() else []
    summary = [{key: r[key] for key in ('id', 'name', 'created', 'verdict', 'counts', 'demo')} for r in reports]
    return jsonify(reports=sorted(summary, key=lambda r: r['created'], reverse=True)[:6])


@app.get('/api/reports/<report_id>')
def read_report(report_id):
    report = read_json(folder(report_id) / 'report.json')
    return jsonify(report) if report else fail('check_failed', 404)


@app.delete('/api/reports/<report_id>')
def delete_report(report_id):
    shutil.rmtree(folder(report_id))
    return jsonify(ok=True)


@app.get('/api/reports/<report_id>/pages/<int:number>.png')
def page_image(report_id, number):
    target = folder(report_id)
    if not 1 <= number <= len(read_json(target / 'meta.json')['pages']):
        abort(404)
    return send_file(pdf_tools.render_page(target / 'drawing.pdf', number, target / 'pages' / f'{number}.png').resolve(), mimetype='image/png')


def report_context(target):
    """What chat is told about the open report: the drawing itself and the results."""
    report = read_json(target / 'report.json')
    results = [{key: f[key] for key in ('rule', 'status', 'found', 'explanation_en', 'page')} for f in report['findings'] if f['status'] != 'not_applicable']
    summary = json.dumps(dict(file=report['name'], building=report['building'], verdict=report['verdict'], results=results, measured=report.get('measured')), ensure_ascii=False)
    return [ai.drawing_block(target), {'type': 'text', 'text': f'Report of the check:\n{summary}'}]


@app.get('/api/reports/<report_id>/chat')
def chat_history(report_id):
    return jsonify(messages=read_json(folder(report_id) / 'chat.json', dict(messages=[]))['messages'])


@app.post('/api/chat')
def chat():
    body = request.get_json(silent=True) or {}
    question, lang, report_id = str(body.get('message', '')).strip(), body.get('lang', 'ka'), body.get('report')
    if not question:
        return fail('empty_message')
    target = folder(report_id) if report_id else None
    log = target / 'chat.json' if target else None
    saved = read_json(log, dict(messages=[])) if log else general_chat
    checked = target and (target / 'report.json').exists()
    context = (lambda: report_context(target)) if checked else list

    def events():
        send = lambda event: f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
        if not settings.read_key():
            yield send(dict(type='text', text=ai.offline_answer(question, lang, read_json(target / 'report.json') if checked else None)))
        else:
            answer = ''
            for event in ai.chat_turn(question, context, saved):
                answer += event.get('text', '')
                yield send(event)
            saved['messages'] += [dict(role='user', text=question), dict(role='assistant', text=answer)]
            if log:
                write_json(log, saved)
        yield send(dict(type='done'))

    return Response(stream_with_context(events()), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8100)
    args = parser.parse_args()
    app.run(host='127.0.0.1', port=args.port, threaded=True)
