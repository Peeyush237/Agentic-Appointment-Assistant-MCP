import React, { useCallback, useEffect, useState } from "react";
import { getAdminAppointments, getAdminDoctors } from "../api/client";

function fmt(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

const STATUS_LABELS = {
  booked:    { label: "Booked",    cls: "statusBooked"    },
  completed: { label: "Completed", cls: "statusCompleted" },
  cancelled: { label: "Cancelled", cls: "statusCancelled" },
  no_show:   { label: "No Show",   cls: "statusNoShow"    },
};

function StatusBadge({ status }) {
  const { label, cls } = STATUS_LABELS[status] || { label: status, cls: "" };
  return <span className={`statusBadge ${cls}`}>{label}</span>;
}

export default function AdminAppointments({ token }) {
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors]           = useState([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState("");

  const [filterDoctor, setFilterDoctor] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterDate,   setFilterDate]   = useState("");
  const [filterDays,   setFilterDays]   = useState(7);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filterDoctor) params.doctor_id = filterDoctor;
      if (filterStatus) params.status    = filterStatus;
      if (filterDate)   params.date      = filterDate;
      else              params.days      = filterDays;
      setAppointments(await getAdminAppointments(token, params));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, filterDoctor, filterStatus, filterDate, filterDays]);

  useEffect(() => {
    getAdminDoctors(token).then(setDoctors).catch(() => {});
  }, [token]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="adminApptPanel surfaceCard">
      <div className="adminPanelHeader">
        <h2>Appointments</h2>
        <button className="refreshBtn" onClick={load} disabled={loading}>Refresh</button>
      </div>

      <div className="adminFilters">
        <select value={filterDoctor} onChange={(e) => setFilterDoctor(e.target.value)}>
          <option value="">All Doctors</option>
          {doctors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>

        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="booked">Booked</option>
          <option value="completed">Completed</option>
          <option value="no_show">No Show</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <input
          type="date"
          value={filterDate}
          onChange={(e) => setFilterDate(e.target.value)}
          title="Filter by specific date"
        />

        {!filterDate && (
          <select value={filterDays} onChange={(e) => setFilterDays(Number(e.target.value))}>
            <option value={1}>Today</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 3 months</option>
          </select>
        )}
      </div>

      {error && <p className="authError">{error}</p>}

      <div className="adminApptCount hint">
        {loading ? "Loading..." : `${appointments.length} appointment(s)`}
      </div>

      <div className="adminApptTable">
        {!loading && appointments.length === 0 && (
          <p className="hint" style={{ padding: "20px" }}>No appointments found for the selected filters.</p>
        )}
        {appointments.map((appt) => (
          <div key={appt.id} className="adminApptRow surfaceCard">
            <div className="adminApptRowLeft">
              <div className="adminApptTime">{fmt(appt.start_time)}</div>
              <StatusBadge status={appt.status} />
            </div>

            <div className="adminApptRowBody">
              <div className="adminApptPatient">{appt.patient_name}</div>
              <div className="hint">{appt.patient_email}</div>
              <div className="hint"><span className="apptMetaIcon">🩺</span> {appt.symptoms}</div>
            </div>

            <div className="adminApptRowRight">
              <div className="adminApptDoctor">{appt.doctor_name}</div>
              <div className="hint">{appt.specialization}</div>
              {appt.notes && (
                <div className="adminApptNotes hint">📝 {appt.notes}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
