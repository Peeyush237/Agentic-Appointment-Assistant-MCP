import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import hash_password
from app.core.config import settings
from app.db.models import Appointment, City, Clinic, Doctor, DoctorAvailability, User

# --------------------------------------------------------------------------- #
# Pan-India clinic data                                                        #
# --------------------------------------------------------------------------- #
CLINIC_DATA: list[dict] = [
    # ── Delhi ──────────────────────────────────────────────────────────────
    {
        "city": "Delhi", "state": "Delhi",
        "name": "Apollo Clinic, Delhi",
        "address": "Sarita Vihar, New Delhi – 110076",
        "phone": "+91-11-2222-3333",
        "doctors": [
            ("Dr. Ahuja",   "General Physician"),
            ("Dr. Rao",     "Pediatrician"),
            ("Dr. Verma",   "Cardiologist"),
        ],
    },
    {
        "city": "Delhi", "state": "Delhi",
        "name": "Max Healthcare, Delhi",
        "address": "Saket, New Delhi – 110017",
        "phone": "+91-11-2666-7777",
        "doctors": [
            ("Dr. Sharma",  "Dermatologist"),
            ("Dr. Gupta",   "Orthopedic Surgeon"),
            ("Dr. Mehta",   "Gynecologist"),
        ],
    },
    # ── Mumbai ─────────────────────────────────────────────────────────────
    {
        "city": "Mumbai", "state": "Maharashtra",
        "name": "Lilavati Hospital, Mumbai",
        "address": "Bandra West, Mumbai – 400050",
        "phone": "+91-22-2675-1000",
        "doctors": [
            ("Dr. Desai",    "General Physician"),
            ("Dr. Joshi",    "Cardiologist"),
            ("Dr. Kulkarni", "Pediatrician"),
        ],
    },
    {
        "city": "Mumbai", "state": "Maharashtra",
        "name": "Kokilaben Hospital, Mumbai",
        "address": "Andheri West, Mumbai – 400053",
        "phone": "+91-22-3069-9999",
        "doctors": [
            ("Dr. Patil",    "Orthopedic Surgeon"),
            ("Dr. Shah",     "Dermatologist"),
            ("Dr. Nair",     "Gynecologist"),
        ],
    },
    # ── Bangalore ──────────────────────────────────────────────────────────
    {
        "city": "Bangalore", "state": "Karnataka",
        "name": "Manipal Hospital, Bangalore",
        "address": "Whitefield, Bangalore – 560066",
        "phone": "+91-80-2502-4444",
        "doctors": [
            ("Dr. Reddy",    "General Physician"),
            ("Dr. Krishnan", "Cardiologist"),
            ("Dr. Murthy",   "Pediatrician"),
        ],
    },
    {
        "city": "Bangalore", "state": "Karnataka",
        "name": "Columbia Asia Hospital, Bangalore",
        "address": "Hebbal, Bangalore – 560024",
        "phone": "+91-80-6165-6888",
        "doctors": [
            ("Dr. Hegde",    "Dermatologist"),
            ("Dr. Shetty",   "Orthopedic Surgeon"),
            ("Dr. Rao B",    "Psychiatrist"),
        ],
    },
    # ── Hyderabad ──────────────────────────────────────────────────────────
    {
        "city": "Hyderabad", "state": "Telangana",
        "name": "CARE Hospital, Hyderabad",
        "address": "Banjara Hills, Hyderabad – 500034",
        "phone": "+91-40-3041-5000",
        "doctors": [
            ("Dr. Naidu",   "General Physician"),
            ("Dr. Chandra", "Cardiologist"),
            ("Dr. Lakshmi", "Gynecologist"),
        ],
    },
    {
        "city": "Hyderabad", "state": "Telangana",
        "name": "Yashoda Hospital, Hyderabad",
        "address": "Somajiguda, Hyderabad – 500082",
        "phone": "+91-40-2337-1111",
        "doctors": [
            ("Dr. Rao H",  "Pediatrician"),
            ("Dr. Prasad", "Orthopedic Surgeon"),
            ("Dr. Suresh", "Dermatologist"),
        ],
    },
    # ── Chennai ────────────────────────────────────────────────────────────
    {
        "city": "Chennai", "state": "Tamil Nadu",
        "name": "Apollo Hospital, Chennai",
        "address": "Greams Road, Chennai – 600006",
        "phone": "+91-44-2829-3333",
        "doctors": [
            ("Dr. Iyer",         "General Physician"),
            ("Dr. Subramanian",  "Cardiologist"),
            ("Dr. Rajan",        "Pediatrician"),
        ],
    },
    {
        "city": "Chennai", "state": "Tamil Nadu",
        "name": "Fortis Malar Hospital, Chennai",
        "address": "Adyar, Chennai – 600020",
        "phone": "+91-44-4229-9999",
        "doctors": [
            ("Dr. Pillai", "Dermatologist"),
            ("Dr. Menon",  "Gynecologist"),
            ("Dr. Nair C", "Orthopedic Surgeon"),
        ],
    },
    # ── Kolkata ────────────────────────────────────────────────────────────
    {
        "city": "Kolkata", "state": "West Bengal",
        "name": "Belle Vue Clinic, Kolkata",
        "address": "Elgin Road, Kolkata – 700020",
        "phone": "+91-33-2282-1234",
        "doctors": [
            ("Dr. Banerjee",    "General Physician"),
            ("Dr. Chakraborty", "Cardiologist"),
            ("Dr. Ghosh",       "Pediatrician"),
        ],
    },
    {
        "city": "Kolkata", "state": "West Bengal",
        "name": "AMRI Hospital, Kolkata",
        "address": "Dhakuria, Kolkata – 700029",
        "phone": "+91-33-4600-2222",
        "doctors": [
            ("Dr. Sen", "Dermatologist"),
            ("Dr. Das", "Orthopedic Surgeon"),
            ("Dr. Roy", "Psychiatrist"),
        ],
    },
    # ── Pune ───────────────────────────────────────────────────────────────
    {
        "city": "Pune", "state": "Maharashtra",
        "name": "Ruby Hall Clinic, Pune",
        "address": "Sassoon Road, Pune – 411001",
        "phone": "+91-20-2616-3391",
        "doctors": [
            ("Dr. Deshpande", "General Physician"),
            ("Dr. Joshi P",   "Cardiologist"),
            ("Dr. Pawar",     "Gynecologist"),
        ],
    },
    {
        "city": "Pune", "state": "Maharashtra",
        "name": "Jehangir Hospital, Pune",
        "address": "Sassoon Road, Pune – 411001",
        "phone": "+91-20-6681-4444",
        "doctors": [
            ("Dr. Kulkarni P", "Pediatrician"),
            ("Dr. Sathe",      "Dermatologist"),
            ("Dr. Pande",      "Orthopedic Surgeon"),
        ],
    },
    # ── Ahmedabad ──────────────────────────────────────────────────────────
    {
        "city": "Ahmedabad", "state": "Gujarat",
        "name": "Sterling Hospital, Ahmedabad",
        "address": "Memnagar, Ahmedabad – 380052",
        "phone": "+91-79-4000-5000",
        "doctors": [
            ("Dr. Patel",  "General Physician"),
            ("Dr. Shah A", "Cardiologist"),
            ("Dr. Gandhi", "Pediatrician"),
        ],
    },
    {
        "city": "Ahmedabad", "state": "Gujarat",
        "name": "Apollo Hospital, Ahmedabad",
        "address": "Bhat, Gandhinagar – 382428",
        "phone": "+91-79-6670-1800",
        "doctors": [
            ("Dr. Mehta A", "Dermatologist"),
            ("Dr. Trivedi", "Gynecologist"),
            ("Dr. Pandya",  "Orthopedic Surgeon"),
        ],
    },
    # ── Jaipur ─────────────────────────────────────────────────────────────
    {
        "city": "Jaipur", "state": "Rajasthan",
        "name": "Fortis Hospital, Jaipur",
        "address": "Jawaharlal Nehru Marg, Jaipur – 302017",
        "phone": "+91-141-2546-666",
        "doctors": [
            ("Dr. Sharma J", "General Physician"),
            ("Dr. Gupta J",  "Cardiologist"),
            ("Dr. Agarwal",  "Pediatrician"),
        ],
    },
    {
        "city": "Jaipur", "state": "Rajasthan",
        "name": "Narayana Hospital, Jaipur",
        "address": "Sector 28, Jaipur – 302033",
        "phone": "+91-141-7116-000",
        "doctors": [
            ("Dr. Mathur",  "Dermatologist"),
            ("Dr. Jain",    "Gynecologist"),
            ("Dr. Singhal", "Orthopedic Surgeon"),
        ],
    },
    # ── Lucknow ────────────────────────────────────────────────────────────
    {
        "city": "Lucknow", "state": "Uttar Pradesh",
        "name": "Medanta Hospital, Lucknow",
        "address": "Sushant Golf City, Lucknow – 226030",
        "phone": "+91-522-4505-050",
        "doctors": [
            ("Dr. Singh",  "General Physician"),
            ("Dr. Mishra", "Cardiologist"),
            ("Dr. Tiwari", "Pediatrician"),
        ],
    },
    {
        "city": "Lucknow", "state": "Uttar Pradesh",
        "name": "Apollo Medics, Lucknow",
        "address": "Kanpur Road, Lucknow – 226012",
        "phone": "+91-522-3505-050",
        "doctors": [
            ("Dr. Bajpai",  "Dermatologist"),
            ("Dr. Shukla",  "Gynecologist"),
            ("Dr. Tripathi","Orthopedic Surgeon"),
        ],
    },
]


