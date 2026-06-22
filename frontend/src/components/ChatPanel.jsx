import React, { useEffect, useRef, useState } from "react";
import { createChat, getChatMessages, getCities, listChats, sendChat } from "../api/client";

function computeSuggestions(items, cities, role) {
  if (role === "doctor") {
    return ["How many appointments today?", "Yesterday's summary", "Tomorrow's schedule?"];
  }
  if (items.length === 0) {
    return cities.slice(0, 4).map((c) => `I'm in ${c.name}`);
  }

  const lastAssistant = [...items].reverse().find((i) => i.from === "assistant");
  const lastText = (lastAssistant?.text || "").toLowerCase();

  if (lastText.includes("booked") || lastText.includes("confirmed") || lastText.includes("appointment id")) {
    return ["Book another appointment", "What should I bring?"];
  }
  if (lastText.includes("clinic") && (lastText.includes("found") || lastText.includes("available"))) {
    return ["Morning slots please", "Afternoon slots please"];
  }
  if (lastText.includes("slot") || lastText.includes("available")) {
    return ["Morning slots please", "Afternoon slots please", "What about tomorrow?"];
  }
  if (lastText.includes("doctor") || lastText.includes("dr.")) {
    return ["Morning slots please", "Afternoon slots please", "Check availability"];
  }
  if (lastText.includes("city") || lastText.includes("where")) {
    return cities.slice(0, 4).map((c) => `I'm in ${c.name}`);
  }
  return ["Book an appointment", "Check availability", "Clinic hours?"];
}

export default function ChatPanel({ token, user }) {
  const [chatId, setChatId] = useState(null);
  const [chats, setChats] = useState([]);
  const [message, setMessage] = useState("");
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loadingChats, setLoadingChats] = useState(true);
  const [cities, setCities] = useState([]);
  const [isListening, setIsListening] = useState(false);

  const chatEndRef = useRef(null);
  const recognitionRef = useRef(null);
  const suggestions = computeSuggestions(items, cities, user.role);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items, busy]);

  useEffect(() => {
    getCities().then(setCities).catch(() => {});
  }, []);

  useEffect(() => {
    async function load() {
      setLoadingChats(true);
      try {
        const threads = await listChats(token);
        setChats(threads);
        if (threads.length > 0) setChatId(threads[0].id);
      } finally {
        setLoadingChats(false);
      }
    }
    load();
  }, [token]);

  useEffect(() => {
    async function loadMessages() {
      if (!chatId) { setItems([]); return; }
      const history = await getChatMessages(token, chatId);
      setItems(history.map((msg) => ({ from: msg.sender, text: msg.content, trace: msg.tool_trace })));
    }
    loadMessages();
  }, [chatId, token]);

  async function refreshChats(preferredChatId = null) {
    const threads = await listChats(token);
    setChats(threads);
    if (preferredChatId) { setChatId(preferredChatId); return; }
    if (!chatId && threads.length > 0) setChatId(threads[0].id);
  }

  async function startNewChat() {
    const thread = await createChat(token, "");
    setChatId(thread.id);
    setItems([]);
    await refreshChats(thread.id);
  }

  async function submitText(outgoing) {
    if (!outgoing.trim()) return;
    setItems((prev) => [...prev, { from: "user", text: outgoing }]);
    setBusy(true);
    try {
      const data = await sendChat(token, { message: outgoing, chat_id: chatId });
      setChatId(data.chat_id);
      setItems((prev) => [...prev, { from: "assistant", text: data.response, trace: data.tool_trace }]);
      await refreshChats(data.chat_id);
    } catch (err) {
      setItems((prev) => [...prev, { from: "assistant", text: `Error: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  async function onSend() {
    const outgoing = message.trim();
    setMessage("");
    await submitText(outgoing);
  }

  function toggleVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice input is not supported in this browser. Please use Chrome or Edge.");
      return;
    }
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;
    recognition.onresult = (e) => {
      setMessage(e.results[0][0].transcript);
      setIsListening(false);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    setIsListening(true);
    recognition.start();
  }

  const showCityCards = user.role === "patient" && items.length === 0 && cities.length > 0;

  return (
    <div className="workspaceGrid">
      <aside className="chatSidebar surfaceCard">
        <div className="chatSidebarHeader">
          <h3>Your Chats</h3>
          <button onClick={startNewChat} disabled={busy}>+ New</button>
        </div>
        {loadingChats ? (
          <p className="hint">Loading chats...</p>
        ) : (
          <div className="chatList">
            {chats.map((thread) => (
              <button
                key={thread.id}
                className={`chatListItem ${thread.id === chatId ? "active" : ""}`}
                onClick={() => setChatId(thread.id)}
              >
                <div className="chatListTitle">{thread.title}</div>
                <div className="chatListMeta">{new Date(thread.updated_at).toLocaleString()}</div>
              </button>
            ))}
            {chats.length === 0 && <p className="hint">No chats yet. Start a new one.</p>}
          </div>
        )}
      </aside>

      <section className="panel surfaceCard">
        <div className="panelTop">
          <h2>{user.role === "patient" ? "Patient Assistant" : "Doctor Report Assistant"}</h2>
          <span className="panelBadge">Live</span>
        </div>

        <div className="chatWindow">
          {showCityCards && (
            <div className="cityCards">
              <p className="hint">Where are you located? Pick a city to find nearby clinics:</p>
              <div className="cityCardGrid">
                {cities.map((city) => (
                  <button
                    key={city.id}
                    className="cityCard"
                    disabled={busy}
                    onClick={() => submitText(`I'm in ${city.name}`)}
                  >
                    <div className="cityCardName">{city.name}</div>
                    <div className="cityCardState">{city.state}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {items.map((item, idx) => (
            <div key={idx} className={`bubble ${item.from}`}>
              <div className="bubbleMeta">{item.from === "user" ? "You" : "Assistant"}</div>
              <div style={{ whiteSpace: "pre-wrap" }}>{item.text}</div>
              {item.trace && item.trace.length > 0 && (
                <details>
                  <summary>Tool Trace</summary>
                  <pre>{JSON.stringify(item.trace, null, 2)}</pre>
                </details>
              )}
            </div>
          ))}

          {busy && (
            <div className="bubble assistant">
              <div className="bubbleMeta">Assistant</div>
              <div className="typingIndicator"><span /><span /><span /></div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {suggestions.length > 0 && !busy && (
          <div className="suggestions">
            {suggestions.map((s, i) => (
              <button key={i} className="suggestionChip" disabled={busy} onClick={() => submitText(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="composer">
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={isListening ? "Listening... speak now" : "Type your request..."}
            disabled={busy}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) onSend(); }}
          />
          <button
            className={`voiceBtn${isListening ? " listening" : ""}`}
            onClick={toggleVoice}
            disabled={busy}
            title={isListening ? "Stop listening" : "Voice input"}
          >
            {isListening ? "■" : "🎤"}
          </button>
          <button onClick={onSend} disabled={busy || !message.trim()}>
            {busy ? "..." : "Send"}
          </button>
        </div>

        {user.role === "doctor" && (
          <div className="quickActions">
            <button disabled={busy} onClick={() => submitText("How many appointments do I have today and tomorrow?")}>
              Trigger Daily Summary
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
