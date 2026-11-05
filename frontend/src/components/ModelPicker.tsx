import { useState } from "react";
import { api } from "../api/client";
import { useModelContext } from "../context/ModelContext";
import { Select, type SelectOption } from "./Select";
import styles from "./ModelPicker.module.css";

export function ModelPicker() {
  const { supported, installed, selected, setSelected, refresh, catalogue } =
    useModelContext();
  const [pulling, setPulling] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const info = catalogue?.find(m => m.id === selected);
  const isInstalled = info?.installed ?? installed.includes(selected);

  const options: SelectOption[] = [...new Set([...supported, ...(selected ? [selected] : [])])].map((m) => ({
    value: m,
    label: m,
    hint: catalogue?.find(entry => entry.id === m)?.installed || installed.includes(m) ? "installed" : "downloadable",
  }));

  const pull = async () => {
    setPulling(true);
    setMsg(`Pulling ${selected}…`);
    try {
      const res = await api.pullModel(selected);
      setMsg(res.message);
      await refresh();
    } catch {
      setMsg("Pull failed.");
    } finally {
      setPulling(false);
    }
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.selectBox}>
        <Select
          ariaLabel="Model"
          value={selected}
          options={options}
          onChange={setSelected}
          placeholder="Model"
        />
      </div>
      {!isInstalled && selected && (
        <button
          type="button"
          className={styles.pull}
          onClick={pull}
          disabled={pulling}
        >
          {pulling ? "Pulling…" : "Pull"}
        </button>
      )}
      {info && <details className={styles.info}><summary>Model info</summary>
        <p>{info.recommended_use}</p><p>{info.resources}</p>
        <p>Tool calling: {info.tools === null ? 'unverified' : info.tools ? 'supported' : 'unsupported'}. Structured output: {info.structured_output === null ? 'unverified' : info.structured_output ? 'supported' : 'unsupported'}.</p>
      </details>}
      {msg && <span role="status" className={styles.msg}>{msg}</span>}
    </div>
  );
}
