import { useEffect, useState, type CSSProperties } from "react";
import { useI18n } from "../lib/i18n";

const TITLE = "NORMA";
// Branch drops along the main run, as x positions in the 240-wide viewBox.
const BRANCHES = [52, 100, 148, 196];
// Riser (48) + main run (224) — used to time each drop to when the run reaches it.
const RUN_LENGTH = 272;

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type Props = {
  /** The engine has answered (or given up); the splash may leave once its animation has played. */
  ready: boolean;
  /** Fired as the splash starts dissolving, so the app can rise in underneath it. */
  onLeave: () => void;
  onDone: () => void;
};

export default function Splash({ ready, onLeave, onDone }: Props) {
  const { t } = useI18n();
  const [played, setPlayed] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const leaving = played && ready;
  const scale = reducedMotion() ? 0.25 : 1;

  useEffect(() => {
    const id = setTimeout(() => setPlayed(true), 3000 * scale);
    return () => clearTimeout(id);
  }, [scale]);

  // Only mention the engine if it is still starting well after the animation finished.
  useEffect(() => {
    if (!played || ready) return;
    const id = setTimeout(() => setWaiting(true), 600);
    return () => clearTimeout(id);
  }, [played, ready]);

  useEffect(() => {
    if (!leaving) return;
    onLeave();
    const id = setTimeout(onDone, 700 * scale);
    return () => clearTimeout(id);
  }, [leaving, onLeave, onDone, scale]);

  return (
    <div className={`splash${leaving ? " is-leaving" : ""}`} aria-label="NORMA" role="status">
      <svg className="splash-route" viewBox="0 0 240 72" aria-hidden="true">
        <path className="route-main" d="M8 64 V16 H232" pathLength={1} />
        {BRANCHES.map((x, i) => {
          const delay = 0.25 + (1.1 * (48 + x - 8)) / RUN_LENGTH;
          return (
            <g key={x} style={{ "--d": `${delay}s` } as CSSProperties}>
              <path className="route-drop" d={`M${x} 16 V44`} pathLength={1} />
              <circle className="route-head" cx={x} cy={50} r={4.5} />
              <circle className="route-core" cx={x} cy={50} r={1.4} style={{ "--i": i } as CSSProperties} />
            </g>
          );
        })}
      </svg>

      <h1 className="splash-title">
        {TITLE.split("").map((ch, i) => (
          <span key={i} style={{ "--i": i } as CSSProperties}>
            {ch === " " ? " " : ch}
          </span>
        ))}
      </h1>
      <p className="splash-caption">{t("splashCaption")}</p>
      <p className={`splash-status${waiting && !ready ? " is-visible" : ""}`}>{t("engineStarting")}</p>
    </div>
  );
}
