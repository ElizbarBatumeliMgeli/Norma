"""Measurements read straight from CAD geometry, in metres. No AI is involved, so the same file always gives the same numbers.

Stairs and doors are found from their shapes, not from layer names, because every office names layers differently.
"""
from collections import Counter, defaultdict, deque
import math
import re
from statistics import median

import numpy as np
from scipy import ndimage

TREAD_RANGE = (0.22, 0.36)
FLIGHT_WIDTH_RANGE = (0.7, 2.6)
MIN_TREADS = 5
MAIN_STAIR_TREADS = 7           # fewer, in a single flight, is an entrance step and not an exit stair
DOOR_RANGE = (0.55, 1.6)
LEVEL = re.compile(r'^\s*([+±-])\s*(\d{1,3}[.,]\d{2,3})\s*$')
STAIR_LABEL = re.compile(r'(\d{1,2})\s*R\s*[xX×хХ]\s*(\d{2,3})?')
UNIT_LABEL = re.compile(r'(?:bina|ბინა)\s*#?\s*\d+|^(?:bina|ბინა)\s*#', re.I)
CELL = 0.05                     # metres per cell of the wall map
OPEN_RADIUS = 0.55              # half the width that counts as open space: doors, at about 0.9 m, close it off
CORRIDOR_MAX_WIDTH = 3.0
WALL_MAX = 0.45                 # thicker than this, two lines are not the faces of one wall
PLAN_MAX = 150                  # metres; a larger frame is a site plan, and a wall map of it would not fit in memory
MIN_CORRIDOR_DOORS = 4
NOT_WALL = re.compile(r'^(P-|M-|E-|F-|G-|S-GRID|C-|FP-|EL-)|pipe|duct|anno|dim|text|grid|axis|оси|ось|numeracia|ზომ|sprink|ventil', re.I)
DEVICES = {
    'sprinklers': re.compile(r'sprink|\bsprn|f-sprn|спринк|სპრინკლ', re.I),
    'cabinets': re.compile(r'muurhydrant|hose.?(cab|reel)|fire.?cab|пожарн.*шкаф|კარადა', re.I),
    'landing_valves': re.compile(r'brandkraan|landing.?valve', re.I),
}


def window(geometry, sheet):
    """The sheet's geometry in metres, from the frame's lower left corner."""
    x0, y0, x1, y1 = sheet['box']
    unit = geometry.unit
    inside = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1
    lines = [((a - x0) * unit, (b - y0) * unit, (c - x0) * unit, (d - y0) * unit, layer)
             for a, b, c, d, layer in geometry.lines if inside(a, b) and inside(c, d)]
    arcs = [((x - x0) * unit, (y - y0) * unit, r * unit, sweep, layer) for x, y, r, sweep, layer, *_ in geometry.arcs if inside(x, y)]
    texts = [((x - x0) * unit, (y - y0) * unit, text) for x, y, _, text, *_ in geometry.texts if inside(x, y)]
    return lines, arcs, texts


def fills(geometry, sheet):
    x0, y0, x1, y1 = sheet['box']
    unit = geometry.unit
    return [((a - x0) * unit, (b - y0) * unit, (c - x0) * unit, (d - y0) * unit, layer)
            for a, b, c, d, layer in geometry.fills if x0 <= a <= x1 and y0 <= b <= y1]


def chains(positions):
    """Runs of evenly spaced values: the treads of a flight, seen across it."""
    values = sorted(positions)
    distinct = [v for i, v in enumerate(values) if i == 0 or v - values[i - 1] > 0.02]
    if len(distinct) < MIN_TREADS:
        return []
    steps = Counter(round(b - a, 2) for a, b in zip(distinct, distinct[1:]))
    found, used = [], set()
    for step, _ in steps.most_common(3):
        if not TREAD_RANGE[0] <= step <= TREAD_RANGE[1]:
            continue
        for start in distinct:
            if start in used:
                continue
            run = [start]
            for value in distinct:
                if value > run[-1] and abs(value - run[-1] - step) <= 0.012:
                    run.append(value)
            if len(run) >= MIN_TREADS:
                used.update(run)
                found.append(run)
    return found


