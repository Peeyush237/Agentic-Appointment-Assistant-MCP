import React, { useCallback, useEffect, useState } from "react";
import { addAdminDoctor, getAdminDoctors, updateAdminDoctor } from "../api/client";

const SPECIALIZATIONS = [
  "General Physician", "Cardiologist", "Pediatrician", "Dermatologist",
  "Orthopedic Surgeon", "Gynecologist", "Psychiatrist", "Dentist",
  "Ophthalmologist", "ENT Specialist",
];

export default function AdminDoctors({ token }) {
  const [doctors, setDoctors]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");
  const [success, setSuccess]   = useState("");
  const [editId, setEditId]     = useState(null);
  const [editName, setEditName] = useState("");
  const [editSpec, setEditSpec] = useState("");
  const [newName, setNewName]   = useState("");
  const [newSpec, setNewSpec]   = useState(SPECIALIZATIONS[0]);
  const [showAdd, setShowAdd]   = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDoctors(await getAdminDoctors(token));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  function flash(msg) { setSuccess(msg); setTimeout(() => setSuccess(""), 3500); }

  function startEdit(d) {
    setEditId(d.id);
    setEditName(d.name);
    setEditSpec(d.specialization);
  }

  async function saveEdit() {
    setSaving(true);
    try {
      const updated = await updateAdminDoctor(token, editId, { name: editName, specialization: editSpec });
      setDoctors((prev) => prev.map((d) => (d.id === editId ? updated : d)));
      setEditId(null);
      flash("Doctor updated.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(d) {
    setSaving(true);
    try {
      const updated = await updateAdminDoctor(token, d.id, { is_active: !d.is_active });
      setDoctors((prev) => prev.map((x) => (x.id === d.id ? updated : x)));
      flash(`Dr. ${d.name} ${!d.is_active ? "activated" : "deactivated"}.`);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleAdd() {
    if (!newName.trim()) { setError("Name is required."); return; }
    setSaving(true);
    try {
      const created = await addAdminDoctor(token, { name: newName.trim(), specialization: newSpec });
      setDoctors((prev) => [...prev, created]);
      setNewName("");
      setNewSpec(SPECIALIZATIONS[0]);
      setShowAdd(false);
      flash(`${created.name} added. Login: dr.${created.name.replace(/^dr\.?\s*/i,"").replace(/\s+/g,"").toLowerCase()}@... / CityName_ClinicName_${created.id}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="adminDoctorsPanel surfaceCard">
      <div className="adminPanelHeader">
        <h2>Manage Doctors</h2>
        <button onClick={() => setShowAdd((v) => !v)} disabled={saving}>
          {showAdd ? "Cancel" : "+ Add Doctor"}
        </button>
      </div>

      {error   && <p className="authError">{error}</p>}
      {success && <p className="successMsg">{success}</p>}

      {showAdd && (
        <div className="adminAddForm surfaceCard">
          <h3>New Doctor</h3>
          <div className="adminAddRow">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Full name e.g. Dr. Khan"
              disabled={saving}
            />
            <select value={newSpec} onChange={(e) => setNewSpec(e.target.value)} disabled={saving}>
              {SPECIALIZATIONS.map((s) => <option key={s}>{s}</option>)}
            </select>
            <button onClick={handleAdd} disabled={saving || !newName.trim()}>
              {saving ? "Adding..." : "Add"}
            </button>
          </div>
          <p className="hint">A login account will be created automatically with the formula credentials.</p>
        </div>
      )}

      {loading ? (
        <p className="hint">Loading doctors...</p>
      ) : (
        <div className="adminTable">
          <div className="adminTableHeader">
            <span>Name</span>
            <span>Specialization</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
          {doctors.map((d) => (
            <div key={d.id} className={`adminTableRow ${!d.is_active ? "adminRowInactive" : ""}`}>
              {editId === d.id ? (
                <>
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} disabled={saving} />
                  <select value={editSpec} onChange={(e) => setEditSpec(e.target.value)} disabled={saving}>
                    {SPECIALIZATIONS.map((s) => <option key={s}>{s}</option>)}
                  </select>
                  <span />
                  <div className="adminRowActions">
                    <button onClick={saveEdit} disabled={saving}>Save</button>
                    <button onClick={() => setEditId(null)} disabled={saving}>Cancel</button>
                  </div>
                </>
              ) : (
                <>
                  <span className="adminDoctorName">{d.name}</span>
                  <span className="hint">{d.specialization}</span>
                  <span>
                    <span className={`statusBadge ${d.is_active !== false ? "statusCompleted" : "statusCancelled"}`}>
                      {d.is_active !== false ? "Active" : "Inactive"}
                    </span>
                  </span>
                  <div className="adminRowActions">
                    <button onClick={() => startEdit(d)} disabled={saving}>Edit</button>
                    <button
                      className={d.is_active !== false ? "apptCancelBtn" : ""}
                      onClick={() => toggleActive(d)}
                      disabled={saving}
                    >
                      {d.is_active !== false ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
