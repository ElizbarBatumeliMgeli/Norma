import { invoke } from "@tauri-apps/api/core";

export type Status = "fail" | "missing" | "verify" | "pass" | "not_applicable";
export type Verdict = "fail" | "missing" | "verify" | "clear";
export type Stage = "reading" | "checking" | "writing" | "done" | "failed";
export type Lang = "ka" | "en";

export type Finding = {
  number: number;
  rule: string;
  category: string;
  title_ka: string;
  title_en: string;
  required_ka: string;
  required_en: string;
  quote: string;
  source: string;
  status: Status;
  found: string;
  explanation_ka: string;
  explanation_en: string;
  fix_ka: string;
  fix_en: string;
  page: number | null;
  /** Fractions of the page: x0, y0, x1, y1 from the top left. */
  box: [number, number, number, number] | null;
};

export type Page = { number: number; width: number; height: number };
export type Counts = Record<Status, number>;

export type Report = {
  id: string;
  name: string;
  created: string;
  demo: boolean;
  pages: Page[];
  building: { name: string; occupancy: string; storeys: number | null; high_rise: boolean | null; summary_ka: string; summary_en: string };
  findings: Finding[];
  counts: Counts;
  verdict: Verdict;
  categories: { key: string; ka: string; en: string; chapters: string }[];
};

export type Recent = Pick<Report, "id" | "name" | "created" | "verdict" | "counts" | "demo">;
export type EngineStatus = {
  ai: boolean;
  rules: number;
  counts: Record<string, number>;
  amendments: number;
  latest: { number: number; date: string };
};
export type ApiError = { code: string; detail?: string };
export type ChatEvent = { type: "text"; text: string } | { type: "searching" } | { type: "error"; code: string } | { type: "done" };

const inTauri = "__TAURI_INTERNALS__" in window;
// In a plain browser (`npm run dev`), Vite proxies /api to a locally running engine/server.py.
let base = "";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Resolves once the Python engine answers, or rejects after `timeoutMs`. */
export async function waitForEngine(timeoutMs = 45000): Promise<void> {
  if (!inTauri) return;
  base = await invoke<string>("engine_url");
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${base}/api/health`)).ok) return;
    } catch {
      /* not listening yet */
    }
    await sleep(300);
  }
  throw new Error("engine_unavailable");
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, init);
  } catch {
    throw { code: "network" } satisfies ApiError;
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw { code: body?.error ?? "check_failed", detail: body?.detail } satisfies ApiError;
  return body;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getStatus = () => call<EngineStatus>("/api/status");
export const saveKey = (key: string) => call("/api/key", json({ key }));
export const forgetKey = () => call("/api/key", { method: "DELETE" });
export const recentReports = () => call<{ reports: Recent[] }>("/api/reports").then((b) => b.reports);
export const getReport = (id: string) => call<Report>(`/api/reports/${id}`);
export const startSample = () => call<{ id: string }>("/api/sample", { method: "POST" }).then((b) => b.id);
export const pageUrl = (id: string, page: number) => `${base}/api/reports/${id}/pages/${page}.png`;
export const chatHistory = (id: string) =>
  call<{ messages: { role: "user" | "assistant"; text: string }[] }>(`/api/reports/${id}/chat`).then((b) => b.messages);

export function uploadPdf(file: File): Promise<string> {
  const body = new FormData();
  body.append("file", file);
  return call<{ id: string }>("/api/reports", { method: "POST", body }).then((b) => b.id);
}

/** Starts a check and reports each stage until it finishes. */
export async function runCheck(id: string, onStage: (stage: Stage) => void): Promise<void> {
  await call(`/api/reports/${id}/check`, { method: "POST" });
  for (;;) {
    const state = await call<{ stage: Stage; error?: string; detail?: string }>(`/api/reports/${id}/stage`);
    onStage(state.stage);
    if (state.stage === "done") return;
    if (state.stage === "failed") throw { code: state.error ?? "check_failed", detail: state.detail } satisfies ApiError;
    await sleep(500);
  }
}

/** Sends a chat message and calls `onEvent` as the answer streams in. */
export async function sendChat(message: string, lang: Lang, report: string | null, onEvent: (event: ChatEvent) => void): Promise<void> {
  const response = await fetch(`${base}/api/chat`, json({ message, lang, report }));
  if (!response.ok || !response.body) throw { code: "ai_failed" } satisfies ApiError;
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const event of events) {
      if (event.startsWith("data: ")) onEvent(JSON.parse(event.slice(6)));
    }
  }
}