def flights(lines):
    """Straight flights: at least five parallel lines of one length, evenly spaced at tread distance."""
    groups = defaultdict(list)
    for x0, y0, x1, y1, _ in lines:
        length = math.hypot(x1 - x0, y1 - y0)
        if FLIGHT_WIDTH_RANGE[0] <= length <= FLIGHT_WIDTH_RANGE[1]:
            angle = round(math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180 / 3) * 3 % 180
            groups[angle, round(length / 0.05)].append((x0, y0, x1, y1, length))
    found = []
    for (angle, _), members in groups.items():
        if len(members) < MIN_TREADS:
            continue
        theta = math.radians(angle)
        along = lambda x, y: x * math.cos(theta) + y * math.sin(theta)
        across = lambda x, y: -x * math.sin(theta) + y * math.cos(theta)
        rows = defaultdict(list)
        for x0, y0, x1, y1, length in members:
            rows[round(along((x0 + x1) / 2, (y0 + y1) / 2) / 0.2)].append((across((x0 + x1) / 2, (y0 + y1) / 2), x0, y0, x1, y1, length))
        for row in rows.values():
            for run in chains([item[0] for item in row]):
                treads = [item for item in row if any(abs(item[0] - value) < 0.005 for value in run)]
                xs = [v for t in treads for v in (t[1], t[3])]
                ys = [v for t in treads for v in (t[2], t[4])]
                found.append(dict(width=round(median(t[5] for t in treads), 2), tread=round((run[-1] - run[0]) / (len(run) - 1), 3),
                                  treads=len(run), box=[min(xs), min(ys), max(xs), max(ys)]))
    return found


def apart(a, b):
    """Shortest distance between two boxes, zero if they touch."""
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return math.hypot(dx, dy)


def stairs(lines, texts):
    """Flights next to each other are one stair."""
    groups = []
    for flight in sorted(flights(lines), key=lambda f: -f['treads']):
        for group in groups:
            if any(apart(flight['box'], other['box']) < 1.2 for other in group):
                group.append(flight)
                break
        else:
            groups.append([flight])
    found = []
    for group in groups:
        box = [min(f['box'][0] for f in group), min(f['box'][1] for f in group), max(f['box'][2] for f in group), max(f['box'][3] for f in group)]
        treads = sum(f['treads'] for f in group)
        stair = dict(width=min(f['width'] for f in group), tread=round(median(f['tread'] for f in group), 3), treads=treads,
                     flights=len(group), box=[round(v, 2) for v in box], main=treads >= MAIN_STAIR_TREADS or len(group) > 1)
        stair.update(label(stair, texts))
        found.append(stair)
    return found


def label(stair, texts):
    """The riser count and height written beside a stair: `20R x 160`, sometimes with the height as separate text."""
    x0, y0, x1, y1 = stair['box']
    near = [(x, y, text) for x, y, text in texts if x0 - 3 <= x <= x1 + 3 and y0 - 3 <= y <= y1 + 3]
    for x, y, text in near:
        match = STAIR_LABEL.search(text)
        if not match:
            continue
        height = match[2] or next((t.strip() for a, b, t in near if math.hypot(a - x, b - y) < 0.6 and re.fullmatch(r'\s*\d{2,3}\s*', t)), None)
        if height:
            value = int(height)
            return dict(risers=int(match[1]), riser=value / 1000 if value >= 50 else value / 100)
        return dict(risers=int(match[1]), riser=None)
    return dict(risers=None, riser=None)


def doors(lines, arcs):
    """Door swings: an arc of about a quarter turn with a leaf from its centre. Width is the leaf."""
    ends = defaultdict(list)
    for x0, y0, x1, y1, _ in lines:
        length = math.hypot(x1 - x0, y1 - y0)
        ends[round(x0 / 0.1), round(y0 / 0.1)].append(length)
        ends[round(x1 / 0.1), round(y1 / 0.1)].append(length)
    found = {}
    for x, y, radius, sweep, layer in arcs:
        if not DOOR_RANGE[0] <= radius <= DOOR_RANGE[1]:
            continue
        named = 'door' in layer.lower() or 'двер' in layer.lower() or 'კარ' in layer.lower()
        cell = round(x / 0.1), round(y / 0.1)
        leaf = any(abs(length - radius) < 0.15 * radius for i in (-1, 0, 1) for j in (-1, 0, 1) for length in ends.get((cell[0] + i, cell[1] + j), ()))
        if (70 <= sweep <= 110 and (leaf or named)) or (named and sweep >= 20):
            found.setdefault((round(x, 1), round(y, 1)), dict(width=round(radius, 2), x=round(x, 2), y=round(y, 2)))
    return list(found.values())


