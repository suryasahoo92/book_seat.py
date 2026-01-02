from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
import logging
import os
import time
import traceback
import sys
import argparse
from datetime import datetime
import shutil

LOG_FILENAME = os.getenv("FLOWSCAPE_LOG", "booking.log")


def setup_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILENAME, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("Logging initialized. Debug=%s", debug)


def _safe_screenshot(driver, name):
    try:
        driver.save_screenshot(name)
        logging.debug("Saved screenshot: %s", name)
    except Exception as e:
        logging.debug("Unable to save screenshot %s: %s", name, e)


def _write_file(name, content):
    try:
        with open(name, "w", encoding="utf-8") as f:
            f.write(content)
        logging.debug("Wrote file: %s", name)
    except Exception as e:
        logging.debug("Failed writing file %s: %s", name, e)


def _dump_page_state(driver, prefix):
    """
    Save page_source, screenshot and browser console logs (if available).
    """
    try:
        _safe_screenshot(driver, f"{prefix}.png")
    except Exception:
        pass
    try:
        _write_file(f"{prefix}.html", driver.page_source)
    except Exception:
        pass
    # browser console logs (Chrome/Chromium)
    try:
        logs = []
        for entry in driver.get_log("browser"):
            logs.append(f"{entry.get('level')} {entry.get('source', '')} {entry.get('message')}")
        _write_file(f"{prefix}_browser_console.log", "\n".join(logs))
    except Exception:
        logging.debug("No browser console logs available or get_log failed.")


def _log_exception(step_name: str, exc: Exception, driver=None):
    logging.exception("Exception during %s: %s", step_name, exc)
    try:
        suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        _dump_page_state(driver, f"error_{step_name}_{suffix}") if driver is not None else None
    except Exception:
        logging.debug("Failed dumping page state for %s", step_name)


def _set_input_value(driver, element, value):
    """
    Robustly set value for an input element: try clear/send_keys, fall back to JS set+events.
    """
    try:
        element.clear()
    except Exception:
        pass
    try:
        element.send_keys(value)
        try:
            element.send_keys("\n")
        except Exception:
            pass
        return True
    except Exception:
        pass

    try:
        driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
            "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));"
            "arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));",
            element,
            value,
        )
        return True
    except Exception:
        return False


def _find_time_input_within(driver, container):
    """
    Return dict with 'start' and 'end' input elements if found, else None entries.
    """
    result = {"start": None, "end": None}
    base = "." if container is not None else ""
    start_xpaths = [
        f"{base}//input[@type='time' and (contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start'))]",
        f"{base}//input[(contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start') or contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start'))]",
        f"{base}//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]/following::input[1]",
    ]
    end_xpaths = [
        f"{base}//input[@type='time' and (contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'end') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'end'))]",
        f"{base}//input[(contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'end') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'end') or contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'end'))]",
        f"{base}//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'end')]/following::input[1]",
    ]

    try:
        for xp in start_xpaths:
            elems = container.find_elements(By.XPATH, xp) if container is not None else driver.find_elements(By.XPATH, xp)
            if elems:
                result["start"] = elems[0]
                break
    except Exception:
        pass

    try:
        for xp in end_xpaths:
            elems = container.find_elements(By.XPATH, xp) if container is not None else driver.find_elements(By.XPATH, xp)
            if elems:
                result["end"] = elems[0]
                break
    except Exception:
        pass

    # fallback: first two input[type=time]
    try:
        if (not result["start"] or not result["end"]):
            time_inputs = (container.find_elements(By.XPATH, ".//input[@type='time']") if container is not None else driver.find_elements(By.XPATH, "//input[@type='time']"))
            if len(time_inputs) >= 2:
                if not result["start"]:
                    result["start"] = time_inputs[0]
                if not result["end"]:
                    result["end"] = time_inputs[1]
    except Exception:
        pass

    return result


