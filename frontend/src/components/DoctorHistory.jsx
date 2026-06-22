import React, { useCallback, useEffect, useState } from "react";
import { getDoctorHistory, updateAppointmentNotes, updateAppointmentStatus } from "../api/client";

function fmt(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    weekday: "short", day: "numeric", month: "short",
    year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const STATUS_LABELS = {
  booked: { label: "Booked", cls: "statusBooked" },
  completed: { label: "Completed", cls: "statusCompleted" },
  cancelled: { label: "Cancelled", cls: "statusCancelled" },
  no_show: { label: "No Show", cls: "statusNoShow" },
};

function StatusBadge({ status }) {
  const { label, cls } = STATUS_LABELS[status] || { label: status, cls: "" };
  return <span className={`statusBadge ${cls}`}>{label}</span>;
}

function AppointmentRow({ appt, token, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [noteText, setNoteText] = useState(appt.notes || "");
  const [saving, setSaving] = useState(false);

  async function saveNotes() {
    setSaving(true);
    try {
      await updateAppointmentNotes(token, appt.id, noteText);
      onUpdate(appt.id, { notes: noteText });
      setEditing(false);
    } catch (e) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function markStatus(s) {
    setSaving(true);
    try {
      await updateAppointmentStatus(token, appt.id, s);
      onUpdate(appt.id, { status: s });
    } catch (e) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="historyCard surfaceCard">
      <div className="historyCardTop">
        <div>
          <div className="historyPatient">{appt.patient_name}</div>
          <div className="hint">{appt.patient_email}</div>
        </div>
        <StatusBadge status={appt.status} />
      </div>

      <div className="historyMeta">
        <span className="apptMetaItem"><span className="apptMetaIcon">📅</span> {fmt(appt.start_time)}</span>
        <span className="apptMetaItem"><span className="apptMetaIcon">🩺</span> {appt.symptoms}</span>
        {appt.clinic_name && (
          <span className="apptMetaItem"><span className="apptMetaIcon">🏥</span> {appt.clinic_name}</span>
        )}
      </div>

      <div className="historyNotes">
        {editing ? (
          <div className="historyNotesEdit">
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Enter clinical notes..."
              rows={3}
              disabled={saving}
            />
            <div className="historyNoteActions">
              <button onClick={saveNotes} disabled={saving}>{saving ? "Saving..." : "Save Notes"}</button>
              <button onClick={() => { setEditing(false); setNoteText(appt.notes || ""); }} disabled={saving}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="historyNoteDisplay" onClick={() => setEditing(true)}>
            {appt.notes
              ? <><span className="historyNoteText">{appt.notes}</span><span className="historyNoteEditHint"> ✎ edit</span></>
              : <span className="historyNoteEmpty">+ Add clinical notes</span>
            }
          </div>
        )}
      </div>

      {appt.status === "booked" && (
        <div className="historyActions">
          <button className="queueActionBtn complete" disabled={saving} onClick={() => markStatus("completed")}>✓ Mark Done</button>
          <button className="queueActionBtn noshow"  disabled={saving} onClick={() => markStatus("no_show")}>✗ No Show</button>
        </div>
      )}
    </div>
  );
}

export default function DoctorHistory({ token }) {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading]           = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [days, setDays]                 = useState(30);
  const [error, setError]               = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getDoctorHistory(token, { status: statusFilter || undefined, days });
      setAppointments(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, days]);

  useEffect(() => { load(); }, [load]);

  function handleUpdate(id, changes) {
    setAppointments((prev) => prev.map((a) => (a.id === id ? { ...a, ...changes } : a)));
  }

  return (
    <div className="historyPanel surfaceCard">
      <div className="historyPanelHeader">
        <h2>Appointment History</h2>
        <div className="historyFilters">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            <option value="booked">Booked</option>
            <option value="completed">Completed</option>
            <option value="no_show">No Show</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 3 months</option>
            <option value={365}>Last year</option>
          </select>
          <button className="refreshBtn" onClick={load} disabled={loading}>Refresh</button>
        </div>
      </div>

      {error && <p className="authError">{error}</p>}

      <div className="historyCount hint">
        {loading ? "Loading..." : `${appointments.length} appointment(s)`}
      </div>

      <div className="historyList">
        {!loading && appointments.length === 0 && (
          <div className="apptEmpty"><p className="hint">No appointments found for this period.</p></div>
        )}
        {appointments.map((appt) => (
          <AppointmentRow key={appt.id} appt={appt} token={token} onUpdate={handleUpdate} />
        ))}
      </div>
    </div>
  );
}
