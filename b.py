import os
import re
import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ===================== CONFIG =====================
CANDIDATES_URL = "https://recruiter.placementindia.com/?page=candidates"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "placementindia_resumes")

# Your CSV of already-downloaded resumes (File Name column = '10012090.pdf' etc.)
EXISTING_CSV_PATH = r"C:\Users\ACER\Desktop\New folder\Resumes - Finals.csv"
EXISTING_CSV_FILENAME_COLUMN = "File Name"   # column that has '10012090.pdf'

# Local log to track numeric IDs downloaded in previous script runs
DOWNLOADED_LOG = os.path.join(os.getcwd(), "downloaded_ids.txt")

MAX_PAGES = None


# ===================== LOAD EXISTING IDs =====================
def load_already_downloaded_ids():
    """
    Build a set of numeric IDs (without extension) from:
    1. Your existing CSV  (e.g. '10012090.pdf'  -> '10012090')
    2. Files already in DOWNLOAD_DIR  (e.g. '10012090.pdf' -> '10012090')
    3. Local downloaded_ids.txt log from previous runs
    """
    seen = set()

    # 1. From your existing CSV
    if os.path.exists(EXISTING_CSV_PATH):
        with open(EXISTING_CSV_PATH, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fname = str(row.get(EXISTING_CSV_FILENAME_COLUMN, "")).strip()
                if fname:
                    numeric_id = os.path.splitext(fname)[0]
                    seen.add(numeric_id)
        print(f"Loaded {len(seen)} IDs from existing CSV.")
    else:
        print(f"WARNING: CSV not found at: {EXISTING_CSV_PATH}")

    # 2. From files already sitting in the download folder
    if os.path.exists(DOWNLOAD_DIR):
        for fname in os.listdir(DOWNLOAD_DIR):
            numeric_id = os.path.splitext(fname)[0]
            if numeric_id:
                seen.add(numeric_id)
        print(f"Total unique IDs after scanning download folder: {len(seen)}")

    # 3. From local log (previous script runs)
    if os.path.exists(DOWNLOADED_LOG):
        with open(DOWNLOADED_LOG, "r", encoding="utf-8") as f:
            for line in f:
                cid = line.strip()
                if cid:
                    seen.add(cid)
        print(f"Total unique IDs after merging local log: {len(seen)}")

    return seen


def log_downloaded_id(numeric_id):
    with open(DOWNLOADED_LOG, "a", encoding="utf-8") as f:
        f.write(numeric_id + "\n")


def get_newly_downloaded_file(before_files):
    """
    Compare files in DOWNLOAD_DIR before and after a download click.
    Returns the numeric ID (without extension) of the new file, or None.
    """
    timeout = 15  # seconds to wait for file to appear
    start = time.time()
    while time.time() - start < timeout:
        after_files = set(os.listdir(DOWNLOAD_DIR))
        new_files = after_files - before_files
        # Ignore .crdownload (incomplete Chrome downloads)
        completed = [f for f in new_files if not f.endswith(".crdownload")]
        if completed:
            fname = completed[0]
            return os.path.splitext(fname)[0]
        time.sleep(0.5)
    return None


# ===================== SETUP DRIVER =====================
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    wait = WebDriverWait(driver, 20)
    fast_wait = WebDriverWait(driver, 8)
    return driver, wait, fast_wait


# ===================== HELPERS =====================
def wait_for_user_to_apply_filters(driver, wait):
    print("\n" + "=" * 60)
    print("FILTER SELECTION STEP")
    print("=" * 60)
    print("The candidates page is now open in Chrome.")
    print("Please type your KEYWORD and apply any other filters.")
    print("Wait for filtered results to fully load in the browser.")
    print("=" * 60)
    input("Press Enter when filtered results are ready to scrape...")

    print("Waiting for candidate links to appear...")
    try:
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href,'page=candidetail') and contains(@href,'detail=')]")
            )
        )
        print("Candidates detected. Starting download...\n")
    except Exception:
        print("WARNING: No candidate links found. Check if the page loaded correctly.")


