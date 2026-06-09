from io import BytesIO

import pandas as pd


POSSIBLE_COMPANY_COLUMNS = [
    "Company Name", "Firma Adı", "Firma Adi", "name", "title", "qBF1Pd", "Company", "company"
]

POSSIBLE_WEBSITE_COLUMNS = [
    "Website", "website", "site", "web", "lcr4fd href", "url", "URL"
]

POSSIBLE_PHONE_COLUMNS = [
    "Phone", "Telefon", "phone", "UsdlK"
]

POSSIBLE_ADDRESS_COLUMNS = [
    "Address", "Adres", "address", "full_address", "W4Efsd 3"
]


RESULT_COLUMNS = [
    "Company Name",
    "Website",
    "Phone",
    "Address",
    "Domain",
    "Source",
    "Source URL",
    "LinkedIn",
    "Emails",
    "Email Status",
    "Email Validation",
    "Checked Pages",
    "Notes",
]


def first_existing_column(df, candidates):
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def safe_series(df, column_name, default=""):
    if column_name and column_name in df.columns:
        return df[column_name].fillna("")
    return default


def normalize_uploaded_maps_file(uploaded_file):
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed:")]

    company_col = first_existing_column(df, POSSIBLE_COMPANY_COLUMNS)
    website_col = first_existing_column(df, POSSIBLE_WEBSITE_COLUMNS)
    phone_col = first_existing_column(df, POSSIBLE_PHONE_COLUMNS)
    address_col = first_existing_column(df, POSSIBLE_ADDRESS_COLUMNS)

    normalized = pd.DataFrame()
    normalized["Company Name"] = safe_series(df, company_col)
    normalized["Website"] = safe_series(df, website_col)
    normalized["Phone"] = safe_series(df, phone_col)
    normalized["Address"] = safe_series(df, address_col)
    normalized["Domain"] = df["Domain"].fillna("") if "Domain" in df.columns else ""
    normalized["Source"] = df["Source"].fillna("") if "Source" in df.columns else "Google Maps CSV"
    normalized["Source URL"] = df["Source URL"].fillna("") if "Source URL" in df.columns else ""
    normalized["LinkedIn"] = df["LinkedIn"].fillna("") if "LinkedIn" in df.columns else ""
    normalized["Emails"] = df["Emails"].fillna("") if "Emails" in df.columns else ""
    normalized["Email Status"] = df["Email Status"].fillna("") if "Email Status" in df.columns else ""
    normalized["Email Validation"] = df["Email Validation"].fillna("") if "Email Validation" in df.columns else ""
    normalized["Checked Pages"] = df["Checked Pages"].fillna("") if "Checked Pages" in df.columns else ""
    normalized["Notes"] = df["Notes"].fillna("") if "Notes" in df.columns else ""

    normalized = normalized.dropna(subset=["Company Name"], how="all")
    normalized = normalized[normalized["Company Name"].astype(str).str.strip() != ""]
    normalized = normalized.reset_index(drop=True)

    for column in RESULT_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    return normalized[RESULT_COLUMNS]


def dataframe_to_excel_bytes(df, sheets=None):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if sheets:
            for sheet_name, sheet_df in sheets.items():
                clean_df = sheet_df.copy().reset_index(drop=True)
                clean_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        else:
            clean_df = df.copy().reset_index(drop=True)
            clean_df.to_excel(writer, index=False, sheet_name="Results")

    return output.getvalue()


def dataframe_to_csv_bytes(df):
    clean_df = df.copy().reset_index(drop=True)
    return clean_df.to_csv(index=False).encode("utf-8-sig")
