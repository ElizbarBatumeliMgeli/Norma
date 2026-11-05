"""DWG and DXF drawings: conversion, sheets, flat geometry and PDF pages.

A worker for one file: `python cad.py <drawing> <folder>` writes sheets.pdf and sheets.json there.
It runs as its own process, so a drawing that hangs or crashes costs one file and not the project.
"""
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

import ezdxf
from ezdxf import bbox, disassemble, path, recover
from ezdxf.addons.drawing import Frontend, RenderContext, config, layout
from ezdxf.addons.drawing.recorder import Recorder
from ezdxf.addons.drawing.svg import SVGBackend
from ezdxf.fonts import fonts
from ezdxf.math import BoundingBox2d, bulge_center, bulge_radius
from ezdxf.tools.text import plain_mtext
import pymupdf

import measure

UNIT_METRES = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}
GEORGIAN_FONTS = ('Arial Unicode.ttf', 'sylfaen.ttf', 'NotoSansGeorgian-Regular.ttf', 'DejaVuSans.ttf')
LEGACY_GEORGIAN = re.compile(r'nusx|litera|grigolia|geo_', re.I)    # old fonts that show Latin letters as Georgian
LATIN_TO_GEORGIAN = str.maketrans('abgdevzTiklmnopJrstufqRySCcZwWxjh', 'აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ')
DEFAULT_LAYOUT = re.compile(r'layout\s*\d+|sheet\s*\d+|лист\s*\d+', re.I)    # a name nobody chose says nothing
SHEET_LONGEST_MM = 1189     # A0: sharp enough to zoom, small enough for a PDF page
MIN_SHEET_SHARE = 0.03      # a part of the drawing with less than this share of its lines is not a sheet
MAX_SHEETS = 60
HATCH_CURVE_STEP = 20       # in drawing units: fine enough in millimetres, and harmless in metres


class CadError(RuntimeError):
    def __init__(self, code, detail=''):
        super().__init__(detail or code)
        self.code, self.detail = code, detail


def find_dwg2dxf():
    found = shutil.which('dwg2dxf')
    if found:
        return found
    # Homebrew paths are often missing from PATH when the app is started from Finder.
    return next((p for p in ('/opt/homebrew/bin/dwg2dxf', '/usr/local/bin/dwg2dxf') if Path(p).exists()), None)


def to_dxf(source, target):
    tool = find_dwg2dxf()
    if not tool:
        raise CadError('dwg_converter_missing')
    try:
        result = subprocess.run([tool, '-y', '-o', str(target), str(source)], capture_output=True, text=True, errors='replace', timeout=240)
    except subprocess.TimeoutExpired:
        raise CadError('unreadable_cad', 'DWG conversion timed out')
    if not Path(target).exists():
        raise CadError('unreadable_cad', result.stderr.strip()[-300:])


def decoded(text):
    """Georgian arrives from LibreDWG as \\U+10D0 codes."""
    return re.sub(r'\\U\+([0-9A-Fa-f]{4})', lambda code: chr(int(code[1], 16)), text)


def fix_text(document):
    """Readable text in every entity: real Georgian letters, and one font that has them."""
    legacy = {style.dxf.name for style in document.styles if LEGACY_GEORGIAN.search(style.dxf.get('font', '') or '')}
    available = next((name for name in GEORGIAN_FONTS if fonts.font_manager.has_font(name)), None)
    for entity in document.entitydb.values():
        kind = entity.dxftype()
        if kind in ('TEXT', 'ATTRIB', 'ATTDEF'):
            text = decoded(entity.dxf.text)
            entity.dxf.text = text.translate(LATIN_TO_GEORGIAN) if entity.dxf.get('style') in legacy else text
        elif kind == 'MTEXT':
            text = decoded(entity.text)
            if entity.dxf.get('style') in legacy or LEGACY_GEORGIAN.search(text):
                text = plain_mtext(text).translate(LATIN_TO_GEORGIAN)
            entity.text = re.sub(r'\\f[^;]*;', '', text)
            if len(plain_mtext(text)) <= 12:
                entity.dxf.width = 0    # a box drawn for another font can be too narrow for one short word
    if available:
        for style in document.styles:
            style.dxf.font = available


