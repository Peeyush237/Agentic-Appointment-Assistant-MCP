from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)
    role: str = Field(pattern="^(patient|doctor|admin)$")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    clinic_id: int | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class ChatCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ChatRequest(BaseModel):
    message: str
    chat_id: str | None = None


class ChatResponse(BaseModel):
    chat_id: str
    response: str
    tool_trace: list[dict]


class ChatThreadResponse(BaseModel):
    id: str
    role: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    id: int
    sender: str
    content: str
    tool_trace: list[dict] | None = None
    created_at: datetime


class HealthResponse(BaseModel):
    status: str


# ── Geography ──────────────────────────────────────────────────────────────

class CityResponse(BaseModel):
    id: int
    name: str
    state: str


class ClinicResponse(BaseModel):
    id: int
    name: str
    city: str
    address: str | None = None
    phone: str | None = None


class DoctorResponse(BaseModel):
    id: int
    name: str
    specialization: str
    clinic_id: int | None = None
    clinic_name: str | None = None
    city: str | None = None
    is_active: bool = True


# ── Appointments ───────────────────────────────────────────────────────────

class AppointmentDetailResponse(BaseModel):
    id: int
    doctor_name: str
    specialization: str | None = None
    clinic_name: str | None = None
    city: str | None = None
    patient_name: str
    patient_email: str
    start_time: datetime
    end_time: datetime
    symptoms: str
    status: str
    notes: str | None = None


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(pattern="^(booked|completed|no_show|cancelled)$")


class AppointmentNotesUpdate(BaseModel):
    notes: str = Field(max_length=2000)


# ── Doctor queue ───────────────────────────────────────────────────────────

class QueueItemResponse(BaseModel):
    id: int
    patient_name: str
    patient_email: str
    symptoms: str
    start_time: datetime
    end_time: datetime
    status: str
    notes: str | None = None


# ── Doctor schedule ────────────────────────────────────────────────────────

class AvailabilityWindowResponse(BaseModel):
    id: int
    day_of_week: int
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int


class AvailabilityWindowCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_hour: int = Field(ge=0, le=23)
    start_minute: int = Field(default=0, ge=0, le=59)
    end_hour: int = Field(ge=0, le=23)
    end_minute: int = Field(default=0, ge=0, le=59)


class ScheduleReplaceRequest(BaseModel):
    windows: list[AvailabilityWindowCreate]


# ── Admin schemas ──────────────────────────────────────────────────────────

class AdminDashboardResponse(BaseModel):
    clinic_name: str
    city: str
    total_doctors: int
    today_total: int
    today_pending: int
    today_completed: int
    today_no_show: int
    today_cancelled: int


class DoctorCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    specialization: str = Field(min_length=2, max_length=120)


class DoctorUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    specialization: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None
