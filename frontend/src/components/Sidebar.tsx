import { useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import { SECTIONS } from "../sections/registry";
import styles from "./Sidebar.module.css";
import { Avatar } from '../profile/Avatar';
import { ACCENT_COLOURS } from '../api/profile';
import { useProfile } from '../profile/ProfileContext';

interface Props {
  collapsed: boolean;
  onToggleCollapse: () => void;
  isMobile: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  isMobile,
  mobileOpen,
  onCloseMobile,
}: Props) {
  const navRef = useRef<HTMLElement>(null);

  // Mobile drawer: close on Esc, trap focus while open.
  useEffect(() => {
    if (!isMobile || !mobileOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseMobile();
      if (e.key === "Tab" && navRef.current) {
        const focusable = navRef.current.querySelectorAll<HTMLElement>(
          'a, button, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    navRef.current?.querySelector<HTMLElement>("a")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [isMobile, mobileOpen, onCloseMobile]);

  const isRail = !isMobile && collapsed;

  const { profile, status, workspace } = useProfile();
  const name = profile.display_name.trim();
  // Personal items (study modes, account, guide) always show the learner's colour, whatever page is
  // open; Coach, Quiz and Flashcards items carry their own colours (data-section in theme.css).
  const own = ACCENT_COLOURS[status === 'ready' && profile.onboarded ? profile.accent : 'blue'];
  const personalVars = { '--accent': own.main, '--accent-vivid': own.vivid, '--accent-deep': own.deep, '--accent-soft': own.soft } as React.CSSProperties;
  const aside = (
    <aside
      ref={navRef}
      className={`${styles.sidebar} ${isRail ? styles.rail : ""} ${
        isMobile ? styles.mobile : ""
      } ${isMobile && mobileOpen ? styles.open : ""}`}
      aria-label="Sections"
      style={personalVars}
      aria-hidden={isMobile && !mobileOpen ? true : undefined}
    >
      <div className={styles.brand}>
        <span className={styles.logo} aria-hidden />
        {!isRail && <span className={styles.brandName}>PreparationPalAI</span>}
      </div>
      {isMobile && <button type="button" onClick={onCloseMobile} aria-label="Close menu">Close menu</button>}

      <nav className={styles.nav}>
        {SECTIONS.map((s) => (
          <NavLink
            key={s.id}
            to={s.path}
            aria-label={s.label}
            data-section={s.id}
            title={isRail ? s.label : undefined}
            className={({ isActive }) =>
              `${styles.item} ${isActive ? styles.active : ""}`
            }
            onClick={() => isMobile && onCloseMobile()}
          >
            <span className={styles.icon}>{s.icon}</span>
            {!isRail && <span className={styles.itemLabel}>{s.label}</span>}
          </NavLink>
        ))}
      </nav>

      {status === 'ready' && profile.onboarded && <NavLink to="/account" className={styles.me} title={isRail ? (name || 'Your profile') : undefined}
        aria-label={`${name || 'Your profile'}: account`} onClick={() => isMobile && onCloseMobile()}>
        <Avatar seed={`${workspace}:${profile.avatar_seed}`} name={name} size={34} />
        {!isRail && <span className={styles.meText}><strong>{name || 'Your profile'}</strong><span>{profile.subjects[0] ?? 'Account'}</span></span>}
      </NavLink>}

      {!isMobile && (
        <button
          type="button"
          className={styles.collapse}
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
        >
          <span className={styles.collapseIcon} data-collapsed={collapsed}>
            ‹
          </span>
          {!isRail && <span>Collapse</span>}
        </button>
      )}
    </aside>
  );

  if (isMobile) {
    return (
      <>
        {mobileOpen && (
          <div
            className={styles.backdrop}
            onClick={onCloseMobile}
            aria-hidden
          />
        )}
        {aside}
      </>
    );
  }
  return aside;
}
