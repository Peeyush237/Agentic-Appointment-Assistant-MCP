from __future__ import annotations

import json
from datetime import datetime, timedelta
from difflib import get_close_matches
from typing import Any
from zoneinfo import ZoneInfo

from dateutil import parser
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select

from app.core.integrations import create_google_calendar_event, send_doctor_notification, send_patient_email
from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Appointment, City, Clinic, Doctor, DoctorAvailability

router = APIRouter()

SLOT_MINUTES = 30


# ─── helpers ────────────────────────────────────────────────────────────────

def _normalize_period(period: str) -> str:
    key = (period or "").lower().strip()
    if key in {"morning", "afternoon", "full_day"}:
        return key
    if key == "evening":
        return "afternoon"
    return "full_day"


def _normalize_doctor_name(name: str) -> str:
    n = name.lower().strip()
    for prefix in ("dr.", "dr"):
        if n.startswith(prefix):
            n = n[len(prefix):].strip()
            break
    return n


def _get_doctor(db, doctor_name: str) -> Doctor | None:
    # 1. Exact case-insensitive
    doctor = db.scalar(select(Doctor).where(Doctor.name.ilike(doctor_name)))
    if doctor:
        return doctor

    all_doctors = db.scalars(select(Doctor)).all()
    if not all_doctors:
        return None

    # 2. Auto-add "Dr. " prefix
    if not doctor_name.lower().strip().startswith("dr"):
        doctor = db.scalar(select(Doctor).where(Doctor.name.ilike(f"Dr. {doctor_name.strip()}")))
        if doctor:
            return doctor

    # 3. Fuzzy on normalized names
    norm_search = _normalize_doctor_name(doctor_name)
    norm_names = [_normalize_doctor_name(d.name) for d in all_doctors]

    for i, n in enumerate(norm_names):
        if n == norm_search:
            return all_doctors[i]

    matches = get_close_matches(norm_search, norm_names, n=1, cutoff=0.5)
    if matches:
        return all_doctors[norm_names.index(matches[0])]

    # 4. Substring fallback
    for d in all_doctors:
        if norm_search in d.name.lower():
            return d

    return None


def _build_slots_from_availability(
    availability: list[DoctorAvailability],
    base_day: datetime,
    period: str,
) -> list[datetime]:
    period_key = _normalize_period(period)
    slots: list[datetime] = []
    for avail in availability:
        if period_key == "morning" and avail.start_hour >= 14:
            continue
        if period_key == "afternoon" and avail.end_hour <= 13:
            continue

        cur = base_day.replace(hour=avail.start_hour, minute=avail.start_minute, second=0, microsecond=0)
        end = base_day.replace(hour=avail.end_hour, minute=avail.end_minute, second=0, microsecond=0)
        while cur < end:
            if period_key == "morning" and cur.hour >= 14:
                break
            if period_key == "afternoon" and cur.hour < 14:
                cur += timedelta(minutes=SLOT_MINUTES)
                continue
            slots.append(cur)
            cur += timedelta(minutes=SLOT_MINUTES)
    return slots


def _validate_slot_for_doctor(db, doctor_id: int, start_time: datetime) -> bool:
    if start_time.minute not in {0, 30} or start_time.second != 0:
        return False
    availability = db.scalars(
        select(DoctorAvailability).where(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.day_of_week == start_time.weekday(),
        )
    ).all()
    for avail in availability:
        w_start = start_time.replace(hour=avail.start_hour, minute=avail.start_minute, second=0, microsecond=0)
        w_end = start_time.replace(hour=avail.end_hour, minute=avail.end_minute, second=0, microsecond=0)
        if w_start <= start_time < w_end:
            return True
    return False


def _current_time_payload() -> dict[str, Any]:
    timezone_name = settings.google_timezone or "UTC"
    try:
        now = datetime.now(ZoneInfo(timezone_name))
    except Exception:
        timezone_name = "UTC"
        now = datetime.now(ZoneInfo("UTC"))
    return {
        "ok": True,
        "timezone": timezone_name,
        "now_iso": now.isoformat(),
        "day_of_week": now.strftime("%A"),
        "date": now.date().isoformat(),
        "time_24h": now.strftime("%H:%M:%S"),
        "message": "Current server date and time",
    }


