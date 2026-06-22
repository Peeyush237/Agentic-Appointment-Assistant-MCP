const RAW_API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" && /localhost|127\.0\.0\.1/.test(window.location.hostname)
    ? "http://127.0.0.1:8000"
    : "");

const normalizedBase = RAW_API_BASE.replace(/\/+$/, "").replace(/\/api$/, "");
const API_BASE = normalizedBase ? `${normalizedBase}/api` : "";

function ensureApiConfigured() {
  if (API_BASE) return;
  throw new Error(
    "Frontend API is not configured. Set VITE_API_BASE_URL in Vercel to your Render backend URL (without /api)."
  );
}

async function request(path, options = {}, token = null) {
  ensureApiConfigured();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body?.detail ? `: ${body.detail}` : "";
    } catch { /* ignore */ }
    throw new Error(`Request failed with status ${response.status}${detail}`);
  }
  return response.status === 204 ? null : response.json();
}

// ── auth ────────────────────────────────────────────────────────────────────
export async function register(payload) {
  return request("/auth/register", { method: "POST", body: JSON.stringify(payload) });
}
export async function login(payload) {
  return request("/auth/login", { method: "POST", body: JSON.stringify(payload) });
}
export async function logout(token) {
  return request("/auth/logout", { method: "POST" }, token);
}
export async function getMe(token) {
  return request("/me", { method: "GET" }, token);
}

// ── geography ────────────────────────────────────────────────────────────────
export async function getCities() {
  return request("/cities", { method: "GET" });
}
export async function getClinics(cityName) {
  const qs = cityName ? `?city=${encodeURIComponent(cityName)}` : "";
  return request(`/clinics${qs}`, { method: "GET" });
}
export async function getDoctors(clinicId) {
  const qs = clinicId ? `?clinic_id=${clinicId}` : "";
  return request(`/doctors${qs}`, { method: "GET" });
}

// ── chat ─────────────────────────────────────────────────────────────────────
export async function listChats(token) {
  return request("/chats", { method: "GET" }, token);
}
export async function createChat(token, title = "") {
  return request("/chats", { method: "POST", body: JSON.stringify({ title }) }, token);
}
export async function getChatMessages(token, chatId) {
  return request(`/chats/${chatId}/messages`, { method: "GET" }, token);
}
export async function sendChat(token, payload) {
  return request("/chat", { method: "POST", body: JSON.stringify(payload) }, token);
}

// ── patient self-service ──────────────────────────────────────────────────────
export async function getMyAppointments(token) {
  return request("/my-appointments", { method: "GET" }, token);
}
export async function cancelAppointment(token, appointmentId) {
  return request(`/appointments/${appointmentId}/cancel`, { method: "POST" }, token);
}

// ── doctor queue ──────────────────────────────────────────────────────────────
export async function getDoctorQueue(token) {
  return request("/doctor/queue", { method: "GET" }, token);
}
export async function updateAppointmentStatus(token, appointmentId, status) {
  return request(
    `/appointments/${appointmentId}/status`,
    { method: "PATCH", body: JSON.stringify({ status }) },
    token
  );
}
