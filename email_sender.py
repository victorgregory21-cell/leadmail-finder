import mimetypes
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional


PROVIDER_PRESETS = {
    "Gmail": {
        "host": "smtp.gmail.com",
        "port": 465,
        "security": "SSL/TLS",
        "username_label": "Gmail address",
        "password_label": "Gmail App Password",
        "help": "Use a Google App Password, not your normal Google password.",
    },
    "Outlook / Hotmail": {
        "host": "smtp.office365.com",
        "port": 587,
        "security": "STARTTLS",
        "username_label": "Outlook / Hotmail address",
        "password_label": "Password or App Password",
        "help": "Some Microsoft accounts may require an app password or SMTP authentication to be enabled.",
    },
    "Yahoo": {
        "host": "smtp.mail.yahoo.com",
        "port": 465,
        "security": "SSL/TLS",
        "username_label": "Yahoo email address",
        "password_label": "Yahoo App Password",
        "help": "Yahoo usually requires an app password for SMTP access.",
    },
    "Custom SMTP": {
        "host": "",
        "port": 465,
        "security": "SSL/TLS",
        "username_label": "SMTP username",
        "password_label": "SMTP password",
        "help": "Use this for custom domains or company email accounts.",
    },
}


@dataclass
class SendResult:
    recipient: str
    status: str
    message: str


@dataclass
class SmtpConfig:
    provider: str
    host: str
    port: int
    security: str
    username: str
    password: str
    sender_email: str


def build_email_message(
    sender_email: str,
    recipient: str,
    subject: str,
    body: str,
    attachment_name: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    if attachment_name and attachment_bytes:
        content_type, _ = mimetypes.guess_type(attachment_name)

        if content_type is None:
            maintype, subtype = "application", "octet-stream"
        else:
            maintype, subtype = content_type.split("/", 1)

        message.add_attachment(
            attachment_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=attachment_name,
        )

    return message


def send_single_email(
    smtp_config: SmtpConfig,
    recipient: str,
    subject: str,
    body: str,
    attachment_name: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
) -> SendResult:
    try:
        message = build_email_message(
            sender_email=smtp_config.sender_email,
            recipient=recipient,
            subject=subject,
            body=body,
            attachment_name=attachment_name,
            attachment_bytes=attachment_bytes,
        )

        security = smtp_config.security

        if security == "SSL/TLS":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                smtp_config.host,
                smtp_config.port,
                context=context,
                timeout=30,
            ) as server:
                server.login(smtp_config.username, smtp_config.password)
                server.send_message(message)

        elif security == "STARTTLS":
            context = ssl.create_default_context()
            with smtplib.SMTP(
                smtp_config.host,
                smtp_config.port,
                timeout=30,
            ) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_config.username, smtp_config.password)
                server.send_message(message)

        else:
            with smtplib.SMTP(
                smtp_config.host,
                smtp_config.port,
                timeout=30,
            ) as server:
                server.login(smtp_config.username, smtp_config.password)
                server.send_message(message)

        return SendResult(
            recipient=recipient,
            status="Sent",
            message="Email sent successfully",
        )

    except smtplib.SMTPAuthenticationError:
        return SendResult(
            recipient=recipient,
            status="Failed",
            message="Authentication failed. Check username, password/app password, and SMTP settings.",
        )

    except smtplib.SMTPRecipientsRefused:
        return SendResult(
            recipient=recipient,
            status="Failed",
            message="Recipient refused by SMTP server.",
        )

    except smtplib.SMTPException as exc:
        return SendResult(
            recipient=recipient,
            status="Failed",
            message=f"SMTP error: {exc}",
        )

    except Exception as exc:
        return SendResult(
            recipient=recipient,
            status="Failed",
            message=f"Unexpected error: {type(exc).__name__}: {exc}",
        )
