import { useEffect, useRef, useState, type DragEvent } from "react";
import { recentReports, type ApiError, type EngineStatus, type Recent, type Verdict } from "../lib/api";
import { useI18n } from "../lib/i18n";

export const CATEGORY_ICONS: Record<string, string> = {
  scope: "M5 20V6l7-3 7 3v14M5 20h14M9.5 9h1M13.5 9h1M9.5 13h1M13.5 13h1M10.5 20v-3h3v3",
  egress: "M4 21h4V4h9v17M13.5 12.5h.01M20 21h-3",
  fire_systems: "M12.6 3c.4 3-1 4.6-2.6 6.4-1.6 1.8-3.5 3.8-3.5 6.8a5.5 5.5 0 0 0 11 0c0-2.3-1-4-2.1-5.2.1 1.5-.5 2.6-1.5 3.1.4-3.4-.4-8-1.3-11.1z",
  fire_resistance: "M12 3l7 3v6c0 4.4-3 7.4-7 9-4-1.6-7-4.6-7-9V6zM9 12l2.2 2.2L15.5 10",
  accessibility: "M12 4.5h.01M6 8.5c4 1 8 1 12 0M12 9.5V14M12 14l-3 6M12 14l3 6",
  interior: "M4 4h16v16H4zM12 4v16M4 12h16",
};

export function CategoryIcon({ id }: { id: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={CATEGORY_ICONS[id]} />
    </svg>
  );
}

const CATEGORY_NAMES: Record<string, { ka: string; en: string }> = {
  scope: { ka: "დანიშნულება და სიმაღლე", en: "Use & height" },
  egress: { ka: "გასასვლელი საშუალებები", en: "Means of egress" },
  fire_systems: { ka: "სახანძრო სისტემები", en: "Fire protection systems" },
  fire_resistance: { ka: "ცეცხლმედეგობა", en: "Fire resistance" },
  accessibility: { ka: "მისაწვდომობა", en: "Accessibility" },
  interior: { ka: "შიგა გარემო", en: "Interior environment" },
};

export const VERDICT_STATUS: Record<Verdict, string> = { fail: "fail", missing: "missing", verify: "verify", clear: "pass" };

type Props = {
  status: EngineStatus | null;
  error: ApiError | null;
  onError: (error: ApiError | null) => void;
  onFile: (file: File) => void;
  onSample: () => void;
  onOpen: (id: string) => void;
};

export default function Home({ status, error, onError, onFile, onSample, onOpen }: Props) {
  const { t, lang } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [recent, setRecent] = useState<Recent[]>([]);
  const other = lang === "ka" ? "en" : "ka";

  useEffect(() => {
    if (status) recentReports().then(setRecent, () => undefined);
  }, [status]);

  function choose(list: FileList | null | undefined) {
    const file = list?.[0];
    if (!file) return;
    if (!/\.pdf$/i.test(file.name)) return onError({ code: "bad_file_type", detail: file.name });
    onError(null);
    onFile(file);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    choose(e.dataTransfer.files);
  }

  return (
    <section className="home">
      <header className="home-hero">
        <h1 className="home-title">
          {t("heroA")} <span>{t("heroB")}</span>
        </h1>
        <p className="home-lede">{t("subtitle")}</p>
      </header>

      <div className="section-head">
        <h2 className="section-label">{t("drawingHeader")}</h2>
        <p className="section-hint">{t("drawingFooter")}</p>
      </div>
      <div
        className={`dropzone${over ? " is-over" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <svg className="dropzone-glyph" viewBox="0 0 48 56" aria-hidden="true">
          <path d="M6 4h24l12 12v36H6z" />
          <path d="M30 4v12h12" />
          <path className="glyph-route" d="M14 42V30h20M20 30v6M28 30v6" pathLength={1} />
        </svg>
        <span className="dropzone-text">
          <span className="dropzone-primary">{t("dropTitle")}</span>
          <span className="dropzone-secondary">
            {t("dropHint")} · <span className="link">{t("chooseFile")}</span>
          </span>
        </span>
      </div>
      <input
        ref={input}
        type="file"
        accept=".pdf"
        hidden
        onChange={(e) => {
          choose(e.currentTarget.files);
          e.currentTarget.value = "";
        }}
      />

      {error && (
        <div className="notice notice-warn" role="alert">
          <p className="notice-title">{t(`error_${error.code}`) || t("error_check_failed")}</p>
          {error.detail && <p className="notice-detail">{error.detail}</p>}
        </div>
      )}

      <div className="home-actions">
        <button type="button" className="btn btn-quiet" onClick={onSample}>
          {t("trySample")}
        </button>
      </div>

      <div className="section-head" style={{ marginTop: 28 }}>
        <h2 className="section-label">{t("categoriesHeader")}</h2>
        {status && <p className="section-hint">{t("categoriesFooter", status.rules, status.amendments)}</p>}
      </div>
      <div className="categories">
        {Object.keys(CATEGORY_NAMES).map((id) => (
          <div key={id} className={`category tone-${id}`}>
            <span className="category-top">
              <span className="category-tile">
                <CategoryIcon id={id} />
              </span>
            </span>
            <span className="category-name">{CATEGORY_NAMES[id][lang]}</span>
            <span className="category-alt">{CATEGORY_NAMES[id][other]}</span>
            {status && <span className="category-count">{t("checks", status.counts[id] ?? 0)}</span>}
          </div>
        ))}
      </div>

      {recent.length > 0 && (
        <div className="recent">
          <div className="section-head">
            <h2 className="section-label">{t("recent")}</h2>
          </div>
          <ul className="recent-list">
            {recent.map((r) => (
              <li key={r.id}>
                <button type="button" className="recent-row" onClick={() => onOpen(r.id)}>
                  <span className="recent-name">{r.name}</span>
                  <span className={`status-pill status-${VERDICT_STATUS[r.verdict]}`}>
                    {r.verdict === "clear" ? t("verdict_clear") : t(`verdict_${r.verdict}`, r.counts[r.verdict as "fail"])}
                  </span>
                  <span className="recent-date">{r.created.slice(0, 10)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="home-note">{t("homeNote")}</p>
    </section>
  );
}
