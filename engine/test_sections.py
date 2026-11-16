"""Checking a project one discipline at a time: which sheets go with which rules, and how answers merge."""
from pathlib import Path
import shutil
import tempfile
import unittest

from errors import ReviewError
import pdf_tools
from rulebook import BY_ID, RULES, rules_for
import sections

SAMPLE = Path(__file__).parent / 'demo' / 'sample.pdf'
BUILDING = dict(name='B', occupancy='სც-2', storeys=12, top_floor_m=36.0, high_rise=True, sprinklered=True, summary_ka='ა', summary_en='a')


def pages(*disciplines):
    return [dict(number=i, width=100, height=100, discipline=d, file=f'{d}.pdf') for i, d in enumerate(disciplines, 1)]


def check(rule_id, status, page=None):
    return dict(rule_id=rule_id, status=status, found='', explanation_ka='', explanation_en='', fix_ka='', fix_en='', page=page, anchors=[], box=None)


class PlanTest(unittest.TestCase):
    def test_each_discipline_gets_its_own_sheets_and_rules(self):
        plan = {key: (numbers, {r['id'] for r in rules}) for key, numbers, rules in sections.plan(pages('fire', 'architecture', 'fire', 'hvac'))}
        self.assertEqual(list(plan), ['architecture', 'fire', 'hvac'])
        self.assertEqual(plan['fire'][0], [1, 3])
        self.assertIn('903.2.8', plan['fire'][1])
        self.assertNotIn('1208.3', plan['fire'][1])
        self.assertEqual(plan['hvac'][1], {r['id'] for r in rules_for('hvac')})

    def test_other_sheets_answer_what_no_discipline_can(self):
        plan = {key: {r['id'] for r in rules} for key, _, rules in sections.plan(pages('other', 'fire'))}
        self.assertEqual(list(plan), ['architecture', 'fire'])
        self.assertIn('1203.4.1', plan['architecture'])     # shown on HVAC drawings, and none were added
        self.assertNotIn('903.2.8', plan['architecture'])   # the fire drawings answer it

    def test_a_drawing_without_disciplines_is_one_request(self):
        [(key, numbers, rules)] = sections.plan([dict(number=1, width=1, height=1), dict(number=2, width=1, height=1)])
        self.assertEqual((key, numbers, len(rules)), (sections.ALL, [1, 2], len(RULES)))

    def test_the_prompt_holds_the_discipline_skill_and_only_its_rules(self):
        prompt = sections.system_prompt('fire', rules_for('fire'))
        self.assertIn('Fire protection review', prompt)
        self.assertIn('only the fire protection drawings', prompt)
        self.assertIn('[903.2.8]', prompt)
        self.assertNotIn('[1208.3]', prompt)
        self.assertNotIn('name: norma-fire-review', prompt)


