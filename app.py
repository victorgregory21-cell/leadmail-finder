import re
import pandas as pd
import streamlit as st

from data_utils import (
    RESULT_COLUMNS,
    dataframe_to_csv_bytes,
    dataframe_to_excel_bytes,
    normalize_uploaded_maps_file,
)
from email_finder import find_emails_on_site
from email_sender import PROVIDER_PRESETS, SmtpConfig, send_single_email
from lead_utils import (
    deduplicate_leads,
    extract_campaign_recipients,
    extract_outreach_list,
    extract_unique_email_list,
    group_by_domain,
    prepare_leads_dataframe,
    validate_dataframe_emails,
)
from search_sources import (
    build_google_maps_search_url,
    build_google_search_url,
    build_linkedin_google_search_url,
    discover_company_websites,
    discover_linkedin_company_pages,
)


st.set_page_config(
    page_title="LeadMail Finder",
    page_icon="📬",
    layout="wide",
)


VISIBLE_COLUMNS = [
    "Company Name",
    "Website",
    "Phone",
    "Emails",
    "Email Status",
    "Email Validation",
]


SEND_VISIBLE_COLUMNS = [
    "Email",
    "Send Status",
    "Send Message",
]


def init_state():
    defaults = {
        "active_job": None,
        "uploaded_df": pd.DataFrame(columns=RESULT_COLUMNS),
        "import_results": pd.DataFrame(columns=RESULT_COLUMNS),
        "discover_results": pd.DataFrame(columns=RESULT_COLUMNS),
        "domain_groups": pd.DataFrame(),
        "last_upload_signature": "",
        "job_index": 0,
        "job_total": 0,
        "job_status": "Idle",
        "job_message": "",
        "job_time_limit": 25,
        "send_recipients": pd.DataFrame(columns=["Email", "Send Status", "Send Message"]),
        "send_job_index": 0,
        "send_status": "Idle",
        "send_message": "",
        "send_test_ok": False,
        "send_attachment_name": "",
        "send_attachment_bytes": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_running():
    return st.session_state.active_job is not None


def is_email_job_running():
    return st.session_state.active_job == "send"


def is_processed(row):
    emails = str(row.get("Emails", "") or "").strip()
    status = str(row.get("Email Status", "") or "").strip()

    if emails:
        return True

    if not status:
        return False

    retryable_statuses = {
        "Waiting",
        "Started",
        "Failed",
        "Skipped after time limit",
        "Time limit exceeded",
    }

    return status not in retryable_statuses


def reset_email_columns(df):
    result = df.copy().reset_index(drop=True)
    result["Emails"] = ""
    result["Email Status"] = ""
    result["Email Validation"] = ""
    result["Checked Pages"] = ""
    return result


def ensure_result_columns(df):
    result = df.copy().reset_index(drop=True)

    for column in RESULT_COLUMNS:
        if column not in result.columns:
            result[column] = ""

    return result[RESULT_COLUMNS]


def progress_value(done, total):
    if total <= 0:
        return 0
    return max(0, min(100, int((done / total) * 100)))


def metrics(df):
    df = ensure_result_columns(df)

    companies = len(df)
    websites = len(df[df["Website"].astype(str).str.strip() != ""])
    emails = len(df[df["Emails"].astype(str).str.strip() != ""])
    done = len(df[df.apply(is_processed, axis=1)])
    remaining = max(0, companies - done)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Companies", companies)
    col2.metric("Websites", websites)
    col3.metric("Emails found", emails)
    col4.metric("Remaining", remaining)


def result_table(df, height=420):
    df = ensure_result_columns(df)

    if df.empty:
        st.info("No companies loaded yet.")
        return

    existing = [col for col in VISIBLE_COLUMNS if col in df.columns]

    st.dataframe(
        df[existing].reset_index(drop=True),
        use_container_width=True,
        height=height,
    )


def download_buttons(df, file_prefix, key_prefix, disabled=False, domain_groups=None):
    df = ensure_result_columns(df)

    if df.empty:
        return

    only_valid_mx = st.checkbox(
        "Export only emails with Valid MX",
        value=False,
        disabled=disabled,
        key=f"{key_prefix}_valid_mx_only",
        help="When enabled, email-only and outreach exports include only addresses whose domain has a valid MX record.",
    )

    email_list_df = extract_unique_email_list(df, only_valid_mx=only_valid_mx)
    outreach_df = extract_outreach_list(df, only_valid_mx=only_valid_mx)

    st.markdown("#### Full data")

    full_col1, full_col2, full_col3 = st.columns([1, 1, 1])

    with full_col1:
        st.download_button(
            "Download full Excel",
            data=dataframe_to_excel_bytes(df),
            file_name=f"{file_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=disabled,
            key=f"{key_prefix}_full_excel",
        )

    with full_col2:
        st.download_button(
            "Download full CSV",
            data=dataframe_to_csv_bytes(df),
            file_name=f"{file_prefix}.csv",
            mime="text/csv",
            disabled=disabled,
            key=f"{key_prefix}_full_csv",
        )

    if domain_groups is not None and not domain_groups.empty:
        with full_col3:
            st.download_button(
                "Download grouped Excel",
                data=dataframe_to_excel_bytes(
                    df,
                    sheets={
                        "Leads": df,
                        "Domain Groups": domain_groups,
                    },
                ),
                file_name=f"{file_prefix}_grouped.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=disabled,
                key=f"{key_prefix}_grouped_excel",
            )

    st.markdown("#### Email exports")

    email_col1, email_col2, email_col3 = st.columns([1, 1, 1])

    with email_col1:
        st.download_button(
            "Download email list CSV",
            data=dataframe_to_csv_bytes(email_list_df),
            file_name=f"{file_prefix}_emails_only.csv",
            mime="text/csv",
            disabled=disabled or email_list_df.empty,
            key=f"{key_prefix}_emails_csv",
        )

    with email_col2:
        st.download_button(
            "Download outreach Excel",
            data=dataframe_to_excel_bytes(outreach_df),
            file_name=f"{file_prefix}_outreach.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=disabled or outreach_df.empty,
            key=f"{key_prefix}_outreach_excel",
        )

    with email_col3:
        st.download_button(
            "Download outreach CSV",
            data=dataframe_to_csv_bytes(outreach_df),
            file_name=f"{file_prefix}_outreach.csv",
            mime="text/csv",
            disabled=disabled or outreach_df.empty,
            key=f"{key_prefix}_outreach_csv",
        )

    if email_list_df.empty:
        st.caption("No exportable email addresses found yet.")
    else:
        st.caption(f"{len(email_list_df)} unique email address(es) ready for export.")


def start_job(job_type, df, time_limit):
    st.session_state.active_job = job_type
    st.session_state.job_index = 0
    st.session_state.job_total = len(df)
    st.session_state.job_status = "Running"
    st.session_state.job_message = "Starting extraction..."
    st.session_state.job_time_limit = time_limit


def stop_job(message="Stopped. You can download the current results."):
    st.session_state.job_status = "Stopped"
    st.session_state.job_message = message
    st.session_state.active_job = None


def complete_job():
    st.session_state.job_status = "Completed"
    st.session_state.job_message = "Extraction completed. You can download the results."
    st.session_state.active_job = None


def get_active_df_key():
    if st.session_state.active_job == "import":
        return "import_results"
    if st.session_state.active_job == "discover":
        return "discover_results"
    return None


def process_one_company(validate_emails_after_scan):
    df_key = get_active_df_key()

    if df_key is None:
        return

    df = ensure_result_columns(st.session_state[df_key])
    total = len(df)

    if total == 0:
        complete_job()
        return

    index = st.session_state.job_index

    while index < total and is_processed(df.iloc[index]):
        index += 1

    if index >= total:
        st.session_state[df_key] = df
        st.session_state.job_index = total
        complete_job()
        return

    company = str(df.at[index, "Company Name"] or "Unknown company")
    website = str(df.at[index, "Website"] or "").strip()

    st.session_state.job_message = f"{index + 1}/{total} · Checking {company}"

    if not website:
        df.at[index, "Email Status"] = "Website not available"
    else:
        try:
            result = find_emails_on_site(
                website,
                max_seconds=st.session_state.job_time_limit,
            )
            df.at[index, "Emails"] = result["emails"]
            df.at[index, "Email Status"] = result["status"]
            df.at[index, "Checked Pages"] = result["checked_pages"]
        except Exception as exc:
            df.at[index, "Email Status"] = f"Failed: {type(exc).__name__}"
            df.at[index, "Checked Pages"] = str(exc)

    if validate_emails_after_scan and str(df.at[index, "Emails"] or "").strip():
        single_row = validate_dataframe_emails(df.iloc[[index]])
        df.at[index, "Email Validation"] = single_row.iloc[0]["Email Validation"]

    st.session_state[df_key] = df
    st.session_state.job_index = index + 1


def render_running_panel(df):
    total = len(df)
    done = min(st.session_state.job_index, total)

    st.progress(progress_value(done, total))
    st.info(st.session_state.job_message or "Extraction is running...")
    result_table(df, height=360)


def normalize_candidate_row(candidate):
    row = {column: "" for column in RESULT_COLUMNS}

    for key, value in candidate.items():
        if key in row:
            row[key] = value

    return row


def discover_to_dataframe(keyword, city, limit, include_web, include_linkedin, strict_filter):
    candidates = []

    if include_web:
        candidates.extend(
            discover_company_websites(
                keyword=keyword,
                city=city,
                limit=limit,
                strict_filter=strict_filter,
            )
        )

    if include_linkedin:
        candidates.extend(
            discover_linkedin_company_pages(
                keyword=keyword,
                city=city,
                limit=limit,
            )
        )

    rows = []
    seen = set()

    for candidate in candidates:
        key = candidate.get("Domain") or candidate.get("Source URL") or candidate.get("Company Name")

        if key in seen:
            continue

        seen.add(key)
        rows.append(normalize_candidate_row(candidate))

    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


def merge_uploaded_files(files):
    frames = []

    for file in files:
        frames.append(normalize_uploaded_maps_file(file))

    if not frames:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    merged = pd.concat(frames, ignore_index=True)
    merged = prepare_leads_dataframe(merged)
    merged = deduplicate_leads(merged)

    return ensure_result_columns(merged)


def apply_cleanup_tools(df, validate_emails_enabled):
    cleaned = ensure_result_columns(df)
    cleaned = prepare_leads_dataframe(cleaned)
    cleaned = deduplicate_leads(cleaned)

    if validate_emails_enabled:
        cleaned = validate_dataframe_emails(cleaned)

    groups = group_by_domain(cleaned)

    return ensure_result_columns(cleaned), groups


def clean_manual_recipients(text):
    if not text:
        return pd.DataFrame(columns=["Email", "Send Status", "Send Message"])

    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    unique = []

    for email in emails:
        email = email.strip().lower()
        if email and email not in unique:
            unique.append(email)

    return pd.DataFrame({
        "Email": unique,
        "Send Status": "",
        "Send Message": "",
    })


def load_recipients_from_file(uploaded_file):
    if uploaded_file is None:
        return pd.DataFrame(columns=["Email", "Send Status", "Send Message"])

    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    possible_columns = ["Email", "Emails", "email", "emails", "Mail", "mail"]
    email_values = []

    for col in possible_columns:
        if col in df.columns:
            for value in df[col].fillna("").astype(str):
                email_values.extend(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", value))

    unique = []
    for email in email_values:
        email = email.strip().lower()
        if email and email not in unique:
            unique.append(email)

    return pd.DataFrame({
        "Email": unique,
        "Send Status": "",
        "Send Message": "",
    })


def get_available_recipients_from_results():
    frames = []

    if not st.session_state.import_results.empty:
        frames.append(extract_campaign_recipients(st.session_state.import_results))

    if not st.session_state.discover_results.empty:
        frames.append(extract_campaign_recipients(st.session_state.discover_results))

    if not frames:
        return pd.DataFrame(columns=["Email", "Send Status", "Send Message"])

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["Email"]).reset_index(drop=True)
    return merged


def send_metrics(df):
    total = len(df)
    sent = len(df[df["Send Status"].astype(str) == "Sent"])
    failed = len(df[df["Send Status"].astype(str) == "Failed"])
    remaining = len(df[df["Send Status"].astype(str).str.strip() == ""])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Recipients", total)
    c2.metric("Sent", sent)
    c3.metric("Failed", failed)
    c4.metric("Remaining", remaining)


def send_log_table(df):
    if df.empty:
        st.info("No recipients loaded yet.")
        return
    st.dataframe(df[SEND_VISIBLE_COLUMNS].reset_index(drop=True), use_container_width=True, height=420)


def start_send_job(recipients_df):
    st.session_state.send_recipients = recipients_df.copy().reset_index(drop=True)
    st.session_state.send_job_index = 0
    st.session_state.send_status = "Running"
    st.session_state.send_message = "Starting campaign..."
    st.session_state.active_job = "send"


def stop_send_job(message="Stopped. You can download the current sending log."):
    st.session_state.send_status = "Stopped"
    st.session_state.send_message = message
    st.session_state.active_job = None


def complete_send_job():
    st.session_state.send_status = "Completed"
    st.session_state.send_message = "Campaign completed."
    st.session_state.active_job = None


def process_one_send(
    smtp_config,
    subject,
    body,
    attachment_name,
    attachment_bytes,
    max_send_count,
):
    df = st.session_state.send_recipients.copy().reset_index(drop=True)

    if df.empty:
        complete_send_job()
        return

    sent_count = len(df[df["Send Status"].astype(str) == "Sent"])

    if sent_count >= max_send_count:
        stop_send_job("Maximum send count reached. You can download the current sending log.")
        return

    index = st.session_state.send_job_index

    while index < len(df) and str(df.at[index, "Send Status"] or "").strip():
        index += 1

    if index >= len(df):
        st.session_state.send_recipients = df
        st.session_state.send_job_index = len(df)
        complete_send_job()
        return

    recipient = str(df.at[index, "Email"] or "").strip().lower()
    st.session_state.send_message = f"{index + 1}/{len(df)} · Sending to {recipient}"

    result = send_single_email(
        smtp_config=smtp_config,
        recipient=recipient,
        subject=subject,
        body=body,
        attachment_name=attachment_name,
        attachment_bytes=attachment_bytes,
    )

    df.at[index, "Send Status"] = result.status
    df.at[index, "Send Message"] = result.message

    st.session_state.send_recipients = df
    st.session_state.send_job_index = index + 1


init_state()

st.title("LeadMail Finder")
st.caption("A local tool for finding company websites, public business email addresses, and sending controlled outreach emails.")

tab_import, tab_discover, tab_send, tab_about = st.tabs([
    "Import CSV",
    "Discover",
    "Send Emails",
    "About",
])


with tab_import:
    running_import = st.session_state.active_job == "import"

    st.subheader("Import and prepare company lists")

    st.write(
        "Upload one or more Google Maps / Instant Data Scraper CSV or Excel files. "
        "LeadMail Finder will merge them, remove duplicates, extract emails, validate email domains, and group results by domain."
    )

    company_time_limit = st.slider(
        "Max seconds per company",
        min_value=10,
        max_value=60,
        value=25,
        step=5,
        disabled=is_running(),
        key="import_time_limit",
    )

    validate_emails_enabled = st.checkbox(
        "Validate email domains with MX check",
        value=True,
        disabled=is_running(),
        key="import_validate",
        help="Checks whether the email domain has MX records. This is not a guarantee that the mailbox exists.",
    )

    uploaded_files = st.file_uploader(
        "Upload CSV or Excel files",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        disabled=is_running(),
        key="import_upload",
    )

    if uploaded_files:
        signature = "|".join([f"{file.name}:{file.size}" for file in uploaded_files])

        if st.session_state.last_upload_signature != signature:
            merged_df = merge_uploaded_files(uploaded_files)
            cleaned_df, groups = apply_cleanup_tools(merged_df, validate_emails_enabled=False)

            st.session_state.uploaded_df = cleaned_df
            st.session_state.import_results = cleaned_df.copy()
            st.session_state.domain_groups = groups
            st.session_state.last_upload_signature = signature
            st.session_state.job_status = "Idle"
            st.session_state.job_message = ""

    current_df = ensure_result_columns(st.session_state.import_results)

    if not current_df.empty:
        st.markdown("### Summary")
        metrics(current_df)

        with st.expander("Preview prepared companies", expanded=False):
            result_table(current_df, height=320)

        st.markdown("### Extraction")

        action_col1, action_col2, action_col3 = st.columns([1, 1, 1])

        has_started = (
            not current_df.empty
            and (current_df["Email Status"].astype(str).str.strip() != "").any()
        )

        with action_col1:
            start_label = "Continue extraction" if has_started and not is_running() else "Start extraction"
            start_clicked = st.button(
                start_label,
                type="primary",
                disabled=is_running() or current_df.empty,
                key="import_start",
            )

        with action_col2:
            restart_clicked = st.button(
                "Restart from beginning",
                disabled=is_running() or current_df.empty,
                key="import_restart",
            )

        with action_col3:
            stop_clicked = st.button(
                "Stop after current company",
                disabled=not running_import,
                key="import_stop",
            )

        if start_clicked:
            st.session_state.import_results = current_df.copy()
            start_job("import", st.session_state.import_results, company_time_limit)
            st.rerun()

        if restart_clicked:
            st.session_state.import_results = reset_email_columns(current_df)
            start_job("import", st.session_state.import_results, company_time_limit)
            st.rerun()

        if stop_clicked and running_import:
            stop_job()
            st.rerun()

        if running_import:
            render_running_panel(st.session_state.import_results)
            process_one_company(validate_emails_enabled)
            st.rerun()

        elif st.session_state.job_status in {"Completed", "Stopped"} and not current_df.empty:
            final_df, domain_groups = apply_cleanup_tools(current_df, validate_emails_enabled)
            st.session_state.import_results = final_df
            st.session_state.domain_groups = domain_groups

            if st.session_state.job_status == "Completed":
                st.success(st.session_state.job_message)
            else:
                st.warning(st.session_state.job_message)

            st.markdown("### Results")
            metrics(final_df)
            result_table(final_df)

            st.markdown("### Domain groups")
            if domain_groups.empty:
                st.info("No domain groups generated.")
            else:
                st.dataframe(domain_groups, use_container_width=True, height=320)

            download_buttons(
                final_df,
                "leadmail_import_results",
                "import_results_download",
                disabled=False,
                domain_groups=domain_groups,
            )

        else:
            st.markdown("### Results")
            st.info("Start extraction to generate email results.")

            st.markdown("### Prepared output")
            download_buttons(
                current_df,
                "leadmail_prepared_companies",
                "prepared_download",
                disabled=False,
                domain_groups=st.session_state.domain_groups,
            )
    else:
        st.info("Upload one or more CSV or Excel files to begin.")


with tab_discover:
    running_discover = st.session_state.active_job == "discover"

    st.subheader("Discover companies")

    st.write(
        "This optional helper searches public web results. For reliable bulk work, use the CSV import workflow."
    )

    discover_time_limit = st.slider(
        "Max seconds per company",
        min_value=10,
        max_value=60,
        value=25,
        step=5,
        disabled=is_running(),
        key="discover_time_limit",
    )

    validate_discover_emails = st.checkbox(
        "Validate email domains with MX check",
        value=True,
        disabled=is_running(),
        key="discover_validate",
    )

    keyword = st.text_input(
        "Keyword",
        value="",
        placeholder="Example: yazılım firması",
        disabled=is_running(),
        key="discover_keyword",
    )

    city = st.text_input(
        "City",
        value="",
        placeholder="Example: Kayseri",
        disabled=is_running(),
        key="discover_city",
    )

    limit = st.slider(
        "Results per source",
        min_value=5,
        max_value=100,
        value=25,
        step=5,
        disabled=is_running(),
        key="discover_limit",
    )

    option_col1, option_col2, option_col3 = st.columns(3)

    with option_col1:
        include_web = st.checkbox(
            "Find company websites",
            value=True,
            disabled=is_running(),
            key="discover_web",
        )

    with option_col2:
        include_linkedin = st.checkbox(
            "Find LinkedIn pages",
            value=True,
            disabled=is_running(),
            key="discover_linkedin",
        )

    with option_col3:
        strict_filter = st.checkbox(
            "Use stricter filtering",
            value=False,
            disabled=is_running(),
            key="discover_strict",
        )

    if keyword and city and not is_running():
        link_col1, link_col2, link_col3 = st.columns(3)
        link_col1.link_button("Google Maps", build_google_maps_search_url(keyword, city))
        link_col2.link_button("Google Search", build_google_search_url(keyword, city))
        link_col3.link_button("LinkedIn via Google", build_linkedin_google_search_url(keyword, city))

    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])

    with action_col1:
        discover_clicked = st.button(
            "Discover and scan",
            type="primary",
            disabled=is_running(),
            key="discover_start",
        )

    with action_col2:
        restart_discover_clicked = st.button(
            "Restart scan",
            disabled=is_running() or st.session_state.discover_results.empty,
            key="discover_restart",
        )

    with action_col3:
        stop_discover_clicked = st.button(
            "Stop after current company",
            disabled=not running_discover,
            key="discover_stop",
        )

    if discover_clicked:
        if not keyword.strip() or not city.strip():
            st.error("Please enter both keyword and city.")
        else:
            with st.spinner("Finding candidate companies..."):
                discovered_df = discover_to_dataframe(
                    keyword=keyword,
                    city=city,
                    limit=limit,
                    include_web=include_web,
                    include_linkedin=include_linkedin,
                    strict_filter=strict_filter,
                )

            if discovered_df.empty:
                st.warning("No companies found. Try another keyword or use CSV import.")
            else:
                discovered_df, groups = apply_cleanup_tools(discovered_df, validate_emails_enabled=False)
                st.session_state.discover_results = discovered_df
                st.session_state.domain_groups = groups
                start_job("discover", discovered_df, discover_time_limit)
                st.rerun()

    if restart_discover_clicked and not st.session_state.discover_results.empty:
        st.session_state.discover_results = reset_email_columns(st.session_state.discover_results)
        start_job("discover", st.session_state.discover_results, discover_time_limit)
        st.rerun()

    if stop_discover_clicked and running_discover:
        stop_job()
        st.rerun()

    current_discover_df = ensure_result_columns(st.session_state.discover_results)

    if running_discover:
        render_running_panel(current_discover_df)
        process_one_company(validate_discover_emails)
        st.rerun()

    elif st.session_state.job_status in {"Completed", "Stopped"} and not current_discover_df.empty:
        final_df, domain_groups = apply_cleanup_tools(current_discover_df, validate_discover_emails)
        st.session_state.discover_results = final_df

        if st.session_state.job_status == "Completed":
            st.success(st.session_state.job_message)
        else:
            st.warning(st.session_state.job_message)

        st.markdown("### Results")
        metrics(final_df)
        result_table(final_df)

        st.markdown("### Domain groups")
        if domain_groups.empty:
            st.info("No domain groups generated.")
        else:
            st.dataframe(domain_groups, use_container_width=True, height=320)

        download_buttons(
            final_df,
            "leadmail_discover_results",
            "discover_results_download",
            disabled=False,
            domain_groups=domain_groups,
        )

    elif not current_discover_df.empty:
        st.markdown("### Results")
        metrics(current_discover_df)
        result_table(current_discover_df)

    else:
        st.info("Run discovery to generate results.")


