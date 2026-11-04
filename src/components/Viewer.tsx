import { useEffect, useRef, useState } from "react";
import { pageUrl, type Finding, type Report } from "../lib/api";
import { useI18n } from "../lib/i18n";

const ZOOMS = [1, 1.5, 2, 3];

type Props = {
  report: Report;
  /** Findings to mark on the sheets. */
  findings: Finding[];
  selected: Finding | null;
  onSelect: (finding: Finding) => void;
};

/** The drawing itself, with a numbered pin on each finding that has a place on the sheet. */
export default function Viewer({ report, findings, selected, onSelect }: Props) {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(0);
  const canvas = useRef<HTMLDivElement>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const size = report.pages[page - 1];
  const marks = findings.filter((f) => f.page === page && f.box);

  // Go to the selected finding: its sheet, closer in, with the mark centred.
  useEffect(() => {
    if (!selected?.page) return;
    setPage(selected.page);
    if (selected.box) setZoom((z) => Math.max(z, 1));
  }, [selected]);

  useEffect(() => {
    if (!selected?.box || selected.page !== page) return;
    const id = setTimeout(() => {
      const view = canvas.current;
      const paper = sheet.current;
      if (!view || !paper || !selected.box) return;
      const [x0, y0, x1, y1] = selected.box;
      view.scrollTo({
        left: paper.offsetLeft + ((x0 + x1) / 2) * paper.offsetWidth - view.clientWidth / 2,
        top: paper.offsetTop + ((y0 + y1) / 2) * paper.offsetHeight - view.clientHeight / 2,
        behavior: "smooth",
      });
    }, 380);
    return () => clearTimeout(id);
  }, [selected, page, zoom]);

  return (
    <div className="viewer">
      <div className="viewer-bar">
        <div className="viewer-group">
          <button type="button" className="viewer-button" aria-label={t("previous")} disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10 3L5 8l5 5" />
            </svg>
          </button>
          <span className="viewer-page-label">
            {t("pageTitle")} {t("page", page, report.pages.length)}
          </span>
          <button
            type="button"
            className="viewer-button"
            aria-label={t("next")}
            disabled={page >= report.pages.length}
            onClick={() => setPage(page + 1)}
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M6 3l5 5-5 5" />
            </svg>
          </button>
        </div>
        <span>{t("sheetNote", marks.length)}</span>
        <div className="viewer-group">
          <button type="button" className="viewer-button" aria-label={t("zoomOut")} disabled={zoom === 0} onClick={() => setZoom(zoom - 1)}>
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3.5 8h9" />
            </svg>
          </button>
          <button type="button" className="viewer-button" onClick={() => setZoom(0)}>
            {t("fit")}
          </button>
          <button
            type="button"
            className="viewer-button"
            aria-label={t("zoomIn")}
            disabled={zoom === ZOOMS.length - 1}
            onClick={() => setZoom(zoom + 1)}
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3.5 8h9M8 3.5v9" />
            </svg>
          </button>
        </div>
      </div>
      <div className="viewer-canvas" ref={canvas}>
        <div
          className="viewer-sheet"
          ref={sheet}
          style={{ width: `${ZOOMS[zoom] * 100}%`, aspectRatio: `${size.width} / ${size.height}` }}
        >
          <img src={pageUrl(report.id, page)} alt={`${t("pageTitle")} ${page}`} draggable={false} />
          {selected?.box && selected.page === page && (
            <div
              key={selected.number}
              className={`mark-box status-${selected.status}`}
              style={{
                left: `${selected.box[0] * 100 - 0.4}%`,
                top: `${selected.box[1] * 100 - 0.5}%`,
                width: `${(selected.box[2] - selected.box[0]) * 100 + 0.8}%`,
                height: `${(selected.box[3] - selected.box[1]) * 100 + 1}%`,
              }}
            />
          )}
          {marks.map((f) => (
            <button
              key={f.number}
              type="button"
              className={`sheet-pin status-${f.status}${f === selected ? " is-selected" : ""}`}
              style={{ left: `${f.box![2] * 100}%`, top: `${f.box![1] * 100}%` }}
              title={f.rule}
              onClick={() => onSelect(f)}
            >
              {f.number}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
