import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { Finding, Report } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { VERDICT_STATUS } from "./Home";
import Viewer from "./Viewer";

const ATTENTION = ["fail", "missing", "verify"];

type Props = {
  report: Report;
  onReset: () => void;
  onAsk: (question: string) => void;
};

function Row({ finding, open, onOpen, onAsk }: { finding: Finding; open: boolean; onOpen: () => void; onAsk: () => void }) {
  const { t, lang } = useI18n();
  const ka = lang === "ka";
  const row = useRef<HTMLLIElement>(null);
  const explanation = ka ? finding.explanation_ka : finding.explanation_en;
  const fix = ka ? finding.fix_ka : finding.fix_en;

  useEffect(() => {
    if (open) row.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [open]);

  return (
    <li
      ref={row}
      className={`finding status-${finding.status}${open ? " is-selected" : ""}`}
      style={{ "--i": Math.min(finding.number, 16) } as CSSProperties}
    >
      <button type="button" className="finding-head" aria-expanded={open} onClick={onOpen}>
        <span className="pin-number">{finding.number}</span>
        <span>
          <span className="finding-title">{ka ? finding.title_ka : finding.title_en}</span>
          <span className="finding-line">
            <span className="status-pill">{t(`status_${finding.status}`)}</span>
            <span className="clause">{finding.rule}</span>
            {finding.found && <span className="finding-found">{finding.found}</span>}
          </span>
        </span>
      </button>
      {open && (
        <div className="finding-body">
          {explanation && (
            <p>
              <span className="finding-label">{t("why")}</span>
              {explanation}
            </p>
          )}
          <p>
            <span className="finding-label">{t("required")}</span>
            {ka ? finding.required_ka : finding.required_en}
          </p>
          {fix && (
            <p>
              <span className="finding-label">{t("fix")}</span>
              {fix}
            </p>
          )}
          <blockquote className="finding-quote" lang="ka">
            „{finding.quote}“
            <span className="finding-source">
              {t("regulationText")} · {finding.rule} · {finding.source === "2016" ? t("sourceBase") : t("sourceAmended", finding.source)}
            </span>
          </blockquote>
          <div className="finding-actions">
            <button type="button" className="link-button" onClick={onAsk}>
              {t("askAbout")}
            </button>
            {!finding.box && <span className="finding-note">{t("notOnDrawing")}</span>}
          </div>
        </div>
      )}
    </li>
  );
}

export default function ReportView({ report, onReset, onAsk }: Props) {
  const { t, lang } = useI18n();
  const ka = lang === "ka";
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState<Finding | null>(null);

  const shown = useMemo(
    () => report.findings.filter((f) => category === "all" || f.category === category),
    [report, category],
  );
  const attention = shown.filter((f) => ATTENTION.includes(f.status));
  const passed = shown.filter((f) => f.status === "pass");
  const notApplicable = shown.filter((f) => f.status === "not_applicable");
  const { counts, verdict } = report;

  const select = (f: Finding) => setSelected((current) => (current === f ? null : f));
  const row = (f: Finding) => (
    <Row
      key={f.number}
      finding={f}
      open={f === selected}
      onOpen={() => select(f)}
      onAsk={() => onAsk(t("askPrompt", f.rule))}
    />
  );

  return (
    <section className="report">
      <header className="report-top">
        <div className="report-heading">
          <h2 className={`report-verdict status-${VERDICT_STATUS[verdict]}`}>
            <svg className="verdict-mark" viewBox="0 0 16 16" aria-hidden="true">
              <path d={verdict === "clear" ? "M4 8.5l2.6 2.5L12 5.5" : "M8 4v5M8 12h.01"} />
            </svg>
            {verdict === "clear" ? t("verdict_clear") : t(`verdict_${verdict}`, counts[verdict])}
          </h2>
          <p className="report-file" title={report.name}>
            {report.building.name || report.name} · {ka ? report.building.summary_ka : report.building.summary_en}
          </p>
        </div>
        <dl className="tally">
          {(["fail", "missing", "verify", "pass"] as const).map((status) => (
            <div key={status} className={`tally-item status-${status}`}>
              <dt>{t(`status_${status}`)}</dt>
              <dd>{counts[status]}</dd>
            </div>
          ))}
        </dl>
        <div className="report-actions">
          <button type="button" className="btn btn-quiet" onClick={onReset}>
            {t("newCheck")}
          </button>
        </div>
      </header>

      {report.demo && (
        <div className="notice notice-warn" role="status">
          <p className="notice-title">{t("sample")}</p>
        </div>
      )}

      <div className="report-body">
        <div className="findings-pane">
          <div className="filter-row" role="group">
            <button type="button" className="filter" aria-pressed={category === "all"} onClick={() => setCategory("all")}>
              {t("allCategories")}
            </button>
            {report.categories.map((c) => {
              const open = report.findings.filter((f) => f.category === c.key && ATTENTION.includes(f.status)).length;
              return (
                <button
                  key={c.key}
                  type="button"
                  className={`filter tone-${c.key}`}
                  aria-pressed={category === c.key}
                  title={`${ka ? c.ka : c.en}`}
                  onClick={() => setCategory(c.key)}
                >
                  {t(`short_${c.key}`)}
                  <span className="filter-count">{open}</span>
                </button>
              );
            })}
          </div>
          <ul className="findings">
            {attention.length > 0 && <li className="findings-title">{t("needsAttention")}</li>}
            {attention.length === 0 && <li className="findings-title">{t("noFindings")}</li>}
            {attention.map(row)}
            {passed.length > 0 && <li className="findings-title">{t("passedGroup")}</li>}
            {passed.map(row)}
            {notApplicable.length > 0 && <li className="findings-title">{t("notApplicableGroup")}</li>}
            {notApplicable.map(row)}
          </ul>
          <p className="legal-note">{t("legalNote")}</p>
        </div>
        <Viewer report={report} findings={shown.filter((f) => ATTENTION.includes(f.status))} selected={selected} onSelect={select} />
      </div>
    </section>
  );
}