# ─── MCP tool handlers ──────────────────────────────────────────────────────

async def _tool_get_current_datetime(arguments: dict[str, Any]) -> dict[str, Any]:
    return _current_time_payload()


async def _tool_list_cities(arguments: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        cities = db.scalars(select(City).where(City.is_active.is_(True)).order_by(City.name)).all()
        return {
            "ok": True,
            "cities": [{"name": c.name, "state": c.state} for c in cities],
            "message": f"{len(cities)} cities available",
        }


async def _tool_list_clinics_in_city(arguments: dict[str, Any]) -> dict[str, Any]:
    city_name = (arguments.get("city_name") or "").strip()
    with SessionLocal() as db:
        city = db.scalar(select(City).where(City.name.ilike(city_name), City.is_active.is_(True)))
        if not city:
            # Fuzzy match city name
            all_cities = db.scalars(select(City).where(City.is_active.is_(True))).all()
            names_lower = [c.name.lower() for c in all_cities]
            matches = get_close_matches(city_name.lower(), names_lower, n=1, cutoff=0.55)
            if matches:
                city = all_cities[names_lower.index(matches[0])]
            else:
                return {"ok": False, "message": f"City '{city_name}' not found. Call list_cities to see options."}

        clinics = db.scalars(
            select(Clinic)
            .where(Clinic.city_id == city.id, Clinic.is_active.is_(True))
            .order_by(Clinic.name)
        ).all()
        return {
            "ok": True,
            "city": city.name,
            "state": city.state,
            "clinics": [
                {"id": c.id, "name": c.name, "address": c.address, "phone": c.phone}
                for c in clinics
            ],
            "message": f"{len(clinics)} clinic(s) in {city.name}",
        }


async def _tool_list_doctors_in_clinic(arguments: dict[str, Any]) -> dict[str, Any]:
    clinic_id = arguments.get("clinic_id")
    clinic_name = (arguments.get("clinic_name") or "").strip()
    with SessionLocal() as db:
        if clinic_id:
            clinic = db.get(Clinic, int(clinic_id))
        else:
            clinic = db.scalar(select(Clinic).where(Clinic.name.ilike(f"%{clinic_name}%")))
        if not clinic:
            return {"ok": False, "message": "Clinic not found. Call list_clinics_in_city first."}

        doctors = db.scalars(
            select(Doctor).where(Doctor.clinic_id == clinic.id).order_by(Doctor.name)
        ).all()
        return {
            "ok": True,
            "clinic_id": clinic.id,
            "clinic_name": clinic.name,
            "doctors": [{"name": d.name, "specialization": d.specialization} for d in doctors],
            "message": f"{len(doctors)} doctor(s) at {clinic.name}",
        }


async def _tool_list_doctors(arguments: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        doctors = db.scalars(select(Doctor)).all()
        return {
            "ok": True,
            "doctors": [{"name": d.name, "specialization": d.specialization} for d in doctors],
            "message": f"Found {len(doctors)} doctor(s)",
        }


async def _tool_check_doctor_availability(arguments: dict[str, Any]) -> dict[str, Any]:
    doctor_name = arguments.get("doctor_name", "")
    date = arguments.get("date", datetime.now().date().isoformat())
    period = _normalize_period(arguments.get("period", "full_day"))

    with SessionLocal() as db:
        doctor = _get_doctor(db, doctor_name)
        if not doctor:
            return {"ok": False, "message": f"Doctor not found: {doctor_name}"}

        base_day = parser.parse(date).replace(second=0, microsecond=0)
        day_of_week = base_day.weekday()

        availability = db.scalars(
            select(DoctorAvailability)
            .where(
                DoctorAvailability.doctor_id == doctor.id,
                DoctorAvailability.day_of_week == day_of_week,
            )
            .order_by(DoctorAvailability.start_hour)
        ).all()

        if not availability:
            return {
                "ok": True,
                "doctor_name": doctor.name,
                "date": base_day.date().isoformat(),
                "available_slots": [],
                "message": "Doctor is not available on this day.",
            }

        day_start = base_day.replace(hour=0, minute=0)
        day_end = day_start + timedelta(days=1)

        occupied = {
            row.start_time.replace(second=0, microsecond=0)
            for row in db.scalars(
                select(Appointment).where(
                    and_(
                        Appointment.doctor_id == doctor.id,
                        Appointment.start_time >= day_start,
                        Appointment.start_time < day_end,
                        Appointment.status != "cancelled",
                    )
                )
            ).all()
        }

        all_slots = _build_slots_from_availability(availability, base_day, period)
        slots = [
            {
                "start_time": cur.isoformat(),
                "end_time": (cur + timedelta(minutes=SLOT_MINUTES)).isoformat(),
            }
            for cur in all_slots
            if cur not in occupied
        ]

        clinic_name = doctor.clinic.name if doctor.clinic else None
        return {
            "ok": True,
            "doctor_name": doctor.name,
            "clinic": clinic_name,
            "date": base_day.date().isoformat(),
            "period": period,
            "available_slots": slots,
            "message": f"Found {len(slots)} available slot(s)",
        }


async def _tool_book_appointment(arguments: dict[str, Any]) -> dict[str, Any]:
    doctor_name = arguments.get("doctor_name", "")
    patient_name = arguments.get("patient_name", "Patient")
    patient_email = arguments.get("patient_email", "patient@example.com")
    symptoms = arguments.get("symptoms", "general")
    start_time_raw = arguments.get("start_time")

    if not start_time_raw:
        return {"ok": False, "message": "start_time is required"}

    start_time = parser.parse(start_time_raw).replace(second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=SLOT_MINUTES)

    with SessionLocal() as db:
        doctor = _get_doctor(db, doctor_name)
        if not doctor:
            return {"ok": False, "message": f"Doctor not found: {doctor_name}"}

        if not _validate_slot_for_doctor(db, doctor.id, start_time):
            return {
                "ok": False,
                "message": "This slot is outside the doctor's available hours. Call check_doctor_availability first.",
            }

        collision = db.scalar(
            select(Appointment).where(
                and_(
                    Appointment.doctor_id == doctor.id,
                    Appointment.start_time == start_time,
                    Appointment.status != "cancelled",
                )
            )
        )
        if collision:
            return {"ok": False, "message": "Slot no longer available. Please choose another."}

        calendar = await create_google_calendar_event(
            summary=f"{doctor.name} with {patient_name}",
            description=f"Symptoms: {symptoms}",
            start_time=start_time,
            end_time=end_time,
            attendee_email=patient_email,
        )

        appt = Appointment(
            doctor_id=doctor.id,
            clinic_id=doctor.clinic_id,
            patient_name=patient_name,
            patient_email=patient_email,
            symptoms=symptoms,
            status="booked",
            start_time=start_time,
            end_time=end_time,
            calendar_event_id=calendar.get("event_id"),
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)

        booking_message = "Appointment booked"
        if calendar.get("mode") == "error":
            booking_message = "Appointment booked (Google Calendar sync failed)"

        clinic_name = doctor.clinic.name if doctor.clinic else None
        return {
            "ok": True,
            "appointment_id": appt.id,
            "doctor_name": doctor.name,
            "clinic_name": clinic_name,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "calendar": calendar,
            "message": booking_message,
        }


async def _tool_send_patient_email(arguments: dict[str, Any]) -> dict[str, Any]:
    patient_email = arguments.get("patient_email")
    patient_name = arguments.get("patient_name", "Patient")
    doctor_name = arguments.get("doctor_name", "Doctor")
    start_time = arguments.get("start_time", "")

    if not patient_email:
        return {"ok": False, "message": "patient_email is required"}

    subject = f"Appointment Confirmation with {doctor_name}"
    body = (
        f"Hello {patient_name},\n\n"
        f"Your appointment with {doctor_name} is confirmed for {start_time}.\n"
        f"Please arrive 10 minutes early.\n\n"
        "Thanks,\nClinic"
    )
    sent = await send_patient_email(patient_email, subject, body)
    return {"ok": True, "delivery": sent, "message": "Patient email sent"}


async def _tool_list_patient_appointments(arguments: dict[str, Any]) -> dict[str, Any]:
    patient_email = (arguments.get("patient_email") or "").strip()
    if not patient_email:
        return {"ok": False, "message": "patient_email is required"}

    now = datetime.now()
    with SessionLocal() as db:
        appointments = db.scalars(
            select(Appointment).where(
                Appointment.patient_email.ilike(patient_email),
                Appointment.start_time >= now,
                Appointment.status != "cancelled",
            ).order_by(Appointment.start_time)
        ).all()

        result = []
        for appt in appointments:
            doctor = db.get(Doctor, appt.doctor_id)
            clinic = db.get(Clinic, appt.clinic_id) if appt.clinic_id else None
            result.append({
                "id": appt.id,
                "doctor_name": doctor.name if doctor else "Unknown",
                "clinic_name": clinic.name if clinic else None,
                "start_time": appt.start_time.isoformat(),
                "end_time": appt.end_time.isoformat(),
                "symptoms": appt.symptoms,
                "status": appt.status,
            })
        return {
            "ok": True,
            "appointments": result,
            "count": len(result),
            "message": f"{len(result)} upcoming appointment(s) found",
        }


async def _tool_cancel_appointment(arguments: dict[str, Any]) -> dict[str, Any]:
    appointment_id = arguments.get("appointment_id")
    if not appointment_id:
        return {"ok": False, "message": "appointment_id is required"}

    with SessionLocal() as db:
        appt = db.get(Appointment, int(appointment_id))
        if not appt:
            return {"ok": False, "message": f"Appointment {appointment_id} not found"}
        if appt.status == "cancelled":
            return {"ok": False, "message": "Appointment is already cancelled"}

        appt.status = "cancelled"
        db.commit()

        doctor = db.get(Doctor, appt.doctor_id)
        return {
            "ok": True,
            "appointment_id": appt.id,
            "doctor_name": doctor.name if doctor else "Unknown",
            "start_time": appt.start_time.isoformat(),
            "message": "Appointment cancelled successfully",
        }


async def _tool_get_doctor_report_stats(arguments: dict[str, Any]) -> dict[str, Any]:
    doctor_name = arguments.get("doctor_name", "Dr. Ahuja")
    timeframe = arguments.get("timeframe", "today")
    symptom = arguments.get("symptom")

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if timeframe == "yesterday":
        start, end = today_start - timedelta(days=1), today_start
    elif timeframe == "tomorrow":
        start, end = today_start + timedelta(days=1), today_start + timedelta(days=2)
    elif timeframe == "today_and_tomorrow":
        start, end = today_start, today_start + timedelta(days=2)
    else:
        start, end = today_start, today_start + timedelta(days=1)

    with SessionLocal() as db:
        doctor = _get_doctor(db, doctor_name)
        if not doctor:
            return {"ok": False, "message": f"Doctor not found: {doctor_name}"}

        stmt = select(func.count(Appointment.id)).where(
            and_(
                Appointment.doctor_id == doctor.id,
                Appointment.start_time >= start,
                Appointment.start_time < end,
                Appointment.status != "cancelled",
            )
        )
        if symptom:
            stmt = stmt.where(Appointment.symptoms.ilike(f"%{symptom}%"))

        count = db.scalar(stmt) or 0
        return {
            "ok": True,
            "doctor_name": doctor.name,
            "timeframe": timeframe,
            "symptom": symptom,
            "count": int(count),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "message": f"{count} appointment(s) found",
        }


async def _tool_send_doctor_notification(arguments: dict[str, Any]) -> dict[str, Any]:
    report_text = arguments.get("report_text", "No report text provided")
    sent = await send_doctor_notification(report_text)
    mode = sent.get("mode")
    ok = mode in {"live", "accepted"}
    message = (
        "Doctor notification delivered" if mode == "live"
        else "Doctor notification accepted (delivery pending)" if mode == "accepted"
        else "Doctor notification failed"
    )
    return {"ok": ok, "delivery": sent, "message": message, "target_source": "default_env"}


# ─── TOOLS registry ─────────────────────────────────────────────────────────

TOOLS: dict[str, dict[str, Any]] = {
    "get_current_datetime": {
        "description": "Get current server date, time, day, and timezone.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "handler": _tool_get_current_datetime,
    },
    "list_cities": {
        "description": (
            "List all cities where clinics are available. "
            "Call this first when a user wants to book an appointment."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "handler": _tool_list_cities,
    },
    "list_clinics_in_city": {
        "description": "List all clinics in a given city.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city_name": {"type": "string", "description": "Name of the city, e.g. 'Delhi'"},
            },
            "required": ["city_name"],
        },
        "handler": _tool_list_clinics_in_city,
    },
    "list_doctors_in_clinic": {
        "description": "List doctors in a specific clinic. Use clinic_id from list_clinics_in_city.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "clinic_id": {"type": "integer"},
                "clinic_name": {"type": "string"},
            },
            "required": [],
        },
        "handler": _tool_list_doctors_in_clinic,
    },
    "list_doctors": {
        "description": (
            "List ALL doctors across all clinics. Use when the user mentions a doctor name "
            "(even partial or misspelled) to find the exact canonical name."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "handler": _tool_list_doctors,
    },
    "check_doctor_availability": {
        "description": "Check available 30-minute slots for a doctor on a given date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string"},
                "date": {"type": "string", "description": "ISO date like 2026-04-05"},
                "period": {"type": "string", "enum": ["morning", "afternoon", "evening", "full_day"]},
            },
            "required": ["doctor_name", "date", "period"],
        },
        "handler": _tool_check_doctor_availability,
    },
    "book_appointment": {
        "description": "Book an appointment and create a calendar event.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string"},
                "patient_name": {"type": "string"},
                "patient_email": {"type": "string"},
                "symptoms": {"type": "string"},
                "start_time": {"type": "string", "description": "ISO datetime"},
            },
            "required": ["doctor_name", "patient_name", "patient_email", "start_time"],
        },
        "handler": _tool_book_appointment,
    },
    "send_patient_email": {
        "description": "Send appointment confirmation email to patient.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_email": {"type": "string"},
                "patient_name": {"type": "string"},
                "doctor_name": {"type": "string"},
                "start_time": {"type": "string"},
            },
            "required": ["patient_email", "patient_name", "doctor_name", "start_time"],
        },
        "handler": _tool_send_patient_email,
    },
    "list_patient_appointments": {
        "description": "Fetch upcoming appointments for a patient by email. Use for view/reschedule/cancel flows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_email": {"type": "string"},
            },
            "required": ["patient_email"],
        },
        "handler": _tool_list_patient_appointments,
    },
    "cancel_appointment": {
        "description": "Cancel an appointment by its ID. Get the ID from list_patient_appointments.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer"},
            },
            "required": ["appointment_id"],
        },
        "handler": _tool_cancel_appointment,
    },
    "get_doctor_report_stats": {
        "description": "Get appointment count for a doctor within a timeframe, with optional symptom filter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string"},
                "timeframe": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "yesterday", "today_and_tomorrow"],
                },
                "symptom": {"type": "string"},
            },
            "required": ["doctor_name", "timeframe"],
        },
        "handler": _tool_get_doctor_report_stats,
    },
    "send_doctor_notification": {
        "description": "Send a report notification to the doctor via WhatsApp.",
        "inputSchema": {
            "type": "object",
            "properties": {"report_text": {"type": "string"}},
            "required": ["report_text"],
        },
        "handler": _tool_send_doctor_notification,
    },
}

