import { useEffect, useMemo, useRef, useState } from "react";
import { pageUrl, type Finding, type Mark, type Page, type Report } from "../lib/api";
import { useI18n } from "../lib/i18n";

const ZOOMS = [1, 1.5, 2, 3];

type Props = {
  report: Report;
  /** Findings to mark on the sheets. */
  findings: Finding[];
  selected: Finding | null;
  onSelect: (finding: Finding) => void;
  /** A place to show that is not a finding, such as a measured value. */
  focus: Mark | null;
};

const sheetName = (page: Page) => [page.file?.replace(/\.[^.]+$/, ""), page.label].filter(Boolean).join(" · ");

/** Sheets by discipline, then by file. */
function grouped(pages: Page[]) {
  const groups = new Map<string, Page[]>();
  for (const page of pages) groups.set(page.discipline ?? "", [...(groups.get(page.discipline ?? "") ?? []), page]);
  return [...groups.entries()];
}

/** The drawing itself, with a numbered pin on each finding that has a place on the sheet. */
export default function Viewer({ report, findings, selected, onSelect, focus }: Props) {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(0);
  const canvas = useRef<HTMLDivElement>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const [picking, setPicking] = useState(false);
  const size = report.pages[page - 1];
  const marks = findings.filter((f) => f.page === page && f.box);
  const shown = focus ?? (selected?.page ? { page: selected.page, box: selected.box } : null);
  const groups = useMemo(() => grouped(report.pages), [report.pages]);
  const isProject = Boolean(size.file);

  // Go to what was selected: its sheet, closer in, with the mark centred.
  useEffect(() => {
    if (!shown) return;
    setPage(shown.page);
    if (shown.box) setZoom((z) => Math.max(z, 1));
  }, [selected, focus]);

  useEffect(() => {
    if (!shown?.box || shown.page !== page) return;
    const id = setTimeout(() => {
      const view = canvas.current;
      const paper = sheet.current;
      if (!view || !paper || !shown.box) return;
      const [x0, y0, x1, y1] = shown.box;
      view.scrollTo({
        left: paper.offsetLeft + ((x0 + x1) / 2) * paper.offsetWidth - view.clientWidth / 2,
        top: paper.offsetTop + ((y0 + y1) / 2) * paper.offsetHeight - view.clientHeight / 2,
        behavior: "smooth",
      });
    }, 380);
    return () => clearTimeout(id);
  }, [selected, focus, page, zoom]);

  return (
    <div className="viewer">
      <div className="viewer-bar">
        <div className="viewer-group">
          <button type="button" className="viewer-button" aria-label={t("previous")} disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10 3L5 8l5 5" />
            </svg>
          </button>
          {isProject ? (
            <button type="button" className="viewer-pick" aria-expanded={picking} title={sheetName(size)} onClick={() => setPicking(!picking)}>
              <span className="viewer-pick-name">{sheetName(size)}</span>
              <span className="viewer-pick-count">{t("page", page, report.pages.length)}</span>
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="M4 6l4 4 4-4" />
              </svg>
            </button>
          ) : (
            <span className="viewer-page-label">
              {t("pageTitle")} {t("page", page, report.pages.length)}
            </span>
          )}
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
        <span className="viewer-note">{t("sheetNote", marks.length)}</span>
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
      {picking && (
        <div className="sheet-list">
          {groups.map(([discipline, pages]) => (
            <section key={discipline}>
              <h3>
                {t(`discipline_${discipline}`)} <span>{pages.length}</span>
              </h3>
              <ul>
                {pages.map((item) => {
                  const count = findings.filter((f) => f.page === item.number && f.box).length;
                  return (
                    <li key={item.number}>
                      <button
                        type="button"
                        className={item.number === page ? "is-current" : undefined}
                        onClick={() => {
                          setPage(item.number);
                          setPicking(false);
                        }}
                      >
                        <span className="sheet-list-name">{sheetName(item)}</span>
                        {count > 0 && <span className="sheet-list-marks">{count}</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
      <div className="viewer-canvas" ref={canvas}>
        <div
          className="viewer-sheet"
          ref={sheet}
          style={{ width: `${ZOOMS[zoom] * 100}%`, aspectRatio: `${size.width} / ${size.height}` }}
        >
          <img src={pageUrl(report.id, page)} alt={`${t("pageTitle")} ${page}`} draggable={false} />
          {shown?.box && shown.page === page && (
            <div
              key={shown.box.join()}
              className={`mark-box status-${focus ? "verify" : selected?.status}`}
              style={{
                left: `${shown.box[0] * 100 - 0.4}%`,
                top: `${shown.box[1] * 100 - 0.5}%`,
                width: `${(shown.box[2] - shown.box[0]) * 100 + 0.8}%`,
                height: `${(shown.box[3] - shown.box[1]) * 100 + 1}%`,
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
