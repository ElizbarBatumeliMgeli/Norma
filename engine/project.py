"""A project: the files of one building, read into one drawing set.

Each DWG or DXF is read in its own process, several at a time. The result is the same as for a single PDF:
drawing.pdf with every sheet, the text items, and page records that say which file a sheet came from.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pymupdf

import measure
import pdf_tools

DISCIPLINES = ('architecture', 'structure', 'fire', 'plumbing', 'hvac', 'electrical', 'elv', 'other')
CAD_TYPES = ('.dwg', '.dxf')
ALLOWED_TYPES = ('.pdf', *CAD_TYPES)
FILE_LIMIT_SECONDS = 300
WORKERS = max(2, min(6, (os.cpu_count() or 4) - 2))


def natural(text):
    """Sort key that puts floor 2 before floor 10."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]


def read_cad(path, folder):
    """Runs one file through the CAD worker: the sheets, or the reason it could not be read."""
    worker = Path(__file__).parent / 'cad.py'
    try:
        done = subprocess.run([sys.executable, str(worker), str(path), str(folder)], capture_output=True, text=True, errors='replace', timeout=FILE_LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        return dict(error='cad_too_slow')
    if done.returncode == 0:
        return json.loads((folder / 'sheets.json').read_text(encoding='utf-8'))
    # The worker's last line says what went wrong; drawing libraries print their own notes before it.
    for line in reversed(done.stdout.strip().splitlines()):
        if line.startswith('{'):
            return json.loads(line)
    return dict(error='unreadable_cad', detail=done.stderr.strip()[-300:])


def build(target, meta, progress):
    """Reads every file. Returns the page records, the text items, the measurements and a line per file."""
    files = sorted(meta['files'], key=lambda f: (DISCIPLINES.index(f['discipline']), natural(f['name'])))
    work = target / 'work'
    finished = [0]

    def read_one(item):
        source = target / 'sources' / item['stored']
        result = read_cad(source, work / item['stored']) if source.suffix.lower() in CAD_TYPES else None
        finished[0] += 1
        progress(finished[0], len(files))
        return item['stored'], result

    with ThreadPoolExecutor(WORKERS) as pool:
        read = dict(pool.map(read_one, files))

    output, pages, anchors, sheets, report = pymupdf.open(), [], [], [], []
    for item in files:
        source, result = target / 'sources' / item['stored'], read[item['stored']]
        line = dict(name=item['name'], discipline=item['discipline'], sheets=0)
        report.append(line)
        if result is not None and 'error' in result:
            line.update(error=result['error'], detail=result.get('detail', ''))
            continue
        first = len(pages)
        path = work / item['stored'] / 'sheets.pdf' if result is not None else source
        try:
            with pdf_tools.open_pdf(path) as document:
                output.insert_pdf(document)
                for index, page in enumerate(document):
                    sheet = result['sheets'][index] if result is not None else dict(label=str(index + 1) if document.page_count > 1 else '', scale=None)
                    pages.append(dict(number=len(pages) + 1, width=page.rect.width, height=page.rect.height, file=item['name'], discipline=item['discipline'], label=sheet['label'], scale=sheet['scale']))
        except pdf_tools.UnreadablePdf as error:
            line.update(error='unreadable_pdf', detail=str(error))
            continue
        line['sheets'] = len(pages) - first
        if result is None:
            anchors += [dict(a, page=a['page'] + first) for a in pdf_tools.anchors(path)]
            continue
        for index, sheet in enumerate(result['sheets']):
            number = first + index + 1
            anchors += [dict(a, page=number) for a in sheet['anchors']]
            sheets.append(dict(page=number, discipline=item['discipline'], measured=sheet['measured'], floors=measure.floors_of(sheet['label'], item['name'])))
    if not pages:
        output.close()
        return [], [], None, report
    output.save(target / 'drawing.pdf', garbage=3, deflate=True)
    output.close()
    for index, anchor in enumerate(anchors):
        anchor['id'] = index
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(target / 'sources', ignore_errors=True)
    return pages, anchors, measure.building(sheets) if sheets else None, report
