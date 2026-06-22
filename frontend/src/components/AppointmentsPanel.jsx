import React, { useCallback, useEffect, useState } from "react";
import { cancelAppointment, getMyAppointments } from "../api/client";

function formatDateTime(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    weekday: "short", day: "numeric", month: "short",
    year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function StatusBadge({ status }) {
  const map = {
    booked:    { label: "Booked",    cls: "statusBooked" },
    completed: { label: "Completed", cls: "statusCompleted" },
    cancelled: { label: "Cancelled", cls: "statusCancelled" },
    no_show:   { label: "No Show",   cls: "statusNoShow" },
  };
  const { label, cls } = map[status] || { label: status, cls: "" };
  return <span className={`statusBadge ${cls}`}>{label}</span>;
}

export default function AppointmentsPanel({ token }) {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getMyAppointments(token);
      setAppointments(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function handleCancel(id) {
    if (!window.confirm("Cancel this appointment?")) return;
    setCancelling(id);
    try {
      await cancelAppointment(token, id);
      await load();
    } catch (err) {
      alert(`Could not cancel: ${err.message}`);
    } finally {
      setCancelling(null);
    }
  }

  return (
    <div className="apptPanel surfaceCard">
      <div className="apptPanelHeader">
        <h2>My Appointments</h2>
        <button onClick={load} disabled={loading} className="refreshBtn">
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error && <p className="authError">{error}</p>}

      {!loading && appointments.length === 0 && (
        <div className="apptEmpty">
          <p className="hint">No upcoming appointments found.</p>
          <p className="hint">Switch to the Chat tab and book one!</p>
        </div>
      )}

      <div className="apptList">
        {appointments.map((appt) => (
          <div key={appt.id} className="apptCard surfaceCard">
            <div className="apptCardTop">
              <div className="apptCardDoctor">{appt.doctor_name}</div>
              <StatusBadge status={appt.status} />
            </div>

            <div className="apptCardMeta">
              {appt.clinic_name && (
                <span className="apptMetaItem">
                  <span className="apptMetaIcon">🏥</span> {appt.clinic_name}
                  {appt.city && `, ${appt.city}`}
                </span>
              )}
              {appt.specialization && (
                <span className="apptMetaItem">
                  <span className="apptMetaIcon">⚕</span> {appt.specialization}
                </span>
              )}
              <span className="apptMetaItem">
                <span className="apptMetaIcon">📅</span> {formatDateTime(appt.start_time)}
              </span>
              <span className="apptMetaItem">
                <span className="apptMetaIcon">🩺</span> {appt.symptoms}
              </span>
            </div>

            {appt.status === "booked" && (
              <button
                className="apptCancelBtn"
                disabled={cancelling === appt.id}
                onClick={() => handleCancel(appt.id)}
              >
                {cancelling === appt.id ? "Cancelling..." : "Cancel Appointment"}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
