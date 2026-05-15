import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    InvalidSessionIdException, WebDriverException,
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
LOGIN_URL  = "https://www.placementindia.com/job-recruiters/login.php"
SEARCH_URL = "https://www.placementindia.com/job-recruiters/search_resume.php"
MAX_PAGES  = None   # None = all pages; set e.g. 5 to stop after 5 pages
# ──────────────────────────────────────────────────────────────────────────────


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        print("ChromeDriver loaded via webdriver-manager.")
    except Exception as e:
        print(f"webdriver-manager failed ({e}), using Selenium default.")
        service = Service()

    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait   = WebDriverWait(driver, 30)
    return driver, wait


def wait_for_page_stable(driver, wait):
    """Wait for results AND for the page to stop loading/re-rendering."""
    # Wait for results container
    wait.until(
        EC.presence_of_element_located(
            (By.XPATH,
             "//div[contains(@class,'mcr-box') or contains(@class,'mcr-item')]")
        )
    )
    # Wait for document ready state
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    # Extra buffer for any JS re-renders
    time.sleep(2)
    print("  Page stable, results visible.")


def select_all_on_page(driver, wait):
    """
    Click the Select-All checkbox using JavaScript to avoid stale element crashes.
    Re-finds the element fresh, scrolls it into view, then JS-clicks it.
    """
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"  Attempting select-all (attempt {attempt})...")

            # Wait until checkbox is present in DOM
            wait.until(EC.presence_of_element_located((By.ID, "chkCheckAll")))
            time.sleep(0.5)

            # Re-find fresh reference every attempt
            chk = driver.find_element(By.ID, "chkCheckAll")

            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", chk)
            time.sleep(0.5)

            # Check current state
            is_checked = driver.execute_script("return arguments[0].checked;", chk)

            if not is_checked:
                # Use JS click — avoids all stale/intercept/chromedriver issues
                driver.execute_script("arguments[0].click();", chk)
                time.sleep(1.5)

            # Verify it's now checked
            chk = driver.find_element(By.ID, "chkCheckAll")  # re-find after click
            is_checked_now = driver.execute_script("return arguments[0].checked;", chk)

            if is_checked_now:
                print("  Select-All checked successfully.")
                return True
            else:
                print(f"  Checkbox not checked after click, retrying...")
                time.sleep(1)

        except StaleElementReferenceException:
            print(f"  Stale element on attempt {attempt}, retrying...")
            time.sleep(2)
        except Exception as e:
            print(f"  Select-All attempt {attempt} failed: {type(e).__name__}: {str(e)[:100]}")
            time.sleep(2)

    print("  All select-all attempts failed, skipping page.")
    return False


def click_download_excel(driver, wait):
    """
    Click the 'Download Excel File' button (class=downloadExcele).
    Uses JS click and waits for it to appear after select-all.
    """
    try:
        # Wait for download button to appear/be clickable
        print("  Waiting for Download Excel button...")
        download_btn = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@class,'downloadExcele')]")
            )
        )
        time.sleep(1)

        # Re-find fresh and JS click
        download_btn = driver.find_element(
            By.XPATH, "//a[contains(@class,'downloadExcele')]"
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", download_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", download_btn)
        time.sleep(3)
        print("  Download Excel triggered successfully.")
        return True

    except TimeoutException:
        # Fallback: try matching by href pattern
        print("  Primary selector timed out, trying fallback...")
        try:
            download_btn = driver.find_element(
                By.XPATH,
                "//a[contains(@data-exeurl,'download-excel-bulk') or contains(@href,'download-excel-bulk')]"
            )
            driver.execute_script("arguments[0].click();", download_btn)
            time.sleep(3)
            print("  Download triggered via fallback selector.")
            return True
        except NoSuchElementException:
            print("  No download button found at all.")
            return False
    except Exception as e:
        print(f"  Download click failed: {type(e).__name__}: {str(e)[:100]}")
        return False


