import { useEffect, useState } from "react";

import { clearStoredApiKey, getStoredApiKey, getSystemConfigSummary, setStoredApiKey } from "../lib/api";

export function ApiKeySessionCard() {
  const [value, setValue] = useState(getStoredApiKey());
  const [saved, setSaved] = useState(Boolean(getStoredApiKey()));
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let cancelled = false;

    getSystemConfigSummary()
      .then((summary) => {
        if (!cancelled) {
          setVisible(summary.integrations.auth_enabled);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setVisible(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  function handleSave() {
    setStoredApiKey(value);
    setSaved(Boolean(value.trim()));
  }

  function handleClear() {
    clearStoredApiKey();
    setValue("");
    setSaved(false);
  }

  if (!visible) {
    return null;
  }

  return (
    <div className="sidebar-auth">
      <p className="eyebrow">本地 API Key</p>
      <input
        type="password"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="用于写入类操作的 X-API-Key"
      />
      <div className="button-row">
        <button className="action-button" type="button" onClick={handleSave}>
          保存
        </button>
        <button className="ghost-button" type="button" onClick={handleClear}>
          清空
        </button>
      </div>
      <p className="brand-copy">
        {saved
          ? "只保存在当前浏览器会话中，不会写入构建产物。"
          : "仅在后端开启写入鉴权时需要；普通浏览和调试可以忽略。"}
      </p>
    </div>
  );
}
