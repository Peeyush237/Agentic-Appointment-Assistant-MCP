const API_BASE = "http://127.0.0.1:8000/api";

export async function sendChat(payload) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body?.detail ? `: ${body.detail}` : "";
    } catch {
      // Ignore parse errors and keep status message.
    }
    throw new Error(`Request failed with status ${response.status}${detail}`);
  }

  return response.json();
}
