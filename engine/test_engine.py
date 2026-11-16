"""The engine end to end. Gemini is a local HTTP stand-in, so requests go through the real SDK:
a wrong field name fails here. Google's own responses are not covered."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from google import genai
import pymupdf

import ai
import pdf_tools
import regulation
import sections
from report import assemble
from rulebook import BY_ID, RULES
import server
import settings
from test_cad import floor_plan

SAMPLE = Path(__file__).parent / 'demo' / 'sample.pdf'


def text_events(text, id='i1', status='completed'):
    return [dict(event_type='interaction.created', interaction=dict(id=id, status='in_progress')),
            dict(event_type='step.start', index=0, step=dict(type='model_output')),
            dict(event_type='step.delta', index=0, delta=dict(type='text', text=text)),
            dict(event_type='step.stop', index=0),
            dict(event_type='interaction.completed', interaction=dict(id=id, status=status))]


def call_events(query, id='i1'):
    return [dict(event_type='interaction.created', interaction=dict(id=id, status='in_progress')),
            dict(event_type='step.start', index=0, step=dict(type='function_call', id='c1', name='search_regulation', arguments={})),
            dict(event_type='step.delta', index=0, delta=dict(type='arguments_delta', arguments=json.dumps(dict(query=query)))),
            dict(event_type='step.stop', index=0),
            dict(event_type='interaction.completed', interaction=dict(id=id, status='requires_action'))]


class StandIn(BaseHTTPRequestHandler):
    """Plays Gemini's Interactions endpoint: each reply is a list of events, or (status, body)."""
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(body)
        if self.server.replies[0] == 'hang':
            self.server.replies.pop(0)
            time.sleep(3)
            return
        # A failure stays in place, since the SDK retries some of them.
        reply = self.server.replies[0] if isinstance(self.server.replies[0], tuple) and len(self.server.replies) == 1 else self.server.replies.pop(0)
        if isinstance(reply, tuple):
            data = json.dumps(reply[1]).encode()
            self.send_response(reply[0])
            self.send_header('Content-Type', 'application/json')
        else:
            data = ''.join(f'data: {json.dumps(event, ensure_ascii=False)}\n\n' for event in reply).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


class GeminiCase(unittest.TestCase):
    place = None    # a Google Cloud project and region, for Gemini on Vertex
    own_settings = False   # True where a test keeps settings in a folder of its own

    def setUp(self):
        self.gemini = ThreadingHTTPServer(('127.0.0.1', 0), StandIn)
        self.gemini.requests, self.gemini.replies = [], []
        threading.Thread(target=self.gemini.serve_forever, daemon=True).start()
        self.addCleanup(self.gemini.server_close)
        self.addCleanup(self.gemini.shutdown)
        url = f'http://127.0.0.1:{self.gemini.server_port}'
        make = lambda: genai.Client(api_key='test-key', http_options=dict(base_url=url, retry_options=dict(attempts=1, http_status_codes=[502, 504])))
        for patch in (mock.patch.object(ai, 'client', make), mock.patch.object(ai, 'model_index', 0), mock.patch.object(ai, 'remembered', {}),
                      *(() if self.own_settings else (mock.patch.object(settings, 'vertex', lambda: self.place),)),
                      mock.patch.object(ai, 'upload', lambda path, record: 'https://files.test/drawing')):
            patch.start()
            self.addCleanup(patch.stop)

    def folder(self):
        folder = Path(tempfile.mkdtemp())
        (folder / 'drawing.pdf').write_bytes(SAMPLE.read_bytes())
        return folder


def review(**check):
    return dict(building=dict(name='B', occupancy='სც-2', storeys=3, top_floor_m=6.0, high_rise=False, sprinklered=None, summary_ka='ა', summary_en='a'),
                checks=[dict(rule_id=r['id'], status='pass', found='', explanation_ka='', explanation_en='', fix_ka='', fix_en='', page=None, anchors=[], box=None)
                        for r in RULES] if not check else [check])


