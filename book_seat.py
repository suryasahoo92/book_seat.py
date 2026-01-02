from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time
import traceback


def _safe_screenshot(driver, name):
    try:
        driver.save_screenshot(name)
        print(f"Saved screenshot: {name}")
    except Exception:
        pass


def _write_file(name, content):
    try:
        with open(name, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Wrote file: {name}")
    except Exception as e:
        print(f"Failed writing file {name}: {e}")


def _set_input_value(driver, element, value):
    """
    Robustly set value for an input element: try clear/send_keys, fall back to JS value set + events, then blur.
    """
    try:
        element.clear()
    except Exception:
        pass
    try:
        element.send_keys(value)
        # some inputs require Enter to commit
        try:
            element.send_keys("\n")
        except Exception:
            pass
        return True
    except Exception:
        pass

    # JS fallback: set value and dispatch input/change/blur events
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


def _dump_modal_state(driver, modal, prefix="debug"):
    """
    Save modal outerHTML, page source, list of candidate inputs/buttons and their attributes.
    """
    try:
        # full page after seat click
        try:
            page_source = driver.page_source
            _write_file(f"{prefix}_page_after_click.html", page_source)
        except Exception:
            pass

        # outerHTML of modal if present
        if modal is not None:
            try:
                outer = driver.execute_script("return arguments[0].outerHTML;", modal)
                _write_file(f"{prefix}_modal.html", outer)
            except Exception:
                pass

        # list candidate inputs/buttons in modal or globally
        lines = []
        lines.append(f"Window handles: {driver.window_handles}\nCurrent URL: {driver.current_url}\n")
        try:
            # find inputs and buttons near modal
            elems = []
            if modal is not None:
                elems = modal.find_elements(By.XPATH, ".//input | .//button | .//div | .//span | .//label")
            else:
                elems = driver.find_elements(By.XPATH, "//input | //button | //div | //span | //label")

            # limit amount
            for i, e in enumerate(elems[:400]):
                try:
                    tag = e.tag_name
                    text = e.text or ""
                    aria = e.get_attribute("aria-label") or ""
                    role = e.get_attribute("role") or ""
                    cls = e.get_attribute("class") or ""
                    idattr = e.get_attribute("id") or ""
                    name = e.get_attribute("name") or ""
                    placeholder = e.get_attribute("placeholder") or ""
                    value = e.get_attribute("value") or ""
                    displayed = e.is_displayed()
                    enabled = e.is_enabled()
                    outer = ""
                    try:
                        outer = driver.execute_script("return arguments[0].outerHTML;", e)
                    except Exception:
                        pass
                    lines.append(
                        f"#{i} tag={tag} displayed={displayed} enabled={enabled} text={text!r} aria={aria!r} role={role!r} id={idattr!r} name={name!r} class={cls!r} placeholder={placeholder!r} value={value!r}\nouterHTML={outer[:4000]}\n---\n"
                    )
                except Exception:
                    continue
        except Exception as e:
            lines.append("Failed enumerating elements: " + str(e) + "\n" + traceback.format_exc())

        _write_file(f"{prefix}_elements.txt", "\n".join(lines))
    except Exception as e:
        print("Error during modal dump: ", e)


def _find_time_input_within(driver, container):
    """
    Return dict with 'start' and 'end' input elements if found, else None.
    Tries several common selectors (aria-label, placeholder, label text, input[type=time]).
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

    for xp in start_xpaths:
        try:
            elems = container.find_elements(By.XPATH, xp) if container is not None else driver.find_elements(By.XPATH, xp)
            if elems:
                result["start"] = elems[0]
                break
        except Exception:
            continue

    for xp in end_xpaths:
        try:
            elems = container.find_elements(By.XPATH, xp) if container is not None else driver.find_elements(By.XPATH, xp)
            if elems:
                result["end"] = elems[0]
                break
        except Exception:
            continue

    # fallback: pick first two inputs[type=time]
    try:
        if (not result["start"] or not result["end"]) and container is not None:
            time_inputs = container.find_elements(By.XPATH, ".//input[@type='time']")
            if len(time_inputs) >= 2:
                if not result["start"]:
                    result["start"] = time_inputs[0]
                if not result["end"]:
                    result["end"] = time_inputs[1]
    except Exception:
        pass

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


def login_flowscape(driver, email=None, password=None, debug=False):
    """
    Logs into Flowscape via Microsoft and attempts to book a seat.
    If email/password are not provided, falls back to FLOWSCAPE_USER and FLOWSCAPE_PASS environment variables.
    Set debug=True to produce detailed dumps (modal.html, page_after_click.html, elements.txt and screenshots).
    Returns True on success, False on failure.
    """
    try:
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
            print("No extra window opened for Microsoft login")

    except Exception as e:
        print(f"Booking failed while opening page or clicking Microsoft sign-in: {e}")
        _safe_screenshot(driver, "layout_error_open.png")
        return False

    USERNAME = email or os.getenv("FLOWSCAPE_USER")
    PASSWORD = password or os.getenv("FLOWSCAPE_PASS")

    try:
        # Microsoft sign-in
        email_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "loginfmt")))
        email_field.clear()
        email_field.send_keys(USERNAME)
        driver.find_element(By.ID, "idSIButton9").click()

        password_field = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.NAME, "passwd")))
        password_field.clear()
        password_field.send_keys(PASSWORD)
        WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()

        # optional MS prompts
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

        # switch back to main flowscape window if possible
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

        # select seat
        seat_identifier = "ID-6F-277 (UK)"
        xpath_exact = f"//*[@aria-label=\"{seat_identifier}\" or @title=\"{seat_identifier}\"]"
        xpath_contains = f"//*[contains(@aria-label, \"{seat_identifier.split()[0]}\") or contains(@title, \"{seat_identifier.split()[0]}\")]"

        my_seat = None
        try:
            my_seat = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath_exact)))
            print(f"Found seat with exact match: {seat_identifier}")
        except Exception:
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
        if debug:
            _safe_screenshot(driver, "after_seat_click.png")
            time.sleep(0.5)

        # detect popup/modal or new window
        popup_handle_switched = False
        popup_window_handle = None
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
            print("No separate popup window detected; expecting an in-page modal/dialog")

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

        # If modal contains an iframe, switch into it
        iframe_switched = False
        try:
            if modal is not None:
                iframes = modal.find_elements(By.TAG_NAME, "iframe")
                if iframes:
                    # switch to first iframe
                    driver.switch_to.frame(iframes[0])
                    iframe_switched = True
                    print("Switched into iframe inside modal")
        except Exception:
            pass

        # Dump debug info if requested
        if debug:
            _dump_modal_state(driver, modal if not iframe_switched else None, prefix="debug")

        # find start/end inputs
        inputs = _find_time_input_within(driver, modal if not iframe_switched else None)
        if not inputs["start"] or not inputs["end"]:
            # try global search (and also try when inside iframe we switched)
            inputs = _find_time_input_within(driver, None)

        if not inputs["start"] or not inputs["end"]:
            print("Failed to find start and/or end input fields in popup.")
            _safe_screenshot(driver, "time_inputs_not_found.png")
            # restore frames / windows
            try:
                if iframe_switched:
                    driver.switch_to.default_content()
                if popup_handle_switched:
                    driver.close()
                    driver.switch_to.window(current_window)
            except Exception:
                pass
            return False

        # set start/end values
        start_ok = _set_input_value(driver, inputs["start"], "08:00")
        end_ok = _set_input_value(driver, inputs["end"], "18:00")
        if not (start_ok and end_ok):
            print("Failed to set start/end values on inputs.")
            _safe_screenshot(driver, "set_time_failed.png")
            try:
                if iframe_switched:
                    driver.switch_to.default_content()
                if popup_handle_switched:
                    driver.close()
                    driver.switch_to.window(current_window)
            except Exception:
                pass
            return False

        print("Filled Start=08:00 and End=18:00")
        if debug:
            _safe_screenshot(driver, "after_setting_times.png")

        # find and click Book button (prefer inside modal)
        book_clicked = False
        try:
            book_btn_candidates = []
            if modal is not None and not iframe_switched:
                book_btn_candidates = modal.find_elements(By.XPATH, ".//button[contains(., 'Book') or contains(., 'BOOK') or contains(., 'Book now') or contains(., 'Confirm') or contains(., 'OK') or contains(., 'Ok') or contains(., 'Yes')]")
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
                if iframe_switched:
                    driver.switch_to.default_content()
                if popup_handle_switched:
                    driver.close()
                    driver.switch_to.window(current_window)
            except Exception:
                pass
            return False

        # restore iframe/window
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
            pass

        # wait for booking confirmation
        try:
            success_xpath = "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirmed') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'booked') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'success') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reservation')]"
            WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.XPATH, success_xpath)))
            print("Booking appears to be successful (found confirmation text).")
            _safe_screenshot(driver, "booking_success.png")
            return True
        except Exception:
            print("No obvious confirmation text found after clicking book. Check debug files for details.")
            _safe_screenshot(driver, "booking_no_confirmation.png")
            if debug:
                # final dump to help debugging
                _dump_modal_state(driver, None, prefix="debug_final")
            return False

    except Exception as e:
        print(f"Failed during login/booking flow: {e}\n{traceback.format_exc()}")
        _safe_screenshot(driver, "layout_error.png")
        return False
