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
  // The learner's own colour becomes the app's accent (only once they have chosen one).
  const accent = status === 'ready' && profile.onboarded ? ACCENT_COLOURS[profile.accent] : null;
  useEffect(() => { document.title = `${section.label} · PreparationPalAI`; }, [section.label]);

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
      style={accent ? { '--accent': accent.main, '--accent-soft': accent.soft, '--accent-border': accent.main } as React.CSSProperties : undefined}>
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
