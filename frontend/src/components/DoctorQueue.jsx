import React, { useCallback, useEffect, useRef, useState } from "react";
import { getDoctorQueue, updateAppointmentStatus } from "../api/client";

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function StatusBadge({ status }) {
  const map = {
    booked:    { label: "Waiting",   cls: "statusBooked" },
    completed: { label: "Done",      cls: "statusCompleted" },
    cancelled: { label: "Cancelled", cls: "statusCancelled" },
    no_show:   { label: "No Show",   cls: "statusNoShow" },
  };
  const { label, cls } = map[status] || { label: status, cls: "" };
  return <span className={`statusBadge ${cls}`}>{label}</span>;
}

export default function DoctorQueue({ token }) {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(null);
  const [error, setError] = useState("");
  const intervalRef = useRef(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await getDoctorQueue(token);
      setQueue(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, 60_000);
    return () => clearInterval(intervalRef.current);
  }, [load]);

  async function handleStatus(id, newStatus) {
    setUpdating(id);
    try {
      await updateAppointmentStatus(token, id, newStatus);
      await load();
    } catch (err) {
      alert(`Update failed: ${err.message}`);
    } finally {
      setUpdating(null);
    }
  }

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  const waiting   = queue.filter((a) => a.status === "booked").length;
  const completed = queue.filter((a) => a.status === "completed").length;

  return (
    <div className="queuePanel surfaceCard">
      <div className="queueHeader">
        <div>
          <h2>Today's Queue</h2>
          <p className="hint">{today}</p>
        </div>
        <div className="queueStats">
          <span className="queueStat"><strong>{queue.length}</strong> total</span>
          <span className="queueStat statusBooked"><strong>{waiting}</strong> waiting</span>
          <span className="queueStat statusCompleted"><strong>{completed}</strong> done</span>
          <button onClick={load} disabled={loading} className="refreshBtn">
            {loading ? "..." : "Refresh"}
          </button>
        </div>
      </div>

      {error && <p className="authError">{error}</p>}

      {!loading && queue.length === 0 && (
        <div className="apptEmpty">
          <p className="hint">No appointments scheduled for today.</p>
        </div>
      )}

      <div className="queueList">
        {queue.map((appt) => (
          <div key={appt.id} className={`queueCard surfaceCard ${appt.status !== "booked" ? "queueCardDone" : ""}`}>
            <div className="queueCardLeft">
              <div className="queueTime">{formatTime(appt.start_time)}</div>
              <div className="queueTimeTo">{formatTime(appt.end_time)}</div>
            </div>

            <div className="queueCardBody">
              <div className="queuePatientName">{appt.patient_name}</div>
              <div className="queuePatientEmail hint">{appt.patient_email}</div>
              <div className="queueSymptoms">
                <span className="apptMetaIcon">🩺</span> {appt.symptoms}
              </div>
            </div>

            <div className="queueCardRight">
              <StatusBadge status={appt.status} />
              {appt.status === "booked" && (
                <div className="queueActions">
                  <button
                    className="queueActionBtn complete"
                    disabled={updating === appt.id}
                    onClick={() => handleStatus(appt.id, "completed")}
                  >
                    ✓ Done
                  </button>
                  <button
                    className="queueActionBtn noshow"
                    disabled={updating === appt.id}
                    onClick={() => handleStatus(appt.id, "no_show")}
                  >
                    ✗ No Show
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
