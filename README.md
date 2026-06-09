# LeadMail Finder

LeadMail Finder is an open-source desktop tool that helps you discover companies, collect publicly available business contact information, clean lead lists, and manage controlled email outreach from one place.

It was originally created to simplify company research and outreach workflows for job seekers, freelancers, founders, recruiters, and small business owners.

Everything runs locally on your computer. No cloud account is required.

---

## Why LeadMail Finder?

Finding companies, collecting contact information, cleaning spreadsheets, and preparing outreach campaigns often requires multiple tools.

LeadMail Finder combines these steps into a single local workflow:

- Discover companies
- Import Google Maps exports
- Extract public business emails
- Remove duplicates
- Validate domains
- Build outreach lists
- Send controlled SMTP campaigns

---

## Example Workflow

1. Search companies on Google Maps
2. Export results with Instant Data Scraper
3. Import the CSV or Excel file
4. Extract public business emails
5. Validate and clean the list
6. Export the final outreach list
7. Send controlled outreach emails

---

## Features

### Company Discovery

- Search companies by keyword and city
- Google Maps workflow support
- Import Google Maps exports
- Multi-file CSV/Excel import
- Company list preview

### Data Processing

- CSV merge
- Duplicate cleanup
- Domain extraction
- Domain-based grouping
- Company data normalization

### Email Extraction

- Extract publicly available business emails from company websites
- Scan common contact pages
- Website timeout protection
- Progress tracking
- Resume extraction workflow

### Email Validation

- MX record validation
- Domain health checks
- Invalid domain filtering

### Export Options

- Full Excel export
- Full CSV export
- Email-only CSV export
- Outreach-ready export
- Sending log export

### Email Outreach

- Gmail support
- Outlook / Hotmail support
- Yahoo support
- Custom SMTP support
- Gmail App Password support
- Test email before campaign sending
- One-by-one sending
- Configurable delay
- Maximum email limit per run
- Stop after current email
- Live sending logs

### Security

- Credentials are never exported
- Credentials are never stored in CSV files
- Credentials are never stored in Excel files
- Session-only authentication
- Clear credentials action
- Local-first architecture

### User Experience

- Real-time progress tracking
- Pause and resume workflows
- Download results at any time
- Local processing
- No cloud dependency

---

## Security Notes

LeadMail Finder does not store SMTP credentials in files, CSV exports, Excel exports, logs, or generated reports.

For Gmail and Yahoo accounts, use an App Password instead of your normal account password.

For custom domains, use SMTP credentials provided by your email provider.

Recommended safe configuration:

- Maximum 25 emails per run
- 60 seconds delay between emails
- Send only to relevant public business addresses
- Always send a test email before starting a campaign

---

## Installation

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
pip install -r requirements.txt
```

### Run Application

```bash
streamlit run app.py
```

---

## Responsible Use

LeadMail Finder is intended for discovering publicly available business contact information and conducting legitimate outreach.

Please use the software responsibly and respectfully.

Do not use LeadMail Finder for:

- Spam
- Harassment
- Bulk unsolicited messaging
- Illegal data collection
- Activities that violate local regulations
- Activities that violate email provider policies

---

## Disclaimer

LeadMail Finder is designed for discovering publicly available business contact information and supporting legitimate outreach workflows.

Users are solely responsible for complying with applicable laws, regulations, email provider policies, and anti-spam requirements.

The project authors and contributors are not responsible for misuse of the software.

---

## License

MIT License
