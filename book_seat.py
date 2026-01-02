from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time


def _safe_screenshot(driver, name):
    try:
        driver.save_screenshot(name)
        print(f"Saved screenshot: {name}")
    except Exception:
        pass


def _set_input_value(driver, element, value):
    """
    Robustly set value for an input element: try clear/send_keys, fall back to JS value set + events.
    """
    try:
        element.clear()
    except Exception:
        pass
    try:
        element.send_keys(value)
        return True
    except Exception:
        try:
            driver.execute_script(
                "arguments[0].value = arguments[1]; "
                "arguments[0].dispatchEvent(new Event('input', { bubbles: true })); "
                "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                element,
                value,
            )
            return True
        except Exception:
            return False


def _find_time_input_within(driver, container):
    """
    Return dict with 'start' and 'end' input elements if found, else None.
    Tries several common selectors (aria-label, placeholder, label text, input[type=time]).
    """
    result = {"start": None, "end": None}
    candidates = []

    # Prepare relative xpaths from container if provided else global
    base = "." if container is not None else ""

    # Possible xpaths for start
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

    # Try each variant inside container (if container provided use find_elements with context)
    for xp in start_xpaths:
        try:
            if container is not None:
                elems = container.find_elements(By.XPATH, xp)
            else:
                elems = driver.find_elements(By.XPATH, xp)
            if elems:
                result["start"] = elems[0]
                break
        except Exception:
            continue

    for xp in end_xpaths:
        try:
            if container is not None:
                elems = container.find_elements(By.XPATH, xp)
            else:
                elems = driver.find_elements(By.XPATH, xp)
            if elems:
                result["end"] = elems[0]
                break
        except Exception:
            continue

    # As a last resort, try to pick the first two time inputs (start, end)
    if (not result["start"] or not result["end"]) and container is not None:
        try:
            time_inputs = container.find_elements(By.XPATH, ".//input[@type='time']")
            if len(time_inputs) >= 2:
                if not result["start"]:
                    result["start"] = time_inputs[0]
                if not result["end"]:
                    result["end"] = time_inputs[1]
        except Exception:
            pass

    # Global fallback (no container)
    if (not result["start"] or not result["end"]) and container is None:
        try:
            time_inputs = driver.find_elements(By.XPATH, "//input[@type='time']")
            if len(time_inputs) >= 2:
                if not result["start"]:
                    result["start"] = time_inputs[0]
                if not result["end"]:
                    result["end"] = time_inputs[1]
        except Exception:
            pass

    return result