class ReportTest(unittest.TestCase):
    sizes = [dict(number=1, width=100, height=100)]

    def test_verdict_is_clear_only_if_every_rule_passed(self):
        report = assemble(review(), [], self.sizes)
        self.assertEqual((report['verdict'], report['counts']['pass']), ('clear', len(RULES)))

    def test_a_rule_left_out_is_never_a_pass(self):
        partial = review()
        partial['checks'] = partial['checks'][1:]
        report = assemble(partial, [], self.sizes)
        self.assertEqual((report['verdict'], report['counts']['verify']), ('verify', 1))

    def test_clause_and_quote_come_from_the_rulebook(self):
        check = dict(rule_id='1009.4', status='fail', found='1,00 მ', quote='made up', anchors=[0], page=1, box=None)
        anchors = [dict(id=0, page=1, text='x', box=[0.1, 0.2, 0.3, 0.4])]
        found = assemble(review(**check), anchors, self.sizes)['findings'][0]
        self.assertEqual((found['rule'], found['quote'], found['box'], found['page']), ('1009.4', BY_ID['1009.4']['quote'], [0.1, 0.2, 0.3, 0.4], 1))

    def test_a_bad_location_is_dropped(self):
        check = dict(rule_id='1009.4', status='fail', page=9, anchors=[77], box=[0.1, 0.2, 5, 0.4])
        found = assemble(review(**check), [], self.sizes)['findings'][0]
        self.assertEqual((found['page'], found['box']), (None, None))


class RegulationTest(unittest.TestCase):
    def test_the_newest_amendment_comes_first(self):
        hits = regulation.search('1018.4')
        self.assertTrue(hits[0]['source'].startswith('№87'))

    def test_table_rows_come_with_a_short_hit(self):
        hit = regulation.search('ცხრილი 1018.2')[0]
        self.assertTrue(hit['source'].startswith('№498'))
        self.assertIn('1,2 მ', hit['text'])


class ReviewTest(GeminiCase):
    def run_review(self):
        return ai.review(self.folder(), pdf_tools.page_sizes(SAMPLE), pdf_tools.anchors(SAMPLE))

    def test_sends_the_drawing_and_its_text_and_parses_the_answer(self):
        self.gemini.replies.append(text_events(json.dumps(review())))
        self.assertEqual(len(self.run_review()['checks']), len(RULES))
        request = self.gemini.requests[0]
        self.assertEqual(request['model'], 'gemini-3.6-flash')
        content = request['input'][0]['content']
        self.assertEqual(content[0], dict(type='document', uri='https://files.test/drawing', mime_type='application/pdf'))
        self.assertIn('კიბე 2', content[-1]['text'])
        self.assertEqual(request['response_format']['mime_type'], 'application/json')
        rule_ids = request['response_format']['schema']['properties']['checks']['items']['properties']['rule_id']['enum']
        self.assertIn('1018.4', rule_ids)
        self.assertEqual(request['generation_config']['thinking_level'], 'high')

    def test_moves_to_the_next_model_when_a_key_cannot_use_one(self):
        self.gemini.replies += [(404, dict(error=dict(code=404, message='model not found'))), text_events(json.dumps(review()))]
        self.run_review()
        self.assertEqual([r['model'] for r in self.gemini.requests], ['gemini-3.6-flash', 'gemini-3.8-flash'])

    def test_an_overloaded_model_is_passed_over_and_the_next_one_remembered(self):
        busy = (503, dict(error=dict(code='service_unavailable', message='high demand')))
        limit = (429, dict(error=dict(code='rate_limit_exceeded', message='limit: 0 on Free Tier')))
        self.gemini.replies += [busy, limit, text_events(json.dumps(review())), text_events(json.dumps(review()))]
        self.run_review()
        self.run_review()
        self.assertEqual([r['model'] for r in self.gemini.requests],
                         ['gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.5-flash', 'gemini-3.5-flash'])

    def test_an_answer_cut_off_is_asked_for_again_on_the_next_model(self):
        self.gemini.replies += [text_events('{"building": {"name"', status='incomplete'), text_events('not json'), text_events(json.dumps(review()))]
        self.assertEqual(len(self.run_review()['checks']), len(RULES))
        self.assertEqual(len(self.gemini.requests), 3)

    def test_an_answer_never_whole_is_named(self):
        self.gemini.replies += [text_events('{', status='incomplete') for _ in ai.MODELS]
        with self.assertRaises(ai.ReviewError) as raised:
            self.run_review()
        self.assertEqual(raised.exception.code, 'ai_truncated')

    def test_a_silent_model_is_passed_over(self):
        self.gemini.replies += ['hang', text_events(json.dumps(review()))]
        with mock.patch.multiple(ai, REVIEW_WAIT=0.3, REVIEW_WAIT_PER_PAGE=0):
            self.assertEqual(len(self.run_review()['checks']), len(RULES))
        self.assertEqual([r['model'] for r in self.gemini.requests], ['gemini-3.6-flash', 'gemini-3.8-flash'])

    def test_when_every_model_is_busy_it_says_so(self):
        self.gemini.replies.append((503, dict(error=dict(code='service_unavailable', message='high demand'))))
        with self.assertRaises(ai.ReviewError) as raised:
            self.run_review()
        self.assertEqual(raised.exception.code, 'ai_busy')
        self.assertEqual(len(self.gemini.requests), len(ai.MODELS))

    def test_failures_are_named(self):
        for reply, code in (((400, dict(error=dict(code=400, message='API key not valid. Please pass a valid API key.'))), 'ai_key_rejected'),
                            ((402, dict(error=dict(code=402, message='credit depleted'))), 'ai_no_credit'),
                            ((403, dict(error=dict(code=403, message='denied'))), 'ai_key_rejected'),
                            ([dict(event_type='error', error=dict(code='x', message='blocked'))], 'ai_failed')):
            self.gemini.replies.append(reply)
            with self.assertRaises(ai.ReviewError, msg=code) as raised:
                self.run_review()
            self.assertEqual(raised.exception.code, code)
            self.gemini.replies.clear()