# ── credential helpers ────────────────────────────────────────────────────────

def _email_slug(text: str) -> str:
    """'Apollo Clinic, Delhi' → 'apolloclinicdelhi'"""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _password_slug(text: str) -> str:
    """'Apollo Clinic, Delhi' → 'ApolloClinicDelhi'"""
    return re.sub(r"[^a-zA-Z0-9]", "", text)


def _name_slug(name: str) -> str:
    """'Dr. Rao B' → 'raob'"""
    stripped = re.sub(r"^dr\.?\s*", "", name.lower().strip())
    return re.sub(r"[^a-z0-9]", "", stripped)


def doctor_email(doctor_name: str, clinic_name: str) -> str:
    return f"dr.{_name_slug(doctor_name)}@{_email_slug(clinic_name)}.local"


def doctor_password(city_name: str, clinic_name: str, doctor_id: int) -> str:
    return f"{city_name}_{_password_slug(clinic_name)}_{doctor_id}"


def admin_email(clinic_name: str) -> str:
    return f"admin@{_email_slug(clinic_name)}.local"


def admin_password(clinic_name: str, clinic_id: int) -> str:
    return f"admin_{_password_slug(clinic_name)}_{clinic_id}"


# ── internal helpers ──────────────────────────────────────────────────────────

def _seed_availability(db: Session, doctor_id: int) -> None:
    """Standard Mon–Fri: 9 AM–1 PM and 2 PM–6 PM."""
    for day in range(5):
        db.add(DoctorAvailability(doctor_id=doctor_id, day_of_week=day, start_hour=9,  end_hour=13))
        db.add(DoctorAvailability(doctor_id=doctor_id, day_of_week=day, start_hour=14, end_hour=18))


