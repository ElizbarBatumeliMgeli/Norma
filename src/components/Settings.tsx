import { useState } from "react";
import { forgetKey, saveKey, type ApiError, type EngineStatus } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Props = { status: EngineStatus | null; onChanged: () => void; onClose: () => void };

export default function Settings({ status, onChanged, onClose }: Props) {
  const { t } = useI18n();
  const [key, setKey] = useState("");
  const [error, setError] = useState<ApiError | null>(null);

  async function save() {
    setError(null);
    try {
      await saveKey(key);
      setKey("");
      onChanged();
    } catch (e) {
      setError(e as ApiError);
    }
  }

  async function remove() {
    await forgetKey();
    onChanged();
  }

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("settings")}>
        <h2>{t("settings")}</h2>
        <p className={`connection status-${status?.ai ? "pass" : "verify"}`}>{t(status?.ai ? "connected" : "notConnected")}</p>
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
        <p>{t("privacy")}</p>
        {status && <p>{t("regulationVersion", status.amendments, status.latest.date)}</p>}
        <div className="modal-row">
          {status?.ai && (
            <button type="button" className="btn btn-quiet" onClick={remove}>
              {t("removeKey")}
            </button>
          )}
          <button type="button" className="btn btn-quiet" onClick={onClose}>
            {t("close")}
          </button>
          <button type="button" className="btn btn-primary" disabled={!key.trim()} onClick={save}>
            {t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