def open_drawing(path):
    try:
        document = ezdxf.readfile(str(path))
    except ezdxf.DXFError:
        try:
            document, _ = recover.readfile(str(path))
        except (OSError, ezdxf.DXFError) as error:
            raise CadError('unreadable_cad', str(error)[:300])
    fix_text(document)
    return document


@dataclass
class Geometry:
    """The drawing flattened to world coordinates, in the file's own units."""
    unit: float = 0.001                             # metres per drawing unit
    lines: list = field(default_factory=list)       # x0, y0, x1, y1, layer
    arcs: list = field(default_factory=list)        # centre x, y, radius, sweep in degrees, layer, start point, end point
    circles: list = field(default_factory=list)     # x, y, radius, layer
    texts: list = field(default_factory=list)       # x, y, height, text, layer, attachment 1–9
    blocks: list = field(default_factory=list)      # x, y, block name, layer
    fills: list = field(default_factory=list)       # outlines of filled areas, as x0, y0, x1, y1, layer: walls are often only this


def add_polyline(entity, geometry, layer):
    points = list(entity.get_points('xyb'))
    if entity.closed and points:
        points.append(points[0])
    for (x0, y0, bulge), (x1, y1, _) in zip(points, points[1:]):
        if abs(bulge) < 1e-9:
            geometry.lines.append((x0, y0, x1, y1, layer))
        elif (x0, y0) != (x1, y1):
            centre = bulge_center((x0, y0), (x1, y1), bulge)
            geometry.arcs.append((centre.x, centre.y, bulge_radius((x0, y0), (x1, y1), bulge), math.degrees(4 * math.atan(abs(bulge))), layer, (x0, y0), (x1, y1)))


def add_arc(entity, geometry, layer):
    centre, radius = entity.dxf.center, entity.dxf.radius
    start, end = entity.dxf.start_angle, entity.dxf.end_angle
    at = lambda angle: (centre.x + radius * math.cos(math.radians(angle)), centre.y + radius * math.sin(math.radians(angle)))
    geometry.arcs.append((centre.x, centre.y, radius, (end - start) % 360, layer, at(start), at(end)))


def add_hatch(entity, geometry, layer):
    for outline in path.from_hatch(entity):
        points = list(outline.flattening(HATCH_CURVE_STEP))
        geometry.fills += [(a.x, a.y, b.x, b.y, layer) for a, b in zip(points, points[1:])]