class VertexTest(GeminiCase):
    place = dict(project='norma-test', location='global')

    def test_a_check_goes_to_the_strongest_model_with_the_drawing_inline(self):
        self.gemini.replies.append(text_events(json.dumps(review())))
        ai.review(ReviewTest.folder(self), pdf_tools.page_sizes(SAMPLE), pdf_tools.anchors(SAMPLE))
        request = self.gemini.requests[0]
        self.assertEqual((request['model'], request['generation_config']['thinking_level']), ('gemini-4-argon', 'medium'))
        document = request['input'][0]['content'][0]
        self.assertEqual((document['type'], document['mime_type'], 'uri' in document), ('document', 'application/pdf', False))
        self.assertTrue(document['data'])

    def test_a_busy_model_passes_to_the_next_strong_one(self):
        self.gemini.replies += [(503, dict(error=dict(code='service_unavailable', message='busy'))), text_events(json.dumps(review()))]
        ai.review(ReviewTest.folder(self), pdf_tools.page_sizes(SAMPLE), pdf_tools.anchors(SAMPLE))
        self.assertEqual([r['model'] for r in self.gemini.requests], ['gemini-4-argon', 'gemini-4-carbon'])

    def test_chat_uses_the_fast_model(self):
        self.gemini.replies.append(text_events('კი.'))
        list(ai.chat_turn('კითხვა', list, {}))
        self.assertEqual(self.gemini.requests[0]['model'], 'gemini-4-hydrogen')

    def test_access_problems_are_named(self):
        from google.genai import errors as genai_errors
        import google.auth.exceptions
        for raised, code in ((genai_errors.ClientError(403, dict(error=dict(code=403, message='denied', status='PERMISSION_DENIED'))), 'vertex_denied'),
                             (genai_errors.ClientError(404, dict(error=dict(code=404, message='no model', status='NOT_FOUND'))), 'vertex_no_model'),
                             (google.auth.exceptions.DefaultCredentialsError('no login'), 'vertex_no_login')):
            broken = mock.Mock()
            broken.models.get.side_effect = raised
            with mock.patch.object(ai, 'client', lambda place=None: broken), self.assertRaises(ai.ReviewError) as caught:
                ai.check_vertex('norma-test', 'global')
            self.assertEqual(caught.exception.code, code)


