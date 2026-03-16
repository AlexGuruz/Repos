import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./main.css";
import { setupElectronMock } from "./electron-mock";

// Setup mock Electron API for browser development
setupElectronMock();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