def unit_of(document, geometry):
    """Metres per drawing unit. Files that do not say are in millimetres, unless a building would then fit on a table."""
    stated = UNIT_METRES.get(document.header.get('$INSUNITS', 0))
    if stated or not geometry.lines:
        return stated or 0.001
    lengths = sorted(math.hypot(x1 - x0, y1 - y0) for x0, y0, x1, y1, _ in geometry.lines)
    return 1.0 if lengths[len(lengths) * 9 // 10] < 20 else 0.001


def flatten(document):
    """Every visible line, arc, circle, text and named block of model space, in world coordinates."""
    geometry = Geometry()
    hidden = {layer.dxf.name for layer in document.layers if layer.is_off() or layer.is_frozen()}
    space = document.modelspace()
    for entity in space:
        if entity.dxftype() == 'INSERT' and entity.dxf.layer not in hidden and measure.device(entity.dxf.name, entity.dxf.layer):
            # Exports from BIM put a block's origin anywhere: its shape says where it is.
            shape = bbox.extents([entity], fast=True)
            if shape.has_data:
                geometry.blocks.append((shape.center.x, shape.center.y, entity.dxf.name, entity.dxf.layer))
    for entity in disassemble.recursive_decompose(space):
        kind, layer = entity.dxftype(), entity.dxf.get('layer', '0')
        if layer in hidden:
            continue
        if kind == 'LINE':
            start, end = entity.dxf.start, entity.dxf.end
            geometry.lines.append((start.x, start.y, end.x, end.y, layer))
        elif kind == 'LWPOLYLINE':
            add_polyline(entity, geometry, layer)
        elif kind == 'ARC':
            add_arc(entity, geometry, layer)
        elif kind == 'CIRCLE':
            geometry.circles.append((entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius, layer))
        elif kind == 'HATCH':
            add_hatch(entity, geometry, layer)
        elif kind == 'TEXT':
            text = entity.plain_text().strip()
            if text:
                at = entity.dxf.insert
                geometry.texts.append((at.x, at.y, entity.dxf.get('height', 1), text, layer, 7))
        elif kind == 'MTEXT':
            text = ' '.join(plain_mtext(entity.text).split())
            if text:
                at = entity.dxf.insert
                geometry.texts.append((at.x, at.y, entity.dxf.get('char_height', 1), text, layer, entity.dxf.get('attachment_point', 1)))
    geometry.unit = unit_of(document, geometry)
    return geometry


def viewport_sheets(document):
    """The sheets the designer framed: each layout's main viewport, as a window on model space."""
    sheets, seen = [], set()
    for sheet_layout in document.layouts:
        if sheet_layout.name == 'Model':
            continue
        # A scale near 1 is the paper's own frame, and a turned view cannot be shown as a plain window.
        views = [v for v in sheet_layout if v.dxftype() == 'VIEWPORT' and v.dxf.get('height', 0) > 0 and v.dxf.get('view_height', 0) / v.dxf.height > 1.5
                 and not v.dxf.get('view_twist_angle', 0)]
        if not views:
            continue
        view = max(views, key=lambda v: v.dxf.width * v.dxf.height)
        scale = view.dxf.view_height / view.dxf.height
        centre, half_w, half_h = view.dxf.view_center_point, view.dxf.width * scale / 2, view.dxf.view_height / 2
        box = tuple(round(v, 3) for v in (centre.x - half_w, centre.y - half_h, centre.x + half_w, centre.y + half_h))
        if box not in seen:
            seen.add(box)
            sheets.append(dict(label='' if DEFAULT_LAYOUT.fullmatch(sheet_layout.name) else sheet_layout.name, box=box, scale=round(scale)))
    return sheets


def spans(geometry):
    """The extent of each piece of geometry: x0, y0, x1, y1."""
    found = [(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)) for x0, y0, x1, y1, _ in geometry.lines]
    found += [(x - r, y - r, x + r, y + r) for x, y, r, *_ in geometry.arcs]
    found += [(x - r, y - r, x + r, y + r) for x, y, r, _ in geometry.circles]
    found += [(t[0], t[1], t[0] + t[2] * 0.55 * len(t[3]), t[1] + t[2]) for t in geometry.texts]
    return found


def split(pieces, total):
    """Cuts the drawing along clear gaps until each part is one sheet. Far-off specks are dropped."""
    x0, y0 = min(p[0] for p in pieces), min(p[1] for p in pieces)
    x1, y1 = max(p[2] for p in pieces), max(p[3] for p in pieces)
    larger = max(x1 - x0, y1 - y0)
    for axis in (0, 1):
        ordered = sorted(pieces, key=lambda p: p[axis])
        reach, cuts = ordered[0][axis + 2], []
        for index, piece in enumerate(ordered[1:], 1):
            if piece[axis] - reach > 0.04 * larger:
                cuts.append((piece[axis] - reach, index))
            reach = max(reach, piece[axis + 2])
        for gap, index in sorted(cuts, reverse=True):
            before, after = ordered[:index], ordered[index:]
            smaller = min(len(before), len(after))
            if smaller >= MIN_SHEET_SHARE * total:
                return split(before, total) + split(after, total)
            if gap > 0.5 * larger:
                return split(before if len(before) > len(after) else after, total)
    return [(x0, y0, x1, y1)]


def gap_sheets(geometry):
    """Sheets for a drawing without framed layouts: the parts of model space with clear gaps between them."""
    pieces = spans(geometry)
    if not pieces:
        return []
    boxes = split(pieces, len(pieces))
    largest = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes)
    boxes = sorted((b for b in boxes if max(b[2] - b[0], b[3] - b[1]) > 0.05 * largest), key=lambda b: (-b[3], b[0]))
    return [dict(label='', box=tuple(round(v, 3) for v in box), scale=None) for box in boxes]


