import type { CSSProperties, ReactNode } from "react";
import { useI18n } from "../lib/i18n";

export type StepState = "pending" | "active" | "done";
export const STEPS = ["upload", "reading", "facts", "checking", "writing"] as const;
export type Step = (typeof STEPS)[number];

const LABELS: Record<Step, string> = { upload: "stageUpload", reading: "stageReading", facts: "stageFacts", checking: "stageChecking", writing: "stageWriting" };
const NOTES: Partial<Record<Step, string>> = { facts: "stageFactsNote", checking: "stageCheckingNote" };
const PINS = [
  [96, 74, 0.9, "fail"],
  [214, 120, 1.6, "missing"],
  [318, 66, 2.3, "fail"],
  [396, 142, 3, "verify"],
  [150, 150, 3.7, "pass"],
] as const;

/** A floor plan being read: a scan line sweeps it and marks appear where a check lands. */
function Scene() {
  return (
    <svg className="plan-scene" viewBox="0 0 480 210" aria-hidden="true">
      <path className="wall draw" pathLength={1} d="M14 16H466V194H14Z" />
      <path className="thin draw" pathLength={1} d="M14 96H200M240 96H466M14 114H466M130 16V96M330 16V96M120 114V194M240 114V194M360 114V194" />
      <path className="thin draw" pathLength={1} d="M200 16V96M240 16V96M204 28H236M204 40H236M204 52H236M204 64H236M204 76H236" />
      <rect className="scan" x={14} y={16} width={2} height={178} />
      {PINS.map(([x, y, delay, status]) => (
        <circle
          key={x}
          className={`pin status-${status}`}
          cx={x}
          cy={y}
          r={7}
          fill="var(--status)"
          stroke="var(--bg)"
          strokeWidth={2}
          style={{ "--d": delay } as CSSProperties}
        />
      ))}
    </svg>
  );
}

/** The steps of a check. `children` (the building data questions) take the place of the picture while they are open. */
export default function Progress({ fileName, current, note, children }: { fileName: string; current: Step; note: string; children?: ReactNode }) {
  const { t } = useI18n();
  const reached = STEPS.indexOf(current);
  return (
    <section className="analyzing">
      <header className="analyzing-head">
        <h2 className="analyzing-file" title={fileName}>
          {fileName}
        </h2>
      </header>
      {children ?? <Scene />}
      <ol className="steps">
        {STEPS.map((step, i) => (
          <li key={step} className={`is-${i < reached ? "done" : i === reached ? "active" : "pending"}`}>
            <span className="step-mark" aria-hidden="true">
              <svg viewBox="0 0 16 16">
                <path d="M4 8.5l2.6 2.5L12 5.5" pathLength={1} />
              </svg>
            </span>
            <span className="step-text">
              <span className="step-label">{t(LABELS[step])}</span>
              <span className="step-note">{i !== reached ? " " : note || (NOTES[step] ? t(NOTES[step]!) : " ")}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
