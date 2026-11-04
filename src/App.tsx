import { useCallback, useEffect, useMemo, useState } from "react";
import Splash from "./components/Splash";
import Home from "./components/Home";
import Progress, { type Step } from "./components/Progress";
import ReportView from "./components/ReportView";
import Assistant from "./components/Assistant";
import Settings from "./components/Settings";
import {
  getReport,
  getStatus,
  runCheck,
  startSample,
  uploadPdf,
  waitForEngine,
  type ApiError,
  type EngineStatus,
  type Lang,
  type Report,
} from "./lib/api";
import { I18n, storeLanguage, storedLanguage, translator } from "./lib/i18n";
import "./App.css";

type View = "home" | "progress" | "report";

const SAMPLE_NAME = "ნიმუში — საცხოვრებელი კორპუსი.pdf";

function App() {
  const [lang, setLang] = useState<Lang>(storedLanguage);
  const i18n = useMemo(() => translator(lang), [lang]);

  const [engine, setEngine] = useState<"starting" | "ready" | "failed">("starting");
  const [splash, setSplash] = useState<"showing" | "leaving" | "gone">("showing");
  const [status, setStatus] = useState<EngineStatus | null>(null);

  const [view, setView] = useState<View>("home");
  const [fileName, setFileName] = useState("");
  const [step, setStep] = useState<Step>("upload");
  const [error, setError] = useState<ApiError | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  const [assistant, setAssistant] = useState(false);
  const [question, setQuestion] = useState<{ text: string } | null>(null);
  const [settings, setSettings] = useState(false);

  const refreshStatus = useCallback(() => {
    getStatus().then(setStatus, () => undefined);
  }, []);

  useEffect(() => {
    waitForEngine().then(
      () => {
        setEngine("ready");
        refreshStatus();
      },
      () => setEngine("failed"),
    );
  }, [refreshStatus]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // Keep stray drops outside the drop zone from navigating the webview away.
  useEffect(() => {
    const block = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => {
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
    };
  }, []);

  const onSplashLeave = useCallback(() => setSplash("leaving"), []);
  const onSplashDone = useCallback(() => setSplash("gone"), []);

  function switchLanguage(next: Lang) {
    setLang(next);
    storeLanguage(next);
  }

  async function check(name: string, prepare: () => Promise<string>) {
    setError(null);
    setFileName(name);
    setStep("upload");
    setView("progress");
    try {
      const id = await prepare();
      await runCheck(id, (stage) => {
        if (stage === "reading" || stage === "checking" || stage === "writing") setStep(stage);
      });
      setReport(await getReport(id));
      setView("report");
      refreshStatus();
    } catch (e) {
      const err = e as ApiError;
      setError(err && err.code ? err : { code: "check_failed" });
      setView("home");
    }
  }

  async function open(id: string) {
    try {
      setReport(await getReport(id));
      setView("report");
    } catch (e) {
      setError(e as ApiError);
    }
  }

  function reset() {
    setReport(null);
    setError(null);
    setView("home");
  }

  function ask(text: string) {
    setAssistant(true);
    setQuestion({ text });
  }

  return (
    <I18n.Provider value={i18n}>
      <div className="app">
        <header className="titlebar" data-tauri-drag-region>
          <span className="wordmark" data-tauri-drag-region>
            NORMA
          </span>
          <div className="titlebar-tools">
            {splash === "gone" && (
              <>
                <button
                  type="button"
                  className={`titlebar-button${assistant ? " is-active" : ""}`}
                  onClick={() => setAssistant(!assistant)}
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M2.5 3.5h11v7.5H7l-3 2.5V11H2.5z" />
                  </svg>
                  {i18n.t("assistant")}
                </button>
                <button type="button" className="titlebar-button" onClick={() => setSettings(true)}>
                  {i18n.t("settings")}
                </button>
              </>
            )}
            <div className="segmented" role="radiogroup" aria-label={i18n.t("language")}>
              {(["ka", "en"] as const).map((l) => (
                <button key={l} type="button" role="radio" aria-checked={lang === l} onClick={() => switchLanguage(l)}>
                  {l === "ka" ? "ქარ" : "ENG"}
                </button>
              ))}
            </div>
          </div>
        </header>

        {splash !== "showing" && (
          <main className={`stage${view === "report" ? " is-report" : ""}`} key={view}>
            {view === "home" && (
              <div className="stack">
                {engine === "failed" && (
                  <div className="notice notice-warn" role="alert">
                    <p className="notice-title">{i18n.t("engineFailed")}</p>
                    <p className="notice-detail">{i18n.t("engineFailedDetail")}</p>
                  </div>
                )}
                <Home
                  status={status}
                  error={error}
                  onError={setError}
                  onFile={(file) => check(file.name, () => uploadPdf(file))}
                  onSample={() => check(SAMPLE_NAME, startSample)}
                  onOpen={open}
                />
              </div>
            )}
            {view === "progress" && <Progress fileName={fileName} current={step} />}
            {view === "report" && report && <ReportView report={report} onReset={reset} onAsk={ask} />}
          </main>
        )}

        {assistant && (
          <Assistant
            report={view === "report" ? report : null}
            connected={Boolean(status?.ai)}
            question={question}
            onQuestionTaken={() => setQuestion(null)}
            onClose={() => setAssistant(false)}
            onConnect={() => setSettings(true)}
          />
        )}
        {settings && <Settings status={status} onChanged={refreshStatus} onClose={() => setSettings(false)} />}
        {splash !== "gone" && <Splash ready={engine !== "starting"} onLeave={onSplashLeave} onDone={onSplashDone} />}
      </div>
    </I18n.Provider>
  );
}

export default App;
