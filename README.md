# Resume Harvesting & Processing Toolkit

A collection of Python automation scripts for sourcing, downloading, converting, and indexing candidate resumes from **PlacementIndia** and **Google Drive**. Designed for recruitment workflows that require bulk resume collection and PDF normalization.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Google API Configuration](#google-api-configuration)
- [Scripts Reference](#scripts-reference)
- [Workflow Guide](#workflow-guide)
- [Configuration Reference](#configuration-reference)
- [Data Files](#data-files)
- [Important Notes](#important-notes)

---

## Overview

This toolkit automates the end-to-end recruitment pipeline:

1. **Scrape** candidate profile data and download resumes from PlacementIndia (recruiter portal)
2. **Index** resume files stored in Google Drive into a formatted Excel sheet
3. **Download** Drive files locally (PDF, DOC, DOCX)
4. **Convert** all resume formats to PDF via the pdf.co API
5. **Track** already-downloaded candidates to avoid duplicates across runs

---

## Project Structure

```
New folder/
│
├── a.py                        # PlacementIndia resume downloader (with manual filter support)
├── b.py                        # Improved downloader with smart duplicate detection via CSV + log
├── x.py                        # Basic resume downloader (no skip logic; full scan)
├── y.py                        # Downloader with SKIP_CANDIDATES offset support
├── z.py                        # Downloader variant with configurable page range
│
├── profiles_download.py        # Bulk Excel export of candidate profiles from PlacementIndia
│
├── D_T_E.py                    # Google Drive → Excel index generator (clickable hyperlinks)
├── drive_downloader.py         # Google Drive folder → local file downloader
├── Convert_resumes_to_pdf.py   # Converts Drive resume links to PDF via pdf.co API
│
├── credentials.json            # Google OAuth2 Desktop client credentials (DO NOT COMMIT)
├── token.json                  # Auto-generated OAuth2 access token (DO NOT COMMIT)
│
├── downloaded_ids.txt          # Persistent log of downloaded candidate IDs
├── drive_file_index.xlsx       # Output: Drive file index with clickable links
├── Resumes - Finals.csv        # Master CSV of processed resumes
│
├── placementindia_resumes/     # Downloaded resume files (PDF/DOC/DOCX)
├── pdfs/                       # Converted PDF output folder
├── converted_pdfs/             # Alternative converted PDF storage
└── old_resume/                 # Archive folder for older resume files
```

---

## Prerequisites

- **Python 3.8+**
- **Google Chrome** (latest stable)
- A **PlacementIndia recruiter account**
- A **Google Cloud project** with the Drive API enabled and OAuth 2.0 Desktop credentials
- A **pdf.co account** with API access (for PDF conversion only)

---

## Setup & Installation

```bash
# Clone or extract the project folder
cd "New folder"

# Install all required packages
pip install selenium webdriver-manager openpyxl requests \
            google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

---

## Google API Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Google Drive API**
4. Navigate to **APIs & Services → Credentials**
5. Create an **OAuth 2.0 Client ID** → Application type: **Desktop app**
6. Download the JSON file and rename it to `credentials.json`
7. Place `credentials.json` in the project root (same directory as the scripts)

> On first run of any Drive script, a browser window will open for OAuth consent. After approval, a `token.json` file is auto-generated and reused for subsequent runs.

> ⚠️ **Never commit `credentials.json` or `token.json` to version control.** Add both to `.gitignore`.

---

## Scripts Reference

### PlacementIndia Scrapers

All scrapers use **Selenium with Chrome** and require manual login at startup. The browser opens automatically; you log in, apply filters if needed, and then press Enter in the terminal to begin.

---

#### `y.py` — Basic Resume Downloader (Recommended Starting Point)

Downloads resumes from the PlacementIndia recruiter candidate list with minimal configuration.

```bash
python y.py
```

**Config (top of file):**
```python
CANDIDATES_URL = "https://recruiter.placementindia.com/?page=candidates"
DOWNLOAD_DIR   = "./placementindia_resumes"
MAX_PAGES      = None   # None = all pages; set an integer to limit
```

**Flow:**
1. Opens Chrome → you log in manually
2. Script navigates to the candidates page
3. Iterates through all paginated pages, opening each candidate detail in a new tab
4. Locates the "Text Resume" section and clicks the download link
5. Closes the tab and moves to the next candidate

---

#### `a.py` — Downloader with Manual Filter Support

Same as `y.py` but pauses before scraping to let you apply search filters (location, experience, skills, etc.) directly in the browser.

```bash
python a.py
```

**Additional Config:**
```python
SKIP_CANDIDATES = 0  # Skip first N candidates (useful for resuming a partial run)
```

---

#### `b.py` — Smart Downloader with Duplicate Detection (Most Feature-Complete)

Most robust version. Loads already-downloaded IDs from three sources before starting:
- An existing **CSV file** (the `Resumes - Finals.csv` master list)
- Files already present in the **download folder**
- A **`downloaded_ids.txt`** log from previous script runs

Checks the candidate ID *before* downloading, skipping any already seen. Logs new downloads to `downloaded_ids.txt` for future runs.

```bash
python b.py
```

**Additional Config:**
```python
EXISTING_CSV_PATH            = r"C:\path\to\Resumes - Finals.csv"
EXISTING_CSV_FILENAME_COLUMN = "File Name"   # Column header containing filenames like '10012090.pdf'
DOWNLOADED_LOG               = "./downloaded_ids.txt"
```

---

#### `z.py` — Downloader with Page Range & Skip Offset

Use when you need to resume from a specific candidate count within a bounded page range.

```bash
python z.py
```

```python
MAX_PAGES       = 15    # Stop after this many pages
SKIP_CANDIDATES = 1000  # Skip the first 1000 candidates already processed
```

---

#### `profiles_download.py` — Bulk Profile Excel Export

Automates the **"Download Excel File"** button on the PlacementIndia search results page. Iterates through all paginated result pages, selecting all candidates on each page and triggering the Excel export.

```bash
python profiles_download.py
```

**Config:**
```python
LOGIN_URL  = "https://www.placementindia.com/job-recruiters/login.php"
SEARCH_URL = "https://www.placementindia.com/job-recruiters/search_resume.php"
MAX_PAGES  = None   # None = all pages
```

**Flow:**
1. Opens Chrome → you log in manually and navigate to Search Resume
2. You set filters and display 100 results per page, then press Enter
3. Script iterates all pages: selects all → clicks Download Excel → deselects → next page

---

### Google Drive Scripts

---

#### `D_T_E.py` — Drive Folder → Excel Index

Scans a Google Drive folder and generates a formatted `.xlsx` file containing file name, type, size, last-modified date, and a clickable "📂 Open" hyperlink for every PDF/DOC/DOCX file found.

```bash
python D_T_E.py
```

**Config:**
```python
DRIVE_FOLDER_NAME = "YOUR_FOLDER_NAME"   # Exact name of the Drive folder to scan
OUTPUT_XLSX       = "drive_file_index.xlsx"
```

**Output columns:** `#`, `File Name`, `Type`, `Size (KB)`, `Modified`, `Open File`

---

#### `drive_downloader.py` — Drive Folder → Local Download

Downloads all PDF/DOC/DOCX files (and exports Google Docs/Sheets/Slides to Office formats) from a specified Drive folder to a local directory.

```bash
python drive_downloader.py
```

**Config:**
```python
DRIVE_FOLDER_NAME = "YOUR_FOLDER_NAME"   # Exact name of the Drive folder
DOWNLOAD_DIR      = "./downloads"
SKIP_EXISTING     = True                 # Skip files already downloaded
```

---

#### `Convert_resumes_to_pdf.py` — Resume Links → PDF via pdf.co

Reads an Excel file (`Resumes-2K.xlsx`) containing Google Drive resume links, converts each file to PDF using the [pdf.co API](https://pdf.co), and writes the resulting hosted PDF URL back into a new `PDF Link` column. Saves progress after every row.

```bash
python Convert_resumes_to_pdf.py
```

**Config:**
```python
API_KEY    = "YOUR_PDF_CO_API_KEY"   # From your pdf.co account dashboard
EXCEL_FILE = "Resumes-2K.xlsx"
DELAY_SEC  = 0.5    # Pause between API calls
MAX_RETRIES = 3
```

**Supported input types:** PDF on Drive, DOC/DOCX on Drive, Google Docs (exported via Drive)

---

## Workflow Guide

### Full Pipeline (First-Time Run)

```
Step 1 ─ profiles_download.py   →  Download candidate Excel sheets from PlacementIndia
Step 2 ─ b.py                   →  Download individual resumes (PDF/DOC/DOCX)
Step 3 ─ D_T_E.py               →  Index all resumes from the Drive folder into Excel
Step 4 ─ Convert_resumes_to_pdf.py → Convert everything to PDF via pdf.co
```

### Resuming a Partial Run

Use `b.py` — it automatically deduplicates against your existing CSV and the `downloaded_ids.txt` log. No manual offset needed.

Alternatively, use `z.py` and set `SKIP_CANDIDATES` to the count already processed.

---

## Configuration Reference

| Variable | Used In | Description |
|---|---|---|
| `CANDIDATES_URL` | `a.py`, `b.py`, `x.py`, `y.py`, `z.py` | PlacementIndia recruiter candidates page URL |
| `DOWNLOAD_DIR` | All scrapers | Local folder where resumes are saved |
| `MAX_PAGES` | All scrapers | Max pages to scrape; `None` for unlimited |
| `SKIP_CANDIDATES` | `a.py`, `y.py`, `z.py` | Number of candidates to skip at the start |
| `EXISTING_CSV_PATH` | `b.py` | Full path to the master resumes CSV |
| `DOWNLOADED_LOG` | `b.py` | Path to the persistent ID log file |
| `DRIVE_FOLDER_NAME` | `D_T_E.py`, `drive_downloader.py` | Exact name of the target Google Drive folder |
| `SKIP_EXISTING` | `drive_downloader.py` | Skip files already present locally |
| `API_KEY` | `Convert_resumes_to_pdf.py` | Your pdf.co API key |
| `EXCEL_FILE` | `Convert_resumes_to_pdf.py` | Input Excel file with resume links |

---

## Data Files

| File | Description |
|---|---|
| `Resumes - Finals.csv` | Master list of all processed resumes; used by `b.py` for deduplication |
| `downloaded_ids.txt` | Append-only log of numeric candidate IDs downloaded in past runs |
| `drive_file_index.xlsx` | Generated by `D_T_E.py`; clickable Drive file index |
| `credentials.json` | Google OAuth2 client credentials — **keep private** |
| `token.json` | Auto-generated OAuth2 token — **keep private** |

---

## Important Notes

**Security**
- `credentials.json` and `token.json` contain sensitive authentication data. Never share or commit them.
- The pdf.co API key has usage limits and billing implications. Store it in an environment variable rather than hardcoding it in production.

**Rate Limits & Stability**
- PlacementIndia scrapers open a new browser tab per candidate. On large runs (1000+ candidates), Chrome memory usage can grow significantly. Consider running in batches using `MAX_PAGES`.
- The pdf.co script includes exponential back-off retries and saves progress after every row, making it safe to interrupt and resume.

**Duplicate Avoidance**
- Prefer `b.py` over the other scrapers for any run where partial data already exists. It is the only script that checks all three deduplication sources before downloading.

**ChromeDriver**
- All scrapers use `webdriver-manager` to auto-install the correct ChromeDriver version. Ensure Chrome is kept up to date.

---

*Last updated: May 2026*
