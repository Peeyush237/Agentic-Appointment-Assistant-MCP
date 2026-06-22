import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    AdminDashboardResponse,
    AppointmentDetailResponse,
    AppointmentNotesUpdate,
    AppointmentStatusUpdate,
    AuthResponse,
    AvailabilityWindowCreate,
    AvailabilityWindowResponse,
    ChatCreateRequest,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatThreadResponse,
    CityResponse,
    ClinicResponse,
    DoctorCreateRequest,
    DoctorResponse,
    DoctorUpdateRequest,
    HealthResponse,
    LoginRequest,
    QueueItemResponse,
    RegisterRequest,
    ScheduleReplaceRequest,
    UserResponse,
)
from app.core.auth import generate_token, hash_password, token_expiry, token_hash, verify_password
from app.core.agent import agent
from app.db.database import get_db
from app.db.models import (
    Appointment, AuthToken, ChatMessage, ChatThread,
    City, Clinic, Doctor, DoctorAvailability, User,
)
from app.db.seed import admin_email, admin_password, doctor_email, doctor_password

router = APIRouter(prefix="/api", tags=["api"])

_UTC = timezone.utc


# ─── auth helpers ────────────────────────────────────────────────────────────

def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")
    return parts[1].strip()


def _current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    hashed = token_hash(token)
    token_row = db.scalar(select(AuthToken).where(AuthToken.token_hash == hashed))
    if not token_row or token_row.expires_at <= datetime.now(_UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")
    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _require_doctor(user: User = Depends(_current_user)) -> User:
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access only")
    if not user.doctor_profile_id:
        raise HTTPException(status_code=404, detail="Doctor profile not linked to this account")
    return user


def _require_admin(user: User = Depends(_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    if not user.clinic_id:
        raise HTTPException(status_code=404, detail="Clinic not linked to this admin account")
    return user


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, email=user.email, full_name=user.full_name,
        role=user.role, clinic_id=user.clinic_id,
    )


def _appt_to_detail(appt: Appointment, db: Session) -> AppointmentDetailResponse:
    doctor = db.get(Doctor, appt.doctor_id)
    clinic = db.get(Clinic, appt.clinic_id) if appt.clinic_id else None
    city = db.get(City, clinic.city_id) if clinic else None
    return AppointmentDetailResponse(
        id=appt.id,
        doctor_name=doctor.name if doctor else "Unknown",
        specialization=doctor.specialization if doctor else None,
        clinic_name=clinic.name if clinic else None,
        city=city.name if city else None,
        patient_name=appt.patient_name,
        patient_email=appt.patient_email,
        start_time=appt.start_time,
        end_time=appt.end_time,
        symptoms=appt.symptoms,
        status=appt.status,
        notes=appt.notes,
    )


def _thread_history(thread_messages: list[ChatMessage]) -> list[dict]:
    return [
        {"role": msg.sender, "content": msg.content}
        for msg in thread_messages if msg.sender in {"user", "assistant"}
    ]


def _to_thread_response(thread: ChatThread) -> ChatThreadResponse:
    return ChatThreadResponse(
        id=thread.id, role=thread.role, title=thread.title,
        created_at=thread.created_at, updated_at=thread.updated_at,
    )


# ─── public endpoints ────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")


@router.get("/cities", response_model=list[CityResponse])
async def list_cities(db: Session = Depends(get_db)):
    cities = db.scalars(select(City).where(City.is_active.is_(True)).order_by(City.name)).all()
    return [CityResponse(id=c.id, name=c.name, state=c.state) for c in cities]


@router.get("/clinics", response_model=list[ClinicResponse])
async def list_clinics(city: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Clinic).where(Clinic.is_active.is_(True))
    if city:
        city_row = db.scalar(select(City).where(City.name.ilike(city)))
        if city_row:
            stmt = stmt.where(Clinic.city_id == city_row.id)
    clinics = db.scalars(stmt.order_by(Clinic.name)).all()
    return [
        ClinicResponse(id=c.id, name=c.name, city=c.city.name if c.city else "",
                       address=c.address, phone=c.phone)
        for c in clinics
    ]


@router.get("/doctors", response_model=list[DoctorResponse])
async def list_doctors(clinic_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Doctor)
    if clinic_id:
        stmt = stmt.where(Doctor.clinic_id == clinic_id)
    doctors = db.scalars(stmt.order_by(Doctor.name)).all()
    return [
        DoctorResponse(
            id=d.id, name=d.name, specialization=d.specialization,
            clinic_id=d.clinic_id,
            clinic_name=d.clinic.name if d.clinic else None,
            city=d.clinic.city.name if d.clinic and d.clinic.city else None,
            is_active=d.is_active if d.is_active is not None else True,
        )
        for d in doctors
    ]


# ─── auth endpoints ──────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == req.email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=req.email.lower(), full_name=req.full_name.strip(),
        role="patient", password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    raw_token = generate_token()
    db.add(AuthToken(user_id=user.id, token_hash=token_hash(raw_token), expires_at=token_expiry()))
    db.commit()
    return AuthResponse(token=raw_token, user=_to_user_response(user))


@router.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == req.email.lower()))
    if not user or user.role != req.role or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    raw_token = generate_token()
    db.add(AuthToken(user_id=user.id, token_hash=token_hash(raw_token), expires_at=token_expiry()))
    db.commit()
    return AuthResponse(token=raw_token, user=_to_user_response(user))


