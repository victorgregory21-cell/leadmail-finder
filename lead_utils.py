import re
from urllib.parse import urlparse

import dns.resolver
import pandas as pd
import tldextract


EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"


def normalize_website(url):
    if not isinstance(url, str) or not url.strip():
        return ""

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def extract_domain_from_website(url):
    url = normalize_website(url)

    if not url:
        return ""

    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")

    if not host:
        return ""

    ext = tldextract.extract(host)

    if not ext.domain or not ext.suffix:
        return host

    return f"{ext.domain}.{ext.suffix}"


def extract_email_list(value):
    if not isinstance(value, str):
        return []

    emails = re.findall(EMAIL_REGEX, value)

    cleaned = []

    for email in emails:
        email = email.strip().lower()

        if email and email not in cleaned:
            cleaned.append(email)

    return cleaned


def normalize_emails(value):
    emails = extract_email_list(value)
    return ", ".join(emails)


def email_domain(email):
    if "@" not in email:
        return ""

    return email.split("@", 1)[1].strip().lower()


def validate_single_email(email):
    email = (email or "").strip().lower()

    if not email:
        return "No email"

    if not re.fullmatch(EMAIL_REGEX, email):
        return "Invalid format"

    domain = email_domain(email)

    if not domain:
        return "Invalid domain"

    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        if answers:
            return "Valid MX"
    except Exception:
        pass

    try:
        answers = dns.resolver.resolve(domain, "A", lifetime=5)
        if answers:
            return "No MX, domain resolves"
    except Exception:
        pass

    return "Domain not found"


def validate_emails(value):
    emails = extract_email_list(value)

    if not emails:
        return "No email"

    statuses = []

    for email in emails:
        statuses.append(f"{email}: {validate_single_email(email)}")

    return " | ".join(statuses)


def prepare_leads_dataframe(df):
    result = df.copy().reset_index(drop=True)

    if "Website" in result.columns:
        result["Website"] = result["Website"].fillna("").astype(str).map(normalize_website)
    else:
        result["Website"] = ""

    if "Domain" not in result.columns:
        result["Domain"] = ""

    result["Domain"] = result.apply(
        lambda row: row["Domain"] if str(row["Domain"]).strip() else extract_domain_from_website(row.get("Website", "")),
        axis=1,
    )

    if "Emails" not in result.columns:
        result["Emails"] = ""

    result["Emails"] = result["Emails"].fillna("").astype(str).map(normalize_emails)

    return result


def deduplicate_leads(df):
    result = prepare_leads_dataframe(df)

    # Strongest duplicate key:
    # 1. Domain if available
    # 2. Website if available
    # 3. Company Name + Phone fallback
    def key_for(row):
        domain = str(row.get("Domain", "") or "").strip().lower()
        website = str(row.get("Website", "") or "").strip().lower()
        company = str(row.get("Company Name", "") or "").strip().lower()
        phone = str(row.get("Phone", "") or "").strip().lower()

        if domain:
            return f"domain:{domain}"

        if website:
            return f"website:{website}"

        return f"company:{company}|phone:{phone}"

    result["_dedupe_key"] = result.apply(key_for, axis=1)

    grouped_rows = []

    for _, group in result.groupby("_dedupe_key", dropna=False):
        base = group.iloc[0].copy()

        # Merge emails
        emails = []
        for value in group.get("Emails", []):
            for email in extract_email_list(value):
                if email not in emails:
                    emails.append(email)

        base["Emails"] = ", ".join(emails)

        # Prefer non-empty values
        for column in result.columns:
            if column == "_dedupe_key":
                continue

            if str(base.get(column, "") or "").strip():
                continue

            non_empty = group[column].dropna().astype(str)
            non_empty = non_empty[non_empty.str.strip() != ""]

            if not non_empty.empty:
                base[column] = non_empty.iloc[0]

        grouped_rows.append(base.drop(labels=["_dedupe_key"]))

    return pd.DataFrame(grouped_rows).reset_index(drop=True)


