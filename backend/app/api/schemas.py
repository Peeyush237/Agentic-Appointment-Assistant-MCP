from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(pattern="^(patient|doctor)$")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str


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
    clinic_name: str | None = None
    city: str | None = None


# ── Appointments ───────────────────────────────────────────────────────────

class AppointmentDetailResponse(BaseModel):
    id: int
    doctor_name: str
    specialization: str | None = None
    clinic_name: str | None = None
    city: str | None = None
    start_time: datetime
    end_time: datetime
    symptoms: str
    status: str


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(pattern="^(booked|completed|no_show|cancelled)$")


# ── Doctor queue ───────────────────────────────────────────────────────────

class QueueItemResponse(BaseModel):
    id: int
    patient_name: str
    patient_email: str
    symptoms: str
    start_time: datetime
    end_time: datetime
    status: str