def login_flowscape(driver, email=None, password=None):
    """
    Logs into Flowscape via Microsoft and attempts to book a seat.
    If email/password are not provided, falls back to FLOWSCAPE_USER and FLOWSCAPE_PASS environment variables.
    Returns True on success, False on failure.
    """
    try:
        # --- PUT YOUR URL HERE ---
        target_url = "https://wsp.flowscape.se/webapp/"
        driver.get(target_url)
        wait = WebDriverWait(driver, 30)

        # 1. Click "Sign in with Microsoft"
        microsoft_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Microsoft') or contains(., 'Sign in with Microsoft')]"))
        )
        current_window = driver.current_window_handle
        microsoft_btn.click()

        # If a new window opens for Microsoft login, switch to it
        try:
            wait.until(lambda d: len(d.window_handles) > 1)
            for handle in driver.window_handles:
                if handle != current_window:
                    driver.switch_to.window(handle)
                    print("Switched to Microsoft login window")
                    break
        except Exception:
            # no new window — continue in same window
            print("No extra window opened for Microsoft login")

    except Exception as e:
        print(f"Booking failed while opening page or clicking Microsoft sign-in: {e}")
        _safe_screenshot(driver, "layout_error_open.png")
        return False

    # Credentials stored as GitHub Action Secrets or passed as args
    USERNAME = email or os.getenv("FLOWSCAPE_USER")
    PASSWORD = password or os.getenv("FLOWSCAPE_PASS")

    try:
        # 2. Enter Microsoft Email
        email_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "loginfmt")))
        email_field.clear()
        email_field.send_keys(USERNAME)
        # Click Next (idSIButton9 is commonly the MS "Next/Sign in" button)
        driver.find_element(By.ID, "idSIButton9").click()

        # 3. Enter Microsoft Password
        # Sometimes there is a delay while it redirects to your company's login page
        password_field = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.NAME, "passwd")))
        password_field.clear()
        password_field.send_keys(PASSWORD)

        # 4. Click "Sign in"
        WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()

        # 4b. Handle optional "Stay signed in?" dialog or other MS prompts
        try:
            time.sleep(1)
            for btn_id in ("idBtn_Back", "idBtn_Accept", "idSIButton9"):
                try:
                    btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, btn_id)))
                    btn.click()
                    print(f"Clicked optional MS prompt button: {btn_id}")
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # After login flows, switch back to main app window if needed
        try:
            main_handle = None
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                if "flowscape" in driver.current_url:
                    main_handle = handle
                    break
            if main_handle:
                driver.switch_to.window(main_handle)
            else:
                driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass

        # 5. Handle seat selection and confirmation
        seat_identifier = "ID-6F-277 (UK)"

        # Try to find exact match first, else try contains
        xpath_exact = f"//*[@aria-label=\"{seat_identifier}\" or @title=\"{seat_identifier}\"]"
        xpath_contains = f"//*[contains(@aria-label, \"{seat_identifier.split()[0]}\") or contains(@title, \"{seat_identifier.split()[0]}\")]"

        my_seat = None
        try:
            my_seat = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath_exact)))
            print(f"Found seat with exact match: {seat_identifier}")
        except Exception:
            # fallback to contains match and try multiple candidates
            print("Exact match not found; trying contains() fallback")
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
            print("Could not locate the seat element on the page.")
            _safe_screenshot(driver, "seat_not_found.png")
            return False

        # Ensure seat is visible & clickable; use JS click to bypass overlay issues
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", my_seat)
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].click();", my_seat)
        except Exception as e:
            print(f"JS click failed on seat element, trying ActionChains click: {e}")
            try:
                from selenium.webdriver import ActionChains
                ActionChains(driver).move_to_element(my_seat).click().perform()
            except Exception as e2:
                print(f"ActionChains click also failed: {e2}")
                _safe_screenshot(driver, "seat_click_failed.png")
                return False

        print(f"Clicked seat: {seat_identifier}")

        # 5b. After clicking the seat, a popup/modal appears where Start and End times must be entered.
        # That popup could be a modal in DOM or a new window. Handle both.

        popup_handle_switched = False
        popup_window_handle = None
        # Short wait to detect a new window
        try:
            WebDriverWait(driver, 3).until(lambda d: len(d.window_handles) > 1)
            for handle in driver.window_handles:
                if handle != driver.current_window_handle:
                    popup_window_handle = handle
                    driver.switch_to.window(popup_window_handle)
                    popup_handle_switched = True
                    print("Switched to popup window for booking")
                    break
        except Exception:
            # No new window — treat as modal in same window
            print("No separate popup window detected; expecting an in-page modal/dialog")

        # Now locate the popup/modal container if present (role=dialog or aria-modal)
        modal = None
        try:
            modal = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[@role='dialog' or @aria-modal='true' or contains(@class,'modal') or contains(@class,'Dialog') or contains(@class,'popup')]")
                )
            )
            print("Found modal/dialog container for booking popup")
        except Exception:
            print("Modal container not detected by role/class heuristics; will attempt to find inputs globally")

        # Try to find start/end inputs within modal (if found) else globally
        inputs = _find_time_input_within(driver, modal)

        if not inputs["start"] or not inputs["end"]:
            print("Could not find both start/end inputs using primary selectors. Will attempt broader search.")
            # Try global search
            inputs = _find_time_input_within(driver, None)

        if not inputs["start"] or not inputs["end"]:
            print("Failed to find start and/or end input fields in popup.")
            _safe_screenshot(driver, "time_inputs_not_found.png")
            # If we switched to a popup window, try switching back before returning
            try:
                if popup_handle_switched:
                    driver.close()
                    driver.switch_to.window(current_window)
            except Exception:
                pass
            return False

        # Fill times
        start_ok = _set_input_value(driver, inputs["start"], "08:00")
        end_ok = _set_input_value(driver, inputs["end"], "18:00")
        if not (start_ok and end_ok):
            print("Failed to set start/end values on inputs.")
            _safe_screenshot(driver, "set_time_failed.png")
            try:
                if popup_handle_switched:
                    driver.close()
                    driver.switch_to.window(current_window)
            except Exception:
                pass
            return False

        print("Filled Start=08:00 and End=18:00")

        # Click the "Book" button inside the modal or popup window
        book_clicked = False
        book_btn_candidates = []
        try:
            # Prefer searching inside modal if present
            if modal is not None:
                book_btn_candidates = modal.find_elements(By.XPATH, ".//button[contains(., 'Book') or contains(., 'BOOK') or contains(., 'Book now') or contains(., 'Book Now') or contains(., 'Confirm') or contains(., 'Book') ]")
            if not book_btn_candidates:
                book_btn_candidates = driver.find_elements(By.XPATH, "//button[contains(., 'Book') or contains(., 'BOOK') or contains(., 'Book now') or contains(., 'Confirm') or contains(., 'OK') or contains(., 'Ok') or contains(., 'Yes')]")
            for btn in book_btn_candidates:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", btn)
                        driver.execute_script("arguments[0].click();", btn)
                        book_clicked = True
                        print("Clicked Book/Confirm button in popup")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"Error while attempting to find/click Book button: {e}")

        if not book_clicked:
            print("Could not click the Book button in popup.")
            _safe_screenshot(driver, "book_button_not_clicked.png")
            try:
                if popup_handle_switched:
                    driver.close()
                    driver.switch_to.window(current_window)
            except Exception:
                pass
            return False

        # If the booking happened in a separate popup window, close it and switch back
        try:
            if popup_handle_switched:
                # give a moment for booking to process
                time.sleep(1)
                try:
                    driver.close()
                except Exception:
                    pass
                driver.switch_to.window(current_window)
        except Exception:
            pass

        # Wait for a success/confirmation indicator in the main app
        try:
            success_xpath = "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirmed') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'booked') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'success') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reservation')]"
            WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.XPATH, success_xpath)))
            print("Booking appears to be successful (found confirmation text).")
            _safe_screenshot(driver, "booking_success.png")
            return True
        except Exception:
            print("No obvious confirmation text found after clicking book. The booking might still have succeeded; check the UI.")
            _safe_screenshot(driver, "booking_no_confirmation.png")
            return False

    except Exception as e:
        print(f"Failed during login/booking flow: {e}")
        _safe_screenshot(driver, "layout_error.png")
        return False