class LargePdfTest(unittest.TestCase):
    def test_an_oversized_pdf_gets_a_lighter_copy_with_its_text(self):
        folder = Path(tempfile.mkdtemp())
        lighter = pdf_tools.for_model(SAMPLE, folder / 'model.pdf', 1)
        self.assertIsNone(lighter)   # nothing fits one byte
        self.assertEqual(pdf_tools.for_model(SAMPLE, folder / 'model.pdf', 10 ** 9), SAMPLE)

    def test_text_positions_follow_a_rotated_page(self):
        path = Path(tempfile.mkdtemp()) / 'rotated.pdf'
        document = pymupdf.open()
        page = document.new_page(width=400, height=200)
        page.insert_text((300, 50), 'MARK', fontsize=12)
        page.set_rotation(90)
        document.save(path)
        box = pdf_tools.anchors(path)[0]['box']
        rendered = pymupdf.open(path)[0]
        expected = (rendered.search_for('MARK')[0] * rendered.rotation_matrix).normalize()
        self.assertAlmostEqual(box[0], expected.x0 / rendered.rect.width, places=2)
        self.assertAlmostEqual(box[1], expected.y0 / rendered.rect.height, places=2)
        self.assertLess(box[1], 1)
        self.assertGreater(box[1], 0.7)   # far right of the unrotated sheet is low on the rotated one

    def test_repeated_marks_are_left_out_of_the_listing(self):
        anchors = [dict(id=i, page=1, text=text) for i, text in enumerate(('ПГ', 'კარი 75 სმ', 'კარი 75 სმ'))]
        self.assertEqual(sections.listing(anchors), '#1 p1: კარი 75 სმ')


class ChatTest(GeminiCase):
    def test_runs_the_search_tool_and_chains_the_conversation(self):
        self.gemini.replies += [call_events('1018.4', id='a'), text_events('ჩიხი 6,0 მ-ია.', id='b'), text_events('კი.', id='c')]
        state = {}
        events = list(ai.chat_turn('რა არის ჩიხის ლიმიტი?', list, state))
        self.assertEqual([e['type'] for e in events], ['searching', 'text'])
        result = self.gemini.requests[1]
        self.assertEqual((result['previous_interaction_id'], result['input'][0]['type'], result['input'][0]['call_id']), ('a', 'function_result', 'c1'))
        self.assertIn('1018.4', result['input'][0]['result'][0]['text'])
        self.assertEqual(state['interaction'], 'b')
        list(ai.chat_turn('მადლობა', list, state))
        self.assertEqual(self.gemini.requests[2]['previous_interaction_id'], 'b')

    def test_a_forgotten_conversation_starts_again_with_the_drawing(self):
        self.gemini.replies += [(404, dict(error=dict(code=404, message='gone'))), text_events('კი.', id='n')]
        state = dict(interaction='old')
        context = lambda: [dict(type='text', text='report')]
        self.assertEqual([e['type'] for e in ai.chat_turn('კითხვა', context, state)], ['text'])
        self.assertEqual(self.gemini.requests[1]['input'][0]['content'][0]['text'], 'report')
        self.assertNotIn('previous_interaction_id', self.gemini.requests[1])
        self.assertEqual(state['interaction'], 'n')

    def test_a_bad_tool_input_is_reported_to_the_model(self):
        self.assertTrue(ai.run_tool(dict(id='c', name='search_regulation', arguments={}, text=''))['is_error'])

    def test_offline_answers_come_from_the_rules_and_say_so(self):
        answer = ai.offline_answer('What is the minimum corridor width?', 'en')
        self.assertIn('1018.2', answer)
        self.assertIn('not written by AI', answer)
        self.assertIn('1018.2', ai.offline_answer('რა მინიმალური სიგანე უნდა ჰქონდეს დერეფანს?', 'ka'))
        self.assertIn('1021.2', ai.offline_answer('How many exits does a storey need?', 'en'))