# ─── PROMPTS ────────────────────────────────────────────────────────────────

PROMPTS: dict[str, str] = {
    "patient_agent_system": (
        "You are a patient appointment assistant for a multi-clinic, pan-India booking system.\n\n"

        "BOOKING FLOW:\n"
        "1. When the user wants to book, call list_cities to show available cities.\n"
        "2. After the user picks a city, call list_clinics_in_city(city_name=...) to show clinics.\n"
        "3. After the user picks a clinic, call list_doctors_in_clinic(clinic_id=...) to show doctors.\n"
        "4. SYMPTOM TRIAGE — if the user describes symptoms instead of naming a doctor, "
        "map to the right specialization and recommend the doctor from the list:\n"
        "   fever/cold/general illness → General Physician\n"
        "   child illness → Pediatrician\n"
        "   chest pain/high BP/heart → Cardiologist\n"
        "   skin rash/acne/eczema → Dermatologist\n"
        "   bone/joint/back pain → Orthopedic Surgeon\n"
        "   pregnancy/women's health → Gynecologist\n"
        "   anxiety/depression/mental health → Psychiatrist\n"
        "   tooth/dental → Dentist\n"
        "   eye/vision problems → Ophthalmologist\n"
        "   ear/nose/throat → ENT Specialist\n"
        "5. Once doctor is selected, call check_doctor_availability then book_appointment.\n"
        "6. After booking, call send_patient_email to send confirmation.\n\n"

        "RESCHEDULE / CANCEL / VIEW:\n"
        "- To view appointments: call list_patient_appointments(patient_email=...).\n"
        "- To cancel: call cancel_appointment(appointment_id=...).\n"
        "- To reschedule: cancel the old one then book a new slot.\n\n"

        "FUZZY DOCTOR NAMES:\n"
        "When user mentions any doctor name (partial, misspelled, without 'Dr.' prefix), "
        "call list_doctors first to get all canonical names and identify the closest match.\n\n"

        "RULES:\n"
        "- For current date/time: call get_current_datetime.\n"
        "- Never claim a slot available without calling check_doctor_availability.\n"
        "- Never confirm booking without book_appointment returning ok=true.\n"
        "- Use conversation history to avoid asking for name/email/symptoms again.\n"
        "- Keep responses short and clear.\n"
        "- Remind patients to check their Spam/Junk folder for confirmation emails."
    ),
    "doctor_agent_system": (
        "You are a doctor reporting assistant for a multi-clinic system. "
        "Use MCP tools to gather appointment statistics and send reports. "
        "For current date/time call get_current_datetime. "
        "Use get_doctor_report_stats to fetch stats and send_doctor_notification to deliver the report."
    ),
}


