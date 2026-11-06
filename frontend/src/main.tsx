import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AccessGate } from "./components/AccessGate";
import { installDiagnostics } from './api/diagnostics';
import "./styles/theme.css";
import "./styles/global.css";

installDiagnostics();
(window as Window & { EXCALIDRAW_ASSET_PATH?: string }).EXCALIDRAW_ASSET_PATH = '/excalidraw/';
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AccessGate><App /></AccessGate>
    </BrowserRouter>
  </StrictMode>,
);
