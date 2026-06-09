import re
import time
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
import tldextract


BLOCKED_DOMAINS = {
    "google.com",
    "google.com.tr",
    "duckduckgo.com",
    "bing.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "tr.linkedin.com",
    "maps.google.com",
}

SOFT_DIRECTORY_DOMAINS = {
    "trbul.net",
    "bulurum.com",
    "yandex.com.tr",
    "nerede360.com",
    "armut.com",
    "iyifirma.com",
    "iyisinerede.com",
    "sahibinden.com",
    "firmasec.com",
    "firmarehberim.com",
    "firmalar.co",
    "kayserifirmarehberi.com",
}


def clean_title(title):
    if not title:
        return ""

    title = re.sub(r"\s+", " ", title).strip()
    title = title.replace("| LinkedIn", "").replace("- LinkedIn", "").strip()
    title = re.sub(r"\s+-\s+.*$", "", title).strip()
    return title


def unwrap_url(url):
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    parsed = urlparse(url)

    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        uddg = query.get("uddg", [""])[0]

        if uddg:
            return unquote(uddg)

    return url


def get_domain(url):
    if not url:
        return ""

    url = unwrap_url(url)
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")

    if not host:
        return ""

    ext = tldextract.extract(host)

    if not ext.domain or not ext.suffix:
        return host

    return f"{ext.domain}.{ext.suffix}"


def is_blocked_platform(url):
    domain = get_domain(url)

    if not domain:
        return True

    for blocked in BLOCKED_DOMAINS:
        if domain == blocked or domain.endswith("." + blocked):
            return True

    return False


def is_soft_directory_result(url, title=""):
    domain = get_domain(url)
    title_lower = (title or "").lower()

    if domain in SOFT_DIRECTORY_DOMAINS:
        return True

    directory_words = [
        "firma rehberi",
        "sarı sayfalar",
        "sari sayfalar",
        "yakınımda",
        "yakinimda",
    ]

    return any(word in title_lower for word in directory_words)


def request_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    response = requests.get(url, headers=headers, timeout=(6, 14))
    response.raise_for_status()
    return response.text


def duckduckgo_search(query, limit=20):
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        html = request_html(url)
    except requests.exceptions.RequestException:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    for result in soup.select(".result"):
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")

        if not title_el:
            continue

        href = unwrap_url(title_el.get("href", "").strip())
        title = clean_title(title_el.get_text(" ", strip=True))
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

        if not href:
            continue

        results.append({
            "title": title,
            "url": href,
            "domain": get_domain(href),
            "snippet": snippet,
            "search_provider": "DuckDuckGo",
        })

        if len(results) >= limit:
            break

    return results


def bing_search(query, limit=20):
    url = f"https://www.bing.com/search?q={quote_plus(query)}&cc=tr"

    try:
        html = request_html(url)
    except requests.exceptions.RequestException:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    for item in soup.select("li.b_algo"):
        title_el = item.select_one("h2 a")
        snippet_el = item.select_one(".b_caption p")

        if not title_el:
            continue

        href = unwrap_url(title_el.get("href", "").strip())
        title = clean_title(title_el.get_text(" ", strip=True))
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

        if not href:
            continue

        results.append({
            "title": title,
            "url": href,
            "domain": get_domain(href),
            "snippet": snippet,
            "search_provider": "Bing",
        })

        if len(results) >= limit:
            break

    return results


def search_web(query, limit=20):
    """
    v8:
    - Try DuckDuckGo first.
    - If empty or unavailable, fallback to Bing.
    - This fixes the 'no result' issue caused by one search provider.
    """
    results = duckduckgo_search(query, limit=limit)

    if results:
        return results

    time.sleep(0.5)
    return bing_search(query, limit=limit)


def build_company_queries(keyword, city):
    keyword = keyword.strip()
    city = city.strip()

    raw_queries = [
        f'{city} {keyword}',
        f'{city} {keyword} iletişim',
        f'{city} {keyword} resmi site',
        f'{city} {keyword} email',
        f'{city} yazılım şirketi',
        f'{city} yazılım firması',
        f'{city} mobil uygulama firması',
        f'{city} web tasarım firması',
        f'{city} teknoloji firması',
        f'{city} ERP firması',
        f'{city} otomasyon firması',
        f'{city} teknopark yazılım',
    ]

    unique_queries = []
    seen = set()

    for query in raw_queries:
        key = query.lower().strip()

        if key in seen:
            continue

        seen.add(key)
        unique_queries.append(query)

    return unique_queries


def discover_company_websites(keyword, city, limit=20, strict_filter=False):
    companies = []
    seen_domains = set()
    per_query_limit = max(10, min(limit, 25))

    for query in build_company_queries(keyword, city):
        raw_results = search_web(query, limit=per_query_limit)

        for item in raw_results:
            url = item["url"]
            domain = item["domain"]
            title = item["title"]

            if is_blocked_platform(url):
                continue

            if strict_filter and is_soft_directory_result(url, title):
                continue

            if domain in seen_domains:
                continue

            seen_domains.add(domain)

            companies.append({
                "Company Name": title,
                "Website": url,
                "Domain": domain,
                "Source": item.get("search_provider", "Web Search"),
                "Source URL": url,
                "LinkedIn": "",
                "Notes": item["snippet"],
            })

            if len(companies) >= limit:
                return companies

    return companies[:limit]


def discover_linkedin_company_pages(keyword, city, limit=20):
    queries = [
        f'site:linkedin.com/company {city} {keyword}',
        f'site:linkedin.com/company {city} yazılım',
        f'site:linkedin.com/company {city} teknoloji',
        f'site:linkedin.com/company {city} software',
        f'site:linkedin.com/company {city} mobile',
    ]

    linkedin_results = []
    seen_urls = set()

    for query in queries:
        raw_results = search_web(query, limit=max(10, min(limit, 25)))

        for item in raw_results:
            url = item["url"]

            if "linkedin.com/company" not in url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            linkedin_results.append({
                "Company Name": item["title"],
                "Website": "",
                "Domain": "",
                "Source": f"LinkedIn Search ({item.get('search_provider', 'Web')})",
                "Source URL": url,
                "LinkedIn": url,
                "Notes": item["snippet"],
            })

            if len(linkedin_results) >= limit:
                return linkedin_results

    return linkedin_results


def build_google_maps_search_url(keyword, city):
    query = quote_plus(f"{city} {keyword}")
    return f"https://www.google.com/maps/search/{query}"


def build_google_search_url(keyword, city):
    query = quote_plus(f"{city} {keyword} firma iletişim")
    return f"https://www.google.com/search?q={query}"


def build_linkedin_google_search_url(keyword, city):
    query = quote_plus(f'site:linkedin.com/company {city} {keyword}')
    return f"https://www.google.com/search?q={query}"
