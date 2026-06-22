import React, { useCallback, useEffect, useState } from "react";
import { getAdminDashboard } from "../api/client";

function StatCard({ label, value, cls }) {
  return (
    <div className={`statCard surfaceCard ${cls || ""}`}>
      <div className="statValue">{value}</div>
      <div className="statLabel">{label}</div>
    </div>
  );
}

export default function AdminDashboard({ token, user }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getAdminDashboard(token));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div className="adminDashboard surfaceCard">
      <div className="adminDashHeader">
        <div>
          <h2>Clinic Dashboard</h2>
          {data && <p className="hint">{data.clinic_name} · {data.city}</p>}
          <p className="hint">{today}</p>
        </div>
        <button className="refreshBtn" onClick={load} disabled={loading}>
          {loading ? "..." : "Refresh"}
        </button>
      </div>

      {error && <p className="authError">{error}</p>}

      {data && (
        <>
          <div className="statGrid">
            <StatCard label="Total Doctors"      value={data.total_doctors}    cls="statNeutral" />
            <StatCard label="Today's Total"      value={data.today_total}      cls="statNeutral" />
            <StatCard label="Waiting"            value={data.today_pending}    cls="statPending" />
            <StatCard label="Completed"          value={data.today_completed}  cls="statDone" />
            <StatCard label="No Show"            value={data.today_no_show}    cls="statWarn" />
            <StatCard label="Cancelled"          value={data.today_cancelled}  cls="statCancel" />
          </div>

          <div className="adminQuickInfo surfaceCard">
            <h3>Admin Account Info</h3>
            <p className="hint">Logged in as <strong>{user.full_name}</strong></p>
            <p className="hint">Managing: <strong>{data.clinic_name}</strong>, {data.city}</p>
            <p className="hint">Use the Doctors tab to add/edit doctors. Use the Appointments tab for a full log.</p>
          </div>
        </>
      )}
    </div>
  );
}
