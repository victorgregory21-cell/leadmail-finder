import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

COMMON_PATHS = [
    "",
    "/iletisim",
    "/iletişim",
    "/contact",
    "/contact-us",
    "/kariyer",
]

REQUEST_TIMEOUT_SECONDS = 6
COMPANY_MAX_SECONDS = 25

BLOCKED_EMAILS = {
    "ornek@mail.com",
    "örnek@mail.com",
    "example@example.com",
    "test@test.com",
    "demo@demo.com",
    "your@email.com",
    "email@example.com",
    "mail@example.com",
    "info@example.com",
}


def normalize_url(url):
    if not isinstance(url, str) or not url.strip() or url.strip().lower() == "nan":
        return None

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def extract_emails_from_text(text):
    emails = set(re.findall(EMAIL_REGEX, text or ""))
    ignored_extensions = (
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
        ".css", ".js", ".ico", ".pdf", ".woff", ".woff2"
    )

    clean_emails = set()

    for email in emails:
        email = email.strip().lower()

        if email in BLOCKED_EMAILS:
            continue

        if email.endswith(ignored_extensions):
            continue

        if any(token in email for token in ["example@", "your@", "ornek@", "örnek@", "test@", "demo@"]):
            continue

        clean_emails.add(email)

    return clean_emails


def fetch_page(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=(REQUEST_TIMEOUT_SECONDS, REQUEST_TIMEOUT_SECONDS),
            allow_redirects=True,
        )

        if response.status_code >= 400:
            return "", f"HTTP {response.status_code}"

        return response.text, "OK"

    except requests.exceptions.Timeout:
        return "", "Timeout"

    except requests.exceptions.SSLError:
        return "", "SSL error"

    except requests.exceptions.ConnectionError:
        return "", "Connection error"

    except Exception as exc:
        return "", f"Error: {type(exc).__name__}"


def find_emails_on_site(base_url, max_seconds=COMPANY_MAX_SECONDS):
    base_url = normalize_url(base_url)

    if not base_url:
        return {
            "emails": "",
            "status": "Website not available",
            "checked_pages": "",
        }

    started_at = time.monotonic()
    found_emails = set()
    checked_urls = []
    last_status = "Started"

    for path in COMMON_PATHS:
        if time.monotonic() - started_at >= max_seconds:
            return {
                "emails": "",
                "status": "Skipped after time limit",
                "checked_pages": " | ".join(checked_urls),
            }

        target_url = urljoin(base_url, path)
        html, status = fetch_page(target_url)
        last_status = status
        checked_urls.append(f"{target_url} [{status}]")

        if not html:
            continue

        found_emails.update(extract_emails_from_text(html))

        soup = BeautifulSoup(html, "lxml")

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()

            if href.startswith("mailto:"):
                email_part = href.replace("mailto:", "").split("?")[0].strip().lower()
                found_emails.update(extract_emails_from_text(email_part))

        if found_emails:
            return {
                "emails": ", ".join(sorted(found_emails)),
                "status": "Email found",
                "checked_pages": " | ".join(checked_urls),
            }

        time.sleep(0.1)

    return {
        "emails": "",
        "status": f"Email not found ({last_status})",
        "checked_pages": " | ".join(checked_urls),
    }
