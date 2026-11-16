import { invoke } from "@tauri-apps/api/core";
import type { Staged } from "./project";

/** "not_checked": no added drawing can show the clause, so it is left out of this check. */
export type Status = "fail" | "missing" | "verify" | "pass" | "not_applicable" | "not_checked";
export type Verdict = "fail" | "missing" | "verify" | "clear";
export type Stage = "reading" | "facts" | "asking" | "checking" | "writing" | "done" | "failed";
export type Lang = "ka" | "en";

export type Finding = {
  number: number;
  rule: string;
  category: string;
  /** The disciplines whose drawings show this clause; the first is the section it belongs to. */
  sections?: string[];
  title_ka: string;
  title_en: string;
  required_ka: string;
  required_en: string;
  quote: string;
  source: string;
  status: Status;
  found: string;
  found_ka?: string;
  found_en?: string;
  explanation_ka: string;
  explanation_en: string;
  fix_ka: string;
  fix_en: string;
  page: number | null;
  /** Fractions of the page: x0, y0, x1, y1 from the top left. */
  box: [number, number, number, number] | null;
  /** Worked out from the CAD geometry, with no AI. */
  measured?: boolean;
};

/** Which file a sheet came from, in a project of several files. */
export type Page = { number: number; width: number; height: number; file?: string; discipline?: string; label?: string };
export type Mark = { page: number; box: [number, number, number, number] | null };

/** One storey, or a group of identical ones, in metres. */
export type Floor = {
  name: string;
  floors: number[];
  page: number;
  level: number | null;
  stairs: number;
  units: number;
  stair_width: number | null;
  tread: number | null;
  riser: number | null;
  stair_doors: number | null;
  sprinklers: number;
  cabinets: number;
  landing_valves: number;
  separation_inner?: number;
  separation_outer?: number;
  corridor?: number;
  narrowest?: number;
  dead_end?: number | null;
  marks: { stairs?: Mark; separation?: Mark; corridor?: Mark };
};

/** A building fact the check depends on: asked in a form, or shown in the report with where it came from. */
export type Fact = {
  key: string;
  kind: "integer" | "number" | "choice" | "text";
  ka: string;
  en: string;
  hint_ka?: string;
  hint_en?: string;
  unit?: string | null;
  essential: boolean;
  options: { value: string; ka: string; en: string }[];
  suggestions: string[];
  /** A value the CAD measurements suggest; offered, never taken without the designer. */
  suggestion?: number | string;
  value?: number | string;
  where?: string;
  source?: "drawing" | "designer";
};
export type Answers = Record<string, string>;

export type ProjectFile = { name: string; discipline: string; sheets: number; error?: string; detail?: string };
export type Provider = "claude" | "vertex" | "gemini";
/** One discipline of the project and how its review went. */
export type Section = {
  key: string;
  ka: string;
  en: string;
  sheets: number;
  status: "done" | "failed" | "not_reviewed" | "no_drawings";
  error?: string | null;
};
export type Counts = Record<Status, number>;

export type Report = {
  id: string;
  name: string;
  created: string;
  demo: boolean;
  /** Who wrote the review, when it did not come from the app's AI. */
  reviewer?: string;
  /** False when the report comes from measuring alone. */
  ai_used?: boolean;
  /** Why the AI could not take part, when the measurements stand without it. */
  ai_error?: string | null;
  /** Which AI reviewed the drawings. */
  ai_provider?: Provider | null;
  /** The project's disciplines, each reviewed on its own. Empty for a single drawing from before. */
  sections?: Section[];
  /** The building data the check used: found on the drawings or given by the designer. */
  facts?: Fact[];
  files?: ProjectFile[];
  measured?: { floors: Floor[]; top_level: number | null; storeys: number } | null;
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
  provider: Provider | null;
  keys: Record<Provider, boolean>;
  /** The Google Cloud project Gemini runs in on Vertex AI. */
  vertex: { project: string; location: string } | null;
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
export const saveKey = (key: string) => call<{ ok: boolean; provider: Provider }>("/api/key", json({ key }));
export const connectVertex = (project: string, location: string) => call<{ ok: boolean; provider: Provider }>("/api/vertex", json({ project, location }));
export const forgetKey = (provider?: Provider) => call(`/api/key${provider ? `?provider=${provider}` : ""}`, { method: "DELETE" });
export const recentReports = () => call<{ reports: Recent[] }>("/api/reports").then((b) => b.reports);
export const getReport = (id: string) => call<Report>(`/api/reports/${id}`);
export const startSample = () => call<{ id: string }>("/api/sample", { method: "POST" }).then((b) => b.id);
export const pageUrl = (id: string, page: number) => `${base}/api/reports/${id}/pages/${page}.png`;
export const chatHistory = (id: string) =>
  call<{ messages: { role: "user" | "assistant"; text: string }[] }>(`/api/reports/${id}/chat`).then((b) => b.messages);

/** Creates a project and sends its files one at a time, so each can be large. */
export async function uploadProject(name: string, staged: Staged[], onFile: (done: number) => void): Promise<string> {
  const { id } = await call<{ id: string }>("/api/reports", json({ name }));
  for (const [index, item] of staged.entries()) {
    const body = new FormData();
    body.append("file", item.file);
    body.append("discipline", item.discipline);
    await call(`/api/reports/${id}/files`, { method: "POST", body });
    onFile(index + 1);
  }
  return id;
}

type CheckState = { stage: Stage; error?: string; detail?: string; done?: number | null; total?: number; questions?: Fact[]; found?: Fact[] };

/** Starts a check and reports each stage until it finishes. When the check asks for building data,
 * `onAsk` shows the questions and resolves with the answers, or null to go on without them. */
export async function runCheck(
  id: string,
  onStage: (stage: Stage, done?: number | null, total?: number) => void,
  onAsk: (questions: Fact[], found: Fact[]) => Promise<Answers | null>,
  details = false,
): Promise<void> {
  await call(`/api/reports/${id}/check`, json({ details }));
  for (;;) {
    const state = await call<CheckState>(`/api/reports/${id}/stage`);
    onStage(state.stage, state.done, state.total);
    if (state.stage === "asking" && state.questions) {
      const answers = await onAsk(state.questions, state.found ?? []);
      await call(`/api/reports/${id}/facts`, json(answers ? { answers } : { skip: true }));
      continue;
    }
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