def _upsert_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    role: str,
    password: str,
    doctor_profile_id: int | None = None,
    clinic_id: int | None = None,
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.full_name = full_name
        user.role = role
        user.password_hash = hash_password(password)
        if doctor_profile_id is not None:
            user.doctor_profile_id = doctor_profile_id
        if clinic_id is not None:
            user.clinic_id = clinic_id
    else:
        user = User(
            email=email,
            full_name=full_name,
            role=role,
            password_hash=hash_password(password),
            doctor_profile_id=doctor_profile_id,
            clinic_id=clinic_id,
        )
        db.add(user)
    return user


# ── main seed ─────────────────────────────────────────────────────────────────

def seed_data(db: Session) -> None:
    cities_exist = db.scalar(select(City).limit(1)) is not None

    if not cities_exist:
        # ── 1. Create cities and clinics ──────────────────────────────────
        city_cache: dict[str, City] = {}
        clinic_cache: dict[str, Clinic] = {}

        for entry in CLINIC_DATA:
            city_name = entry["city"]
            if city_name not in city_cache:
                city = City(name=city_name, state=entry["state"], is_active=True)
                db.add(city)
                db.flush()
                city_cache[city_name] = city

            clinic = Clinic(
                name=entry["name"],
                city_id=city_cache[city_name].id,
                address=entry.get("address"),
                phone=entry.get("phone"),
                is_active=True,
            )
            db.add(clinic)
            db.flush()
            clinic_cache[entry["name"]] = clinic

        # ── 2. Upsert doctors + availability ─────────────────────────────
        for entry in CLINIC_DATA:
            clinic_obj = clinic_cache[entry["name"]]
            for doctor_name, specialization in entry["doctors"]:
                doctor = db.scalar(select(Doctor).where(Doctor.name == doctor_name))
                if doctor:
                    doctor.clinic_id = clinic_obj.id
                    doctor.specialization = specialization
                else:
                    doctor = Doctor(name=doctor_name, specialization=specialization, clinic_id=clinic_obj.id)
                    db.add(doctor)
                db.flush()

                if not db.scalar(select(DoctorAvailability).where(DoctorAvailability.doctor_id == doctor.id).limit(1)):
                    _seed_availability(db, doctor.id)

        db.commit()

        # ── 3. Sample completed appointment for Dr. Ahuja ─────────────────
        ahuja = db.scalar(select(Doctor).where(Doctor.name == "Dr. Ahuja"))
        if ahuja:
            yesterday_noon = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
            if not db.scalar(select(Appointment).where(
                Appointment.doctor_id == ahuja.id, Appointment.start_time == yesterday_noon
            )):
                db.add(Appointment(
                    doctor_id=ahuja.id, clinic_id=ahuja.clinic_id,
                    patient_name="Seed Patient", patient_email="seed@example.com",
                    symptoms="fever", status="completed",
                    start_time=yesterday_noon, end_time=yesterday_noon + timedelta(minutes=30),
                    notes="Follow-up in one week",
                ))
                db.commit()
    else:
        # Cities exist but doctors may still need clinic_id (migration run)
        clinic_cache: dict[str, Clinic] = {
            c.name: c for c in db.scalars(select(Clinic)).all()
        }
        for entry in CLINIC_DATA:
            clinic_obj = clinic_cache.get(entry["name"])
            if not clinic_obj:
                continue
            for doctor_name, specialization in entry["doctors"]:
                doctor = db.scalar(select(Doctor).where(Doctor.name == doctor_name))
                if doctor and not doctor.clinic_id:
                    doctor.clinic_id = clinic_obj.id
                    db.flush()
                if doctor and not db.scalar(
                    select(DoctorAvailability).where(DoctorAvailability.doctor_id == doctor.id).limit(1)
                ):
                    _seed_availability(db, doctor.id)
        db.commit()

    # ── 4. Create/update User accounts for every doctor ───────────────────
    all_clinics: dict[str, Clinic] = {
        c.name: c for c in db.scalars(select(Clinic)).all()
    }
    all_cities: dict[int, City] = {
        city.id: city for city in db.scalars(select(City)).all()
    }

    for entry in CLINIC_DATA:
        clinic_obj = all_clinics.get(entry["name"])
        if not clinic_obj:
            continue
        city_obj = all_cities.get(clinic_obj.city_id)
        city_name = city_obj.name if city_obj else entry["city"]

        for doctor_name, _ in entry["doctors"]:
            doctor = db.scalar(select(Doctor).where(Doctor.name == doctor_name))
            if not doctor:
                continue
            _upsert_user(
                db,
                email=doctor_email(doctor_name, entry["name"]),
                full_name=doctor_name,
                role="doctor",
                password=doctor_password(city_name, entry["name"], doctor.id),
                doctor_profile_id=doctor.id,
            )

        # Admin user per clinic
        _upsert_user(
            db,
            email=admin_email(entry["name"]),
            full_name=f"Admin – {entry['name']}",
            role="admin",
            password=admin_password(entry["name"], clinic_obj.id),
            clinic_id=clinic_obj.id,
        )

    db.commit()

    # ── 5. Keep legacy demo account (doctor@clinic.local → Dr. Ahuja) ─────
    ahuja = db.scalar(select(Doctor).where(Doctor.name == "Dr. Ahuja"))
    _upsert_user(
        db,
        email=settings.default_doctor_login_email,
        full_name="Dr. Ahuja (Demo)",
        role="doctor",
        password=settings.default_doctor_login_password,
        doctor_profile_id=ahuja.id if ahuja else None,
    )
    db.commit()
