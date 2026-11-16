import { useMemo, useState, type FormEvent } from "react";
import type { Answers, Fact } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Props = {
  questions: Fact[];
  found: Fact[];
  onAnswer: (answers: Answers | null) => void;
};

const NUMBER = /^\s*\d+([.,]\d+)?\s*$/;

/** A fact's value as text: the option's name for a choice, the number with its unit otherwise. */
export function factValue(fact: Fact, value: Fact["value"], lang: "ka" | "en", t: (key: string) => string) {
  if (value === undefined || value === null || value === "") return "";
  if (fact.kind === "choice") return fact.options.find((o) => o.value === value)?.[lang] ?? String(value);
  const text = String(value).replace(".", lang === "ka" ? "," : ".");
  return fact.unit ? `${text} ${t(`unit_${fact.unit}`)}` : text;
}

function Field({ fact, value, onChange }: { fact: Fact; value: string; onChange: (value: string) => void }) {
  const { t, lang } = useI18n();
  const ka = lang === "ka";
  const id = `fact-${fact.key}`;
  const hint = ka ? fact.hint_ka : fact.hint_en;
  const numeric = fact.kind === "integer" || fact.kind === "number";
  const invalid = numeric && value.trim() !== "" && !NUMBER.test(value);

  return (
    <div className={`ask-field${value ? " is-filled" : ""}`}>
      <label className="ask-label" htmlFor={id}>
        {ka ? fact.ka : fact.en}
      </label>
      {hint && <p className="ask-hint">{hint}</p>}

      {fact.kind === "choice" && (
        <div className="ask-choices" role="radiogroup" aria-label={ka ? fact.ka : fact.en} id={id}>
          {fact.options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={value === o.value}
              className="ask-choice"
              onClick={() => onChange(value === o.value ? "" : o.value)}
            >
              {ka ? o.ka : o.en}
            </button>
          ))}
        </div>
      )}

      {numeric && (
        <div className={`ask-number${invalid ? " is-invalid" : ""}`}>
          <input
            id={id}
            className="field-input"
            inputMode="decimal"
            autoComplete="off"
            placeholder="—"
            value={value}
            aria-invalid={invalid}
            onChange={(e) => onChange(e.currentTarget.value)}
          />
          {fact.unit && <span className="ask-unit">{t(`unit_${fact.unit}`)}</span>}
        </div>
      )}
      {invalid && <p className="ask-error">{t("askNotNumber")}</p>}

      {fact.kind === "text" && (
        <>
          <input
            id={id}
            className="field-input"
            autoComplete="off"
            spellCheck={false}
            placeholder="—"
            value={value}
            onChange={(e) => onChange(e.currentTarget.value)}
          />
          {fact.suggestions.length > 0 && (
            <div className="ask-suggestions">
              {fact.suggestions.slice(0, 8).map((s) => (
                <button key={s} type="button" className="ask-suggestion" aria-pressed={value === s} onClick={() => onChange(value === s ? "" : s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {fact.suggestion !== undefined && !value && (
        <button type="button" className="ask-measured" onClick={() => onChange(String(fact.suggestion))}>
          {t("askUseMeasured", factValue(fact, fact.suggestion, lang, t))}
        </button>
      )}
    </div>
  );
}

/** The building data the drawings did not give: a short form, prepared before the check goes on.
 * Anything left blank is skipped; Skip goes on without any of it. */
export default function Questions({ questions, found, onAnswer }: Props) {
  const { t, lang } = useI18n();
  const ka = lang === "ka";
  const [values, setValues] = useState<Answers>({});
  const [changing, setChanging] = useState<Fact[]>([]);
  const asked = useMemo(() => [...questions, ...changing], [questions, changing]);
  const filled = asked.filter((q) => (values[q.key] ?? "").trim()).length;
  const set = (key: string, value: string) => setValues((current) => ({ ...current, [key]: value }));

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const answers = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim()));
    onAnswer(Object.keys(answers).length ? answers : null);
  }

  function change(fact: Fact) {
    setChanging((current) => [...current, fact]);
    set(fact.key, String(fact.value ?? ""));
  }

  return (
    <form className="ask" onSubmit={submit}>
      <div className="ask-head">
        <span className="ask-badge" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M5 21V7l7-4 7 4v14M5 21h14M9 21v-4h6v4" />
            <path d="M10.2 9.6a1.9 1.9 0 1 1 2.7 1.7c-.6.3-.9.7-.9 1.3M12 14.6h.01" />
          </svg>
        </span>
        <div>
          <h2 className="ask-title">{t("askTitle")}</h2>
          <p className="ask-intro">{t("askIntro")}</p>
        </div>
      </div>

      <div className="ask-fields">
        {asked.map((fact) => (
          <Field key={fact.key} fact={fact} value={values[fact.key] ?? ""} onChange={(v) => set(fact.key, v)} />
        ))}
      </div>

      {found.length > 0 && (
        <div className="ask-found">
          <h3 className="ask-found-title">{t("askFoundTitle")}</h3>
          <ul>
            {found
              .filter((f) => !changing.some((c) => c.key === f.key))
              .map((f) => (
                <li key={f.key}>
                  <span className="ask-found-label">{ka ? f.ka : f.en}</span>
                  <span className="ask-found-value">{factValue(f, f.value, lang, t)}</span>
                  {f.where && <span className="ask-found-where">{f.where}</span>}
                  <button type="button" className="link-button" onClick={() => change(f)}>
                    {t("askChange")}
                  </button>
                </li>
              ))}
          </ul>
        </div>
      )}

      <div className="ask-actions">
        <span className="ask-count">{t("askFilled", filled, asked.length)}</span>
        <button type="button" className="btn btn-quiet" onClick={() => onAnswer(null)}>
          {t("askSkip")}
        </button>
        <button type="submit" className="btn btn-primary">
          {t("askContinue")}
        </button>
      </div>
    </form>
  );
}