def recording(document):
    space = document.modelspace()
    context = RenderContext(document)
    context.set_current_layout(space)
    recorder = Recorder()
    settings = config.Configuration(background_policy=config.BackgroundPolicy.WHITE, color_policy=config.ColorPolicy.COLOR,
                                    lineweight_scaling=0.6)
    Frontend(context, recorder, config=settings).draw_layout(space)
    return recorder.player()


def inline_styles(svg):
    """The PDF converter ignores style sheets, which leaves every shape solid black: each style goes on its shapes."""
    attributes = {}
    for name, body in re.findall(r'\.(C\w+) \{([^}]*)\}', svg):
        pairs = [item.split(':') for item in body.split(';') if item.strip()]
        attributes[name] = ' '.join(f'{key.strip()}="{value.strip()}"' for key, value in pairs if key.strip() != 'stroke-width' or value.strip() != 'none')
    return re.sub(r'class="(C\w+)"', lambda match: attributes.get(match[1], ''), svg)


def render(player, sheet):
    """One sheet as a PDF page with the frame's exact proportions, so a position maps straight to a fraction.
    Going through SVG is several times faster than drawing each path into the PDF from Python."""
    x0, y0, x1, y1 = sheet['box']
    width, height = x1 - x0, y1 - y0
    part = player.copy()
    part.crop_rect((x0, y0), (x1, y1), max(width, height) / 20000)
    backend = SVGBackend()
    part.replay(backend)
    fit = SHEET_LONGEST_MM / max(width, height)
    page = layout.Page(width * fit, height * fit, layout.Units.mm, margins=layout.Margins.all(0))
    svg = backend.get_string(page, settings=layout.Settings(fit_page=True), render_box=BoundingBox2d([(x0, y0), (x1, y1)]))
    with pymupdf.open(stream=inline_styles(svg).encode(), filetype='svg') as document:
        return document.convert_to_pdf()


def fraction(sheet, x, y):
    x0, y0, x1, y1 = sheet['box']
    return (x - x0) / (x1 - x0), (y1 - y) / (y1 - y0)


def anchors(geometry, sheet):
    """The text of a sheet, placed like pdf_tools.anchors. A CAD page has its letters as shapes, so they are placed from the file."""
    x0, y0, x1, y1 = sheet['box']
    found = []
    for x, y, height, text, _, attachment in geometry.texts:
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        width = height * 0.55 * len(text)
        column, row = (attachment - 1) % 3, (attachment - 1) // 3
        left, top = x - width * column / 2, y + height * (1 - row / 2 if row < 2 else 1)
        a, b = fraction(sheet, left, top)
        c, d = fraction(sheet, left + width, top - height)
        found.append(dict(text=text, box=[round(min(max(v, 0), 1), 4) for v in (a, b, c, d)]))
    return found


def run(drawing, folder):
    drawing, folder = Path(drawing), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    converted = folder / 'drawing.dxf'
    if drawing.suffix.lower() == '.dwg':
        to_dxf(drawing, converted)
    document = open_drawing(converted if drawing.suffix.lower() == '.dwg' else drawing)
    geometry = flatten(document)
    sheets = viewport_sheets(document) or gap_sheets(geometry)
    if not sheets:
        raise CadError('empty_cad')
    player = recording(document)
    output = pymupdf.open()
    for sheet in sheets[:MAX_SHEETS]:
        with pymupdf.open('pdf', render(player, sheet)) as page:
            output.insert_pdf(page)
        sheet['anchors'] = anchors(geometry, sheet)
        sheet['measured'] = measure.sheet(geometry, sheet)
    output.save(folder / 'sheets.pdf', garbage=3, deflate=True)
    (folder / 'sheets.json').write_text(json.dumps(dict(sheets=sheets[:MAX_SHEETS]), ensure_ascii=False), encoding='utf-8')
    converted.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        run(sys.argv[1], sys.argv[2])
    except CadError as error:
        print(json.dumps(dict(error=error.code, detail=error.detail)))
        sys.exit(2)