def level(texts):
    """The floor level written on the plan, in metres. ±0.000 wins; otherwise the commonest mark."""
    marks = []
    for _, _, text in texts:
        match = LEVEL.match(text)
        if match:
            value = float(match[2].replace(',', '.'))
            marks.append(-value if match[1] == '-' else value)
    if not marks:
        return None
    return 0.0 if 0.0 in marks else Counter(marks).most_common(1)[0][0]


def device(block, layer):
    """Which fire device a block is, if any."""
    return next((name for name, pattern in DEVICES.items() if pattern.search(block) or pattern.search(layer)), None)


def devices(geometry, sheet):
    x0, y0, x1, y1 = sheet['box']
    counts = {name: 0 for name in DEVICES}
    for x, y, block, layer in geometry.blocks:
        if x0 <= x <= x1 and y0 <= y <= y1:
            counts[device(block, layer)] += 1
    return counts


def crosses(line, others):
    """How many of `others` this line passes straight through."""
    p, q = line[:2], line[2:]
    side = lambda a, b, points: (b[0] - a[0]) * (points[:, 1] - a[1]) - (b[1] - a[1]) * (points[:, 0] - a[0])
    first, second = side(p, q, others[:, :2]), side(p, q, others[:, 2:])
    across = lambda point: (others[:, 2] - others[:, 0]) * (point[1] - others[:, 1]) - (others[:, 3] - others[:, 1]) * (point[0] - others[:, 0])
    return int(((first * second < -1e-6) & (across(p) * across(q) < -1e-6)).sum())


def paired(segment, others):
    """Whether a line has a parallel neighbour at wall distance along part of its length: a wall has two faces."""
    x0, y0, x1, y1 = segment
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    mid_x, mid_y = (others[:, 0] + others[:, 2]) / 2 - x0, (others[:, 1] + others[:, 3]) / 2 - y0
    dx, dy = others[:, 2] - others[:, 0], others[:, 3] - others[:, 1]
    sizes = np.hypot(dx, dy)
    parallel = np.abs(dx * uy - dy * ux) <= 0.05 * sizes
    offset = np.abs(mid_x * uy - mid_y * ux)
    along = mid_x * ux + mid_y * uy
    return bool((parallel & (offset >= 0.04) & (offset <= 0.65) & (along >= -sizes / 2) & (along <= length + sizes / 2)).any())


def wall_map(lines, fills, size):
    """A grid of the plan, true where something is drawn. Pipes and notes are left out by layer name. Shapes rule out
    the rest: a long line that cuts through several others is a grid axis, and a line with no second face is a mark
    across a room, such as a section line, and not a wall."""
    kept = np.array([line[:4] for line in lines + fills if not NOT_WALL.search(line[4])], float)
    columns, rows = int(size[0] / CELL) + 2, int(size[1] / CELL) + 2
    grid = np.zeros((rows, columns), bool)
    if not len(kept):
        return grid
    lengths = np.hypot(kept[:, 2] - kept[:, 0], kept[:, 3] - kept[:, 1])
    solid = kept[lengths >= 0.3]
    keep = [i for i, length in enumerate(lengths) if length < 0.8 or (paired(kept[i], solid) and (length < 5 or crosses(kept[i], solid) < 4))]
    for x0, y0, x1, y1 in kept[keep]:
        steps = max(int(math.hypot(x1 - x0, y1 - y0) / (CELL / 2)), 1) + 1
        grid[(np.linspace(y0, y1, steps) / CELL).astype(int).clip(0, rows - 1), (np.linspace(x0, x1, steps) / CELL).astype(int).clip(0, columns - 1)] = True
    return grid


