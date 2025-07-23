import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()  # wczytuje dane z pliku .env

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

def send_leave_notification(admin_emails, employee_name, date_from, date_to, comment):
    subject = f"Nowy urlop: {employee_name}"
    body = f"""
Użytkownik {employee_name} zgłosił nowy urlop:

Od: {date_from}
Do: {date_to}
Komentarz: {comment or '-'}
"""

    for recipient in admin_emails:
        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL_SENDER
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, recipient, msg.as_string())
        except Exception as e:
            print(f"Błąd wysyłania e-maila do {recipient}: {e}")