# ─── MCP HTTP handler ───────────────────────────────────────────────────────

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] = {}


def _mcp_result(req_id: int | str | None, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _mcp_error(req_id: int | str | None, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


@router.post("")
async def mcp_handler(req: MCPRequest):
    if req.method == "initialize":
        return _mcp_result(req.id, {"name": "appointment-mcp-server", "version": "2.0.0"})

    if req.method == "tools/list":
        tools = [
            {"name": name, "description": conf["description"], "inputSchema": conf["inputSchema"]}
            for name, conf in TOOLS.items()
        ]
        return _mcp_result(req.id, {"tools": tools})

    if req.method == "tools/call":
        name = req.params.get("name", "")
        arguments = req.params.get("arguments", {})
        if name not in TOOLS:
            return _mcp_error(req.id, -32601, f"Unknown tool: {name}")
        try:
            result = await TOOLS[name]["handler"](arguments)
            return _mcp_result(req.id, {"content": [{"type": "text", "text": json.dumps(result)}]})
        except Exception as exc:  # noqa: BLE001
            return _mcp_error(req.id, -32000, str(exc))

    if req.method == "resources/list":
        return _mcp_result(req.id, {
            "resources": [{
                "uri": "resource://doctors",
                "name": "Doctors",
                "description": "All doctors across all clinics",
                "mimeType": "application/json",
            }]
        })

    if req.method == "resources/read":
        uri = req.params.get("uri")
        if uri != "resource://doctors":
            return _mcp_error(req.id, -32602, "Unknown resource URI")
        with SessionLocal() as db:
            doctors = db.scalars(select(Doctor)).all()
            payload = [{"name": d.name, "specialization": d.specialization} for d in doctors]
        return _mcp_result(req.id, {
            "contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(payload)}]
        })

    if req.method == "prompts/list":
        return _mcp_result(req.id, {
            "prompts": [{"name": name, "description": "Agent system prompt"} for name in PROMPTS]
        })

    if req.method == "prompts/get":
        name = req.params.get("name")
        if name not in PROMPTS:
            return _mcp_error(req.id, -32602, f"Unknown prompt: {name}")
        return _mcp_result(req.id, {
            "description": "Prompt loaded",
            "messages": [{"role": "system", "content": {"type": "text", "text": PROMPTS[name]}}],
        })

    return _mcp_error(req.id, -32601, f"Unknown method: {req.method}")