def get_candidate_detail_links(driver):
    retries = 0
    while True:
        try:
            links = driver.find_elements(
                By.XPATH,
                "//a[contains(@href,'page=candidetail') and contains(@href,'detail=')]"
            )
            hrefs = []
            for a in links:
                try:
                    href = a.get_attribute("href")
                    if href and href not in hrefs:
                        hrefs.append(href)
                except Exception:
                    hrefs = []
                    raise
            return hrefs
        except Exception:
            retries += 1
            print("Stale elements, retrying...", retries)
            if retries >= 3:
                print("Could not get stable candidate links, skipping page.")
                return []
            time.sleep(1)


def extract_id_from_url(url):
    """Extract numeric ID from detail URL query param e.g. detail=13734320"""
    match = re.search(r"detail=(\d+)", url)
    if match:
        return match.group(1)
    return None


def extract_id_from_text(text):
    """Extract first 6+ digit number from a string (href, onclick, etc.)"""
    match = re.search(r"(\d{6,})", text)
    if match:
        return match.group(1)
    return None


def check_candidate_already_downloaded(driver, fast_wait, detail_url, already_downloaded):
    """
    Open the detail page, extract the real numeric ID BEFORE downloading.
    Uses 3 fallback methods to find the ID without downloading:
      1. Direct file link href (.pdf / .doc / .docx)
      2. Download button onclick / href attribute (regex for 6+ digit number)
      3. The detail= param in the page URL itself

    Only downloads if the ID is NOT already in already_downloaded.
    Returns (numeric_id or None, should_skip: bool)
    """
    driver.execute_script("window.open(arguments[0], '_blank');", detail_url)
    driver.switch_to.window(driver.window_handles[-1])

    try:
        fast_wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(),'Candidates Details') or contains(text(),'Candidate Details')]")
            )
        )

        text_resume_label = fast_wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(),'Text Resume')]")
            )
        )

        numeric_id = None
        resume_link_el = None
        download_btn_el = None

        # ── METHOD 1: Direct file link (.pdf / .doc / .docx) ─────────────
        resume_links = text_resume_label.find_elements(
            By.XPATH,
            ".//following::a[contains(@href,'.pdf') or contains(@href,'.doc') or contains(@href,'.docx')][1]"
        )
        if resume_links:
            resume_link_el = resume_links[0]
            href = resume_link_el.get_attribute("href") or ""
            fname = href.split("/")[-1].split("?")[0]
            candidate_id = os.path.splitext(fname)[0]
            if candidate_id:
                numeric_id = candidate_id
                print(f"  [ID via direct link]: {numeric_id}")

        # ── METHOD 2: Download button onclick / href ──────────────────────
        if not numeric_id:
            try:
                download_btn_el = text_resume_label.find_element(
                    By.XPATH,
                    ".//following::a[contains(@href,'javascript:void') or contains(@onclick,'download') "
                    "or contains(@href,'download') or contains(@href,'resume')][1]"
                )
                onclick = download_btn_el.get_attribute("onclick") or ""
                href    = download_btn_el.get_attribute("href") or ""
                candidate_id = extract_id_from_text(onclick + href)
                if candidate_id:
                    numeric_id = candidate_id
                    print(f"  [ID via button attr]: {numeric_id}")
            except Exception:
                pass

        # ── METHOD 3: Fallback — extract from detail URL ──────────────────
        if not numeric_id:
            candidate_id = extract_id_from_url(detail_url)
            if candidate_id:
                numeric_id = candidate_id
                print(f"  [ID via page URL fallback]: {numeric_id}")

        # ── Duplicate check BEFORE any download ───────────────────────────
        if numeric_id and numeric_id in already_downloaded:
            print(f"  [SKIP] ID {numeric_id} already exists.")
            return numeric_id, True

        # ── Not a duplicate → now download ────────────────────────────────
        before_files = set(os.listdir(DOWNLOAD_DIR))

        if resume_link_el is not None:
            print(f"  Downloading (direct link): {numeric_id}")
            resume_link_el.click()
        elif download_btn_el is not None:
            print(f"  Clicking download button (pre-check ID: {numeric_id})")
            download_btn_el.click()
        else:
            # Last resort: find any clickable download element near Text Resume
            try:
                any_btn = text_resume_label.find_element(
                    By.XPATH, ".//following::a[1]"
                )
                print(f"  Clicking nearest link (pre-check ID: {numeric_id})")
                any_btn.click()
            except Exception as e:
                print(f"  No download element found on {detail_url}: {e}")
                return numeric_id, False

        # Wait for file to land and confirm actual ID from filename
        downloaded_id = get_newly_downloaded_file(before_files)
        if downloaded_id:
            if downloaded_id != numeric_id:
                print(f"  Note: pre-check ID was {numeric_id}, actual file ID: {downloaded_id}")
            numeric_id = downloaded_id
            print(f"  Confirmed downloaded file ID: {numeric_id}")
        else:
            print(f"  WARNING: File did not appear within timeout for ID: {numeric_id}")

        return numeric_id, False

    except Exception as e:
        print(f"  Error on {detail_url}: {e}")
        return None, False
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])