with tab_send:
    running_send = st.session_state.active_job == "send"

    st.subheader("Send controlled outreach emails")

    st.write(
        "Send emails from your own Gmail account using a Gmail App Password. "
        "Use this only for legitimate, respectful outreach. The app sends one email at a time and logs every result."
    )

    st.warning(
        "Safety note: No tool can guarantee that an email provider will never limit, flag, or reject sending. "
        "LeadMail Finder reduces risk with small batches, one-by-one sending, required test email, delays, and logs. "
        "Always send only relevant messages to public business addresses."
    )

    st.markdown("### Security and privacy")

    with st.expander("Important security information", expanded=True):
        st.markdown(
            """
- LeadMail Finder never asks for your normal account password when an app password is available.
- Credentials are used only for the current local session.
- Credentials are not written to CSV, Excel, logs, or exported files.
- For Gmail and Yahoo, use an App Password.
- For custom domains, use your provider's SMTP credentials.
- If you are unsure, create a dedicated email account for outreach.
"""
        )

    clear_credentials_clicked = st.button(
        "Clear credentials from session",
        disabled=running_send,
        key="send_clear_credentials",
    )

    if clear_credentials_clicked:
        for key in [
            "send_sender_email",
            "send_username",
            "send_password",
            "send_custom_host",
            "send_custom_port",
        ]:
            if key in st.session_state:
                st.session_state[key] = ""
        st.session_state.send_test_ok = False
        st.success("Credentials cleared from the current session.")

    st.markdown("### Email provider")

    provider = st.selectbox(
        "Provider",
        options=list(PROVIDER_PRESETS.keys()),
        index=0,
        disabled=running_send,
        key="send_provider",
    )

    preset = PROVIDER_PRESETS[provider]

    provider_col1, provider_col2, provider_col3 = st.columns([1, 1, 1])

    with provider_col1:
        smtp_host = st.text_input(
            "SMTP host",
            value=preset["host"],
            disabled=running_send or provider != "Custom SMTP",
            key="send_custom_host" if provider == "Custom SMTP" else "send_preset_host",
        )

    with provider_col2:
        smtp_port = st.number_input(
            "SMTP port",
            min_value=1,
            max_value=65535,
            value=int(preset["port"]),
            disabled=running_send or provider != "Custom SMTP",
            key="send_custom_port" if provider == "Custom SMTP" else "send_preset_port",
        )

    with provider_col3:
        smtp_security = st.selectbox(
            "Security",
            options=["SSL/TLS", "STARTTLS", "None"],
            index=["SSL/TLS", "STARTTLS", "None"].index(preset["security"]),
            disabled=running_send or provider != "Custom SMTP",
            key="send_custom_security" if provider == "Custom SMTP" else "send_preset_security",
        )

    st.caption(preset["help"])

    st.markdown("### Sender credentials")

    sender_col1, sender_col2, sender_col3 = st.columns([1, 1, 1])

    with sender_col1:
        sender_email = st.text_input(
            "Sender email",
            value="",
            placeholder="your.email@example.com",
            disabled=running_send,
            key="send_sender_email",
        )

    with sender_col2:
        smtp_username = st.text_input(
            preset["username_label"],
            value=sender_email,
            placeholder="Usually same as sender email",
            disabled=running_send,
            key="send_username",
        )

    with sender_col3:
        smtp_password = st.text_input(
            preset["password_label"],
            value="",
            type="password",
            disabled=running_send,
            key="send_password",
            help="This value is not exported or saved by LeadMail Finder.",
        )

    smtp_config = SmtpConfig(
        provider=provider,
        host=smtp_host,
        port=int(smtp_port),
        security=smtp_security,
        username=smtp_username,
        password=smtp_password,
        sender_email=sender_email,
    )

    st.markdown("### Recipients")

    source_option = st.radio(
        "Recipient source",
        options=[
            "Use emails found in LeadMail Finder",
            "Upload email list",
            "Paste emails manually",
        ],
        disabled=running_send,
        key="send_source_option",
    )

    only_valid_mx_for_send = st.checkbox(
        "Use only emails with Valid MX when using LeadMail Finder results",
        value=False,
        disabled=running_send,
        key="send_valid_mx_only",
    )

    recipients_df = pd.DataFrame(columns=["Email", "Send Status", "Send Message"])

    if source_option == "Use emails found in LeadMail Finder":
        base_recipients = get_available_recipients_from_results()

        if only_valid_mx_for_send:
            filtered = []
            source_frames = []
            if not st.session_state.import_results.empty:
                source_frames.append(extract_campaign_recipients(st.session_state.import_results, only_valid_mx=True))
            if not st.session_state.discover_results.empty:
                source_frames.append(extract_campaign_recipients(st.session_state.discover_results, only_valid_mx=True))
            if source_frames:
                base_recipients = pd.concat(source_frames, ignore_index=True).drop_duplicates(subset=["Email"])

        recipients_df = base_recipients.reset_index(drop=True)

    elif source_option == "Upload email list":
        recipient_file = st.file_uploader(
            "Upload CSV or Excel with Email column",
            type=["csv", "xlsx"],
            disabled=running_send,
            key="send_recipient_file",
        )
        recipients_df = load_recipients_from_file(recipient_file)

    else:
        manual_emails = st.text_area(
            "Paste email addresses",
            value="",
            placeholder="info@example.com\nhr@example.com",
            disabled=running_send,
            key="send_manual_emails",
            height=120,
        )
        recipients_df = clean_manual_recipients(manual_emails)

    recipients_df = recipients_df.drop_duplicates(subset=["Email"]).reset_index(drop=True)

    send_metrics(recipients_df)

    with st.expander("Preview recipients", expanded=False):
        send_log_table(recipients_df)

    st.markdown("### Message")

    subject = st.text_input(
        "Subject",
        value="",
        placeholder="Android Developer Application",
        disabled=running_send,
        key="send_subject",
    )

    body = st.text_area(
        "Message",
        value="",
        placeholder="Hello,\n\nI am sharing my CV for possible suitable opportunities.\n\nBest regards,",
        height=220,
        disabled=running_send,
        key="send_body",
    )

    attachment = st.file_uploader(
        "Attachment",
        type=["pdf", "doc", "docx"],
        disabled=running_send,
        key="send_attachment",
        help="Recommended: attach your CV as PDF. Gmail attachment limit is 25 MB.",
    )

    if attachment is not None and not running_send:
        st.session_state.send_attachment_name = attachment.name
        st.session_state.send_attachment_bytes = attachment.getvalue()

    st.markdown("### Safety settings")

    safety_col1, safety_col2 = st.columns([1, 1])

    with safety_col1:
        delay_between_emails = st.slider(
            "Delay between emails",
            min_value=15,
            max_value=120,
            value=60,
            step=15,
            disabled=running_send,
            key="send_delay",
            help="Higher delay is safer for Gmail accounts.",
        )

    with safety_col2:
        max_send_count = st.slider(
            "Maximum emails per run",
            min_value=5,
            max_value=100,
            value=25,
            step=5,
            disabled=running_send,
            key="send_max_count",
        )

    st.caption(
        "Recommended safe start: 25 emails per run with 30-60 seconds delay. "
        "Send relevant emails only and avoid repeated sends to the same recipients."
    )

    st.markdown("### Test and campaign")

    test_recipient = st.text_input(
        "Test recipient",
        value=sender_email,
        disabled=running_send,
        key="send_test_recipient",
        help="Send a test email before starting the campaign.",
    )

    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])

    can_test = bool(sender_email and smtp_username and smtp_password and smtp_host and smtp_port and subject and body and test_recipient)
    can_send = (
        can_test
        and st.session_state.send_test_ok
        and not recipients_df.empty
        and st.session_state.send_attachment_bytes is not None
    )

    with action_col1:
        test_clicked = st.button(
            "Send test email",
            type="secondary",
            disabled=running_send or not can_test,
            key="send_test_button",
        )

    with action_col2:
        start_campaign_clicked = st.button(
            "Start campaign",
            type="primary",
            disabled=running_send or not can_send,
            key="send_start_button",
        )

    with action_col3:
        stop_send_clicked = st.button(
            "Stop after current email",
            disabled=not running_send,
            key="send_stop_button",
        )

    if test_clicked:
        result = send_single_email(
            smtp_config=smtp_config,
            recipient=test_recipient,
            subject=subject,
            body=body,
            attachment_name=st.session_state.send_attachment_name,
            attachment_bytes=st.session_state.send_attachment_bytes,
        )

        if result.status == "Sent":
            st.session_state.send_test_ok = True
            st.success("Test email sent successfully. Campaign sending is now enabled.")
        else:
            st.session_state.send_test_ok = False
            st.error(result.message)

    if stop_send_clicked and running_send:
        stop_send_job()
        st.rerun()

    if start_campaign_clicked:
        campaign_df = recipients_df.copy().reset_index(drop=True)
        campaign_df["Send Status"] = ""
        campaign_df["Send Message"] = ""
        st.session_state.send_test_ok = False
        start_send_job(campaign_df)
        st.rerun()

    if running_send:
        progress = progress_value(st.session_state.send_job_index, len(st.session_state.send_recipients))
        st.progress(progress)
        st.info(st.session_state.send_message or "Campaign is running...")
        send_log_table(st.session_state.send_recipients)

        process_one_send(
            smtp_config=smtp_config,
            subject=subject,
            body=body,
            attachment_name=st.session_state.send_attachment_name,
            attachment_bytes=st.session_state.send_attachment_bytes,
            max_send_count=max_send_count,
        )

        # Delay happens after each single send. Streamlit reruns after the delay.
        import time
        time.sleep(delay_between_emails)
        st.rerun()

    elif st.session_state.send_status in {"Completed", "Stopped"} and not st.session_state.send_recipients.empty:
        if st.session_state.send_status == "Completed":
            st.success(st.session_state.send_message)
        else:
            st.warning(st.session_state.send_message)

        st.markdown("### Sending log")
        send_metrics(st.session_state.send_recipients)
        send_log_table(st.session_state.send_recipients)

        st.download_button(
            "Download sending log CSV",
            data=dataframe_to_csv_bytes(st.session_state.send_recipients),
            file_name="leadmail_sending_log.csv",
            mime="text/csv",
            key="send_log_csv",
        )

    elif not st.session_state.send_recipients.empty:
        st.markdown("### Previous sending log")
        send_log_table(st.session_state.send_recipients)
        st.download_button(
            "Download previous sending log CSV",
            data=dataframe_to_csv_bytes(st.session_state.send_recipients),
            file_name="leadmail_sending_log.csv",
            mime="text/csv",
            key="send_previous_log_csv",
        )


with tab_about:
    st.subheader("About LeadMail Finder")

    st.write(
        "LeadMail Finder is an open-source local tool for building company outreach lists from public data."
    )

    st.markdown(
        """
### Purpose

LeadMail Finder helps with job searching, local company research, and B2B prospecting by extracting publicly visible business email addresses from company websites.

### Main workflow

1. Export company lists from Google Maps with Instant Data Scraper.
2. Import one or more CSV/Excel files.
3. LeadMail Finder merges files and removes duplicates.
4. It extracts public business emails from company websites.
5. It validates email domains with MX checks.
6. It groups results by domain.
7. You download a clean Excel or CSV outreach list.
8. Optionally, you can send controlled outreach emails from Gmail, Outlook/Hotmail, Yahoo, or a custom SMTP account.

### Email sending safety

The sender module is designed for small, respectful, controlled outreach. It requires a test email before campaign sending, supports Gmail/Outlook/Yahoo/custom SMTP, stores no credentials in exported files, sends one email at a time, supports delays, limits maximum emails per run, and logs every result.

### Responsible use

Use the tool only for legitimate research and respectful outreach. Do not use it for spam, harassment, or illegal data collection.
"""
    )
