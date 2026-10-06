import { useEffect, useId, useRef, useState } from "react";
import { streamPost } from '../api/stream';
import { useModelContext } from "../context/ModelContext";
import { Select, type SelectOption } from "./Select";
import styles from "./ModelPicker.module.css";

export function ModelPicker() {
  const { supported, installed, selected, setSelected, refresh, catalogue, online } =
    useModelContext();
  const [pulling, setPulling] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const infoId = useId();
  useEffect(() => { dialog.current?.close(); setMsg(null); }, [selected]);

  const info = catalogue?.find(m => m.id === selected);
  const isInstalled = info?.installed ?? installed.includes(selected);

  const options: SelectOption[] = [...new Set([...supported, ...(selected ? [selected] : [])])].map((m) => ({
    value: m,
    label: m,
    hint: !online ? 'unavailable: Ollama offline' : catalogue?.find(entry => entry.id === m)?.installed || installed.includes(m) ? "installed" : catalogue?.find(entry => entry.id === m)?.availability ?? 'unknown',
  }));

  const pull = async () => {
    setPulling(true);
    setMsg(`Pulling ${selected}…`);
    try {
      let failed = false;
      await streamPost('/api/models/pull/stream', { model: selected }, { onEvent(event) {
        if (event.type === 'progress') setMsg(`${event.status}${event.total ? ` · ${Math.round(event.completed / event.total * 100)}%` : ''}`);
        if (event.type === 'error') { failed = true; setMsg(event.message); }
      } });
      if (!failed) setMsg('Model ready.');
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
      {info && <>
        <button type="button" className={styles.infoButton} aria-haspopup="dialog"
          onClick={() => dialog.current?.showModal()}>Model info</button>
        <dialog ref={dialog} className={styles.info} aria-labelledby={infoId}
          onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}>
          <div className={styles.infoHeader}><h2 id={infoId}>{selected}</h2>
            <button type="button" autoFocus aria-label="Close model info" onClick={() => dialog.current?.close()}>Close</button></div>
          <p className={styles.availability}>{!online ? 'Ollama is offline' : isInstalled ? 'Installed and ready' : 'Not installed'}</p>
          <h3>Best for</h3><p>{info.recommended_use}</p>
          <h3>Resources</h3><p>{info.resources}</p>
          <dl><div><dt>Tool calling</dt><dd>{info.tools == null ? 'Not verified' : info.tools ? 'Supported' : 'Not supported'}</dd></div>
            <div><dt>Structured output</dt><dd>{info.structured_output == null ? 'Not verified' : info.structured_output ? 'Supported' : 'Not supported'}</dd></div></dl>
          <p className={styles.note}>Capabilities depend on the installed model version. Practice answers still need checking.</p>
        </dialog>
      </>}
      {msg && <span role="status" className={styles.msg}>{msg}</span>}
    </div>
  );
}