def hits(grid, x, y, dx, dy, limit=4.0):
    """Distances to drawn lines, walking out from a point. Cells that touch count as one line."""
    rows, columns = grid.shape
    found, before = [], False
    for distance in np.arange(CELL, limit, CELL / 2):
        row, column = int((y + dy * distance) / CELL), int((x + dx * distance) / CELL)
        if not (0 <= row < rows and 0 <= column < columns):
            break
        drawn = bool(grid[row, column])
        if drawn and not before:
            found.append(float(distance))
        before = drawn
    return found


def face(grid, x, y, dx, dy):
    """The wall beside a flight, as inner and outer face. Treads run up to the wall, so a line within wall
    thickness of their ends is the wall's far side, and their ends are its near side."""
    lines = hits(grid, x, y, dx, dy)
    if not lines:
        return None, None
    if lines[0] <= WALL_MAX:
        return 0.0, lines[0]
    return lines[0], next((d for d in lines[1:] if d - lines[0] <= WALL_MAX + 0.15), None)


def enclosure(stair, grid):
    """The stair room around the flights: its inner faces and, where the wall's far side shows, its outer faces."""
    x0, y0, x1, y1 = stair['box']
    inner, outer = [x0, y0, x1, y1], [x0, y0, x1, y1]
    for index, (dx, dy, edge) in enumerate(((-1, 0, x0), (0, -1, y0), (1, 0, x1), (0, 1, y1))):
        hits = [face(grid, edge, y0 + (y1 - y0) * t, dx, dy) if dx else face(grid, x0 + (x1 - x0) * t, edge, dx, dy) for t in (0.2, 0.35, 0.5, 0.65, 0.8)]
        near = [h[0] for h in hits if h[0] is not None]
        far = [h[1] for h in hits if h[1] is not None]
        sign = -1 if index < 2 else 1
        inner[index] = edge + sign * median(near) if near else edge
        outer[index] = edge + sign * median(far) if far else inner[index]
    return inner, outer


def stair_doors(found, door_list, grid):
    """Leaf widths of the doors at each main stair: those hinged within reach of its room."""
    widths = []
    for stair in (s for s in found if s['main']):
        inner, _ = enclosure(stair, grid)
        widths += [d['width'] for d in door_list if apart(inner, [d['x'], d['y'], d['x'], d['y']]) <= 1.0]
    return widths


def separation(found, grid):
    """Between the two main stairs furthest apart: the distance between stair rooms, taken both ways."""
    main = [s for s in found if s['main']]
    if len(main) < 2:
        return None
    rooms = [enclosure(s, grid) for s in main]
    pairs = [(apart(rooms[i][0], rooms[j][0]), apart(rooms[i][1], rooms[j][1]), i, j) for i in range(len(main)) for j in range(i + 1, len(main))]
    inner, outer, i, j = max(pairs)
    return dict(inner=round(inner, 2), outer=round(outer, 2), box=[round(v, 2) for v in (min(rooms[i][0][0], rooms[j][0][0]), min(rooms[i][0][1], rooms[j][0][1]),
                                                                                        max(rooms[i][0][2], rooms[j][0][2]), max(rooms[i][0][3], rooms[j][0][3]))])


def walk(mask, starts):
    """Steps from `starts` to every cell of `mask`, in metres."""
    distance = np.full(mask.shape, np.inf)
    queue = deque()
    for start in starts:
        distance[start] = 0
        queue.append(start)
    while queue:
        row, column = queue.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            r, c = row + dr, column + dc
            if 0 <= r < mask.shape[0] and 0 <= c < mask.shape[1] and mask[r, c] and distance[r, c] == np.inf:
                distance[r, c] = distance[row, column] + CELL
                queue.append((r, c))
    return distance


def nearest_cell(mask, box):
    rows, columns = np.nonzero(mask)
    cx, cy = (box[0] + box[2]) / 2 / CELL, (box[1] + box[3]) / 2 / CELL
    index = int(np.argmin((columns - cx) ** 2 + (rows - cy) ** 2))
    return int(rows[index]), int(columns[index])