class ServerCase(GeminiCase):
    own_settings = True
    reads_building_data = False   # the quick pass for the building data, and its questions; BuildingDataTest covers them
    def setUp(self):
        super().setUp()
        folder = Path(tempfile.mkdtemp())
        for patch in (mock.patch.object(settings, 'REPORTS', folder / 'reports'), mock.patch.object(settings, 'CONFIG', folder / 'config.json'),
                      mock.patch.object(settings, 'HOME', folder), mock.patch.object(server, 'SAMPLE_PAUSE', 0), mock.patch.object(server, 'ASK_TIMEOUT', 5),
                      *(() if self.reads_building_data else (mock.patch.object(server, 'building_data', lambda *_: None),)),
                      mock.patch.dict('os.environ', GEMINI_API_KEY='', GOOGLE_API_KEY='', ANTHROPIC_API_KEY='', NORMA_VERTEX_PROJECT='')):
            patch.start()
            self.addCleanup(patch.stop)
        self.app = server.app.test_client()

    def finish(self, report_id, until=('done', 'failed'), **options):
        if options.get('start', True):
            self.assertEqual(self.app.post(f'/api/reports/{report_id}/check', json=dict(details=options.get('details', False))).status_code, 200)
        for _ in range(1500):
            stage = self.app.get(f'/api/reports/{report_id}/stage').json
            if stage['stage'] in until or stage['stage'] in ('done', 'failed'):
                return stage
            time.sleep(0.02)
        self.fail('check did not finish')

    def project(self, *files):
        """A new project with these (name, bytes, discipline) files."""
        report_id = self.app.post('/api/reports', json=dict(name='Plan')).json['id']
        for name, data, discipline in files:
            self.send(report_id, name, data, discipline)
        return report_id

    def send(self, report_id, name, data, discipline='fire'):
        return self.app.post(f'/api/reports/{report_id}/files', data=dict(file=(io.BytesIO(data), name), discipline=discipline), content_type='multipart/form-data')


