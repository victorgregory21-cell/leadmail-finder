import asyncio
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import pandas as pd
import requests
import tldextract
import urllib3
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from data_utils import RESULT_COLUMNS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REQUEST_TIMEOUT = 12
PAGE_TIMEOUT_MS = 18000
MAX_SOURCE_DETAIL_PAGES = 250
DETAIL_PAGE_TIMEOUT_SECONDS = 10
MAX_CONCURRENT_DETAIL_SCANS = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

DOMAIN_REGEX = re.compile(
    r"(?<!@)\b(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\b(?:/[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?"
)

SOURCE_DETAIL_KEYWORDS = [
    "firma", "firmalar", "company", "companies", "tenant", "startup", "giris", "giriş",
    "detay", "detail", "store", "magaza", "mağaza", "proje", "project"
]

BAD_DOMAINS = [
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "google.com", "maps.google", "wa.me", "whatsapp.com",
    "t.me", "telegram.me", "apple.com", "play.google.com", "schema.org", "w3.org",
    "wordpress.org", "jquery.com", "bootstrapcdn.com", "cloudflare.com", "fontawesome.com",
    "gstatic.com", "googletagmanager.com", "googleapis.com", "doubleclick.net"
]

BAD_FILE_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".css", ".js", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".mp4", ".mp3"
)


@dataclass(frozen=True)
class CandidateSite:
    url: str
    source: str


def root_domain(url: str) -> str:
    parsed = urlparse(url)
    ext = tldextract.extract(parsed.netloc)

    if not ext.domain or not ext.suffix:
        return parsed.netloc.lower().replace("www.", "")

    return f"{ext.domain}.{ext.suffix}".lower()


def normalize_url(url: str) -> str | None:
    if not url:
        return None

    url = unquote(str(url).strip())
    url = url.replace("\\/", "/")

    if url.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None

    if url.startswith("//"):
        url = "https:" + url

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    if not parsed.netloc or "." not in parsed.netloc:
        return None

    host = parsed.netloc.lower().strip()

    if host.startswith("www."):
        host = host[4:]

    normalized = f"{parsed.scheme}://{host}"

    if any(host.endswith(ext) for ext in BAD_FILE_EXTENSIONS):
        return None

    if not is_valid_company_domain(normalized):
        return None

    return normalized


def normalize_page_url(base_url: str, url: str) -> str | None:
    if not url:
        return None

    url = unquote(str(url).strip())

    if url.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None

    absolute = urljoin(base_url, url).split("#")[0]
    parsed = urlparse(absolute)

    if not parsed.netloc:
        return None

    if parsed.path.lower().endswith(BAD_FILE_EXTENSIONS):
        return None

    return absolute


def is_valid_company_domain(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "").strip()

    if not host or "." not in host:
        return False

    if any(char in host for char in ["_", ".."]):
        return False

    if re.fullmatch(r"[0-9.\-]+", host):
        return False

    ext = tldextract.extract(host)

    if not ext.domain or not ext.suffix:
        return False

    if ext.domain.isdigit() or ext.suffix.isdigit():
        return False

    if len(ext.domain) < 2 or len(ext.suffix) < 2:
        return False

    # Reject version/chunk-like hosts such as 0.1, 0-11.8, 1-2-3.4.
    if re.fullmatch(r"[0-9][0-9a-z.\-]*", host) and not re.search(r"[a-z]{2,}", host):
        return False

    return True


def is_bad_domain(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return any(bad in domain for bad in BAD_DOMAINS)


def extract_links(base_url: str, html: str) -> set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    links = set()

    for tag in soup.find_all("a", href=True):
        normalized = normalize_page_url(base_url, tag["href"])
        if normalized:
            links.add(normalized)

    return links


def extract_domains_from_text(base_url: str, html: str) -> set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)
    combined = f"{html or ''} {text}"
    domains = set()

    for match in DOMAIN_REGEX.findall(combined):
        candidate = match.strip().strip(".,;:()[]{}<>\"'")

        if "@" in candidate:
            continue

        if candidate.lower().endswith(BAD_FILE_EXTENSIONS):
            continue

        normalized = normalize_url(candidate)

        if not normalized:
            continue

        if is_bad_domain(normalized):
            continue

        if not is_valid_company_domain(normalized):
            continue

        if root_domain(normalized) == root_domain(base_url):
            continue

        domains.add(normalized)

    return domains


def get_html_with_requests(url: str) -> str | None:
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            verify=False,
        )
        response.raise_for_status()
        return response.text
    except Exception:
        return None


