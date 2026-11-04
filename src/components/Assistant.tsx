import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { chatHistory, sendChat, type ChatEvent, type Report } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Message = { role: "user" | "assistant" | "error"; text: string };

type Props = {
  report: Report | null;
  connected: boolean;
  /** A question to send as soon as the panel is ready. */
  question: { text: string } | null;
  onQuestionTaken: () => void;
  onClose: () => void;
  onConnect: () => void;
};

/** Renders **bold**, the only markdown the assistant's short answers need. */
function Text({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
      )}
    </>
  );
}

export default function Assistant({ report, connected, question, onQuestionTaken, onClose, onConnect }: Props) {
  const { t, lang } = useI18n();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [searching, setSearching] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const list = useRef<HTMLDivElement>(null);
  const reportId = report?.id ?? null;

  // The saved conversation loads first, so a question sent from the report lands after it.
  useEffect(() => {
    setMessages([]);
    setLoaded(false);
    const done = () => setLoaded(true);
    if (reportId) chatHistory(reportId).then(setMessages).then(done, done);
    else done();
  }, [reportId]);

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight });
  }, [messages, searching]);

  async function send(text: string) {
    const clean = text.trim();
    if (!clean || busy) return;
    setDraft("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: clean }, { role: "assistant", text: "" }]);
    const append = (more: string) =>
      setMessages((m) => [...m.slice(0, -1), { ...m[m.length - 1], text: m[m.length - 1].text + more }]);
    const fail = (code: string) =>
      setMessages((m) => [...m.filter((x, i) => i < m.length - 1 || x.text), { role: "error", text: t(`error_${code}`) || t("error_ai_failed") }]);
    const onEvent = (event: ChatEvent) => {
      if (event.type === "searching") setSearching(true);
      if (event.type === "text") {
        setSearching(false);
        append(event.text);
      }
      if (event.type === "error") fail(event.code);
    };
    try {
      await sendChat(clean, lang, reportId, onEvent);
    } catch {
      fail("ai_failed");
    }
    setSearching(false);
    setBusy(false);
  }

  useEffect(() => {
    if (question && loaded) {
      onQuestionTaken();
      send(question.text);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, loaded]);

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(draft);
    }
  }

  const suggestions = (report ? ["r1", "r2", "r3"] : ["q1", "q2", "q3"]).map((k) => t(k));

  return (
    <aside className="assistant" aria-label={t("assistant")}>
      <header className="assistant-head">
        <div style={{ minWidth: 0 }}>
          <p className="assistant-title">{t("assistant")}</p>
          <p className="assistant-context">{report ? report.name : t("general")}</p>
        </div>
        <button type="button" className="icon-button" aria-label={t("close")} onClick={onClose}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 7l10 10M17 7L7 17" />
          </svg>
        </button>
      </header>

      {!connected && (
        <div className="assistant-offline">
          {t("assistantOffline")}{" "}
          <button type="button" className="link-button" onClick={onConnect}>
            {t("connect")}
          </button>
        </div>
      )}

      <div className="messages" ref={list}>
        {messages.length === 0 && (
          <>
            <p className="assistant-hello">{t("assistantHello")}</p>
            <div className="suggestions">
              {suggestions.map((s) => (
                <button key={s} type="button" className="suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message is-${m.role}`}>
            {m.text ? (
              <Text text={m.text} />
            ) : (
              <span className="thinking-dots" aria-label={searching ? t("searching") : undefined}>
                {[0, 1, 2].map((d) => (
                  <span key={d} style={{ "--i": d } as React.CSSProperties} />
                ))}
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="composer">
        <textarea
          rows={1}
          value={draft}
          placeholder={t("composer")}
          onChange={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={onKey}
        />
        <button type="button" className="send" aria-label={t("send")} disabled={busy || !draft.trim()} onClick={() => send(draft)}>
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M8 13V3M3.5 7.5L8 3l4.5 4.5" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