class ServerTest(ServerCase):
    def test_sample_gives_a_full_report_without_a_key(self):
        report_id = self.app.post('/api/sample').json['id']
        self.assertEqual(self.finish(report_id)['stage'], 'done')
        report = self.app.get(f'/api/reports/{report_id}').json
        self.assertTrue(report['demo'])
        self.assertEqual(report['verdict'], 'fail')
        door = next(f for f in report['findings'] if f['rule'] == '1008.1.1')
        self.assertEqual((door['page'], door['found']), (2, '75 სმ'))
        self.assertIsNotNone(door['box'])
        with self.app.get(f'/api/reports/{report_id}/pages/2.png') as image:
            self.assertEqual(image.mimetype, 'image/png')
        self.assertEqual(self.app.get(f'/api/reports/{report_id}/pages/9.png').status_code, 404)
        self.assertEqual(len(self.app.get('/api/reports').json['reports']), 1)

    def test_upload_rejects_what_is_not_a_drawing(self):
        report_id = self.project()
        self.assertEqual(self.send(report_id, 'a.docx', b'x').json['error'], 'bad_file_type')
        self.assertEqual(self.send(report_id, 'a.pdf', b'not a pdf').json['error'], 'unreadable_pdf')

    def test_a_real_check_needs_a_key_and_uses_it(self):
        report_id = self.project(('plan.pdf', SAMPLE.read_bytes(), 'other'))
        self.assertEqual(self.app.post(f'/api/reports/{report_id}/check').json['error'], 'ai_not_connected')
        self.app.post('/api/key', json=dict(key='sk-test'))
        self.assertEqual(self.app.get('/api/status').json['provider'], 'gemini')
        self.gemini.replies.append(text_events(json.dumps(review())))
        self.assertEqual(self.finish(report_id)['stage'], 'done')
        # A set marked "other" may hold every discipline, so it is checked against every rule.
        report = self.app.get(f'/api/reports/{report_id}').json
        self.assertEqual((report['verdict'], report['ai_provider']), ('clear', 'gemini'))
        self.assertEqual(settings.CONFIG.stat().st_mode & 0o777, 0o600)

    def test_clauses_no_added_drawing_shows_are_left_out_of_the_check(self):
        report_id = self.project(('plan.pdf', SAMPLE.read_bytes(), 'architecture'))
        self.app.post('/api/key', json=dict(key='sk-test'))
        self.gemini.replies.append(text_events(json.dumps(review())))
        self.assertEqual(self.finish(report_id)['stage'], 'done')
        report = self.app.get(f'/api/reports/{report_id}').json
        # Only architecture was added: the clauses only fire drawings show are not checked, and do not hold the verdict back.
        self.assertEqual(report['verdict'], 'clear')
        sprinklers = next(f for f in report['findings'] if f['rule'] == '903.2.8')
        self.assertEqual((sprinklers['status'], sprinklers['sections']), ('not_checked', ['fire']))
        self.assertIn('ხანძარსაწინააღმდეგო', sprinklers['explanation_ka'])
        self.assertEqual(report['counts']['verify'], 0)
        by_key = {s['key']: s for s in report['sections']}
        self.assertEqual((by_key['architecture']['status'], by_key['fire']['status']), ('done', 'no_drawings'))
        # Only the architecture rules were asked for.
        asked = self.gemini.requests[0]['response_format']['schema']['properties']['checks']['items']['properties']['rule_id']['enum']
        self.assertIn('1009.4', asked)
        self.assertNotIn('903.2.8', asked)

    def test_a_failed_check_names_the_reason(self):
        report_id = self.project(('plan.pdf', SAMPLE.read_bytes(), 'architecture'))
        self.app.post('/api/key', json=dict(key='sk-test'))
        self.gemini.replies.append((429, dict(error=dict(code=429, message='quota'))))
        self.assertEqual(self.finish(report_id)['error'], 'ai_busy')

    def cad_project(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = Path(folder) / 'plan.dxf'
            floor_plan(plan)
            return self.project(('10 სართული.dxf', plan.read_bytes(), 'fire'))

    def test_the_ai_is_given_the_measurements_and_the_sheet_list(self):
        report_id = self.cad_project()
        self.app.post('/api/key', json=dict(key='sk-test'))
        self.gemini.replies.append(text_events(json.dumps(review())))
        self.assertEqual(self.finish(report_id)['stage'], 'done')
        sent = json.dumps(self.gemini.requests[-1]['input'], ensure_ascii=False)
        self.assertIn('Measured from the CAD geometry', sent)
        self.assertIn('p1: fire · 10 სართული.dxf', sent)
        report = self.app.get(f'/api/reports/{report_id}').json
        self.assertTrue(report['ai_used'])
        self.assertTrue(next(f for f in report['findings'] if f['rule'] == '1009.4')['measured'])

    def test_measurements_survive_a_failed_ai(self):
        report_id = self.cad_project()
        self.app.post('/api/key', json=dict(key='sk-test'))
        self.gemini.replies.append((429, dict(error=dict(code=429, message='quota'))))
        self.assertEqual(self.finish(report_id)['stage'], 'done')
        report = self.app.get(f'/api/reports/{report_id}').json
        self.assertEqual((report['ai_used'], report['ai_error']), (False, 'ai_busy'))
        self.assertEqual(next(f for f in report['findings'] if f['rule'] == '1009.4')['status'], 'pass')

    def test_chat_with_a_key_remembers_the_conversation(self):
        report_id = self.app.post('/api/sample').json['id']
        self.finish(report_id)
        self.app.post('/api/key', json=dict(key='sk-test'))
        self.gemini.replies.append(text_events('პასუხი', id='z'))
        body = self.app.post('/api/chat', json=dict(message='კითხვა', report=report_id)).get_data(as_text=True)
        self.assertIn('პასუხი', body)
        content = self.gemini.requests[0]['input'][0]['content']
        self.assertEqual(content[0]['type'], 'document')
        self.assertIn('Report of the check', content[1]['text'])
        said = self.app.get(f'/api/reports/{report_id}/chat').json['messages']
        self.assertEqual([m['text'] for m in said], ['კითხვა', 'პასუხი'])

    def test_found_values_read_in_both_languages(self):
        report = assemble(review(rule_id='1009.4', status='fail', found_ka='1,00 მ', found_en='1.00 m'), [], [dict(number=1, width=1, height=1)])
        stair = next(f for f in report['findings'] if f['rule'] == '1009.4')
        self.assertEqual((stair['found_ka'], stair['found_en']), ('1,00 მ', '1.00 m'))

    def test_vertex_is_connected_after_a_test_request(self):
        self.assertEqual(self.app.post('/api/vertex', json=dict(project='Bad Project')).json['error'], 'vertex_invalid')
        with mock.patch.object(ai, 'check_vertex', mock.Mock(side_effect=ai.ReviewError('vertex_denied', 'no role'))):
            self.assertEqual(self.app.post('/api/vertex', json=dict(project='my-project-123')).status_code, 422)
        self.app.post('/api/key', json=dict(key='AIza-gemini'))
        with mock.patch.object(ai, 'check_vertex', lambda project, location: None):
            self.assertEqual(self.app.post('/api/vertex', json=dict(project='my-project-123')).json['provider'], 'vertex')
        status = self.app.get('/api/status').json
        self.assertEqual((status['provider'], status['vertex']), ('vertex', dict(project='my-project-123', location='global')))
        self.assertEqual(status['keys'], dict(claude=False, vertex=True, gemini=True))
        self.app.delete('/api/key?provider=vertex')
        self.assertEqual(self.app.get('/api/status').json['provider'], 'gemini')

    def test_chat_works_offline_and_ids_are_checked(self):
        body = self.app.post('/api/chat', json=dict(message='When is a building high-rise?', lang='en')).get_data(as_text=True)
        self.assertIn('23', body)
        self.assertIn('"done"', body)
        self.assertEqual(self.app.get('/api/reports/../../etc').status_code, 404)
        self.assertEqual(self.app.get('/api/reports/0123/pages/1.png').status_code, 404)


class BuildingDataTest(ServerCase):
    reads_building_data = True
    found = dict(values=dict(occupancy='სც-2', storeys_above=9, building_class='IV', sprinklered='maybe'), where=dict(occupancy='p1: ბინა'))

    def start(self, **options):
        report_id = self.project(('plan.pdf', SAMPLE.read_bytes(), 'architecture'), ('fire.pdf', SAMPLE.read_bytes(), 'fire'))
        self.app.post('/api/key', json=dict(key='sk-test'))
        self.gemini.replies += [text_events(json.dumps(self.found)), text_events(json.dumps(review())), text_events(json.dumps(review()))]
        return report_id, self.finish(report_id, until=('asking',), **options)

    def test_asks_only_the_essential_facts_it_could_not_find(self):
        report_id, stage = self.start()
        self.assertEqual(stage['stage'], 'asking')
        self.assertEqual([q['key'] for q in stage['questions']], ['storeys_below', 'top_floor_m', 'sprinklered'])   # 'maybe' is no answer
        self.assertEqual({f['key']: f['value'] for f in stage['found']}, dict(building_class='IV', occupancy='სც-2', storeys_above=9))
        quick = self.gemini.requests[0]
        self.assertEqual(quick['generation_config']['thinking_level'], 'low')
        self.assertIn('building data', quick['system_instruction'])
        # Answers go in, a bad one is dropped, the found storeys are corrected, and every section is told.
        self.app.post(f'/api/reports/{report_id}/facts', json=dict(answers=dict(top_floor_m='24,5', storeys_below='many', storeys_above=10)))
        self.assertEqual(self.finish(report_id, start=False)['stage'], 'done')
        for sent in self.gemini.requests[1:]:
            note = next(b['text'] for b in sent['input'][0]['content'] if 'Building data for this check' in b.get('text', ''))
            self.assertIn('"top_floor_m": {"value": 24.5, "source": "given by the designer"}', note)
        report = self.app.get(f'/api/reports/{report_id}').json
        facts = {f['key']: (f['value'], f['source']) for f in report['facts']}
        self.assertEqual(facts['top_floor_m'], (24.5, 'designer'))
        self.assertEqual(facts['storeys_above'], (10, 'designer'))
        self.assertEqual(facts['occupancy'], ('სც-2', 'drawing'))
        self.assertNotIn('storeys_below', facts)
        self.assertEqual(self.app.post(f'/api/reports/{report_id}/facts', json=dict(skip=True)).status_code, 409)

    def test_details_are_asked_only_when_ticked_and_a_skip_goes_on(self):
        report_id, stage = self.start(details=True)
        self.assertIn('building_length_m', [q['key'] for q in stage['questions']])
        self.app.post(f'/api/reports/{report_id}/facts', json=dict(skip=True))
        self.assertEqual(self.finish(report_id, start=False)['stage'], 'done')
        facts = {f['key'] for f in self.app.get(f'/api/reports/{report_id}').json['facts']}
        self.assertEqual(facts, {'building_class', 'occupancy', 'storeys_above'})


if __name__ == '__main__':
    unittest.main()
