import { useEffect, useId, useRef, useState } from "react";
import styles from "./Select.module.css";

export interface SelectOption {
  value: string;
  label: string;
  hint?: string; // small trailing note, e.g. "not installed"
}

interface Props {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  label?: string;
  ariaLabel?: string;
  placeholder?: string;
  disabled?: boolean;
}

/**
 * Accessible custom dropdown styled to the app theme (replaces native <select>).
 * Implements the listbox pattern: button toggles a popup list; arrow keys move,
 * Enter/Space select, Escape closes, click-outside dismisses.
 */
export function Select({
  value,
  options,
  onChange,
  label,
  ariaLabel,
  placeholder = "Select…",
  disabled,
}: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLUListElement>(null);
  const listId = useId();

  const selected = options.find((o) => o.value === value);
  useEffect(() => { if (open) popupRef.current?.focus(); }, [open]);
  useEffect(() => {
    if (open) document.getElementById(`${listId}-${active}`)?.scrollIntoView?.({ block: 'nearest' });
  }, [active, open, listId]);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  useEffect(() => {
    if (open) {
      const idx = options.findIndex((o) => o.value === value);
      setActive(idx >= 0 ? idx : 0);
    }
  }, [open, options, value]);

  const choose = (idx: number) => {
    const opt = options[idx];
    if (opt) {
      onChange(opt.value);
      setOpen(false);
      triggerRef.current?.focus();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (!open) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((a) => Math.min(a + 1, options.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((a) => Math.max(a - 1, 0));
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        choose(active);
        break;
      case "Escape":
        e.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
        break;
      case "Home":
        e.preventDefault();
        setActive(0);
        break;
      case "End":
        e.preventDefault();
        setActive(options.length - 1);
        break;
      case "Tab":
        setOpen(false);
        triggerRef.current?.focus();
        break;
      default:
        if (e.key.length === 1 && /\S/.test(e.key)) {
          const next = options.findIndex((option, index) => index > active && option.label.toLowerCase().startsWith(e.key.toLowerCase()));
          const first = options.findIndex(option => option.label.toLowerCase().startsWith(e.key.toLowerCase()));
          if (next >= 0 || first >= 0) setActive(next >= 0 ? next : first);
        }
    }
  };

  return (
    <div className={styles.wrap} ref={rootRef} onBlur={e => {
      if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false);
    }}>
      {label && <span className={styles.label}>{label}</span>}
      <button
        type="button"
        ref={triggerRef}
        className={styles.trigger}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={ariaLabel ?? label}
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        onKeyDown={onKeyDown}
      >
        <span className={styles.value} data-placeholder={!selected}>
          {selected ? selected.label : placeholder}
        </span>
        <span className={styles.chevron} data-open={open} aria-hidden>
          ⌄
        </span>
      </button>

      {open && (
        <ul ref={popupRef} tabIndex={-1} onKeyDown={onKeyDown} className={styles.list} role="listbox" id={listId}
          aria-activedescendant={`${listId}-${active}`} aria-label={ariaLabel ?? label}>
          {options.map((opt, i) => (
            <li
              key={opt.value}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={opt.value === value}
              className={`${styles.option} ${i === active ? styles.active : ""} ${
                opt.value === value ? styles.selected : ""
              }`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(i);
              }}
            >
              <span className={styles.optLabel}>{opt.label}</span>
              {opt.hint && <span className={styles.optHint}>{opt.hint}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
