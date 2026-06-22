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
    "Frontend API is not configured. Set VITE_API_BASE_URL in Vercel to your Render backend URL."
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

// ── auth ─────────────────────────────────────────────────────────────────────
export const register = (payload) => request("/auth/register", { method: "POST", body: JSON.stringify(payload) });
export const login    = (payload) => request("/auth/login",    { method: "POST", body: JSON.stringify(payload) });
export const logout   = (token)   => request("/auth/logout",   { method: "POST" }, token);
export const getMe    = (token)   => request("/me",            { method: "GET" },  token);

// ── geography ────────────────────────────────────────────────────────────────
export const getCities  = ()         => request("/cities", { method: "GET" });
export const getClinics = (cityName) => request(`/clinics${cityName ? `?city=${encodeURIComponent(cityName)}` : ""}`, { method: "GET" });
export const getDoctors = (clinicId) => request(`/doctors${clinicId ? `?clinic_id=${clinicId}` : ""}`, { method: "GET" });

// ── chat ─────────────────────────────────────────────────────────────────────
export const listChats       = (token)          => request("/chats",                           { method: "GET" },  token);
export const createChat      = (token, title)   => request("/chats",                           { method: "POST", body: JSON.stringify({ title }) }, token);
export const getChatMessages = (token, chatId)  => request(`/chats/${chatId}/messages`,        { method: "GET" },  token);
export const sendChat        = (token, payload) => request("/chat",                            { method: "POST", body: JSON.stringify(payload) }, token);

// ── patient self-service ──────────────────────────────────────────────────────
export const getMyAppointments = (token)     => request("/my-appointments",            { method: "GET" },  token);
export const cancelAppointment = (token, id) => request(`/appointments/${id}/cancel`,  { method: "POST" }, token);

// ── doctor queue ──────────────────────────────────────────────────────────────
export const getDoctorQueue          = (token)             => request("/doctor/queue",              { method: "GET" },  token);
export const updateAppointmentStatus = (token, id, s)      => request(`/appointments/${id}/status`, { method: "PATCH", body: JSON.stringify({ status: s }) }, token);
export const updateAppointmentNotes  = (token, id, notes)  => request(`/appointments/${id}/notes`,  { method: "PATCH", body: JSON.stringify({ notes }) }, token);

// ── doctor schedule ───────────────────────────────────────────────────────────
export const getDoctorSchedule     = (token)          => request("/doctor/schedule",      { method: "GET" },  token);
export const replaceDoctorSchedule = (token, windows) => request("/doctor/schedule",      { method: "PUT",  body: JSON.stringify({ windows }) }, token);
export const deleteScheduleWindow  = (token, id)      => request(`/doctor/schedule/${id}`,{ method: "DELETE" }, token);

// ── doctor history ────────────────────────────────────────────────────────────
export const getDoctorHistory = (token, { status, days } = {}) => {
  const qs = new URLSearchParams();
  if (status) qs.set("status", status);
  if (days)   qs.set("days",   String(days));
  return request(`/doctor/history${qs.toString() ? `?${qs}` : ""}`, { method: "GET" }, token);
};

// ── admin ─────────────────────────────────────────────────────────────────────
export const getAdminDashboard    = (token)              => request("/admin/dashboard", { method: "GET" }, token);
export const getAdminDoctors      = (token)              => request("/admin/doctors",   { method: "GET" }, token);
export const addAdminDoctor       = (token, payload)     => request("/admin/doctors",   { method: "POST",  body: JSON.stringify(payload) }, token);
export const updateAdminDoctor    = (token, id, payload) => request(`/admin/doctors/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
export const getAdminAppointments = (token, params = {}) => {
  const qs = new URLSearchParams();
  if (params.doctor_id) qs.set("doctor_id", String(params.doctor_id));
  if (params.status)    qs.set("status",    params.status);
  if (params.date)      qs.set("date",      params.date);
  if (params.days)      qs.set("days",      String(params.days));
  return request(`/admin/appointments${qs.toString() ? `?${qs}` : ""}`, { method: "GET" }, token);
};
