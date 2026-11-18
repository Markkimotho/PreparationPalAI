import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useIsMobile } from "../hooks/useMediaQuery";
import { sectionForPath } from "../sections/registry";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import styles from "./AppLayout.module.css";
import { ACCENT_COLOURS } from '../api/profile';
import { useProfile } from '../profile/ProfileContext';

const COLLAPSE_KEY = "exam-prep.sidebar-collapsed";

export function AppLayout() {
  const location = useLocation();
  const isMobile = useIsMobile();
  const section = sectionForPath(location.pathname);
  const { profile, status } = useProfile();
  // As on the phone: Coach, Quiz and Flashcards keep their own colours (theme.css); the learner's
  // own colour fills the personal pages (study modes, account, guide, drawings).
  const personal = !['prepare', 'quiz', 'cards'].includes(section.id);
  const accent = personal && status === 'ready' && profile.onboarded ? ACCENT_COLOURS[profile.accent] : null;
  useEffect(() => { document.title = `${section.label} · Tayarishe`; }, [section.label]);

  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(COLLAPSE_KEY) === "1",
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const toggleCollapse = () =>
    setCollapsed((c) => {
      localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      return !c;
    });

  return (
    <div className={styles.app} data-section={section.id}
      style={accent ? { '--accent': accent.main, '--accent-vivid': accent.vivid, '--accent-deep': accent.deep, '--accent-soft': accent.soft,
        '--accent-border': `color-mix(in srgb, ${accent.main} 35%, white)`, '--focus': `color-mix(in srgb, ${accent.main} 45%, transparent)` } as React.CSSProperties : undefined}>
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={toggleCollapse}
        isMobile={isMobile}
        mobileOpen={mobileOpen}
          onCloseMobile={closeMobile}
      />
      <div className={styles.main}>
        <TopBar
          title={section.label}
          isMobile={isMobile}
          onOpenMenu={() => setMobileOpen(true)}
        />
        <main className={styles.content} key={section.id}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