def dead_end(core, found):
    """The longest stretch of corridor beyond the route between the stairs: from there, only one way leads out."""
    main = [s for s in found if s['main']]
    if len(main) < 2:
        return None
    a, b = nearest_cell(core, main[0]['box']), nearest_cell(core, main[1]['box'])
    from_a, from_b = walk(core, [a]), walk(core, [b])
    if not np.isfinite(from_a[b]):
        return None
    route = np.argwhere(from_a + from_b <= from_a[b] + 2 * CELL)
    beyond = walk(core, [tuple(int(v) for v in cell) for cell in route])
    return round(float(beyond[np.isfinite(beyond)].max()), 1)


def corridor(grid, found, door_list):
    """The open space most doors open onto, if it has the shape of a corridor. Spaces wider than a door are
    separated by closing the map's openings of door width; whatever reaches the sheet edge is outdoors."""
    clearance = ndimage.distance_transform_edt(~grid) * CELL
    labels, _ = ndimage.label(clearance >= OPEN_RADIUS)
    edges = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])))
    reach = int(1.2 / CELL)     # a door hinged on the far wall of a corridor is this far from its middle
    counts = Counter()
    for door in door_list:
        row, column = int(door['y'] / CELL), int(door['x'] / CELL)
        counts.update(int(v) for v in np.unique(labels[max(row - reach, 0):row + reach, max(column - reach, 0):column + reach]) if v and v not in edges)
    if not counts or counts.most_common(1)[0][1] < MIN_CORRIDOR_DOORS:
        return None
    core = labels == counts.most_common(1)[0][0]
    # The middle line of the space, and twice the distance from it to the walls is the width at each point.
    spread = np.where(core, clearance, 0)
    middle = (spread >= ndimage.maximum_filter(spread, size=5) - 1e-9) & core
    widths = 2 * clearance[middle]
    if not len(widths) or np.median(widths) > CORRIDOR_MAX_WIDTH:
        return None
    rows, columns = np.nonzero(core)
    return dict(width=round(float(np.percentile(widths, 15)), 2), narrowest=round(float(np.percentile(widths, 3)), 2), dead_end=dead_end(core, found),
                box=[round(v * CELL, 2) for v in (int(columns.min()), int(rows.min()), int(columns.max()), int(rows.max()))])


def sheet(geometry, frame):
    """What one sheet shows. Boxes are in metres from the frame's lower left corner."""
    lines, arcs, texts = window(geometry, frame)
    x0, y0, x1, y1 = frame['box']
    size = [(x1 - x0) * geometry.unit, (y1 - y0) * geometry.unit]
    found = stairs(lines, texts)
    door_list = doors(lines, arcs)
    result = dict(size=[round(v, 2) for v in size], stairs=found, doors=len(door_list), stair_doors=[], level=level(texts), separation=None, corridor=None,
                  units=sum(bool(UNIT_LABEL.search(text)) for _, _, text in texts), **devices(geometry, frame))
    if max(size) <= PLAN_MAX:
        grid = wall_map(lines, fills(geometry, frame), size)
        result.update(separation=separation(found, grid), corridor=corridor(grid, found, door_list), stair_doors=stair_doors(found, door_list, grid))
    if lines:
        xs = sorted(v for line in lines for v in (line[0], line[2]))
        ys = sorted(v for line in lines for v in (line[1], line[3]))
        trim = len(xs) // 100      # the plan, without grid bubbles and stray marks
        result['plan'] = [round(v, 2) for v in (xs[trim], ys[trim], xs[-trim - 1], ys[-trim - 1])]
    return result


# ---------- The building, from all its sheets ----------

FLOOR_WORD = re.compile(r'(?<![\d.])(?:(\d{1,3})\s*-\s*)?(-?\d{1,3})\s*(?:სართ|fl(?:oo)?r|level|этаж)', re.I)
FLOOR_LABEL = re.compile(r'\s*(-?\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*')
HIGH_RISE_M = 23
SEPARATION_M = 9.0
SEPARATION_MARGIN = 0.5         # the wall map can be this far out, so a closer result is not a pass
DEAD_END_M, DEAD_END_SPRINKLERED_M = 6.0, 15.0


