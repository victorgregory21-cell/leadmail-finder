# LeadMail Finder

LeadMail Finder is an open-source local tool for building company outreach lists from public data.

## Main Workflow

1. Search companies on Google Maps.
2. Export one or more lists with Instant Data Scraper.
3. Import CSV/Excel files into LeadMail Finder.
4. Merge lists and remove duplicates.
5. Extract publicly visible business emails from company websites.
6. Validate email domains with MX checks.
7. Group results by domain.
8. Download clean Excel/CSV output, email-only CSV, or outreach list.
9. Optionally send controlled outreach emails from Gmail, Outlook/Hotmail, Yahoo, or custom SMTP.

## Features

- Multi-file CSV/Excel import
- CSV merge
- Duplicate cleanup
- Domain extraction
- Domain-based grouping
- Email extraction from public websites
- MX-based email domain validation
- Email-only CSV export
- Outreach Excel/CSV export
- Multi-provider SMTP sender
- Gmail App Password support
- Outlook/Hotmail SMTP support
- Yahoo App Password support
- Custom SMTP support
- Credentials are session-only and never exported
- Clear credentials button
- Test email required before campaign
- One-by-one sending
- Configurable delay between emails
- Maximum emails per run
- Sending log export
- Stop after current email
- Runs fully locally

## Security Notes

LeadMail Finder does not store SMTP credentials in files, CSV, Excel, logs, or exports.

For Gmail and Yahoo, use an App Password instead of your normal account password.

For custom domains, use SMTP credentials provided by your email provider.

Recommended safe start:

- 25 emails per run
- 60 seconds delay
- Send only to relevant public business addresses
- Always send a test email first

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Responsible Use

This project is intended for collecting publicly available business contact information and sending respectful outreach.

Do not use it for spam, harassment, or illegal data collection.

## License

MIT
