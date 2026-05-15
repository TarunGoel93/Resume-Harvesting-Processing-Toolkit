import os
import time
import urllib.parse
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

SKIP_CANDIDATES = 0
MAX_PAGES = None

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


driver, wait, fast_wait = setup_driver()

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# ===================== HELPERS =====================
def go_to_candidates_page():
    """Open the candidates list and wait until candidate rows are visible."""
    driver.get(CANDIDATES_URL)

    wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//a[contains(@href,'page=candidetail') and contains(@href,'detail=')]"
            )
        )
    )


def wait_for_user_to_apply_filters():
    """
    Navigate to the candidates page, let the user apply filters manually,
    then wait for them to press Enter before starting to scrape.
    """
    print("\nNavigating to candidates page for filter selection...")
    driver.get(CANDIDATES_URL)

    print("\n" + "="*60)
    print("FILTER SELECTION STEP")
    print("="*60)
    print("The candidates page is now open in Chrome.")
    print("Please apply all your desired filters now")
    print("(e.g. location, experience, skills, freshness, etc.)")
    print()
    print("Once the filtered results are loaded and you are")
    print("satisfied with what you see, come back here.")
    print("="*60)
    input("Press Enter when filters are applied and results are ready...")

    print("Waiting for candidate links to appear after filter...")
    wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//a[contains(@href,'page=candidetail') and contains(@href,'detail=')]"
            )
        )
    )
    print("Candidate results detected. Starting download process...\n")


def get_candidate_detail_links():
    """Collect all candidate detail links on the current page, robust to stale elements."""
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
            print("Stale elements while reading candidate links, retrying...", retries)
            if retries >= 3:
                print("Could not get stable candidate links on this page, moving on.")
                return []
            time.sleep(1)


def get_candidate_id_from_url(url):
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    return qs.get("detail", [""])[0]


def has_resume_already(url):
    """Skip if a file for this candidate already exists in the download folder."""
    cid = get_candidate_id_from_url(url)
    if not cid:
        return False
    for name in os.listdir(DOWNLOAD_DIR):
        if cid in name:
            return True
    return False


def download_resume_from_detail(detail_url):
    """
    Open candidate detail page, find the 'Text Resume' section and download.
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

        resume_links = text_resume_label.find_elements(
            By.XPATH,
            ".//following::a[contains(@href,'.pdf') or contains(@href,'.doc') or contains(@href,'.docx')][1]"
        )

        if resume_links:
            resume_link = resume_links[0]
            resume_name = resume_link.text.strip() or resume_link.get_attribute("href")
            print("  Downloading resume (direct link):", resume_name)
            resume_link.click()
        else:
            download_btn = text_resume_label.find_element(
                By.XPATH,
                ".//following::a[contains(@href,'javascript:void') or contains(@onclick,'download')][1]"
            )
            print("  Clicking download button near Text Resume")
            download_btn.click()

        time.sleep(0.5)

    except Exception as e:
        print(f"  Could not download from {detail_url}: {e}")
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])


def go_to_next_page():
    """Click the Next pagination link if it exists, otherwise return False."""
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
    try:
        # ── STEP 1: Login ──────────────────────────────────────────
        print("="*60)
        print("STEP 1: LOGIN")
        print("="*60)
        print("Chrome is open. Please log in to PlacementIndia")
        print("using your mobile + password credentials.")
        input("Press Enter once you are fully logged in...")

        # ── STEP 2: Filter Selection ───────────────────────────────
        wait_for_user_to_apply_filters()

        # ── STEP 3: Scrape & Download ──────────────────────────────
        page_count = 0
        processed = 0

        while True:
            page_count += 1
            print(f"\nProcessing candidates page {page_count}...")

            detail_links = get_candidate_detail_links()
            print(f"Found {len(detail_links)} candidate detail links on page {page_count}")

            for url in detail_links:
                if processed < SKIP_CANDIDATES:
                    processed += 1
                    continue

                if has_resume_already(url):
                    processed += 1
                    continue

                processed += 1
                print(f"Processing candidate #{processed}: {url}")
                download_resume_from_detail(url)

            if MAX_PAGES is not None and page_count >= MAX_PAGES:
                print("Reached MAX_PAGES limit, stopping.")
                break

            if not go_to_next_page():
                print("No Next page button found, stopping.")
                break

        print("\nAll done. Check the 'placementindia_resumes' folder.")

    finally:
        time.sleep(5)
        driver.quit()


if __name__ == "__main__":
    main()