"""
CSV Downloader Service
Downloads CSV data from Google Sheets with authentication and error handling
"""

import hashlib
import logging
import os
import random
from typing import Optional
from services.common.config_loader import load_config
from services.common.retry import RetryPolicy, retry_call
from services.intake.sheets_intake import build_bounded_range, find_last_ready_row, quote_tab_a1, values_to_csv

import requests
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request

log = logging.getLogger(__name__)


class CSVDownloadError(Exception):
    """Raised when CSV download fails"""
    pass


def get_csv_download_url(spreadsheet_id: str, sheet_name: str = "PETTY CASH") -> str:
    """Generate direct CSV download URL for Google Sheets"""
    # Google Sheets CSV export URL format
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"


def get_file_fingerprint(csv_content: str) -> str:
    """Generate SHA256 hash of CSV content for deduplication"""
    return hashlib.sha256(csv_content.encode('utf-8')).hexdigest()


def download_petty_cash_csv(
    spreadsheet_id: str,
    service_account_path: str,
    config_path: str = "config/csv_processor_config.json",
    output_path: Optional[str] = None,
    retry_count: int = 5,
    retry_delay: float = 1.5,
    *,
    sheet_name_override: Optional[str] = None,
) -> str:
    """
    Download petty cash data as CSV from Google Sheets using Google Sheets API
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        service_account_path: Path to service account JSON file
        output_path: Optional path to save CSV file
        retry_count: Number of retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        CSV content as string, or file path if output_path provided
    
    Raises:
        CSVDownloadError: If download fails after retries
    """
    
    # Resolve service account path: prefer explicit, then YAML config, then error
    sa_path = service_account_path
    if not sa_path:
        try:
            cfg = load_config()
            sa_path = cfg.get('google.service_account_json_path')
        except Exception:
            sa_path = None
    if not sa_path or not os.path.exists(sa_path):
        raise CSVDownloadError(f"Service account file not found: {sa_path or service_account_path}")
    
    # Load sheet name: prefer explicit override; then YAML intake.sheet_name; then json config; else default
    sheet_name = sheet_name_override or 'PETTY CASH'
    try:
        cfg = load_config()
        if sheet_name_override is None:
            sheet_name = cfg.get('intake.sheet_name', sheet_name)
    except Exception:
        pass
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
            petty_cash_config = config.get('petty_cash', {})
            if sheet_name_override is None:
                sheet_name = petty_cash_config.get('sheet_name', sheet_name)
        except Exception:
            pass
    
    log.info(f"Downloading data from spreadsheet: {spreadsheet_id}, sheet: {sheet_name}")
    
    # Load service account credentials
    try:
        creds = Credentials.from_service_account_file(
            sa_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
    except Exception as e:
        raise CSVDownloadError(f"Failed to load service account credentials: {e}")
    
    # Import Google Sheets API
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise CSVDownloadError("Google Sheets API not available. Install with: pip install google-api-python-client")
    
    # Build the Sheets service once (avoid rebuild per attempt).
    service = build('sheets', 'v4', credentials=creds)

    bounded_enabled = (os.environ.get("KYLO_INTAKE_BOUNDED_READ", "1").strip().lower() not in ("0", "false", "no", "n"))
    # Reads up to column Z (includes Column F = Posted, Column G = Notes)
    # When Column F or G changes, CSV content changes → checksum changes → watcher detects change and triggers re-posting
    last_col = (os.environ.get("KYLO_INTAKE_BOUNDED_LAST_COL", "Z") or "Z").strip().upper()

    # Determine the read range. Default: bounded by last non-empty Column A (DATE).
    # Kill switch: KYLO_INTAKE_BOUNDED_READ=0 falls back to legacy A1:Z100000 reads.
    if bounded_enabled and sheet_name:
        col_a_range = f"{quote_tab_a1(sheet_name)}!A:A"
        policy = RetryPolicy(
            max_attempts=int(retry_count or 5),
            base_delay_secs=float(retry_delay or 1.5),
            max_delay_secs=60.0,
        )

        def _fetch_col_a():
            return service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=col_a_range,
                valueRenderOption="UNFORMATTED_VALUE",
            ).execute()

        try:
            col_a_resp = retry_call(_fetch_col_a, policy=policy, label="csv_downloader.colA.get")
            col_a_vals = col_a_resp.get("values", []) or []
            last_ready_row = find_last_ready_row(col_a_vals, header_rows=1)
        except Exception:
            last_ready_row = 0

        if last_ready_row <= 1:
            # No ready rows; return only header row to keep downstream parsing stable.
            range_spec = build_bounded_range(sheet_name, last_row=1, last_col=last_col)
        else:
            range_spec = build_bounded_range(sheet_name, last_row=last_ready_row, last_col=last_col)
        log.info(f"Bounded intake read: tab={sheet_name} last_ready_row={last_ready_row} range={range_spec}")
    else:
        # Legacy behavior: fixed large range (kept for emergency rollback).
        range_spec = f"{quote_tab_a1(sheet_name)}!A1:Z100000" if sheet_name else "A1:Z100000"

    def _fetch_values():
        log.info(f"Downloading via Sheets API range={range_spec}")
        return service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_spec).execute()

    try:
        # Single retry layer (shared helper) to avoid retry amplification.
        policy = RetryPolicy(
            max_attempts=int(retry_count or 5),
            base_delay_secs=float(retry_delay or 1.5),
            max_delay_secs=60.0,
        )
        result = retry_call(_fetch_values, policy=policy, label="csv_downloader.values.get")
        values = (result or {}).get('values', [])
    except Exception as e:
        raise CSVDownloadError(f"Failed to download CSV after {policy.max_attempts} attempts: {e}")

    if not values:
        raise CSVDownloadError(f"No data found in sheet '{sheet_name}'")

    # Convert to CSV format (robust quoting)
    csv_content = values_to_csv(values)
    try:
        log.info(f"Intake bytes={len(csv_content.encode('utf-8'))} range={range_spec}")
    except Exception:
        pass

    # Validate CSV content
    if not csv_content.strip():
        raise CSVDownloadError("Downloaded CSV is empty")

    # Generate file fingerprint
    file_fingerprint = get_file_fingerprint(csv_content)
    log.info(f"Downloaded CSV with fingerprint: {file_fingerprint[:16]}...")

    # Save to file if output_path provided
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        log.info(f"CSV saved to: {output_path}")
        return output_path

    return csv_content