def floors_of(label, file_name):
    """Which storeys a sheet shows, from its layout name or else the file name: `3-4` is storeys 3 and 4."""
    match = FLOOR_LABEL.fullmatch(label or '')
    if match:
        first, last = int(match[1]), int(match[2] or match[1])
    else:
        match = FLOOR_WORD.search(file_name)
        if not match:
            return []
        last = int(match[2])
        first = int(match[1]) if match[1] else last
    # File names repeat the number (`10-10`) or give the level below (`0--1`).
    return list(range(first, last + 1)) if last >= first else [last]


def place(sheet_record, box):
    """A box in metres as page and page fractions, the way findings point at things."""
    width, height = sheet_record['measured']['size']
    return dict(page=sheet_record['page'], box=[round(v, 4) for v in (box[0] / width, 1 - box[3] / height, box[2] / width, 1 - box[1] / height)])


def floor_row(group):
    """One storey, or a group of identical storeys, combined from every sheet that shows it. Stairs come from the
    sheet that shows most of them. Pipes and ducts can only narrow a corridor on the map, so the widest reading counts."""
    rich = max(group, key=lambda s: (len([x for x in s['measured']['stairs'] if x['main']]), s['discipline'] == 'architecture', s['discipline'] == 'fire'))
    main = [x for x in rich['measured']['stairs'] if x['main']]
    corridors = [s for s in group if s['measured']['corridor']]
    wide = max(corridors, key=lambda s: s['measured']['corridor']['width'], default=None)
    fire = [s for s in group if s['discipline'] == 'fire'] or group
    apart_at = next((s for s in sorted(group, key=lambda s: s is not rich) if s['measured']['separation']), None)
    row = dict(floors=group[0]['floors'], name=group[0]['floor_name'], page=rich['page'], level=next((s['measured']['level'] for s in group if s['measured']['level'] is not None), None),
               stairs=len(main), units=max(s['measured']['units'] for s in group),
               stair_width=min((x['width'] for x in main), default=None), tread=min((x['tread'] for x in main), default=None),
               riser=max((x['riser'] for x in main if x['riser']), default=None), stair_doors=min((w for s in group for w in s['measured']['stair_doors']), default=None),
               sprinklers=max(s['measured']['sprinklers'] for s in fire), cabinets=max(s['measured']['cabinets'] for s in fire), landing_valves=max(s['measured']['landing_valves'] for s in fire),
               marks={})
    if main:
        row['marks']['stairs'] = place(rich, main[0]['box'])
    if apart_at:
        found = apart_at['measured']['separation']
        row.update(separation_inner=found['inner'], separation_outer=found['outer'])
        row['marks']['separation'] = place(apart_at, found['box'])
    if wide:
        found = wide['measured']['corridor']
        row.update(corridor=found['width'], narrowest=found['narrowest'], dead_end=found['dead_end'])
        row['marks']['corridor'] = place(wide, found['box'])
    plan = rich['measured'].get('plan')
    row['diagonal'] = round(math.hypot(plan[2] - plan[0], plan[3] - plan[1]), 1) if plan else None
    return row


def building(sheets):
    """The floor-by-floor table. Sheets with no storey in their name join the storey with the same level mark."""
    levels = {s['measured']['level']: tuple(s['floors']) for s in sheets if s['floors'] and s['measured']['level'] is not None}
    groups = defaultdict(list)
    for record in sheets:
        floors = tuple(record['floors']) or levels.get(record['measured']['level'])
        if not floors or not (record['measured']['stairs'] or record['measured']['corridor'] or any(record['measured'][k] for k in DEVICES)):
            continue
        name = str(floors[0]) if len(floors) == 1 else f'{floors[0]}–{floors[-1]}'
        groups[floors].append(dict(record, floors=list(floors), floor_name=name))
    rows = [floor_row(group) for _, group in sorted(groups.items(), key=lambda item: item[0][0])]
    marks = [r['level'] for r in rows if r['level'] is not None]
    return dict(floors=rows, top_level=max(marks, default=None), storeys=len({floor for r in rows for floor in r['floors'] if floor > 0}))