def deselect_all(driver):
    """Uncheck the select-all box before moving to next page."""
    try:
        chk = driver.find_element(By.ID, "chkCheckAll")
        is_checked = driver.execute_script("return arguments[0].checked;", chk)
        if is_checked:
            driver.execute_script("arguments[0].click();", chk)
            time.sleep(1)
            print("  Deselected all.")
    except Exception:
        pass


def go_to_next_page(driver, wait):
    """Click Next in pagination. Returns False if last page or not found."""
    try:
        # Find next button — try multiple XPath patterns
        next_btn = None
        xpaths = [
            "//ul[contains(@class,'pagination')]/li[not(contains(@class,'disabled'))]/a[normalize-space(.)='Next']",
            "//ul[contains(@class,'pagination')]/li[not(contains(@class,'disabled'))]/a[contains(.,'›')]",
            "//ul[contains(@class,'pagination')]/li[not(contains(@class,'disabled'))]/a[normalize-space(.)='>']",
            "//a[@rel='next']",
        ]
        for xp in xpaths:
            try:
                el = driver.find_element(By.XPATH, xp)
                if el.is_displayed():
                    next_btn = el
                    break
            except NoSuchElementException:
                continue

        if next_btn is None:
            print("  No active Next button found — last page.")
            return False

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", next_btn)
        time.sleep(3)
        wait_for_page_stable(driver, wait)
        return True

    except Exception as e:
        print(f"  Pagination error: {type(e).__name__}: {str(e)[:80]}")
        return False


def get_current_page_number(driver):
    """Read active page number from pagination."""
    try:
        active = driver.find_element(
            By.XPATH,
            "//ul[contains(@class,'pagination')]/li[contains(@class,'active')]/a"
        )
        return active.text.strip()
    except Exception:
        return "?"


def main():
    print("Starting Chrome...")
    try:
        driver, wait = setup_driver()
    except Exception as e:
        print(f"\nFailed to launch Chrome: {e}")
        print("Fix: pip install --upgrade selenium webdriver-manager")
        return

    try:
        # ── Step 1: Login ─────────────────────────────────────────────────────
        print(f"\nOpening login page: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        print("\n>>> Please log in manually in the Chrome window.")
        input(">>> After login, when you are on the recruiter dashboard, press Enter...\n")

        # ── Step 2: Go to Search Resume ───────────────────────────────────────
        print(f"Navigating to: {SEARCH_URL}")
        driver.get(SEARCH_URL)
        print("\n>>> Set your search filters and set 'Show: 100' per page.")
        print(">>> Wait for results to fully load before pressing Enter.")
        input(">>> Press Enter when 100 results are visible...\n")

        wait_for_page_stable(driver, wait)

        # ── Step 3: Page loop ─────────────────────────────────────────────────
        page = 0
        total_downloads = 0

        while True:
            page += 1
            pg_num = get_current_page_number(driver)
            print(f"\n{'─'*50}")
            print(f"  Page {page}  (paginator: {pg_num})")
            print(f"{'─'*50}")

            selected = select_all_on_page(driver, wait)

            if selected:
                success = click_download_excel(driver, wait)
                if success:
                    total_downloads += 1
                    print(f"  ✓ Download queued for page {page}.")
                deselect_all(driver)
            else:
                print("  Skipping download this page.")

            if MAX_PAGES is not None and page >= MAX_PAGES:
                print(f"\nReached MAX_PAGES ({MAX_PAGES}). Stopping.")
                break

            if not go_to_next_page(driver, wait):
                print("\nNo more pages.")
                break

        print(f"\n{'='*50}")
        print(f"Done! Pages processed : {page}")
        print(f"Downloads triggered   : {total_downloads}")
        print("Check your PlacementIndia account for downloaded files.")
        print(f"{'='*50}")

    except (InvalidSessionIdException, WebDriverException) as e:
        print(f"\nBrowser/session error: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        try:
            time.sleep(2)
            driver.quit()
            print("Browser closed.")
        except Exception:
            pass


if __name__ == "__main__":
    main()