def login_flowscape(driver, email=None, password=None, seat_identifier="ID-6F-280 (UK)", debug=True):
    """
    Full flow with extensive logging and state dumps. Returns True on success.
    """
    wait = WebDriverWait(driver, 30)
    current_window = None
    try:
        logging.info("Opening target URL")
        target_url = os.getenv("FLOWSCAPE_URL") or "https://wsp.flowscape.se/webapp/"
        driver.get(target_url)
        current_window = driver.current_window_handle
        logging.info("Opened %s (handle=%s)", target_url, current_window)
        _dump_page_state(driver, "after_open")
    except Exception as e:
        _log_exception("open_page", e, driver)
        return False

    # 1. Click "Sign in with Microsoft"
    try:
        logging.info("Waiting for Microsoft sign-in button")
        microsoft_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Microsoft') or contains(., 'Sign in with Microsoft')]"))
        )
        logging.info("Clicking Microsoft sign-in button")
        microsoft_btn.click()
        logging.debug("Clicked Microsoft sign-in")
    except Exception as e:
        _log_exception("click_microsoft", e, driver)
        return False

    # handle potential new window
    try:
        logging.info("Checking for new login window")
        WebDriverWait(driver, 5).until(lambda d: len(d.window_handles) > 1)
        for handle in driver.window_handles:
            if handle != current_window:
                driver.switch_to.window(handle)
                logging.info("Switched to login window: %s", handle)
                break
    except Exception:
        logging.info("No new login window detected; continuing in same window")

    # Credentials
    USERNAME = email or os.getenv("FLOWSCAPE_USER")
    PASSWORD = password or os.getenv("FLOWSCAPE_PASS")
    logging.debug("Using username from env present=%s", bool(USERNAME))

    try:
        # Enter email
        logging.info("Filling email")
        email_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "loginfmt")))
        email_field.clear()
        email_field.send_keys(USERNAME)
        driver.find_element(By.ID, "idSIButton9").click()
        logging.debug("Email entered and next clicked")
    except Exception as e:
        _log_exception("enter_email", e, driver)
        return False

    try:
        logging.info("Filling password")
        password_field = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.NAME, "passwd")))
        password_field.clear()
        password_field.send_keys(PASSWORD)
        WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
        logging.debug("Password entered and signed in")
    except Exception as e:
        _log_exception("enter_password", e, driver)
        return False

    # handle optional MS prompts
    try:
        logging.info("Handling optional MS prompts (if any)")
        time.sleep(1)
        for btn_id in ("idBtn_Back", "idBtn_Accept", "idSIButton9"):
            try:
                btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, btn_id)))
                btn.click()
                logging.info("Clicked MS optional button %s", btn_id)
                break
            except Exception:
                continue
    except Exception:
        logging.debug("No optional MS prompt handled")

    # switch back to flowscape main window
    try:
        logging.info("Switching back to main Flowscape window")
        main_handle = None
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                if "flowscape" in driver.current_url:
                    main_handle = handle
                    break
            except Exception:
                continue
        if main_handle:
            driver.switch_to.window(main_handle)
            logging.info("Switched to main handle %s", main_handle)
        else:
            driver.switch_to.window(driver.window_handles[0])
            logging.info("Switched to fallback handle %s", driver.current_window_handle)
    except Exception as e:
        logging.debug("Error while switching back to main app: %s", e)

    # find and click seat
    try:
        logging.info("Locating seat: %s", seat_identifier)
        xpath_exact = f"//*[@aria-label=\"{seat_identifier}\" or @title=\"{seat_identifier}\"]"
        xpath_contains = f"//*[contains(@aria-label, \"{seat_identifier.split()[0]}\") or contains(@title, \"{seat_identifier.split()[0]}\")]"
        my_seat = None
        try:
            my_seat = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, xpath_exact)))
            logging.info("Found exact seat element")
        except Exception:
            logging.info("Exact seat not found; trying contains fallback")
            candidates = driver.find_elements(By.XPATH, xpath_contains)
            for c in candidates:
                try:
                    aria = c.get_attribute("aria-label") or c.get_attribute("title") or c.text or ""
                    if seat_identifier.split()[0] in aria:
                        my_seat = c
                        break
                except Exception:
                    continue
        if not my_seat:
            logging.error("Seat element not found - dumping page and returning")
            _dump_page_state(driver, "seat_not_found")
            return False

        logging.info("Clicking seat element")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", my_seat)
        driver.execute_script("arguments[0].click();", my_seat)
        _dump_page_state(driver, "after_seat_click")
    except Exception as e:
        _log_exception("click_seat", e, driver)
        return False

    # detect popup/modal or new window for booking and fill Start/End times
    popup_handle_switched = False
    iframe_switched = False
    modal = None
    try:
        logging.info("Detecting booking popup/modal or window")
        # short time to allow popup window to appear
        try:
            WebDriverWait(driver, 3).until(lambda d: len(d.window_handles) > 1)
            for handle in driver.window_handles:
                if handle != driver.current_window_handle:
                    popup_handle_switched = True
                    driver.switch_to.window(handle)
                    logging.info("Switched to popup window: %s", handle)
                    break
        except Exception:
            logging.debug("No separate popup window detected")

        # try to find modal
        try:
            modal = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//*[@role='dialog' or @aria-modal='true' or contains(@class,'modal') or contains(@class,'Dialog') or contains(@class,'popup')]"))
            )
            logging.info("Found modal element for booking")
        except Exception:
            logging.debug("Modal not detected by role/class heuristics")

        # if modal contains iframe, switch into it
        try:
            if modal is not None:
                iframes = modal.find_elements(By.TAG_NAME, "iframe")
                if iframes:
                    driver.switch_to.frame(iframes[0])
                    iframe_switched = True
                    logging.info("Switched into iframe inside modal")
        except Exception:
            logging.debug("No iframe inside modal or switching failed")

        # dump state now
        _dump_page_state(driver, "popup_detected")
    except Exception as e:
        _log_exception("detect_popup", e, driver)
        return False

    # locate time inputs
    try:
        inputs = _find_time_input_within(driver, modal if not iframe_switched else None)
        if not inputs["start"] or not inputs["end"]:
            logging.info("Primary selectors didn't find start/end; trying global search")
            inputs = _find_time_input_within(driver, None)

        if not inputs["start"] or not inputs["end"]:
            logging.error("Start/end inputs not found - dumping and returning")
            _dump_page_state(driver, "time_inputs_not_found")
            # restore contexts
            if iframe_switched:
                driver.switch_to.default_content()
            if popup_handle_switched:
                try:
                    driver.close()
                except Exception:
                    pass
                driver.switch_to.window(current_window)
            return False

        logging.info("Setting start/end times")
        if not _set_input_value(driver, inputs["start"], "08:00") or not _set_input_value(driver, inputs["end"], "18:00"):
            logging.error("Failed to set start/end values")
            _dump_page_state(driver, "set_time_failed")
            if iframe_switched:
                driver.switch_to.default_content()
            if popup_handle_switched:
                try:
                    driver.close()
                except Exception:
                    pass
                driver.switch_to.window(current_window)
            return False
        _dump_page_state(driver, "after_setting_times")
    except Exception as e:
        _log_exception("set_times", e, driver)
        return False

    # click Book button
    try:
        logging.info("Attempting to click Book/Confirm button")
        book_btn_candidates = []
        if modal is not None and not iframe_switched:
            book_btn_candidates = modal.find_elements(By.XPATH, ".//button[contains(., 'Book') or contains(., 'BOOK') or contains(., 'Book now') or contains(., 'Confirm') or contains(., 'OK') or contains(., 'Ok') or contains(., 'Yes')]")
        if not book_btn_candidates:
            book_btn_candidates = driver.find_elements(By.XPATH, "//button[contains(., 'Book') or contains(., 'BOOK') or contains(., 'Book now') or contains(., 'Confirm') or contains(., 'OK') or contains(., 'Ok') or contains(., 'Yes')]")

        clicked = False
        for btn in book_btn_candidates:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", btn)
                    driver.execute_script("arguments[0].click();", btn)
                    clicked = True
                    logging.info("Clicked a Book/Confirm button candidate")
                    break
            except Exception:
                continue

        if not clicked:
            logging.error("Could not find or click the Book button")
            _dump_page_state(driver, "book_button_not_clicked")
            if iframe_switched:
                driver.switch_to.default_content()
            if popup_handle_switched:
                try:
                    driver.close()
                except Exception:
                    pass
                driver.switch_to.window(current_window)
            return False
    except Exception as e:
        _log_exception("click_book", e, driver)
        return False

    # restore contexts and wait for confirmation
    try:
        if iframe_switched:
            driver.switch_to.default_content()
        if popup_handle_switched:
            time.sleep(1)
            try:
                driver.close()
            except Exception:
                pass
            driver.switch_to.window(current_window)
    except Exception:
        logging.debug("Failed restoring windows/frames after clicking Book")

    try:
        logging.info("Waiting for booking confirmation indicator")
        success_xpath = "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirmed') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'booked') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'success') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reservation')]"
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, success_xpath)))
        logging.info("Booking appears successful (confirmation found)")
        _dump_page_state(driver, "booking_success")
        return True
    except Exception:
        logging.warning("No explicit confirmation found after booking click. Dumping final state.")
        _dump_page_state(driver, "booking_no_confirmation")
        return False


