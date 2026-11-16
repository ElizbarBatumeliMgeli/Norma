import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { Finding, Mark, Report } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { factValue } from "./Questions";
import { VERDICT_STATUS } from "./Home";
import Measurements from "./Measurements";
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
  const found = (ka ? finding.found_ka : finding.found_en) || finding.found;
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
            {found && <span className="finding-found">{found}</span>}
            {finding.measured && <span className="measured-tag">{t("measuredTag")}</span>}
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
  const [section, setSection] = useState("all");
  const [selected, setSelected] = useState<Finding | null>(null);
  const [focus, setFocus] = useState<Mark | null>(null);
  const [tab, setTab] = useState<"findings" | "floors">("findings");
  const [showNotChecked, setShowNotChecked] = useState(false);
  const floors = report.measured?.floors ?? [];
  const unread = report.files?.filter((f) => f.error) ?? [];
  // Only the sections whose drawings were added: checking fire drawings alone shows no low-voltage or HVAC filter.
  const added = (report.sections ?? []).filter((s) => s.sheets > 0);
  const sections = added.length > 1 ? added : [];
  const failedSections = added.filter((s) => s.status === "failed");
  const inSection = (f: Finding, key: string) => key === "all" || (f.sections ?? []).includes(key);

  const shown = useMemo(
    () => report.findings.filter((f) => inSection(f, section) && (category === "all" || f.category === category)),
    [report, category, section],
  );
  const attention = shown.filter((f) => ATTENTION.includes(f.status));
  const passed = shown.filter((f) => f.status === "pass");
  const notApplicable = shown.filter((f) => f.status === "not_applicable");
  const notChecked = shown.filter((f) => f.status === "not_checked");
  const facts = report.facts ?? [];
  const { counts, verdict } = report;

  const select = (f: Finding) => {
    setFocus(null);
    setSelected((current) => (current === f ? null : f));
  };
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
            {report.ai_provider && ` · ${t("aiLabel", t(`provider_${report.ai_provider}`))}`}
          </p>
          {facts.length > 0 && (
            <ul className="fact-chips" aria-label={t("factsLabel")}>
              {facts.map((f) => (
                <li
                  key={f.key}
                  className={f.source === "designer" ? "is-given" : undefined}
                  title={f.source === "designer" ? t("factGiven") : t("factFound", f.where ?? "")}
                >
                  <span className="fact-name">{ka ? f.ka : f.en}</span> {factValue(f, f.value, lang, t)}
                </li>
              ))}
            </ul>
          )}
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

      {report.reviewer && (
        <div className="notice notice-info" role="status">
          <p className="notice-title">{t("reviewedBy", report.reviewer)}</p>
        </div>
      )}

      {report.ai_used === false && !report.demo && !report.reviewer && (
        <div className="notice notice-info" role="status">
          <p className="notice-title">{t(report.ai_error ? "aiFailedMeasured" : "measuredOnly", report.counts.pass)}</p>
          {report.ai_error && <p className="notice-detail">{t(`error_${report.ai_error}`)}</p>}
        </div>
      )}

      {failedSections.length > 0 && (
        <div className="notice notice-warn" role="status">
          <p className="notice-title">{t("sectionsFailed", failedSections.map((s) => (ka ? s.ka : s.en)).join(", "))}</p>
          {failedSections[0].error && <p className="notice-detail">{t(`error_${failedSections[0].error}`)}</p>}
        </div>
      )}

      {unread.length > 0 && (
        <details className="notice notice-warn">
          <summary className="notice-title">{t("filesUnread", unread.length)}</summary>
          <ul className="notice-list">
            {unread.map((f) => (
              <li key={f.name}>
                {f.name}: {t(`error_${f.error}`) || t("error_check_failed")}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className={`report-body${tab === "floors" ? " is-wide" : ""}`}>
        <div className="findings-pane">
          {floors.length > 0 && (
            <div className="segmented report-tabs" role="radiogroup">
              {(["findings", "floors"] as const).map((key) => (
                <button key={key} type="button" role="radio" aria-checked={tab === key} onClick={() => setTab(key)}>
                  {t(key === "findings" ? "tabFindings" : "tabFloors")}
                </button>
              ))}
            </div>
          )}
          {tab === "floors" ? (
            <Measurements
              floors={floors}
              onFocus={(mark) => {
                setSelected(null);
                setFocus({ ...mark });
              }}
            />
          ) : (
            <>
          {sections.length > 0 && (
            <div className="filter-row section-filter" role="group" aria-label={t("sectionsLabel")}>
              <button type="button" className="filter" aria-pressed={section === "all"} onClick={() => setSection("all")}>
                {t("allSections")}
              </button>
              {sections.map((s) => {
                const open = report.findings.filter((f) => inSection(f, s.key) && ATTENTION.includes(f.status)).length;
                const note = s.status === "no_drawings" ? t("sectionNoDrawings") : s.status === "failed" ? t("sectionFailed") : t("sectionSheets", s.sheets);
                return (
                  <button
                    key={s.key}
                    type="button"
                    className={`filter tone-${s.key}${s.sheets ? "" : " is-empty"}`}
                    aria-pressed={section === s.key}
                    title={`${ka ? s.ka : s.en} · ${note}`}
                    onClick={() => setSection(s.key)}
                  >
                    {t(`discipline_${s.key}`)}
                    <span className="filter-count">{open}</span>
                  </button>
                );
              })}
            </div>
          )}
          <div className="filter-row" role="group">
            <button type="button" className="filter" aria-pressed={category === "all"} onClick={() => setCategory("all")}>
              {t("allCategories")}
            </button>
            {report.categories.map((c) => {
              const open = report.findings.filter((f) => inSection(f, section) && f.category === c.key && ATTENTION.includes(f.status)).length;
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
            {notChecked.length > 0 && (
              <li className="findings-title not-checked-title">
                <button type="button" className="not-checked-toggle" aria-expanded={showNotChecked} onClick={() => setShowNotChecked(!showNotChecked)}>
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M6 4l4 4-4 4" />
                  </svg>
                  {t("notCheckedGroup", notChecked.length)}
                </button>
                <span className="not-checked-hint">{t("notCheckedHint")}</span>
              </li>
            )}
            {showNotChecked && notChecked.map(row)}
          </ul>
          <p className="legal-note">{t("legalNote")}</p>
            </>
          )}
        </div>
        <Viewer report={report} findings={shown.filter((f) => ATTENTION.includes(f.status))} selected={selected} onSelect={select} focus={focus} />
      </div>
    </section>
  );
}

