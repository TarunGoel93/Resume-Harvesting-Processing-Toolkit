import os
import time
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

# We want to cover pages 1–10 in this run,
# but skip candidates 1–500 (pages 1–5), so effectively only pages 6–10.
MAX_PAGES = 15

# You already processed 500 candidates (pages 1–5)
SKIP_CANDIDATES = 1000

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
    return driver, wait


driver, wait = setup_driver()

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


def get_candidate_detail_links():
    """Collect all candidate detail links on the current page."""
    links = driver.find_elements(
        By.XPATH,
        "//a[contains(@href,'page=candidetail') and contains(@href,'detail=')]"
    )
    hrefs = []
    for a in links:
        href = a.get_attribute("href")
        if href and href not in hrefs:
            hrefs.append(href)
    return hrefs


def download_resume_from_detail(detail_url):
    """
    Open candidate detail page, find the 'Text Resume' section and:
    - Click direct .pdf/.doc/.docx link if present, OR
    - Click a javascript:void(0)/download button near Text Resume.
    """
    driver.execute_script("window.open(arguments[0], '_blank');", detail_url)
    driver.switch_to.window(driver.window_handles[-1])

    try:
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(),'Candidates Details') or contains(text(),'Candidate Details')]")
            )
        )

        text_resume_label = wait.until(
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
            print("Downloading resume (direct link):", resume_name)
            resume_link.click()
        else:
            download_btn = text_resume_label.find_element(
                By.XPATH,
                ".//following::a[contains(@href,'javascript:void') or contains(@onclick,'download')][1]"
            )
            print("Clicking download button near Text Resume")
            download_btn.click()

        time.sleep(3)

    except Exception as e:
        print(f"Could not download from {detail_url}: {e}")
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
        time.sleep(3)
        return True
    except Exception:
        return False

# ===================== MAIN =====================
def main():
    try:
        print("Chrome opened. Please log in to PlacementIndia in this window,")
        print("using your normal login form (mobile + password).")
        print("After login, you can stay on dashboard or any recruiter page.")
        input("When you are fully logged in, come back here and press Enter...")

        go_to_candidates_page()

        page_count = 0
        processed = 0  # total candidates counted across pages

        while True:
            page_count += 1
            print(f"Processing candidates page {page_count}...")

            detail_links = get_candidate_detail_links()
            print(f"Found {len(detail_links)} candidate detail links on page {page_count}")

            for url in detail_links:
                # Skip first 500 already processed candidates (pages 1–5)
                if processed < SKIP_CANDIDATES:
                    processed += 1
                    print("Skipping already processed candidate:", url)
                    continue

                processed += 1
                print("Processing candidate #", processed, ":", url)
                download_resume_from_detail(url)

            # Stop this run after page 10 (so this run covers pages 1–10)
            if MAX_PAGES is not None and page_count >= MAX_PAGES:
                print("Reached MAX_PAGES limit, stopping.")
                break

            if not go_to_next_page():
                print("No Next page button found, stopping.")
                break

        print("All done. Check the 'placementindia_resumes' folder.")
    finally:
        time.sleep(5)
        driver.quit()


if __name__ == "__main__":
    main()

