import re
import time
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

COMMON_PATHS = [
    "",
    "/iletisim",
    "/iletişim",
    "/contact",
    "/contact-us",
    "/kariyer",
    "/career",
    "/careers",
    "/jobs",
    "/insan-kaynaklari",
    "/insan-kaynakları",
    "/hakkimizda",
    "/hakkımızda",
]

PRIORITY_LINK_KEYWORDS = [
    "iletisim", "iletişim", "contact", "contacts", "bize-ulasin", "bize-ulaşın",
    "kariyer", "career", "careers", "jobs", "insan-kaynaklari", "insan-kaynakları",
    "hr", "ik", "about", "hakkimizda", "hakkımızda", "kurumsal"
]

REQUEST_TIMEOUT_SECONDS = 8
COMPANY_MAX_SECONDS = 25
MAX_INTERNAL_LINKS = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

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

BAD_FILE_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".ico",
    ".pdf", ".woff", ".woff2", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar"
)


def normalize_url(url):
    if not isinstance(url, str) or not url.strip() or url.strip().lower() == "nan":
        return None

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def same_domain(url1, url2):
    return urlparse(url1).netloc.lower().replace("www.", "") == urlparse(url2).netloc.lower().replace("www.", "")


def decode_obfuscated_emails(text):
    if not text:
        return ""

    replacements = {
        " [at] ": "@", "[at]": "@", "(at)": "@", " at ": "@",
        " [dot] ": ".", "[dot]": ".", "(dot)": ".", " dot ": ".",
        " {at} ": "@", "{at}": "@", " {dot} ": ".", "{dot}": ".",
    }

    decoded = text
    for old, new in replacements.items():
        decoded = decoded.replace(old, new).replace(old.upper(), new)

    return decoded


def extract_emails_from_text(text):
    emails = set(re.findall(EMAIL_REGEX, decode_obfuscated_emails(text or "")))
    clean_emails = set()

    for email in emails:
        email = email.strip().lower().strip(".,;:()[]{}<>\"'")

        if email in BLOCKED_EMAILS:
            continue

        if email.endswith(BAD_FILE_EXTENSIONS):
            continue

        if any(token in email for token in ["example@", "your@", "ornek@", "örnek@", "test@", "demo@"]):
            continue

        if ".." in email:
            continue

        clean_emails.add(email)

    return clean_emails


def fetch_page_requests(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=(REQUEST_TIMEOUT_SECONDS, REQUEST_TIMEOUT_SECONDS),
            allow_redirects=True,
            verify=False,
        )

        if response.status_code >= 400:
            return "", f"HTTP {response.status_code}"

        return response.text, "OK"

    except requests.exceptions.Timeout:
        return "", "Timeout"

    except requests.exceptions.ConnectionError:
        return "", "Connection error"

    except Exception as exc:
        return "", f"Error: {type(exc).__name__}"


def fetch_page_browser(url):
    browser = None
    context = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--ignore-certificate-errors",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="tr-TR",
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 1000},
            )
            page = context.new_page()
            page.set_default_timeout(12000)
            page.goto(url, wait_until="domcontentloaded", timeout=12000)
            page.wait_for_timeout(1200)

            for _ in range(2):
                page.mouse.wheel(0, 2200)
                page.wait_for_timeout(500)

            return page.content(), "OK browser"
    except Exception as exc:
        return "", f"Browser error: {type(exc).__name__}"
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if browser:
            try:
                browser.close()
            except Exception:
                pass


def fetch_page(url):
    html, status = fetch_page_requests(url)

    if html and len(html) > 1200:
        return html, status

    browser_html, browser_status = fetch_page_browser(url)

    if browser_html:
        return browser_html, browser_status

    return html, status


def extract_mailto_emails(html):
    soup = BeautifulSoup(html or "", "lxml")
    emails = set()

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()

        if href.startswith("mailto:"):
            email_part = href.replace("mailto:", "").split("?")[0].strip().lower()
            emails.update(extract_emails_from_text(email_part))

    return emails


def find_priority_links(base_url, html):
    soup = BeautifulSoup(html or "", "lxml")
    links = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        absolute = urljoin(base_url, href).split("#")[0]

        if not same_domain(base_url, absolute):
            continue

        lowered = absolute.lower()
        if not any(keyword in lowered for keyword in PRIORITY_LINK_KEYWORDS):
            continue

        if absolute in seen:
            continue

        seen.add(absolute)
        links.append(absolute)

    return links[:MAX_INTERNAL_LINKS]


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
    urls_to_check = []
    seen_urls = set()

    for path in COMMON_PATHS:
        target_url = urljoin(base_url, path)
        if target_url not in seen_urls:
            seen_urls.add(target_url)
            urls_to_check.append(target_url)

    index = 0
    while index < len(urls_to_check):
        if time.monotonic() - started_at >= max_seconds:
            return {
                "emails": ", ".join(sorted(found_emails)),
                "status": "Time limit exceeded" if found_emails else "Skipped after time limit",
                "checked_pages": " | ".join(checked_urls),
            }

        target_url = urls_to_check[index]
        index += 1

        html, status = fetch_page(target_url)
        last_status = status
        checked_urls.append(f"{target_url} [{status}]")

        if not html:
            continue

        found_emails.update(extract_emails_from_text(html))
        found_emails.update(extract_mailto_emails(html))

        if index == 1:
            for internal_link in find_priority_links(base_url, html):
                if internal_link not in seen_urls:
                    seen_urls.add(internal_link)
                    urls_to_check.append(internal_link)

        if found_emails:
            return {
                "emails": ", ".join(sorted(found_emails)),
                "status": "Email found",
                "checked_pages": " | ".join(checked_urls),
            }

        time.sleep(0.05)

    return {
        "emails": ", ".join(sorted(found_emails)),
        "status": "Email found" if found_emails else f"Email not found ({last_status})",
        "checked_pages": " | ".join(checked_urls),
    }
