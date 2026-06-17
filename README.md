# LeadMail Finder

LeadMail Finder is an open-source desktop tool for discovering companies, collecting publicly available business email addresses, validating domains, and preparing controlled outreach campaigns.

It runs entirely on your machine and is designed for job seekers, freelancers, founders, recruiters, agencies, and small teams that need a local-first workflow for company research and respectful email outreach.

---

## Why LeadMail Finder?

Company research and outreach usually require multiple separate tools:

- Finding relevant companies
- Importing and cleaning spreadsheets
- Discovering company websites
- Extracting public business emails
- Validating domains
- Preparing outreach lists
- Sending emails safely and slowly
- Tracking sending results

LeadMail Finder combines these steps into a single local workflow.

---

## Features

### Company Discovery

- Search companies by keyword and city
- Google Maps workflow support
- Import Google Maps / Instant Data Scraper exports
- Import multiple CSV and Excel files
- Merge company lists into a single dataset
- Automatic duplicate cleanup
- Company website normalization
- Domain extraction and grouping

### Teknopark Finder

- Discover companies directly from public Teknopark websites
- Extract company websites from:
  - Direct website links
  - Text-based domains
  - Internal company detail pages
- JavaScript-rendered page support via Playwright
- Broken SSL certificate tolerance where technically possible
- Timeout and error handling for unstable company websites
- Automatic public email scanning after company discovery
- Export Teknopark results as CSV or Excel

### Email Discovery

- Extract publicly visible business emails from company websites
- Scan homepage, contact, career, about, and HR-related pages
- Detect `mailto:` emails
- Detect common plain-text email formats
- Deduplicate emails
- Filter invalid or noisy matches
- Timeout protection per website
- Progress tracking during extraction

### Email Validation

- MX record validation
- Domain health checks
- Invalid domain filtering
- Domain-based grouping
- Email-only export generation
- Outreach-ready export generation

### Controlled Email Outreach

LeadMail Finder includes a local SMTP-based outreach workflow designed for controlled, manual, and responsible sending.

Supported providers:

- Gmail
- Outlook / Hotmail
- Yahoo
- Custom SMTP servers

Outreach safety features:

- Test email required before campaign sending
- One-by-one email sending
- Configurable delay between emails
- Maximum emails per run
- Stop after current email
- Live sending logs
- Sending log export
- Session-only SMTP credentials
- Clear credentials action

Recommended safe starting configuration:

- Send a test email first
- Use a low maximum email count per run
- Use at least 60 seconds delay between emails
- Send only relevant, personalized, legitimate outreach
- Avoid bulk unsolicited messaging

### Privacy & Security

- Runs completely locally
- No cloud processing
- No external database
- No analytics or tracking
- SMTP credentials remain session-only
- SMTP credentials are never exported
- SMTP credentials are never stored in CSV files
- SMTP credentials are never stored in Excel files
- SMTP credentials are never stored in sending logs

---

## Main Workflows

### Workflow 1 – CSV / Excel Import

1. Export company data from any source.
2. Import one or more CSV/Excel files.
3. Merge and clean the data.
4. Discover or normalize company websites.
5. Extract publicly available business emails.
6. Validate domains.
7. Export the final list.

### Workflow 2 – Teknopark Finder

1. Open the Teknopark Finder tab.
2. Paste one or more public Teknopark company-list URLs.
3. Discover company websites automatically.
4. Scan websites for publicly visible business emails.
5. Validate and clean the results.
6. Export the final Teknopark lead list.

### Workflow 3 – Controlled Outreach Campaign

1. Build or import a verified contact list.
2. Configure SMTP credentials.
3. Send a test email.
4. Set delay and maximum sending limits.
5. Start the campaign.
6. Monitor live sending logs.
7. Stop after the current email when needed.
8. Export the sending log.

---

## Installation

### Requirements

- Python 3.11 or Python 3.12 recommended
- Chromium browser for Playwright

### Clone Repository

```bash
git clone https://github.com/mahmutaunal/leadmail-finder.git
cd leadmail-finder
```

### Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Install Playwright Chromium

```bash
python -m playwright install chromium
```

### Run Application

```bash
streamlit run app.py
```

Default local URL:

```text
http://localhost:8501
```

---

## Running After First Setup

After the first installation, you only need:

```bash
cd leadmail-finder
source venv/bin/activate
streamlit run app.py
```

Stop the application with:

```text
Ctrl + C
```

---

## Supported Input Sources

- Google Maps exports
- Instant Data Scraper exports
- CSV files
- Excel files (`.xlsx`)
- Public Teknopark company directories
- Custom company lists

---

## Supported Output Formats

- Full CSV export
- Full Excel export
- Email-only CSV export
- Outreach-ready CSV export
- Outreach-ready Excel export
- Sending log export

---

## Responsible Use

LeadMail Finder is intended for discovering publicly available business contact information and supporting legitimate outreach workflows.

Users are responsible for complying with applicable laws, regulations, email provider policies, anti-spam rules, and platform terms of service.

Do not use LeadMail Finder for:

- Spam
- Harassment
- Bulk unsolicited messaging
- Illegal data collection
- Circumventing access controls
- Activities that violate local regulations
- Activities that violate email provider policies

The project author and contributors are not responsible for misuse of the software.

---

## Security Notes

- Use Gmail or Yahoo App Passwords instead of normal account passwords.
- Use provider-specific SMTP credentials for custom domains.
- Keep sending limits low and delays high.
- Always send a test email before starting a campaign.
- Review your recipient list before sending.
- Send only relevant and respectful messages.

---

## Tech Stack

- Python
- Streamlit
- Pandas
- Requests
- BeautifulSoup
- Playwright
- OpenPyXL
- DNSPython
- TLDExtract

---

## License

MIT License

Copyright (c) 2026 AlpWare Studio