def worst(rows, key, pick=min):
    """The row with the lowest (or highest) value of `key`, among those that have one."""
    known = [r for r in rows if r.get(key) is not None]
    return pick(known, key=lambda r: r[key]) if known else None


def result(rule, status, found, ka, en, row=None, mark=None, fix_ka='', fix_en=''):
    place_at = (row or {}).get('marks', {}).get(mark) or {}
    return dict(rule_id=rule, status=status, found=found, explanation_ka=ka, explanation_en=en, fix_ka=fix_ka, fix_en=fix_en,
                page=place_at.get('page') or (row or {}).get('page'), anchors=[], box=place_at.get('box'), measured=True)


def names(rows):
    return ', '.join(r['name'] for r in rows)


def stair_checks(rows):
    with_stairs = [r for r in rows if r['stairs']]
    if not with_stairs:
        return []
    found = []
    narrow = worst(with_stairs, 'stair_width')
    width = narrow['stair_width']
    found.append(result('1009.4', 'pass' if width >= 1.1 else 'fail', f'{width:.2f} მ',
                        f'კიბის მარშის სიგანე CAD ფაილიდან გაიზომა {len(with_stairs)} დონეზე. ყველაზე ვიწროა {width:.2f} მ ({narrow["name"]} დონე).',
                        f'Flight width was measured from the CAD file on {len(with_stairs)} levels. The narrowest is {width:.2f} m (level {narrow["name"]}).', narrow, 'stairs',
                        '' if width >= 1.1 else 'გააფართოვეთ კიბე 1,1 მ-მდე.', '' if width >= 1.1 else 'Widen the stair to 1.1 m.'))
    shallow, tall = worst(with_stairs, 'tread'), worst(with_stairs, 'riser', max)
    tread, riser = shallow['tread'], tall['riser'] if tall else None
    bad = tread < 0.28 - 0.002 or (riser is not None and not 0.10 <= riser <= 0.18)
    status = 'fail' if bad else 'pass' if riser else 'verify'
    label = f'{riser * 100:.0f} × {tread * 100:.0f} სმ' if riser else f'საბიჯელი {tread * 100:.0f} სმ'
    found.append(result('1009.7.2', status, label,
                        f'საბიჯელი გაიზომა ნახაზიდან: {tread * 100:.0f} სმ.' + (f' საფეხურის სიმაღლე წარწერიდან: {riser * 100:.0f} სმ.' if riser else ' საფეხურის სიმაღლის წარწერა ვერ მოიძებნა.'),
                        f'The tread was measured from the drawing: {tread * 100:.0f} cm.' + (f' The riser is from the label: {riser * 100:.0f} cm.' if riser else ' No riser label was found.'), shallow, 'stairs'))
    few = [r for r in rows if r['stairs'] < 2]
    if few:
        found.append(result('1021.2', 'verify', f'დონეები {names(few)}', f'ამ დონეებზე ორი კიბე ვერ მოიძებნა: {names(few)}. შესაძლოა კიბე სხვანაირადაა დახაზული, ან დონე სახურავი ან ტექნიკურია.',
                            f'Two stairs were not found on these levels: {names(few)}. A stair may be drawn differently, or the level may be a roof or technical level.', few[0], 'stairs',
                            'შეამოწმეთ ამ დონეებიდან გასასვლელები.', 'Check the exits from these levels.'))
    else:
        found.append(result('1021.2', 'pass', f'2 კიბე, {len(rows)} დონე', f'ორი ან მეტი კიბე მოიძებნა ყველა {len(rows)} გაზომილ დონეზე.', f'Two or more stairs were found on all {len(rows)} measured levels.', rows[0], 'stairs'))
    return found