def group_by_domain(df):
    result = prepare_leads_dataframe(df)

    if result.empty:
        return pd.DataFrame()

    rows = []

    for domain, group in result.groupby("Domain", dropna=False):
        domain = str(domain or "").strip()

        if not domain:
            domain = "No domain"

        company_names = []
        websites = []
        phones = []
        emails = []

        for _, row in group.iterrows():
            company = str(row.get("Company Name", "") or "").strip()
            website = str(row.get("Website", "") or "").strip()
            phone = str(row.get("Phone", "") or "").strip()

            if company and company not in company_names:
                company_names.append(company)

            if website and website not in websites:
                websites.append(website)

            if phone and phone not in phones:
                phones.append(phone)

            for email in extract_email_list(str(row.get("Emails", "") or "")):
                if email not in emails:
                    emails.append(email)

        rows.append({
            "Domain": domain,
            "Companies": " | ".join(company_names),
            "Websites": " | ".join(websites),
            "Phones": " | ".join(phones),
            "Emails": ", ".join(emails),
            "Company Count": len(group),
            "Email Count": len(emails),
        })

    return pd.DataFrame(rows).sort_values(
        by=["Email Count", "Company Count"],
        ascending=[False, False],
    ).reset_index(drop=True)


def validate_dataframe_emails(df):
    result = prepare_leads_dataframe(df)

    if "Email Validation" not in result.columns:
        result["Email Validation"] = ""

    for index, row in result.iterrows():
        result.at[index, "Email Validation"] = validate_emails(row.get("Emails", ""))

    return result


def is_exportable_email(email):
    email = (email or "").strip().lower()

    if not email:
        return False

    if not re.fullmatch(EMAIL_REGEX, email):
        return False

    blocked_tokens = [
        "example",
        "ornek",
        "örnek",
        "test",
        "demo",
        "your",
        "mail.com",
    ]

    local_part = email.split("@", 1)[0]
    domain = email.split("@", 1)[1] if "@" in email else ""

    if len(local_part) > 64:
        return False

    if len(domain) > 253:
        return False

    if any(token in email for token in blocked_tokens):
        return False

    # Prevent long hashes accidentally captured as email-like strings.
    if len(local_part) > 32 and not any(ch in local_part for ch in [".", "_", "-"]):
        return False

    return True


def extract_unique_email_list(df, only_valid_mx=False):
    result = prepare_leads_dataframe(df)
    rows = []
    seen = set()

    for _, row in result.iterrows():
        validation_text = str(row.get("Email Validation", "") or "")

        for email in extract_email_list(row.get("Emails", "")):
            if not is_exportable_email(email):
                continue

            if only_valid_mx and f"{email}: Valid MX" not in validation_text:
                continue

            if email in seen:
                continue

            seen.add(email)
            rows.append({"Email": email})

    return pd.DataFrame(rows).sort_values("Email").reset_index(drop=True) if rows else pd.DataFrame(columns=["Email"])


def extract_outreach_list(df, only_valid_mx=False):
    result = prepare_leads_dataframe(df)
    rows = []
    seen = set()

    for _, row in result.iterrows():
        company = str(row.get("Company Name", "") or "").strip()
        website = str(row.get("Website", "") or "").strip()
        phone = str(row.get("Phone", "") or "").strip()
        domain = str(row.get("Domain", "") or "").strip()
        validation_text = str(row.get("Email Validation", "") or "")

        for email in extract_email_list(row.get("Emails", "")):
            if not is_exportable_email(email):
                continue

            if only_valid_mx and f"{email}: Valid MX" not in validation_text:
                continue

            key = f"{company}|{email}"

            if key in seen:
                continue

            seen.add(key)

            rows.append({
                "Company Name": company,
                "Email": email,
                "Website": website,
                "Phone": phone,
                "Domain": domain,
                "Email Validation": validation_text,
            })

    return pd.DataFrame(rows).reset_index(drop=True) if rows else pd.DataFrame(
        columns=["Company Name", "Email", "Website", "Phone", "Domain", "Email Validation"]
    )


def extract_campaign_recipients(df, only_valid_mx=False):
    """Return a clean single-column recipient dataframe for email campaigns."""
    email_df = extract_unique_email_list(df, only_valid_mx=only_valid_mx)
    if email_df.empty:
        return pd.DataFrame(columns=["Email", "Send Status", "Send Message"])

    email_df["Send Status"] = ""
    email_df["Send Message"] = ""
    return email_df