@router.post("/auth/logout")
async def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    raw = _extract_bearer_token(authorization)
    token_row = db.scalar(select(AuthToken).where(AuthToken.token_hash == token_hash(raw)))
    if token_row:
        db.delete(token_row)
        db.commit()
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(_current_user)):
    return _to_user_response(user)


# ─── chat endpoints ──────────────────────────────────────────────────────────

@router.get("/chats", response_model=list[ChatThreadResponse])
async def list_chats(user: User = Depends(_current_user), db: Session = Depends(get_db)):
    threads = db.scalars(
        select(ChatThread).where(ChatThread.user_id == user.id).order_by(ChatThread.updated_at.desc())
    ).all()
    return [_to_thread_response(t) for t in threads]


@router.post("/chats", response_model=ChatThreadResponse)
async def create_chat(req: ChatCreateRequest, user: User = Depends(_current_user), db: Session = Depends(get_db)):
    default_title = "Doctor Chat" if user.role == "doctor" else "Patient Chat"
    thread = ChatThread(user_id=user.id, role=user.role, title=(req.title or default_title).strip()[:200])
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return _to_thread_response(thread)


@router.get("/chats/{chat_id}/messages", response_model=list[ChatMessageResponse])
async def get_chat_messages(chat_id: str, user: User = Depends(_current_user), db: Session = Depends(get_db)):
    thread = db.scalar(select(ChatThread).where(ChatThread.id == chat_id, ChatThread.user_id == user.id))
    if not thread:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = db.scalars(
        select(ChatMessage).where(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
    ).all()
    return [
        ChatMessageResponse(
            id=msg.id, sender=msg.sender, content=msg.content,
            tool_trace=json.loads(msg.tool_trace_json) if msg.tool_trace_json else None,
            created_at=msg.created_at,
        )
        for msg in messages
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user: User = Depends(_current_user), db: Session = Depends(get_db)):
    thread = None
    if req.chat_id:
        thread = db.scalar(select(ChatThread).where(ChatThread.id == req.chat_id, ChatThread.user_id == user.id))
        if not thread:
            raise HTTPException(status_code=404, detail="Chat not found")
    else:
        default_title = "Doctor Chat" if user.role == "doctor" else "Patient Chat"
        thread = ChatThread(user_id=user.id, role=user.role, title=default_title)
        db.add(thread)
        db.commit()
        db.refresh(thread)

    thread_messages = db.scalars(
        select(ChatMessage).where(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
    ).all()
    db.add(ChatMessage(thread_id=thread.id, sender="user", content=req.message))
    db.commit()

    result = await agent.run(
        role=user.role, user_message=req.message,
        session_id=thread.id, history=_thread_history(thread_messages),
    )

    for trace_item in result.get("tool_trace", []):
        if trace_item.get("tool") == "book_appointment" and trace_item.get("result", {}).get("ok"):
            appt_id = trace_item["result"].get("appointment_id")
            if appt_id:
                appt = db.get(Appointment, appt_id)
                if appt and not appt.user_id:
                    appt.user_id = user.id
                    db.commit()

    db.add(ChatMessage(
        thread_id=thread.id, sender="assistant",
        content=result["answer"], tool_trace_json=json.dumps(result["tool_trace"]),
    ))
    if thread.title in {"Patient Chat", "Doctor Chat", "New Chat"}:
        thread.title = req.message.strip()[:60] or thread.title
    thread.updated_at = datetime.now(_UTC)
    db.commit()
    return ChatResponse(chat_id=thread.id, response=result["answer"], tool_trace=result["tool_trace"])


# ─── patient self-service ────────────────────────────────────────────────────

@router.get("/my-appointments", response_model=list[AppointmentDetailResponse])
async def my_appointments(user: User = Depends(_current_user), db: Session = Depends(get_db)):
    now = datetime.now(_UTC)
    appointments = db.scalars(
        select(Appointment).where(
            and_(
                or_(Appointment.user_id == user.id, Appointment.patient_email == user.email),
                Appointment.start_time >= now,
                Appointment.status != "cancelled",
            )
        ).order_by(Appointment.start_time)
    ).all()
    return [_appt_to_detail(a, db) for a in appointments]


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: int, user: User = Depends(_current_user), db: Session = Depends(get_db)):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.user_id != user.id and appt.patient_email.lower() != user.email.lower():
        raise HTTPException(status_code=403, detail="Not your appointment")
    if appt.status == "cancelled":
        raise HTTPException(status_code=400, detail="Already cancelled")
    appt.status = "cancelled"
    db.commit()
    return {"ok": True, "appointment_id": appt.id}


# ─── doctor queue ─────────────────────────────────────────────────────────────

@router.get("/doctor/queue", response_model=list[QueueItemResponse])
async def doctor_queue(user: User = Depends(_require_doctor), db: Session = Depends(get_db)):
    today_start = datetime.now(_UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    appointments = db.scalars(
        select(Appointment).where(
            and_(
                Appointment.doctor_id == user.doctor_profile_id,
                Appointment.start_time >= today_start,
                Appointment.start_time < today_end,
                Appointment.status != "cancelled",
            )
        ).order_by(Appointment.start_time)
    ).all()
    return [
        QueueItemResponse(
            id=a.id, patient_name=a.patient_name, patient_email=a.patient_email,
            symptoms=a.symptoms, start_time=a.start_time, end_time=a.end_time,
            status=a.status, notes=a.notes,
        )
        for a in appointments
    ]


@router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: int, req: AppointmentStatusUpdate,
    user: User = Depends(_require_doctor), db: Session = Depends(get_db),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.doctor_id != user.doctor_profile_id:
        raise HTTPException(status_code=403, detail="Not your appointment")
    appt.status = req.status
    db.commit()
    return {"ok": True, "appointment_id": appt.id, "status": appt.status}


@router.patch("/appointments/{appointment_id}/notes")
async def update_appointment_notes(
    appointment_id: int, req: AppointmentNotesUpdate,
    user: User = Depends(_require_doctor), db: Session = Depends(get_db),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.doctor_id != user.doctor_profile_id:
        raise HTTPException(status_code=403, detail="Not your appointment")
    appt.notes = req.notes.strip()
    db.commit()
    return {"ok": True, "appointment_id": appt.id}


# ─── doctor schedule ─────────────────────────────────────────────────────────

@router.get("/doctor/schedule", response_model=list[AvailabilityWindowResponse])
async def get_doctor_schedule(user: User = Depends(_require_doctor), db: Session = Depends(get_db)):
    windows = db.scalars(
        select(DoctorAvailability)
        .where(DoctorAvailability.doctor_id == user.doctor_profile_id)
        .order_by(DoctorAvailability.day_of_week, DoctorAvailability.start_hour)
    ).all()
    return [
        AvailabilityWindowResponse(
            id=w.id, day_of_week=w.day_of_week,
            start_hour=w.start_hour, start_minute=w.start_minute,
            end_hour=w.end_hour, end_minute=w.end_minute,
        )
        for w in windows
    ]


@router.put("/doctor/schedule")
async def replace_doctor_schedule(
    req: ScheduleReplaceRequest,
    user: User = Depends(_require_doctor), db: Session = Depends(get_db),
):
    db.query(DoctorAvailability).filter(DoctorAvailability.doctor_id == user.doctor_profile_id).delete()
    for w in req.windows:
        db.add(DoctorAvailability(
            doctor_id=user.doctor_profile_id,
            day_of_week=w.day_of_week,
            start_hour=w.start_hour, start_minute=w.start_minute,
            end_hour=w.end_hour, end_minute=w.end_minute,
        ))
    db.commit()
    return {"ok": True, "windows_saved": len(req.windows)}


@router.post("/doctor/schedule/add", response_model=AvailabilityWindowResponse)
async def add_schedule_window(
    req: AvailabilityWindowCreate,
    user: User = Depends(_require_doctor), db: Session = Depends(get_db),
):
    window = DoctorAvailability(
        doctor_id=user.doctor_profile_id,
        day_of_week=req.day_of_week,
        start_hour=req.start_hour, start_minute=req.start_minute,
        end_hour=req.end_hour, end_minute=req.end_minute,
    )
    db.add(window)
    db.commit()
    db.refresh(window)
    return AvailabilityWindowResponse(
        id=window.id, day_of_week=window.day_of_week,
        start_hour=window.start_hour, start_minute=window.start_minute,
        end_hour=window.end_hour, end_minute=window.end_minute,
    )


@router.delete("/doctor/schedule/{window_id}")
async def delete_schedule_window(
    window_id: int,
    user: User = Depends(_require_doctor), db: Session = Depends(get_db),
):
    window = db.get(DoctorAvailability, window_id)
    if not window or window.doctor_id != user.doctor_profile_id:
        raise HTTPException(status_code=404, detail="Window not found")
    db.delete(window)
    db.commit()
    return {"ok": True}


# ─── doctor appointment history ───────────────────────────────────────────────

@router.get("/doctor/history", response_model=list[AppointmentDetailResponse])
async def doctor_history(
    status_filter: str | None = Query(default=None, alias="status"),
    days: int = Query(default=30),
    user: User = Depends(_require_doctor), db: Session = Depends(get_db),
):
    since = datetime.now(_UTC) - timedelta(days=days)
    stmt = select(Appointment).where(
        Appointment.doctor_id == user.doctor_profile_id,
        Appointment.start_time >= since,
    )
    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)
    appointments = db.scalars(stmt.order_by(Appointment.start_time.desc())).all()
    return [_appt_to_detail(a, db) for a in appointments]


# ─── admin: dashboard ─────────────────────────────────────────────────────────

@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    clinic = db.get(Clinic, user.clinic_id)
    city = db.get(City, clinic.city_id) if clinic else None

    total_doctors = db.scalar(
        select(func.count(Doctor.id)).where(Doctor.clinic_id == user.clinic_id)
    ) or 0

    today_start = datetime.now(_UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    base = select(func.count(Appointment.id)).where(
        Appointment.clinic_id == user.clinic_id,
        Appointment.start_time >= today_start,
        Appointment.start_time < today_end,
    )
    today_total     = db.scalar(base) or 0
    today_pending   = db.scalar(base.where(Appointment.status == "booked")) or 0
    today_completed = db.scalar(base.where(Appointment.status == "completed")) or 0
    today_no_show   = db.scalar(base.where(Appointment.status == "no_show")) or 0
    today_cancelled = db.scalar(base.where(Appointment.status == "cancelled")) or 0

    return AdminDashboardResponse(
        clinic_name=clinic.name if clinic else "",
        city=city.name if city else "",
        total_doctors=total_doctors,
        today_total=today_total,
        today_pending=today_pending,
        today_completed=today_completed,
        today_no_show=today_no_show,
        today_cancelled=today_cancelled,
    )


# ─── admin: doctor management ─────────────────────────────────────────────────

@router.get("/admin/doctors", response_model=list[DoctorResponse])
async def admin_list_doctors(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    doctors = db.scalars(
        select(Doctor).where(Doctor.clinic_id == user.clinic_id).order_by(Doctor.name)
    ).all()
    clinic = db.get(Clinic, user.clinic_id)
    city = db.get(City, clinic.city_id) if clinic else None
    return [
        DoctorResponse(
            id=d.id, name=d.name, specialization=d.specialization,
            clinic_id=d.clinic_id,
            clinic_name=clinic.name if clinic else None,
            city=city.name if city else None,
            is_active=d.is_active if d.is_active is not None else True,
        )
        for d in doctors
    ]


@router.post("/admin/doctors", response_model=DoctorResponse)
async def admin_add_doctor(
    req: DoctorCreateRequest,
    user: User = Depends(_require_admin), db: Session = Depends(get_db),
):
    existing = db.scalar(select(Doctor).where(Doctor.name.ilike(req.name)))
    if existing:
        raise HTTPException(status_code=409, detail="A doctor with that name already exists")

    doctor = Doctor(name=req.name.strip(), specialization=req.specialization.strip(),
                    clinic_id=user.clinic_id, is_active=True)
    db.add(doctor)
    db.flush()

    # Seed default Mon-Fri schedule
    for day in range(5):
        db.add(DoctorAvailability(doctor_id=doctor.id, day_of_week=day, start_hour=9, end_hour=13))
        db.add(DoctorAvailability(doctor_id=doctor.id, day_of_week=day, start_hour=14, end_hour=18))

    # Create login account for new doctor
    clinic = db.get(Clinic, user.clinic_id)
    city = db.get(City, clinic.city_id) if clinic else None
    city_name = city.name if city else "City"
    clinic_name = clinic.name if clinic else "Clinic"

    from app.db.seed import _upsert_user  # noqa: PLC0415
    _upsert_user(
        db,
        email=doctor_email(doctor.name, clinic_name),
        full_name=doctor.name,
        role="doctor",
        password=doctor_password(city_name, clinic_name, doctor.id),
        doctor_profile_id=doctor.id,
    )
    db.commit()
    db.refresh(doctor)

    return DoctorResponse(
        id=doctor.id, name=doctor.name, specialization=doctor.specialization,
        clinic_id=doctor.clinic_id, clinic_name=clinic_name, city=city_name, is_active=True,
    )


@router.patch("/admin/doctors/{doctor_id}", response_model=DoctorResponse)
async def admin_update_doctor(
    doctor_id: int, req: DoctorUpdateRequest,
    user: User = Depends(_require_admin), db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, doctor_id)
    if not doctor or doctor.clinic_id != user.clinic_id:
        raise HTTPException(status_code=404, detail="Doctor not found in your clinic")

    if req.name is not None:
        doctor.name = req.name.strip()
    if req.specialization is not None:
        doctor.specialization = req.specialization.strip()
    if req.is_active is not None:
        doctor.is_active = req.is_active
    db.commit()
    db.refresh(doctor)

    clinic = db.get(Clinic, user.clinic_id)
    city = db.get(City, clinic.city_id) if clinic else None
    return DoctorResponse(
        id=doctor.id, name=doctor.name, specialization=doctor.specialization,
        clinic_id=doctor.clinic_id,
        clinic_name=clinic.name if clinic else None,
        city=city.name if city else None,
        is_active=doctor.is_active if doctor.is_active is not None else True,
    )


# ─── admin: appointment overview ──────────────────────────────────────────────

@router.get("/admin/appointments", response_model=list[AppointmentDetailResponse])
async def admin_appointments(
    doctor_id: int | None = Query(default=None),
    appt_status: str | None = Query(default=None, alias="status"),
    date: str | None = Query(default=None),
    days: int = Query(default=7),
    user: User = Depends(_require_admin), db: Session = Depends(get_db),
):
    if date:
        from dateutil import parser as dateparser  # noqa: PLC0415
        day_start = dateparser.parse(date).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
    else:
        day_start = datetime.now(_UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        day_end = day_start + timedelta(days=days + 1)

    stmt = select(Appointment).where(
        Appointment.clinic_id == user.clinic_id,
        Appointment.start_time >= day_start,
        Appointment.start_time < day_end,
    )
    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if appt_status:
        stmt = stmt.where(Appointment.status == appt_status)

    appointments = db.scalars(stmt.order_by(Appointment.start_time.desc())).all()
    return [_appt_to_detail(a, db) for a in appointments]
