import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    AppointmentDetailResponse,
    AppointmentStatusUpdate,
    AuthResponse,
    ChatCreateRequest,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatThreadResponse,
    CityResponse,
    ClinicResponse,
    DoctorResponse,
    HealthResponse,
    LoginRequest,
    QueueItemResponse,
    RegisterRequest,
    UserResponse,
)
from app.core.auth import generate_token, hash_password, token_expiry, token_hash, verify_password
from app.core.agent import agent
from app.db.database import get_db
from app.db.models import Appointment, AuthToken, ChatMessage, ChatThread, City, Clinic, Doctor, User

router = APIRouter(prefix="/api", tags=["api"])


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
    if not token_row or token_row.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")
    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


def _to_thread_response(thread: ChatThread) -> ChatThreadResponse:
    return ChatThreadResponse(
        id=thread.id, role=thread.role, title=thread.title,
        created_at=thread.created_at, updated_at=thread.updated_at,
    )


def _thread_history(thread_messages: list[ChatMessage]) -> list[dict]:
    return [
        {"role": msg.sender, "content": msg.content}
        for msg in thread_messages
        if msg.sender in {"user", "assistant"}
    ]


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
        ClinicResponse(
            id=c.id,
            name=c.name,
            city=c.city.name if c.city else "",
            address=c.address,
            phone=c.phone,
        )
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
            id=d.id,
            name=d.name,
            specialization=d.specialization,
            clinic_name=d.clinic.name if d.clinic else None,
            city=d.clinic.city.name if d.clinic and d.clinic.city else None,
        )
        for d in doctors
    ]


# ─── auth endpoints ──────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == req.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=req.email.lower(),
        full_name=req.full_name.strip(),
        role="patient",
        password_hash=hash_password(req.password),
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    raw_token = generate_token()
    db.add(AuthToken(user_id=user.id, token_hash=token_hash(raw_token), expires_at=token_expiry()))
    db.commit()
    return AuthResponse(token=raw_token, user=_to_user_response(user))


@router.post("/auth/logout")
async def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    raw = _extract_bearer_token(authorization)
    hashed = token_hash(raw)
    token_row = db.scalar(select(AuthToken).where(AuthToken.token_hash == hashed))
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    messages = db.scalars(
        select(ChatMessage).where(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
    ).all()
    output = []
    for msg in messages:
        trace = json.loads(msg.tool_trace_json) if msg.tool_trace_json else None
        output.append(ChatMessageResponse(
            id=msg.id, sender=msg.sender, content=msg.content,
            tool_trace=trace, created_at=msg.created_at,
        ))
    return output


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user: User = Depends(_current_user), db: Session = Depends(get_db)):
    thread = None
    if req.chat_id:
        thread = db.scalar(select(ChatThread).where(ChatThread.id == req.chat_id, ChatThread.user_id == user.id))
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    else:
        default_title = "Doctor Chat" if user.role == "doctor" else "Patient Chat"
        thread = ChatThread(user_id=user.id, role=user.role, title=default_title)
        db.add(thread)
        db.commit()
        db.refresh(thread)

    thread_messages = db.scalars(
        select(ChatMessage).where(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
    ).all()
    history = _thread_history(thread_messages)

    db.add(ChatMessage(thread_id=thread.id, sender="user", content=req.message))
    db.commit()

    result = await agent.run(
        role=user.role,
        user_message=req.message,
        session_id=thread.id,
        history=history,
    )

    # Link any freshly booked appointment to this user
    for trace_item in result.get("tool_trace", []):
        if trace_item.get("tool") == "book_appointment" and trace_item.get("result", {}).get("ok"):
            appt_id = trace_item["result"].get("appointment_id")
            if appt_id:
                appt = db.get(Appointment, appt_id)
                if appt and not appt.user_id:
                    appt.user_id = user.id
                    db.commit()

    db.add(ChatMessage(
        thread_id=thread.id,
        sender="assistant",
        content=result["answer"],
        tool_trace_json=json.dumps(result["tool_trace"]),
    ))
    if thread.title in {"Patient Chat", "Doctor Chat", "New Chat"}:
        thread.title = req.message.strip()[:60] or thread.title
    thread.updated_at = datetime.utcnow()
    db.commit()

    return ChatResponse(chat_id=thread.id, response=result["answer"], tool_trace=result["tool_trace"])


# ─── patient self-service ────────────────────────────────────────────────────

@router.get("/my-appointments", response_model=list[AppointmentDetailResponse])
async def my_appointments(user: User = Depends(_current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    appointments = db.scalars(
        select(Appointment).where(
            and_(
                or_(Appointment.user_id == user.id, Appointment.patient_email == user.email),
                Appointment.start_time >= now,
                Appointment.status != "cancelled",
            )
        ).order_by(Appointment.start_time)
    ).all()

    result = []
    for appt in appointments:
        doctor = db.get(Doctor, appt.doctor_id)
        clinic = db.get(Clinic, appt.clinic_id) if appt.clinic_id else None
        city = db.get(City, clinic.city_id) if clinic else None
        result.append(AppointmentDetailResponse(
            id=appt.id,
            doctor_name=doctor.name if doctor else "Unknown",
            specialization=doctor.specialization if doctor else None,
            clinic_name=clinic.name if clinic else None,
            city=city.name if city else None,
            start_time=appt.start_time,
            end_time=appt.end_time,
            symptoms=appt.symptoms,
            status=appt.status,
        ))
    return result


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
):
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


# ─── doctor queue ────────────────────────────────────────────────────────────

@router.get("/doctor/queue", response_model=list[QueueItemResponse])
async def doctor_queue(user: User = Depends(_current_user), db: Session = Depends(get_db)):
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access only")
    if not user.doctor_profile_id:
        raise HTTPException(status_code=404, detail="Doctor profile not linked to this account")

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
            id=appt.id,
            patient_name=appt.patient_name,
            patient_email=appt.patient_email,
            symptoms=appt.symptoms,
            start_time=appt.start_time,
            end_time=appt.end_time,
            status=appt.status,
        )
        for appt in appointments
    ]


@router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: int,
    req: AppointmentStatusUpdate,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access only")

    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.doctor_id != user.doctor_profile_id:
        raise HTTPException(status_code=403, detail="Not your appointment")

    appt.status = req.status
    db.commit()
    return {"ok": True, "appointment_id": appt.id, "status": appt.status}