def separation_check(rows, high_rise):
    known = [r for r in rows if r.get('separation_outer') is not None]
    if not known or high_rise is False:
        return []
    closest = worst(known, 'separation_outer')
    outer, inner = closest['separation_outer'], closest['separation_inner']
    diagonal = closest.get('diagonal')
    needed = min(SEPARATION_M, diagonal / 4) if diagonal else SEPARATION_M
    status = 'pass' if outer >= needed + SEPARATION_MARGIN else 'fail' if inner < needed else 'verify'
    return [result('403.5.1', status, f'{outer:.1f}–{inner:.1f} მ', f'კიბის უჯრედებს შორის გარე კედლებიდან {outer:.1f} მ-ია, შიდა სივრცეებს შორის {inner:.1f} მ. საჭიროა {needed:.1f} მ. უახლოესი მაჩვენებელი {closest["name"]} დონეზეა.',
                   f'The stair rooms are {outer:.1f} m apart between outer walls and {inner:.1f} m between interiors. {needed:.1f} m is needed. The closest reading is on level {closest["name"]}.', closest, 'separation',
                   '' if status == 'pass' else 'დააზუსტეთ გაზომვის წერტილები ექსპერტთან.', '' if status == 'pass' else 'Agree the measuring points with a specialist.')]


def corridor_checks(rows):
    known = [r for r in rows if r.get('corridor') is not None]
    if not known:
        return []
    tight = worst(known, 'narrowest')
    narrowest = tight['narrowest']
    status = 'pass' if narrowest >= 1.2 else 'verify'    # a duct or a column on the map can look like a narrow corridor, so this never fails by itself
    found = [result('1018.2', status, f'≈ {tight["corridor"]:.1f} მ', f'დერეფნის სიგანე შეფასდა {len(known)} დონეზე ნახაზის ხაზებიდან. ტიპური სიგანე დაახლოებით {tight["corridor"]:.1f} მ-ია, ყველაზე ვიწრო ადგილი {narrowest:.1f} მ.',
                    f'Corridor width was estimated from the drawing lines on {len(known)} levels. It is typically about {tight["corridor"]:.1f} m, and {narrowest:.1f} m at the narrowest point.', tight, 'corridor')]
    long_end = worst([r for r in known if r.get('dead_end') is not None], 'dead_end', max)
    if long_end:
        length = long_end['dead_end']
        status = 'pass' if length <= DEAD_END_M else 'fail' if length > DEAD_END_SPRINKLERED_M else 'verify'
        found.append(result('1018.4', status, f'≈ {length:.1f} მ', f'ყველაზე გრძელი ჩიხი შეფასებით დაახლოებით {length:.1f} მ-ია ({long_end["name"]} დონე). 6 მ-ზე მეტი დასაშვებია მხოლოდ გამონაკლისით.',
                            f'The longest dead end is estimated at about {length:.1f} m (level {long_end["name"]}). Over 6 m is only allowed under an exception.', long_end, 'corridor'))
    return found


def door_check(rows):
    narrow = worst(rows, 'stair_doors')
    if not narrow:
        return []
    width = narrow['stair_doors']
    status = 'pass' if width >= 0.87 else 'verify'
    return [result('1008.1.1', status, f'ფრთა {width:.2f} მ', f'კიბის კარების ყველაზე ვიწრო ფრთა {width:.2f} მ-ია ({narrow["name"]} დონე). თავისუფალი სიგანე ფრთაზე ოდნავ ნაკლებია, ასე რომ ეს შეფასებაა.',
                   f'The narrowest stair door leaf is {width:.2f} m (level {narrow["name"]}). Clear width is a little less than the leaf, so this is an estimate.', narrow, 'stairs')]


def checks(summary):
    """Rule results that follow from the measurements alone, in the shape of an AI review's checks."""
    rows = summary['floors']
    if not rows:
        return []
    top = summary['top_level']
    high_rise = top > HIGH_RISE_M if top is not None else None
    found = stair_checks(rows) + separation_check(rows, high_rise) + corridor_checks(rows) + door_check(rows)
    if top is not None:
        highest = worst(rows, 'level', max)
        found.append(result('202', 'pass', f'+{top:.2f} მ', f'ყველაზე მაღალი ნიშნული ნახაზზე +{top:.2f} მ-ია, ამიტომ შენობა {"მაღლივია" if high_rise else "მაღლივი არ არის"} (ზღვარი 23 მ).',
                            f'The highest level mark on the drawings is +{top:.2f} m, so the building is {"high-rise" if high_rise else "not high-rise"} (limit 23 m).', highest))
    return found
