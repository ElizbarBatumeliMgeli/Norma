"""CAD reading and measuring on a small floor plan drawn here: its dimensions are known exactly."""
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

import ezdxf
import pymupdf

import cad
import measure
import pdf_tools
from report import assemble
import server
import settings


def walls(space, x0, y0, x1, y1, thickness=0.2):
    """A wall as two faces, in millimetres."""
    horizontal = abs(y1 - y0) < abs(x1 - x0)
    dx, dy = (0, thickness) if horizontal else (thickness, 0)
    space.add_line((x0 * 1000, y0 * 1000), (x1 * 1000, y1 * 1000), dxfattribs=dict(layer='WALL'))
    space.add_line(((x0 + dx) * 1000, (y0 + dy) * 1000), ((x1 + dx) * 1000, (y1 + dy) * 1000), dxfattribs=dict(layer='WALL'))


def stair(space, x, y, width=1.3, tread=0.3, count=9):
    """Two flights side by side, treads across the width."""
    for flight in range(2):
        left = x + flight * (width + 0.1)
        for index in range(count):
            at = y + index * tread
            space.add_line((left * 1000, at * 1000), ((left + width) * 1000, at * 1000), dxfattribs=dict(layer='STAIR'))
    space.add_text('20R x 16', dxfattribs=dict(insert=(x * 1000, y * 1000), height=200))


def door(space, x, y, leaf=0.9):
    space.add_arc((x * 1000, y * 1000), leaf * 1000, 0, 90, dxfattribs=dict(layer='DOOR'))
    space.add_line((x * 1000, y * 1000), (x * 1000, (y + leaf) * 1000), dxfattribs=dict(layer='DOOR'))


def floor_plan(path, flight=1.3, tread=0.3):
    """Two stairs in rooms at either end of a corridor 1.8 m wide, with five doors along it."""
    document = ezdxf.new(setup=True)
    document.header['$INSUNITS'] = 4
    space = document.modelspace()
    walls(space, 2, 10, 30, 10)         # corridor walls: clear between 10.2 and 12.0
    walls(space, 2, 12, 30, 12)
    walls(space, 2, 10, 2, 12.2)
    walls(space, 30, 10, 30, 12.2)
    for x in (3, 27):                   # stair rooms below the corridor
        walls(space, x - 0.2, 3, x + 3.1, 3)
        walls(space, x - 0.2, 3, x - 0.2, 10)
        walls(space, x + 3.1, 3, x + 3.1, 10)
        stair(space, x, 4, flight, tread)
    for x in (7, 11, 15, 19, 23):
        door(space, x, 12.2)
    space.add_text('+32.000', dxfattribs=dict(insert=(10000, 14000), height=300))
    space.add_text('\\U+10D1\\U+10D8\\U+10DC\\U+10D0 # 1001', dxfattribs=dict(insert=(12000, 14000), height=300))
    document.saveas(path)


