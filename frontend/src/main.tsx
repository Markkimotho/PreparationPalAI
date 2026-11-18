import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AccessGate } from "./components/AccessGate";
import { ProfileProvider } from './profile/ProfileContext';
import { installDiagnostics } from './api/diagnostics';
import { registerServiceWorker } from './pwa/register';
import "./styles/theme.css";
import "./styles/global.css";

installDiagnostics();
void registerServiceWorker();
(window as Window & { EXCALIDRAW_ASSET_PATH?: string }).EXCALIDRAW_ASSET_PATH = '/excalidraw/';
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AccessGate><ProfileProvider><App /></ProfileProvider></AccessGate>
    </BrowserRouter>
  </StrictMode>,
);