async def get_html_with_browser(url: str) -> str | None:
    browser = None
    context = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--ignore-certificate-errors",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="tr-TR",
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 1000},
            )

            page = await context.new_page()
            page.set_default_timeout(PAGE_TIMEOUT_MS)
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            await page.wait_for_timeout(1200)

            for _ in range(2):
                await page.mouse.wheel(0, 2200)
                await page.wait_for_timeout(500)

            return await page.content()
    except Exception:
        return None
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


async def get_html(url: str) -> str | None:
    html = get_html_with_requests(url)

    if html and len(html) > 1200:
        return html

    return await get_html_with_browser(url)


def looks_like_source_detail_link(source_url: str, link: str) -> bool:
    if root_domain(source_url) != root_domain(link):
        return False

    lowered = link.lower()
    return any(keyword in lowered for keyword in SOURCE_DETAIL_KEYWORDS)


def pick_source_detail_pages(source_url: str, html: str) -> list[str]:
    detail_links = []

    for link in extract_links(source_url, html):
        if is_bad_domain(link):
            continue

        if looks_like_source_detail_link(source_url, link):
            detail_links.append(link)

    unique = []
    seen = set()

    for link in detail_links:
        if link not in seen:
            seen.add(link)
            unique.append(link)

    return unique[:MAX_SOURCE_DETAIL_PAGES]


def extract_candidate_sites_from_html(source_url: str, html: str, source_label: str) -> set[CandidateSite]:
    candidates = set()
    source_root = root_domain(source_url)

    for link in extract_links(source_url, html):
        if is_bad_domain(link):
            continue

        if root_domain(link) == source_root:
            continue

        normalized = normalize_url(link)
        if normalized:
            candidates.add(CandidateSite(normalized, source_label))

        parsed = urlparse(link)
        query_values = parse_qs(parsed.query)

        for values in query_values.values():
            for value in values:
                possible_url = normalize_url(value)
                if possible_url and root_domain(possible_url) != source_root and not is_bad_domain(possible_url):
                    candidates.add(CandidateSite(possible_url, source_label))

    for domain in extract_domains_from_text(source_url, html):
        candidates.add(CandidateSite(domain, source_label))

    return candidates


async def inspect_detail_page(detail_url: str, source_url: str, semaphore: asyncio.Semaphore) -> set[CandidateSite]:
    async with semaphore:
        try:
            detail_html = await asyncio.wait_for(get_html(detail_url), timeout=DETAIL_PAGE_TIMEOUT_SECONDS)
        except Exception:
            return set()

        if not detail_html:
            return set()

        return extract_candidate_sites_from_html(detail_url, detail_html, source_url)


async def discover_one_source(source_url: str) -> set[CandidateSite]:
    source_url = normalize_url(source_url) or source_url
    html = await get_html(source_url)

    if not html:
        return set()

    candidates = extract_candidate_sites_from_html(source_url, html, source_url)
    detail_pages = pick_source_detail_pages(source_url, html)

    if len(candidates) < 40 and detail_pages:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DETAIL_SCANS)
        tasks = [inspect_detail_page(url, source_url, semaphore) for url in detail_pages]

        for task in asyncio.as_completed(tasks):
            try:
                candidates.update(await task)
            except Exception:
                continue

    return candidates


def dedupe_candidates(candidates: set[CandidateSite]) -> list[CandidateSite]:
    by_root: dict[str, CandidateSite] = {}

    for candidate in candidates:
        normalized = normalize_url(candidate.url)

        if not normalized or is_bad_domain(normalized) or not is_valid_company_domain(normalized):
            continue

        key = root_domain(normalized)

        if not key or key in by_root:
            continue

        by_root[key] = CandidateSite(normalized, candidate.source)

    return sorted(by_root.values(), key=lambda item: item.url)


def candidates_to_dataframe(candidates: list[CandidateSite]) -> pd.DataFrame:
    rows = []

    for candidate in candidates:
        row = {column: "" for column in RESULT_COLUMNS}
        domain = root_domain(candidate.url)
        row["Company Name"] = domain
        row["Website"] = candidate.url
        row["Domain"] = domain
        row["Source"] = "Teknopark"
        row["Source URL"] = candidate.source
        rows.append(row)

    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


def discover_teknopark_companies(source_urls: list[str]) -> pd.DataFrame:
    async def run() -> pd.DataFrame:
        all_candidates: set[CandidateSite] = set()

        for source_url in source_urls:
            try:
                all_candidates.update(await discover_one_source(source_url))
            except Exception:
                continue

        return candidates_to_dataframe(dedupe_candidates(all_candidates))

    try:
        return asyncio.run(run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(run())
        finally:
            loop.close()
