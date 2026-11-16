import { useState } from "react";
import { connectVertex, forgetKey, saveKey, type ApiError, type EngineStatus, type Provider } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Props = { status: EngineStatus | null; onChanged: () => void; onClose: () => void };

const KEYED: Provider[] = ["claude", "gemini"];
const PRIVACY: Record<Provider, string> = { claude: "privacyClaude", vertex: "privacyVertex", gemini: "privacy" };

export default function Settings({ status, onChanged, onClose }: Props) {
  const { t } = useI18n();
  const [key, setKey] = useState("");
  const [project, setProject] = useState(status?.vertex?.project ?? "");
  const [region, setRegion] = useState(status?.vertex?.location ?? "global");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    setBusy(true);
    try {
      await action();
      onChanged();
      return true;
    } catch (e) {
      setError(e as ApiError);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const save = () => run(() => saveKey(key.trim())).then((ok) => ok && setKey(""));
  const connect = () => run(() => connectVertex(project.trim(), region.trim() || "global"));
  const remove = (provider: Provider) => run(() => forgetKey(provider));

  const active = status?.provider ?? null;
  const vertex = status?.vertex ?? null;

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("settings")}>
        <h2>{t("settings")}</h2>
        <p className={`connection status-${active ? "pass" : "verify"}`}>
          {active ? t("connectedTo", t(`provider_${active}`)) : t("notConnected")}
        </p>

        <h3 className="settings-subhead">{t("vertexTitle")}</h3>
        <p>{vertex ? t("vertexConnected", vertex.project, vertex.location) : t("vertexIntro")}</p>
        <div className="settings-pair">
          <input
            className="field-input"
            value={project}
            placeholder={t("vertexProject")}
            aria-label={t("vertexProject")}
            spellCheck={false}
            autoComplete="off"
            onChange={(e) => setProject(e.currentTarget.value)}
          />
          <input
            className="field-input settings-region"
            value={region}
            placeholder="global"
            aria-label={t("vertexRegion")}
            spellCheck={false}
            autoComplete="off"
            onChange={(e) => setRegion(e.currentTarget.value)}
          />
          <button type="button" className="btn btn-quiet" disabled={busy || !project.trim()} onClick={connect}>
            {t("vertexConnect")}
          </button>
        </div>

        <h3 className="settings-subhead">{t("apiKeys")}</h3>
        <p>{t("settingsIntro")}</p>
        <input
          className="field-input"
          type="password"
          value={key}
          placeholder={t("keyPlaceholder")}
          spellCheck={false}
          autoComplete="off"
          onChange={(e) => setKey(e.currentTarget.value)}
        />
        {error && (
          <div className="notice notice-warn" role="alert" style={{ margin: 0 }}>
            <p className="notice-title">{t(`error_${error.code}`)}</p>
          </div>
        )}
        <p>{t(PRIVACY[active ?? "gemini"])}</p>
        {status && <p>{t("regulationVersion", status.amendments, status.latest.date)}</p>}
        <div className="modal-row">
          {vertex && (
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => remove("vertex")}>
              {t("removeVertex")}
            </button>
          )}
          {KEYED.filter((p) => status?.keys?.[p]).map((p) => (
            <button key={p} type="button" className="btn btn-quiet" disabled={busy} onClick={() => remove(p)}>
              {t("removeKeyOf", t(`provider_${p}`))}
            </button>
          ))}
          <button type="button" className="btn btn-quiet" onClick={onClose}>
            {t("close")}
          </button>
          <button type="button" className="btn btn-primary" disabled={busy || !key.trim()} onClick={save}>
            {t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
