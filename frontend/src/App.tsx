import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { KnowledgeBaseProvider } from "./context/KnowledgeBaseContext";
import { ModelProvider } from "./context/ModelContext";
import { Flashcards } from "./sections/Flashcards";
import { Guide } from "./sections/Guide";
import { ProgrammingAssistant } from "./sections/ProgrammingAssistant";
import { QuizPrep } from "./sections/QuizPrep";
import { RegularChat } from "./sections/RegularChat";
import { StudyAgent } from "./sections/StudyAgent";
import { Coach } from "./sections/Coach";
import { DrawingReviews } from './sections/DrawingReviews';
import { Account } from './sections/Account/Account';
import { Setup } from './sections/Setup/Setup';
import { useProfile } from './profile/ProfileContext';

/** A learner who has not made the app theirs yet starts at setup (if the profile could not be
 *  loaded at all, the app opens with defaults instead of blocking). */
export function NeedsSetup() {
  const { profile, status } = useProfile();
  const { pathname } = useLocation();
  if (status === 'ready' && !profile.onboarded && pathname !== '/setup') return <Navigate to="/setup" replace />;
  return null;
}

export function App() {
  const { status } = useProfile();
  if (status === 'loading') return <p role="status" className="sr-only">Loading your profile…</p>;
  return (
    <ModelProvider>
      <KnowledgeBaseProvider>
        <NeedsSetup />
        <Routes>
          <Route path="/setup" element={<Setup />} />
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/prepare" replace />} />
            <Route path="/prepare" element={<Coach />} />
            <Route path="/quiz" element={<QuizPrep />} />
            <Route path="/agent" element={<StudyAgent />} />
            <Route path="/code" element={<ProgrammingAssistant />} />
            <Route path="/chat" element={<RegularChat />} />
            <Route path="/flashcards" element={<Flashcards />} />
            <Route path="/guide" element={<Guide />} />
            <Route path="/drawings" element={<DrawingReviews />} />
            <Route path="/account" element={<Account />} />
            <Route path="*" element={<Navigate to="/quiz" replace />} />
          </Route>
        </Routes>
      </KnowledgeBaseProvider>
    </ModelProvider>
  );
}