def make_driver(headless=True, enable_console_logs=True):
    """
    Create a Chrome WebDriver with optional browser console logging enabled.
    Uses Selenium 4+ style (Service + options) and sets logging prefs on options.
    """
    options = webdriver.ChromeOptions()
    if headless:
        # use new headless mode flag where available
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Ensure window-size so screenshots look consistent
    options.add_argument("--window-size=1920,1080")

    # Enable browser console logs (Chrome) via capabilities set on options
    if enable_console_logs:
        try:
            options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        except Exception:
            # fallback: older selenium might still accept desired_capabilities but we prefer set_capability
            pass

    # Find chromedriver from PATH if available
    chromedriver_path = shutil.which("chromedriver")
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()

    try:
        driver = webdriver.Chrome(service=service, options=options)
        logging.info("Launched Chrome WebDriver (headless=%s)", headless)
        return driver
    except TypeError as e:
        # back-compat fallback: try without service argument (some environments)
        logging.warning("webdriver.Chrome(service=..., options=...) failed: %s. Retrying without service.", e)
        try:
            driver = webdriver.Chrome(options=options)
            logging.info("Launched Chrome WebDriver (fallback without service) (headless=%s)", headless)
            return driver
        except Exception as ex:
            logging.exception("Failed to launch Chrome WebDriver in fallback: %s", ex)
            raise
    except WebDriverException as e:
        logging.exception("Failed to launch Chrome WebDriver: %s", e)
        raise


def main():
    parser = argparse.ArgumentParser(description="Flowscape seat booker with verbose logging")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging and save debug artifacts")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode (default: env HEADLESS or True)")
    parser.add_argument("--seat", type=str, default=os.getenv("FLOWSCAPE_SEAT", "ID-6F-277 (UK)"), help="Seat identifier to book")
    args = parser.parse_args()

    debug = args.debug or os.getenv("FLOWSCAPE_DEBUG", "1") == "1"
    # default headless True unless explicitly set
    headless_env = os.getenv("HEADLESS")
    if headless_env is not None:
        headless = headless_env.lower() not in ("0", "false", "no")
    else:
        headless = True if not args.headless else True

    setup_logging(debug)

    driver = None
    try:
        driver = make_driver(headless=headless, enable_console_logs=True)
        success = login_flowscape(driver, email=None, password=None, seat_identifier=args.seat, debug=debug)
        if success:
            logging.info("Seat booking flow completed: SUCCESS")
            sys.exit(0)
        else:
            logging.error("Seat booking flow completed: FAILURE")
            sys.exit(2)
    except Exception as e:
        logging.exception("Unhandled exception in main: %s", e)
        _dump_page_state(driver, "fatal_error") if driver is not None else None
        sys.exit(3)
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
