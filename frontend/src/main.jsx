import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

const rootEl = document.getElementById("root");

if (!rootEl) {
  throw new Error("Root element not found");
}

try {
  createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
} catch (err) {
  rootEl.innerHTML = `<div style=\"padding:16px;font-family:Segoe UI,Arial,sans-serif;color:#b91c1c\">Frontend render error: ${String(err)}</div>`;
}

window.addEventListener("error", (event) => {
  rootEl.innerHTML = `<div style=\"padding:16px;font-family:Segoe UI,Arial,sans-serif;color:#b91c1c\">Runtime error: ${String(event.error || event.message)}</div>`;
});