def go_to_next_page(driver):
    try:
        next_btn = driver.find_element(
            By.XPATH,
            "//a[contains(.,'Next') or contains(.,'›') or contains(.,'>')]"
        )
        next_btn.click()
        time.sleep(2)
        return True
    except Exception:
        return False


# ===================== MAIN =====================
def main():
    # Load all already-downloaded IDs upfront
    already_downloaded = load_already_downloaded_ids()
    print(f"\nTotal IDs to skip: {len(already_downloaded)}\n")

    driver, wait, fast_wait = setup_driver()

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    try:
        # ── STEP 1: Login ──────────────────────────────────────────
        print("=" * 60)
        print("STEP 1: LOGIN")
        print("=" * 60)
        print("Chrome is open. Please log in to PlacementIndia.")
        input("Press Enter once you are fully logged in...")

        # ── STEP 2: Go to candidates page & apply filters ──────────
        driver.get(CANDIDATES_URL)
        wait_for_user_to_apply_filters(driver, wait)

        # ── STEP 3: Scrape & Download ──────────────────────────────
        page_count = 0
        newly_downloaded = 0
        skipped_duplicates = 0

        while True:
            page_count += 1
            print(f"\n--- Page {page_count} ---")

            detail_links = get_candidate_detail_links(driver)
            print(f"Found {len(detail_links)} candidates on this page.")

            for url in detail_links:
                numeric_id, should_skip = check_candidate_already_downloaded(
                    driver, fast_wait, url, already_downloaded
                )

                if should_skip:
                    skipped_duplicates += 1
                    print(f"  (Total skipped: {skipped_duplicates})")
                    continue

                if numeric_id:
                    already_downloaded.add(numeric_id)
                    log_downloaded_id(numeric_id)
                    newly_downloaded += 1
                    print(f"  [SAVED] ID: {numeric_id} "
                          f"| Downloaded: {newly_downloaded} | Skipped: {skipped_duplicates}")

            if MAX_PAGES is not None and page_count >= MAX_PAGES:
                print("Reached MAX_PAGES limit, stopping.")
                break

            if not go_to_next_page(driver):
                print("No Next page found. All pages processed.")
                break

        print("\n" + "=" * 60)
        print(f"DONE.")
        print(f"  Newly downloaded this run : {newly_downloaded}")
        print(f"  Duplicates skipped        : {skipped_duplicates}")
        print(f"  Resumes saved to          : {DOWNLOAD_DIR}")
        print("=" * 60)

    finally:
        time.sleep(5)
        driver.quit()


if __name__ == "__main__":
    main()