def validate_csv_content(csv_content: str, min_rows: int = 20) -> bool:
    """
    Validate CSV content for basic structure
    
    Args:
        csv_content: CSV content as string
        min_rows: Minimum number of rows expected
    
    Returns:
        True if CSV appears valid
    """
    lines = csv_content.strip().split('\n')
    
    if len(lines) < min_rows:
        log.warning(f"CSV has only {len(lines)} rows, expected at least {min_rows}")
        return False
    
    # Check if first few lines have expected structure
    for i, line in enumerate(lines[:5]):
        if not line.strip():
            continue
        
        # Basic CSV structure check (should have commas)
        if ',' not in line:
            log.warning(f"Line {i + 1} appears to not be CSV format: {line[:100]}...")
            return False
    
    return True


def get_csv_metadata(csv_content: str) -> dict:
    """
    Extract basic metadata from CSV content
    
    Args:
        csv_content: CSV content as string
    
    Returns:
        Dictionary with metadata
    """
    lines = csv_content.strip().split('\n')
    file_fingerprint = get_file_fingerprint(csv_content)
    
    return {
        'file_fingerprint': file_fingerprint,
        'total_lines': len(lines),
        'non_empty_lines': len([line for line in lines if line.strip()]),
        'file_size_bytes': len(csv_content.encode('utf-8')),
        'first_line_preview': lines[0][:100] if lines else '',
        'last_line_preview': lines[-1][:100] if lines else ''
    }
