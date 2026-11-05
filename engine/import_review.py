"""Puts a review written by hand into a report, for testing the app without the AI.

    .venv/bin/python import_review.py <report folder> <review.json> [reviewer name]

`review.json` has the shape of ai.REVIEW_SCHEMA; a check's `anchors` come from pdf_tools.anchors.
The report opens in the app like any other and is labelled with who reviewed it.
"""
import json
from pathlib import Path
import sys

import pdf_tools
from report import assemble


def main(folder, review_path, reviewer='Claude'):
    folder = Path(folder)
    meta = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
    anchors = pdf_tools.anchors(folder / 'drawing.pdf')
    (folder / 'anchors.json').write_text(json.dumps(anchors, ensure_ascii=False), encoding='utf-8')
    review = json.loads(Path(review_path).read_text(encoding='utf-8'))
    report = dict(assemble(review, anchors, meta['pages'], meta.get('measured')), **meta, reviewer=reviewer)
    (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    print(report['verdict'], report['counts'])


if __name__ == '__main__':
    main(*sys.argv[1:])
