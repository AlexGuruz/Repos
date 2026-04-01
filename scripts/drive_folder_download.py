"""
Download a Google Drive folder using the stashbox service account.
Usage: python drive_folder_download.py [folder_id] [destination_dir]
Defaults: folder_id from env or 1HeWcSmtgM4c7NO32j8Fs11_awk7Xz7It, dest Repos root
"""
import os
import sys
import io

# Service account path - stashbox (Project-Kylo .secrets)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPOS_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
STASHBOX_CREDENTIALS = os.path.join(
    REPOS_ROOT, "Project-Kylo", ".secrets", "service_account.json"
)

FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1HeWcSmtgM4c7NO32j8Fs11_awk7Xz7It")
DEST_DIR = os.environ.get("DRIVE_DEST", REPOS_ROOT)

# Google Drive export MIME mapping for native docs
EXPORT_MIMES = {
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.presentation": "application/pdf",
}


def get_service(credentials_path: str):
    """Build Drive API service using service account credentials."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def list_files_in_folder(service, folder_id: str):
    """List all files and subfolders in a Drive folder (one page)."""
    results = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed = false",
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, size)",
        )
        .execute()
    )
    return results.get("files", [])


def list_all_in_folder(service, folder_id: str):
    """List all items in folder with pagination."""
    items = []
    page_token = None
    while True:
        resp = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token or "",
            )
            .execute()
        )
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def download_file(service, file_id: str, dest_path: str, mime_type: str) -> bool:
    """Download a single file. Export Google Workspace docs to PDF/XLSX."""
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    try:
        if mime_type in EXPORT_MIMES:
            export_mime = EXPORT_MIMES[mime_type]
            ext = ".xlsx" if "spreadsheet" in export_mime else ".pdf"
            if not dest_path.lower().endswith(ext):
                dest_path = dest_path + ext
            content = (
                service.files()
                .export_media(fileId=file_id, mimeType=export_mime)
                .execute()
            )
            with open(dest_path, "wb") as f:
                f.write(content)
        else:
            request = service.files().get_media(fileId=file_id)
            with io.BytesIO() as buf:
                from googleapiclient.http import MediaIoBaseDownload
                downloader = MediaIoBaseDownload(buf, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                with open(dest_path, "wb") as f:
                    f.write(buf.getvalue())
        print("  OK:", dest_path)
        return True
    except Exception as e:
        print("  FAIL:", dest_path, str(e))
        return False


def download_folder_recursive(service, folder_id: str, parent_name: str, base_dest: str):
    """Recursively list and download folder contents into base_dest."""
    items = list_all_in_folder(service, folder_id)
    for item in items:
        name = item["name"]
        file_id = item["id"]
        mime = item.get("mimeType", "")
        local_path = os.path.join(base_dest, parent_name, name)

        if mime == "application/vnd.google-apps.folder":
            download_folder_recursive(service, file_id, os.path.join(parent_name, name), base_dest)
        else:
            download_file(service, file_id, local_path, mime)


def main():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or STASHBOX_CREDENTIALS
    folder_id = sys.argv[1] if len(sys.argv) > 1 else FOLDER_ID
    dest = os.path.normpath(sys.argv[2] if len(sys.argv) > 2 else DEST_DIR)

    if not os.path.isfile(creds_path):
        print("Credentials not found:", creds_path)
        print("Set GOOGLE_APPLICATION_CREDENTIALS or ensure Project-Kylo/.secrets/service_account.json exists.")
        sys.exit(1)

    print("Using credentials:", creds_path)
    print("Folder ID:", folder_id)
    print("Destination:", dest)
    service = get_service(creds_path)

    # Get root folder name for the top-level directory
    try:
        root = service.files().get(fileId=folder_id, fields="name").execute()
        root_name = root.get("name", "drive_folder")
    except Exception as e:
        print("Cannot access folder (share it with the service account email):", e)
        sys.exit(1)

    out_root = os.path.join(dest, root_name)
    os.makedirs(out_root, exist_ok=True)
    print("Downloading into:", out_root)
    download_folder_recursive(service, folder_id, "", out_root)
    print("Done.")


if __name__ == "__main__":
    main()
