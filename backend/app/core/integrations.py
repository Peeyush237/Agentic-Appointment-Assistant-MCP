from datetime import datetime

import httpx
from twilio.rest import Client

from app.core.config import settings


async def create_google_calendar_event(summary: str, description: str, start_time: datetime, end_time: datetime) -> dict:
    if not settings.google_access_token:
        return {
            "mode": "mock",
            "event_id": f"mock-{int(start_time.timestamp())}",
            "message": "Google token missing, created mock calendar event",
        }

    payload = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": settings.google_timezone,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": settings.google_timezone,
        },
    }

    url = f"https://www.googleapis.com/calendar/v3/calendars/{settings.google_calendar_id}/events"
    headers = {"Authorization": f"Bearer {settings.google_access_token}"}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            return {
                "mode": "error",
                "event_id": None,
                "message": f"Calendar API failed: {response.text}",
            }
        data = response.json()
        return {"mode": "live", "event_id": data.get("id"), "message": "Calendar event created"}


async def send_patient_email(to_email: str, subject: str, body: str) -> dict:
    provider = settings.email_provider.lower().strip()

    if provider != "sendgrid":
        return {
            "mode": "mock",
            "message": f"Unsupported email provider '{provider}'. Mock email sent to {to_email}",
            "subject": subject,
            "body": body,
        }

    if not settings.email_api_key:
        return {
            "mode": "mock",
            "message": f"SendGrid API key missing, mock email sent to {to_email}",
            "subject": subject,
            "body": body,
        }

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": settings.email_from},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }

    headers = {
        "Authorization": f"Bearer {settings.email_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers)

    if response.status_code == 202:
        return {
            "mode": "live",
            "message": f"SendGrid accepted email for {to_email}",
            "subject": subject,
        }

    return {
        "mode": "error",
        "message": f"SendGrid email failed ({response.status_code}): {response.text}",
        "subject": subject,
    }


async def send_doctor_notification(message: str) -> dict:
    if settings.whatsapp_provider.lower() != "twilio":
        return {
            "mode": "mock",
            "message": "Unsupported WhatsApp provider configured. Falling back to mock delivery.",
            "payload": message,
        }

    required = [
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_whatsapp_from,
        settings.doctor_whatsapp_to,
    ]
    if any(not value for value in required):
        return {
            "mode": "mock",
            "message": "Twilio WhatsApp credentials missing, mock doctor notification delivered",
            "payload": message,
        }

    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        twilio_message = client.messages.create(
            from_=settings.twilio_whatsapp_from,
            to=settings.doctor_whatsapp_to,
            body=message,
        )
        return {
            "mode": "live",
            "message": "Doctor WhatsApp notification sent",
            "sid": twilio_message.sid,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "mode": "error",
            "message": f"Twilio WhatsApp notification failed: {exc}",
        }
