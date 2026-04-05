import React from "react";
import { useState } from "react";
import { sendChat } from "../api/client";

export default function ChatPanel({ role }) {
  const [sessionId, setSessionId] = useState(null);
  const [message, setMessage] = useState("");
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

  async function submitText(outgoing) {
    if (!outgoing.trim()) return;

    setItems((prev) => [...prev, { from: "user", text: outgoing }]);
    setBusy(true);

    try {
      const data = await sendChat({
        role,
        message: outgoing,
        session_id: sessionId,
      });

      setSessionId(data.session_id);
      setItems((prev) => [
        ...prev,
        {
          from: "assistant",
          text: data.response,
          trace: data.tool_trace,
        },
      ]);
    } catch (err) {
      setItems((prev) => [...prev, { from: "assistant", text: `Error: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  async function onSend() {
    const outgoing = message;
    setMessage("");
    await submitText(outgoing);
  }

  return (
    <div className="panel">
      <h2>{role === "patient" ? "Patient Assistant" : "Doctor Report Assistant"}</h2>
      <p className="hint">
        {role === "patient"
          ? "Try: I want to book an appointment with Dr. Ahuja tomorrow morning"
          : "Try: How many patients visited yesterday?"}
      </p>

      <div className="chatWindow">
        {items.map((item, idx) => (
          <div key={idx} className={`bubble ${item.from}`}>
            <div>{item.text}</div>
            {item.trace && item.trace.length > 0 && (
              <details>
                <summary>Tool Trace</summary>
                <pre>{JSON.stringify(item.trace, null, 2)}</pre>
              </details>
            )}
          </div>
        ))}
      </div>

      <div className="composer">
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type your request..."
          disabled={busy}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSend();
          }}
        />
        <button onClick={onSend} disabled={busy}>
          {busy ? "Thinking..." : "Send"}
        </button>
      </div>

      {role === "doctor" && (
        <div className="quickActions">
          <button
            disabled={busy}
            onClick={() => submitText("How many appointments do I have today and tomorrow for Dr. Ahuja?")}
          >
            Trigger Daily Summary
          </button>
        </div>
      )}
    </div>
  );
}
