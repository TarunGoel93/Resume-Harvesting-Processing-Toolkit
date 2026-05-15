"""
Download all PDF / DOC / DOCX files from a Google Drive folder to your local system.

Setup:
1. pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
2. Place credentials.json (from Google Cloud Console) next to this script
3. Run: python drive_downloader.py
"""

import io
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ── CONFIG ────────────────────────────────────────────────────────────────────
DRIVE_FOLDER_NAME = "B"           # ← exact name of your Drive folder
DOWNLOAD_DIR      = "./downloads" # ← local folder to save files into
SKIP_EXISTING     = True          # ← set False to re-download already saved files
# ─────────────────────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

SUPPORTED_MIMES = {
    "application/pdf":                                                         ".pdf",
    "application/msword":                                                      ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

# Google Docs / Sheets / Slides need export — map to export MIME + extension
GOOGLE_EXPORT_MIMES = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


# ── Auth ──────────────────────────────────────────────────────────────────────
def authenticate():
    creds = None
    token_path  = Path("token.json")
    creds_path  = Path("credentials.json")

    if not creds_path.exists():
        print("ERROR: credentials.json not found.")
        print("Download it from Google Cloud Console → APIs & Services → Credentials.")
        sys.exit(1)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ── Drive helpers ─────────────────────────────────────────────────────────────
def find_folder_id(service, folder_name):
    q = (
        f"name='{folder_name}' "
        "and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    res = service.files().list(q=q, fields="files(id,name)").execute()
    files = res.get("files", [])
    if not files:
        print(f"ERROR: No Drive folder named '{folder_name}' found.")
        sys.exit(1)
    if len(files) > 1:
        print(f"⚠️  Multiple folders named '{folder_name}' found. Using the first one.")
    print(f"  Found folder: {files[0]['name']} (id={files[0]['id']})")
    return files[0]["id"]


def list_files(service, folder_id):
    all_mimes = list(SUPPORTED_MIMES.keys()) + list(GOOGLE_EXPORT_MIMES.keys())
    mime_filter = " or ".join(f"mimeType='{m}'" for m in all_mimes)
    q = f"'{folder_id}' in parents and ({mime_filter}) and trashed=false"
    fields = "nextPageToken, files(id, name, mimeType, size)"

    results, page_token = [], None
    while True:
        resp = service.files().list(
            q=q, fields=fields, pageSize=1000, pageToken=page_token
        ).execute()
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return sorted(results, key=lambda f: f["name"].lower())


# ── Download helpers ──────────────────────────────────────────────────────────
def safe_filename(name: str, ext: str) -> str:
    """Ensure file has the correct extension."""
    p = Path(name)
    if p.suffix.lower() != ext:
        return p.stem + ext
    return name


def download_binary(service, file_id: str, dest: Path):
    """Download a regular binary file (PDF, DOC, DOCX)."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request, chunksize=8 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    dest.write_bytes(buf.getvalue())


def export_google_doc(service, file_id: str, export_mime: str, dest: Path):
    """Export a Google Docs/Sheets/Slides file to an Office format."""
    request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request, chunksize=8 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    dest.write_bytes(buf.getvalue())


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)

    print("Authenticating with Google Drive ...")
    service = authenticate()

    print(f"\nLooking for folder: '{DRIVE_FOLDER_NAME}' ...")
    folder_id = find_folder_id(service, DRIVE_FOLDER_NAME)

    print("\nFetching file list ...")
    files = list_files(service, folder_id)

    if not files:
        print("No supported files found in that folder.")
        sys.exit(0)

    print(f"Found {len(files)} file(s). Starting download into '{download_dir.resolve()}' ...\n")

    success, skipped, failed = 0, 0, 0

    for i, f in enumerate(files, start=1):
        mime    = f["mimeType"]
        name    = f["name"]
        file_id = f["id"]

        # Determine destination path + download method
        if mime in SUPPORTED_MIMES:
            ext  = SUPPORTED_MIMES[mime]
            dest = download_dir / safe_filename(name, ext)
            mode = "binary"
        elif mime in GOOGLE_EXPORT_MIMES:
            export_mime, ext = GOOGLE_EXPORT_MIMES[mime]
            dest = download_dir / safe_filename(name, ext)
            mode = "export"
        else:
            print(f"  [{i}/{len(files)}] SKIP (unsupported): {name}")
            skipped += 1
            continue

        prefix = f"  [{i}/{len(files)}]"

        if SKIP_EXISTING and dest.exists():
            print(f"{prefix} SKIP (exists): {dest.name}")
            skipped += 1
            continue

        try:
            print(f"{prefix} Downloading: {name} ...", end=" ", flush=True)
            if mode == "binary":
                download_binary(service, file_id, dest)
            else:
                export_google_doc(service, file_id, export_mime, dest)
            size_kb = dest.stat().st_size / 1024
            print(f"✅  ({size_kb:.1f} KB)")
            success += 1
        except Exception as e:
            print(f"❌  ERROR: {e}")
            failed += 1

    print(f"\n── Summary ─────────────────────────────")
    print(f"  ✅  Downloaded : {success}")
    print(f"  ⏭️   Skipped   : {skipped}")
    print(f"  ❌  Failed     : {failed}")
    print(f"  📁  Saved to  : {download_dir.resolve()}")
    print("────────────────────────────────────────\n")


if __name__ == "__main__":
    main()