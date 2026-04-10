import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings
import asyncio
from db.connection import get_db
from datetime import datetime


def _send_email_sync(to_email: str, subject: str, body_html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.send_message(msg)


async def _send_async(to_email, subject, body):
    """Run blocking SMTP in thread pool so we don't block event loop"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_email_sync, to_email, subject, body)


async def log_notification(booking_id: str, recipient_email: str, notif_type: str, status: str, error_message: str = None):
    """Log email notification to database"""
    try:
        db = get_db()
        await db.notifications_log.insert_one({
            "booking_id": booking_id,
            "recipient_email": recipient_email,
            "type": notif_type,
            "status": status,
            "error_message": error_message,
            "sent_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        })
    except Exception as e:
        print(f"[Email] Failed to log notification: {e}")


async def send_booking_confirmation(
    to_email, name, booking_ref, date, time, party_size, table_number, restaurant_name
):
    subject = f"Booking Confirmed — {booking_ref}"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2d3748;">Your table is confirmed! 🎉</h2>
            <p>Hi {name},</p>
            <p>Your reservation at <strong>{restaurant_name}</strong> is confirmed.</p>
            <div style="background: #f7fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <ul style="list-style: none; padding: 0; margin: 0;">
                    <li style="margin-bottom: 8px;"><strong>Reference:</strong> {booking_ref}</li>
                    <li style="margin-bottom: 8px;"><strong>Date:</strong> {date}</li>
                    <li style="margin-bottom: 8px;"><strong>Time:</strong> {time}</li>
                    <li style="margin-bottom: 8px;"><strong>Party size:</strong> {party_size}</li>
                    <li><strong>Table:</strong> {table_number}</li>
                </ul>
            </div>
            <p style="color: #718096; font-size: 14px;">
                To cancel, reply to this email with your reference number or use the chatbot.
            </p>
            <p style="margin-top: 30px; color: #718096; font-size: 12px;">
                {restaurant_name}
            </p>
        </div>
    </body>
    </html>
    """
    try:
        await _send_async(to_email, subject, body)
        print(f"[Email] Sent booking confirmation to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send confirmation: {e}")
        return False


async def send_cancellation_email(to_email, name, booking_ref, restaurant_name="The Restaurant"):
    subject = f"Booking Cancelled — {booking_ref}"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2d3748;">Booking Cancelled</h2>
            <p>Hi {name},</p>
            <p>Your reservation <strong>{booking_ref}</strong> has been cancelled.</p>
            <p>We hope to see you soon!</p>
            <p style="margin-top: 30px; color: #718096; font-size: 12px;">
                {restaurant_name}
            </p>
        </div>
    </body>
    </html>
    """
    try:
        await _send_async(to_email, subject, body)
        print(f"[Email] Sent cancellation email to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send cancellation: {e}")
        return False
