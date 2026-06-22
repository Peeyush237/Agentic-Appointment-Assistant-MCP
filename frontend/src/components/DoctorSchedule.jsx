import React, { useCallback, useEffect, useState } from "react";
import { deleteScheduleWindow, getDoctorSchedule, replaceDoctorSchedule } from "../api/client";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function pad(n) { return String(n).padStart(2, "0"); }
function fmtTime(h, m) { return `${pad(h)}:${pad(m)}`; }

function WindowRow({ win, onDelete, saving }) {
  return (
    <div className="scheduleWindowRow">
      <span className="scheduleWindowTime">
        {fmtTime(win.start_hour, win.start_minute)} – {fmtTime(win.end_hour, win.end_minute)}
      </span>
      <button className="scheduleDeleteBtn" disabled={saving} onClick={() => onDelete(win.id)}>✕</button>
    </div>
  );
}

const DEFAULT_WINDOWS = [
  { day_of_week: 0, start_hour: 9,  start_minute: 0, end_hour: 13, end_minute: 0 },
  { day_of_week: 0, start_hour: 14, start_minute: 0, end_hour: 18, end_minute: 0 },
  { day_of_week: 1, start_hour: 9,  start_minute: 0, end_hour: 13, end_minute: 0 },
  { day_of_week: 1, start_hour: 14, start_minute: 0, end_hour: 18, end_minute: 0 },
  { day_of_week: 2, start_hour: 9,  start_minute: 0, end_hour: 13, end_minute: 0 },
  { day_of_week: 2, start_hour: 14, start_minute: 0, end_hour: 18, end_minute: 0 },
  { day_of_week: 3, start_hour: 9,  start_minute: 0, end_hour: 13, end_minute: 0 },
  { day_of_week: 3, start_hour: 14, start_minute: 0, end_hour: 18, end_minute: 0 },
  { day_of_week: 4, start_hour: 9,  start_minute: 0, end_hour: 13, end_minute: 0 },
  { day_of_week: 4, start_hour: 14, start_minute: 0, end_hour: 18, end_minute: 0 },
];

export default function DoctorSchedule({ token }) {
  const [windows, setWindows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState("");
  const [success, setSuccess] = useState("");

  // add-window form
  const [addDay,        setAddDay]        = useState(0);
  const [addStartHour,  setAddStartHour]  = useState(9);
  const [addStartMin,   setAddStartMin]   = useState(0);
  const [addEndHour,    setAddEndHour]    = useState(13);
  const [addEndMin,     setAddEndMin]     = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDoctorSchedule(token);
      setWindows(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function handleDelete(winId) {
    setSaving(true);
    try {
      await deleteScheduleWindow(token, winId);
      setWindows((prev) => prev.filter((w) => w.id !== winId));
      flash("Window removed.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleAddWindow() {
    if (addEndHour < addStartHour || (addEndHour === addStartHour && addEndMin <= addStartMin)) {
      setError("End time must be after start time.");
      return;
    }
    const newWin = {
      day_of_week: addDay, start_hour: addStartHour, start_minute: addStartMin,
      end_hour: addEndHour, end_minute: addEndMin,
    };
    setSaving(true);
    try {
      const current = [...windows.map((w) => ({
        day_of_week: w.day_of_week, start_hour: w.start_hour, start_minute: w.start_minute,
        end_hour: w.end_hour, end_minute: w.end_minute,
      })), newWin];
      await replaceDoctorSchedule(token, current);
      await load();
      flash("Window added.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (!window.confirm("Reset to default Mon–Fri 9–1 PM and 2–6 PM?")) return;
    setSaving(true);
    try {
      await replaceDoctorSchedule(token, DEFAULT_WINDOWS);
      await load();
      flash("Schedule reset to default.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleClearDay(dayIndex) {
    const remaining = windows
      .filter((w) => w.day_of_week !== dayIndex)
      .map((w) => ({
        day_of_week: w.day_of_week, start_hour: w.start_hour, start_minute: w.start_minute,
        end_hour: w.end_hour, end_minute: w.end_minute,
      }));
    setSaving(true);
    try {
      await replaceDoctorSchedule(token, remaining);
      await load();
      flash(`${DAYS[dayIndex]} cleared.`);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function flash(msg) {
    setSuccess(msg);
    setError("");
    setTimeout(() => setSuccess(""), 3000);
  }

  const byDay = DAYS.map((_, i) => windows.filter((w) => w.day_of_week === i));

  return (
    <div className="schedulePanel surfaceCard">
      <div className="schedulePanelHeader">
        <h2>My Schedule</h2>
        <button className="refreshBtn" onClick={handleReset} disabled={saving || loading}>
          Reset to Default
        </button>
      </div>

      {error   && <p className="authError">{error}</p>}
      {success && <p className="successMsg">{success}</p>}

      {loading ? (
        <p className="hint">Loading schedule...</p>
      ) : (
        <div className="scheduleGrid">
          {DAYS.map((dayName, dayIdx) => (
            <div key={dayIdx} className={`scheduleDayCard surfaceCard ${byDay[dayIdx].length === 0 ? "scheduleDayOff" : ""}`}>
              <div className="scheduleDayHeader">
                <span className="scheduleDayName">{dayName}</span>
                {byDay[dayIdx].length > 0 && (
                  <button className="scheduleClearDayBtn" disabled={saving} onClick={() => handleClearDay(dayIdx)}>
                    Clear
                  </button>
                )}
                {byDay[dayIdx].length === 0 && <span className="scheduleOffBadge">Off</span>}
              </div>
              {byDay[dayIdx].map((win) => (
                <WindowRow key={win.id} win={win} onDelete={handleDelete} saving={saving} />
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="scheduleAddForm surfaceCard">
        <h3>Add Time Window</h3>
        <div className="scheduleAddRow">
          <select value={addDay} onChange={(e) => setAddDay(Number(e.target.value))} disabled={saving}>
            {DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
          </select>
          <label>From</label>
          <input type="number" min={0} max={23} value={addStartHour} onChange={(e) => setAddStartHour(Number(e.target.value))} disabled={saving} className="scheduleTimeInput" />
          <span>:</span>
          <select value={addStartMin} onChange={(e) => setAddStartMin(Number(e.target.value))} disabled={saving}>
            <option value={0}>00</option><option value={30}>30</option>
          </select>
          <label>To</label>
          <input type="number" min={0} max={23} value={addEndHour} onChange={(e) => setAddEndHour(Number(e.target.value))} disabled={saving} className="scheduleTimeInput" />
          <span>:</span>
          <select value={addEndMin} onChange={(e) => setAddEndMin(Number(e.target.value))} disabled={saving}>
            <option value={0}>00</option><option value={30}>30</option>
          </select>
          <button onClick={handleAddWindow} disabled={saving}>Add</button>
        </div>
      </div>
    </div>
  );
}