class Plan(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / '10 სართული.dxf'
        floor_plan(self.path)

    def read(self):
        document = cad.open_drawing(self.path)
        geometry = cad.flatten(document)
        return document, geometry, cad.gap_sheets(geometry)[0]

    def test_georgian_codes_become_letters(self):
        _, geometry, _ = self.read()
        self.assertIn('ბინა # 1001', [t[3] for t in geometry.texts])

    def test_stairs_doors_and_level_are_measured(self):
        _, geometry, sheet = self.read()
        found = measure.sheet(geometry, sheet)
        self.assertEqual(found['level'], 32.0)
        self.assertEqual(found['units'], 1)
        self.assertEqual(found['doors'], 5)
        main = [s for s in found['stairs'] if s['main']]
        self.assertEqual(len(main), 2)
        self.assertEqual((main[0]['width'], main[0]['tread'], main[0]['risers'], main[0]['riser']), (1.3, 0.3, 20, 0.16))

    def test_corridor_and_separation_are_measured(self):
        _, geometry, sheet = self.read()
        found = measure.sheet(geometry, sheet)
        self.assertAlmostEqual(found['corridor']['width'], 1.8, delta=0.15)
        # The rooms' facing walls: 6.1 to 26.8 between the outer faces, 5.9 to 27 inside the second face.
        self.assertAlmostEqual(found['separation']['outer'], 20.7, delta=0.4)

    def test_a_page_keeps_the_frame_proportions(self):
        document, geometry, sheet = self.read()
        with pymupdf.open('pdf', cad.render(cad.recording(document), sheet)) as pages:
            rect = pages[0].rect
        x0, y0, x1, y1 = sheet['box']
        self.assertAlmostEqual(rect.width / rect.height, (x1 - x0) / (y1 - y0), places=2)

    def test_a_page_shows_lines_and_not_solid_shapes(self):
        document, _, sheet = self.read()
        with pymupdf.open('pdf', cad.render(cad.recording(document), sheet)) as pages:
            picture = pages[0].get_pixmap(dpi=20, colorspace=pymupdf.csGRAY)
        dark = sum(value < 128 for value in picture.samples) / len(picture.samples)
        self.assertLess(dark, 0.3)
        self.assertGreater(dark, 0)

    def test_text_is_placed_inside_the_sheet(self):
        _, geometry, sheet = self.read()
        item = next(a for a in cad.anchors(geometry, sheet) if a['text'] == '+32.000')
        self.assertTrue(0 <= item['box'][0] < item['box'][2] <= 1 and 0 <= item['box'][1] < item['box'][3] <= 1)


class Sheets(unittest.TestCase):
    def test_parts_with_clear_gaps_are_separate_sheets(self):
        geometry = cad.Geometry()
        for origin in (0, 100000):
            geometry.lines += [(origin + i * 100, i * 100, origin + i * 100 + 500, i * 100, 'A') for i in range(100)]
        self.assertEqual(len(cad.gap_sheets(geometry)), 2)

    def test_a_far_speck_is_dropped(self):
        geometry = cad.Geometry()
        geometry.lines += [(i * 100, i * 100, i * 100 + 500, i * 100, 'A') for i in range(200)]
        geometry.lines.append((9000000, 0, 9000100, 0, 'A'))
        sheets = cad.gap_sheets(geometry)
        self.assertEqual(len(sheets), 1)
        self.assertLess(sheets[0]['box'][2], 100000)

    def test_a_file_with_no_unit_is_read_from_its_sizes(self):
        document = ezdxf.new()
        document.header['$INSUNITS'] = 0
        document.modelspace().add_line((0, 0), (3, 0))
        self.assertEqual(cad.flatten(document).unit, 1.0)
        document.modelspace().delete_all_entities()
        document.modelspace().add_line((0, 0), (3000, 0))
        self.assertEqual(cad.flatten(document).unit, 0.001)

    def test_layout_viewports_frame_the_sheets_and_give_the_scale(self):
        document = ezdxf.new(setup=True)
        layout = document.layouts.new('3-4')
        layout.add_viewport(center=(200, 150), size=(400, 300), view_center_point=(20000, 15000), view_height=30000)
        sheets = cad.viewport_sheets(document)
        self.assertEqual([(s['label'], s['scale'], s['box']) for s in sheets if s['label'] == '3-4'], [('3-4', 100, (0, 0, 40000, 30000))])

    def test_storeys_come_from_the_layout_or_file_name(self):
        self.assertEqual(measure.floors_of('Layout1', 'PA-MP-BO-FF-10-10 სართულის ხანძარქრობა.dwg'), [10])
        self.assertEqual(measure.floors_of('Layout1', 'PA-MP-BO-FF-0--1 სართულის ხანძარქრობა.dwg'), [-1])
        self.assertEqual(measure.floors_of('3-4', 'plan.dwg'), [3, 4])
        self.assertEqual(measure.floors_of('-1', 'plan.dwg'), [-1])
        self.assertEqual(measure.floors_of('Layout1', 'PR-MP-BO-HC-19-03-გათბობა.dwg'), [])


def row(**values):
    return dict(dict(name='10', floors=[10], page=3, level=32.0, stairs=2, units=0, stair_width=1.3, tread=0.3, riser=0.16, stair_doors=0.94, sprinklers=0, cabinets=0, landing_valves=0,
                     separation_inner=11.0, separation_outer=10.0, corridor=1.6, narrowest=1.5, dead_end=4.0, diagonal=40.0, marks=dict(stairs=dict(page=3, box=[0.1, 0.1, 0.2, 0.2]))), **values)


def statuses(*rows):
    return {c['rule_id']: c['status'] for c in measure.checks(dict(floors=list(rows), top_level=max(r['level'] for r in rows), storeys=len(rows)))}


class Rules(unittest.TestCase):
    def test_a_compliant_building_passes_what_was_measured(self):
        found = statuses(row())
        for rule in ('202', '1008.1.1', '1009.4', '1009.7.2', '1018.2', '1018.4', '1021.2', '403.5.1'):
            self.assertEqual(found[rule], 'pass', rule)

    def test_a_narrow_stair_fails_and_a_steep_step_fails(self):
        self.assertEqual(statuses(row(stair_width=1.0))['1009.4'], 'fail')
        self.assertEqual(statuses(row(riser=0.19))['1009.7.2'], 'fail')
        self.assertEqual(statuses(row(tread=0.26))['1009.7.2'], 'fail')

    def test_a_tread_without_a_riser_label_stays_to_verify(self):
        self.assertEqual(statuses(row(riser=None))['1009.7.2'], 'verify')

    def test_what_the_map_can_get_wrong_never_fails_alone(self):
        self.assertEqual(statuses(row(narrowest=1.0))['1018.2'], 'verify')
        self.assertEqual(statuses(row(stairs=1))['1021.2'], 'verify')
        self.assertEqual(statuses(row(stair_doors=0.8))['1008.1.1'], 'verify')

    def test_a_dead_end_needs_an_exception_over_six_metres(self):
        self.assertEqual(statuses(row(dead_end=9.0))['1018.4'], 'verify')
        self.assertEqual(statuses(row(dead_end=16.0))['1018.4'], 'fail')

    def test_separation_depends_on_where_it_is_measured(self):
        self.assertEqual(statuses(row(separation_outer=8.5, separation_inner=9.1))['403.5.1'], 'verify')
        self.assertEqual(statuses(row(separation_outer=7.0, separation_inner=8.0))['403.5.1'], 'fail')

    def test_a_separation_only_just_over_the_limit_is_not_a_pass(self):
        self.assertEqual(statuses(row(separation_outer=9.06, separation_inner=9.9))['403.5.1'], 'verify')

    def test_separation_is_not_asked_of_a_low_building(self):
        self.assertNotIn('403.5.1', statuses(row(level=9.0, separation_outer=5.0, separation_inner=6.0)))

    def test_measuring_settles_what_the_ai_left_open_but_not_what_it_failed(self):
        summary = dict(floors=[row()], top_level=32.0, storeys=1)
        building = dict(name='', occupancy='', storeys=1, top_floor_m=None, high_rise=None, sprinklered=None, summary_ka='', summary_en='')
        review = dict(building=building, checks=[dict(rule_id='1009.4', status='verify'), dict(rule_id='1018.2', status='fail', found='ცხრილი')])
        by_rule = {f['rule']: f for f in assemble(review, [], [dict(number=3)] * 3, summary)['findings']}
        self.assertEqual((by_rule['1009.4']['status'], by_rule['1009.4']['measured']), ('pass', True))
        self.assertEqual((by_rule['1018.2']['status'], by_rule['1018.2']['measured']), ('fail', False))


class Project(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        home = Path(self.folder.name)
        patches = [mock.patch.object(settings, 'REPORTS', home / 'reports'), mock.patch.object(settings, 'CONFIG', home / 'config.json'), mock.patch.dict('os.environ', clear=False)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        settings.REPORTS.mkdir()
        self.app = server.app.test_client()
        self.plan = home / 'plan.dxf'
        floor_plan(self.plan)

    def run_check(self, *files):
        report_id = self.app.post('/api/reports', json=dict(name='Project')).json['id']
        for name, data, discipline in files:
            sent = self.app.post(f'/api/reports/{report_id}/files', data=dict(file=(io.BytesIO(data), name), discipline=discipline), content_type='multipart/form-data')
            self.assertEqual(sent.status_code, 200)
        with mock.patch.object(settings, 'provider', lambda: None):
            self.assertEqual(self.app.post(f'/api/reports/{report_id}/check').status_code, 200)
            for thread in list(server.threading.enumerate()):
                if thread is not server.threading.current_thread() and thread.daemon:
                    thread.join(120)
        return report_id

    def test_a_project_is_measured_without_an_ai_key(self):
        sample = Path(server.__file__).parent / 'demo' / 'sample.pdf'
        report_id = self.run_check(('PA-FF-10-10 სართულის ხანძარქრობა.dxf', self.plan.read_bytes(), 'fire'), ('plan.pdf', sample.read_bytes(), 'architecture'), ('broken.dxf', b'not a drawing', 'other'))
        self.assertEqual(self.app.get(f'/api/reports/{report_id}/stage').json['stage'], 'done')
        report = self.app.get(f'/api/reports/{report_id}').json
        # Sheets run in discipline order, and each knows its file.
        self.assertEqual(report['pages'][0]['discipline'], 'architecture')
        self.assertEqual(report['pages'][-1]['file'], 'PA-FF-10-10 სართულის ხანძარქრობა.dxf')
        self.assertFalse(report['ai_used'])
        by_rule = {f['rule']: f for f in report['findings']}
        self.assertEqual(by_rule['1009.4']['status'], 'pass')
        self.assertTrue(by_rule['1009.4']['measured'])
        self.assertEqual(report['measured']['floors'][0]['name'], '10')
        self.assertEqual(by_rule['1009.4']['page'], len(report['pages']))
        self.assertEqual([f['error'] for f in report['files'] if f.get('error')], ['unreadable_cad'])
        anchors = json.loads((settings.REPORTS / report_id / 'anchors.json').read_text(encoding='utf-8'))
        self.assertEqual({a['id'] for a in anchors}, set(range(len(anchors))))
        self.assertFalse((settings.REPORTS / report_id / 'sources').exists())
        with self.app.get(f'/api/reports/{report_id}/pages/{len(report["pages"])}.png') as image:
            self.assertEqual(image.mimetype, 'image/png')


class ForModel(unittest.TestCase):
    def test_a_project_too_big_to_send_keeps_its_page_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'all.pdf', Path(folder) / 'model.pdf'
            noise = random.Random(1)
            with pymupdf.open() as document:
                for _ in range(6):
                    # Vector pages like a CAD sheet's: a lot of data that makes a small picture.
                    shape = document.new_page(width=800, height=600).new_shape()
                    for _ in range(30000):
                        x, y = noise.uniform(0, 90), noise.uniform(0, 90)
                        shape.draw_line((x, y), (x + noise.uniform(0, 9), y + noise.uniform(0, 9)))
                    shape.finish(width=0.1)
                    shape.commit()
                document.save(source, deflate=True)
            with pymupdf.open(source) as document:
                zoom = 2200 / 800
                limit = int(len(document[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes('jpeg', jpg_quality=70)) * 2.5)     # room for two sheets
            result = pdf_tools.for_model(source, target, limit, first=[5, 4])
            self.assertIsNotNone(result)
            with pymupdf.open(result) as sent:
                self.assertEqual(sent.page_count, 6)
                self.assertTrue(sent[4].get_images())
                self.assertFalse(sent[0].get_images())


if __name__ == '__main__':
    unittest.main()