class MergeTest(unittest.TestCase):
    groups = [('architecture', [1], RULES), ('fire', [2], RULES)]

    def merged(self, architecture, fire, errors=None):
        results = {key: dict(building=BUILDING, checks=checks) for key, checks in (('architecture', architecture), ('fire', fire)) if checks is not None}
        return sections.merge(self.groups, results, errors or {})['checks']

    def test_a_failure_anywhere_stands_with_every_place_it_was_found(self):
        merged = self.merged([check('1022.4', 'fail', 1), check('1022.4', 'pass')], [check('1022.4', 'fail', 2)])
        self.assertEqual([(c['status'], c['page']) for c in merged], [('fail', 1), ('fail', 2)])

    def test_a_system_shown_in_one_discipline_is_not_missing(self):
        self.assertEqual([c['status'] for c in self.merged([check('907.2.13', 'missing')], [check('907.2.13', 'pass')])], ['pass'])
        self.assertEqual([c['status'] for c in self.merged([check('907.2.13', 'missing')], [check('907.2.13', 'verify')])], ['verify'])

    def test_a_failed_section_is_recorded(self):
        result = sections.merge(self.groups, dict(architecture=dict(building=BUILDING, checks=[])), dict(fire=ReviewError('ai_busy')))
        self.assertEqual(result['sections'], dict(architecture=dict(status='done'), fire=dict(status='failed', error='ai_busy')))
        self.assertEqual(result['coverage']['903.2.8'], ['architecture', 'fire'])

    def test_answers_come_back_with_project_page_numbers_and_asked_rules_only(self):
        answer = dict(building=BUILDING, checks=[check('903.2.8', 'fail', 2), check('1208.3', 'pass', 1), check('403.3', 'pass', 9)])
        found = sections.localize(answer, [4, 7], {'903.2.8', '403.3'})['checks']
        self.assertEqual([(c['rule_id'], c['page']) for c in found], [('903.2.8', 7), ('403.3', None)])


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        shutil.copy(SAMPLE, self.folder / 'drawing.pdf')
        count = len(pdf_tools.page_sizes(SAMPLE))
        self.sizes = [dict(p, discipline='architecture' if p['number'] == 1 else 'fire', file='x.pdf') for p in pdf_tools.page_sizes(SAMPLE)]
        self.assertGreater(count, 1)
        self.anchors = pdf_tools.anchors(SAMPLE)

    def test_architecture_goes_first_and_tells_the_others_about_the_building(self):
        asked = []

        def ask(folder, request):
            asked.append(request)
            if request['key'] == 'fire':
                return dict(building=dict(BUILDING, name='fire view'), checks=[check('903.2.8', 'missing', 1)])
            return dict(building=BUILDING, checks=[check('1009.4', 'pass', 1)])

        progress = []
        result = sections.review(self.folder, self.sizes, self.anchors, ask, progress=lambda done, total: progress.append((done, total)))
        self.assertEqual([r['key'] for r in asked], ['architecture', 'fire'])
        self.assertFalse(any('architecture review' in note for note in asked[0]['notes']))
        self.assertTrue(any('"high_rise": true' in note for note in asked[1]['notes']))
        with pdf_tools.open_pdf(asked[1]['pdf']) as part:
            self.assertEqual(part.page_count, len(self.sizes) - 1)
        self.assertTrue(all(a.startswith('#') for a in asked[1]['listing'].splitlines()[1:2]))
        self.assertEqual(result['building']['name'], 'B')                # architecture's word on the building
        self.assertEqual({c['rule_id']: c['page'] for c in result['checks']}, {'1009.4': 1, '903.2.8': 2})
        self.assertEqual(progress[-1], (2, 2))

    def test_one_section_failing_leaves_the_others(self):
        def ask(folder, request):
            if request['key'] == 'fire':
                raise ReviewError('ai_busy')
            return dict(building=BUILDING, checks=[])

        result = sections.review(self.folder, self.sizes, self.anchors, ask)
        self.assertEqual(result['sections']['fire'], dict(status='failed', error='ai_busy'))

    def test_every_section_failing_is_named(self):
        def ask(folder, request):
            raise ReviewError('ai_key_rejected')

        with self.assertRaises(ReviewError) as raised:
            sections.review(self.folder, self.sizes, self.anchors, ask)
        self.assertEqual(raised.exception.code, 'ai_key_rejected')


class ReportTest(unittest.TestCase):
    def test_rules_left_open_say_why(self):
        from report import assemble
        review = dict(building=BUILDING, checks=[], sections=dict(architecture=dict(status='done'), fire=dict(status='failed', error='ai_busy')),
                      coverage={r['id']: [k for k in ('architecture', 'fire') if k in r['on']] for r in RULES})
        sizes = pages('architecture', 'fire')
        report = assemble(review, [], sizes)
        by_rule = {f['rule']: f for f in report['findings']}
        self.assertIn('could not review this section', by_rule['903.2.8']['explanation_en'])
        self.assertIn('heating & ventilation', by_rule['406.6.2']['explanation_en'])
        self.assertIn('No result came back', by_rule['1009.4']['explanation_en'])
        self.assertEqual(by_rule['406.6.2']['sections'], ['hvac'])
        by_key = {s['key']: s for s in report['sections']}
        self.assertEqual((by_key['fire']['status'], by_key['fire']['error'], by_key['hvac']['status']), ('failed', 'ai_busy', 'no_drawings'))
        self.assertTrue(all(BY_ID[f['rule']] for f in report['findings']))


if __name__ == '__main__':
    unittest.main()
