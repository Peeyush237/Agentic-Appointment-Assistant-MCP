import React from "react";
import { useState } from "react";
import ChatPanel from "./components/ChatPanel";

export default function App() {
  const [role, setRole] = useState("patient");

  return (
    <main className="container">
      <header>
        <h1>Agentic Appointment Assistant (MCP)</h1>
        <p>LLM + MCP Tools + FastAPI + PostgreSQL + React</p>
      </header>

      <div className="roleToggle">
        <button className={role === "patient" ? "active" : ""} onClick={() => setRole("patient")}>
          Patient Mode
        </button>
        <button className={role === "doctor" ? "active" : ""} onClick={() => setRole("doctor")}>
          Doctor Mode
        </button>
      </div>

      <ChatPanel role={role} />
    </main>
  );
}
