import { useEffect, useRef, useState, type DragEvent } from "react";
import { recentReports, type ApiError, type EngineStatus, type Recent, type Verdict } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { DISCIPLINES, droppedFiles, guessDiscipline, isCad, isDrawing, ordered, projectName, type Discipline, type Staged } from "../lib/project";

export const CATEGORY_ICONS: Record<string, string> = {
  scope: "M5 20V6l7-3 7 3v14M5 20h14M9.5 9h1M13.5 9h1M9.5 13h1M13.5 13h1M10.5 20v-3h3v3",
  egress: "M4 21h4V4h9v17M13.5 12.5h.01M20 21h-3",
  fire_systems: "M12.6 3c.4 3-1 4.6-2.6 6.4-1.6 1.8-3.5 3.8-3.5 6.8a5.5 5.5 0 0 0 11 0c0-2.3-1-4-2.1-5.2.1 1.5-.5 2.6-1.5 3.1.4-3.4-.4-8-1.3-11.1z",
  fire_access: "M3 17h2l1.5-5h7L16 17h5M6.5 12V8h5v4M16 17V9l3 3M7 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
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
  fire_access: { ka: "სახანძრო მისასვლელი და ტერიტორია", en: "Fire access & site" },
  fire_resistance: { ka: "ცეცხლმედეგობა", en: "Fire resistance" },
  accessibility: { ka: "მისაწვდომობა", en: "Accessibility" },
  interior: { ka: "შიგა გარემო", en: "Interior environment" },
};

export const VERDICT_STATUS: Record<Verdict, string> = { fail: "fail", missing: "missing", verify: "verify", clear: "pass" };

type Props = {
  status: EngineStatus | null;
  error: ApiError | null;
  onError: (error: ApiError | null) => void;
  onProject: (name: string, staged: Staged[], details: boolean) => void;
  onSample: () => void;
  onOpen: (id: string) => void;
};

export default function Home({ status, error, onError, onProject, onSample, onOpen }: Props) {
  const { t, lang } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [recent, setRecent] = useState<Recent[]>([]);
  const [staged, setStaged] = useState<Staged[]>([]);
  const [name, setName] = useState<string | null>(null);
  const [details, setDetails] = useState(false);
  const other = lang === "ka" ? "en" : "ka";
  const counts = DISCIPLINES.map((d) => [d, staged.filter((s) => s.discipline === d).length] as const).filter(([, n]) => n);

  useEffect(() => {
    if (status) recentReports().then(setRecent, () => undefined);
  }, [status]);

  function add(found: { file: File; path: string }[]) {
    const drawings = found.filter((f) => isDrawing(f.file.name));
    if (!drawings.length) return onError({ code: "bad_file_type", detail: found[0]?.file.name });
    onError(null);
    setStaged((current) => {
      const known = new Set(current.map((s) => s.path));
      const fresh = drawings.filter((f) => !known.has(f.path)).map((f) => ({ ...f, discipline: guessDiscipline(f.path) }));
      return ordered([...current, ...fresh]);
    });
  }

  function choose(list: FileList | null | undefined) {
    if (list?.length) add([...list].map((file) => ({ file, path: file.webkitRelativePath || file.name })));
  }

  async function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    add(await droppedFiles(e.dataTransfer));
  }

  const setDiscipline = (path: string, discipline: Discipline) =>
    setStaged((current) => ordered(current.map((s) => (s.path === path ? { ...s, discipline } : s))));

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
            {t("dropHint")} · <span className="link">{t("chooseFile")}</span> ·{" "}
            <button
              type="button"
              className="link link-button-plain"
              onClick={(e) => {
                e.stopPropagation();
                folderInput.current?.click();
              }}
            >
              {t("chooseFolder")}
            </button>
          </span>
        </span>
      </div>
      <input
        ref={input}
        type="file"
        accept=".pdf,.dwg,.dxf"
        multiple
        hidden
        onChange={(e) => {
          choose(e.currentTarget.files);
          e.currentTarget.value = "";
        }}
      />
      <input
        ref={folderInput}
        type="file"
        hidden
        {...({ webkitdirectory: "" } as object)}
        onChange={(e) => {
          choose(e.currentTarget.files);
          e.currentTarget.value = "";
        }}
      />

      {staged.length > 0 && (
        <div className="staged">
          <div className="staged-head">
            <input
              className="staged-name"
              aria-label={t("projectName")}
              placeholder={t("projectName")}
              value={name ?? projectName(staged)}
              onChange={(e) => setName(e.target.value)}
            />
            <ul className="staged-counts">
              {counts.map(([discipline, count]) => (
                <li key={discipline}>
                  {t(`discipline_${discipline}`)} <span>{count}</span>
                </li>
              ))}
            </ul>
          </div>
          <ul className="staged-list">
            {staged.map((item) => (
              <li key={item.path}>
                <span className={`file-kind${isCad(item.file.name) ? " is-cad" : ""}`}>{item.file.name.split(".").pop()}</span>
                <span className="staged-file" title={item.path}>
                  {item.file.name}
                </span>
                <select
                  className="staged-select"
                  aria-label={t("disciplineLabel")}
                  value={item.discipline}
                  onChange={(e) => setDiscipline(item.path, e.target.value as Discipline)}
                >
                  {DISCIPLINES.map((d) => (
                    <option key={d} value={d}>
                      {t(`discipline_${d}`)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="staged-remove"
                  aria-label={t("removeFile")}
                  onClick={() => setStaged((current) => current.filter((s) => s.path !== item.path))}
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M4 4l8 8M12 4l-8 8" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
          {status && !status.ai && <p className="staged-note">{t(staged.some((s) => isCad(s.file.name)) ? "noAiCad" : "noAiPdf")}</p>}
          <div className="staged-actions">
            {status?.ai && (
              <label className="check-option" title={t("askDetailsHint")}>
                <input type="checkbox" checked={details} onChange={(e) => setDetails(e.currentTarget.checked)} />
                <span className="check-box" aria-hidden="true">
                  <svg viewBox="0 0 16 16">
                    <path d="M4 8.5l2.6 2.5L12 5.5" />
                  </svg>
                </span>
                <span className="check-text">
                  {t("askDetails")}
                  <span className="check-hint">{t("askDetailsHint")}</span>
                </span>
              </label>
            )}
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => {
                setStaged([]);
                setName(null);
              }}
            >
              {t("clearFiles")}
            </button>
            <button type="button" className="btn btn-primary" onClick={() => onProject((name ?? projectName(staged)).trim() || staged[0].file.name, staged, details)}>
              {t("startCheck", staged.length)}
            </button>
          </div>
        </div>
      )}

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
