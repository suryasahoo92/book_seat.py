from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time

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
        wait = WebDriverWait(driver, 20)

        # 1. Click "Sign in with Microsoft"
        microsoft_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Microsoft')]"))
        )
        microsoft_btn.click()
    except Exception as e:
        print(f"Booking failed while opening page or clicking Microsoft sign-in: {e}")
        return False

    # Credentials stored as GitHub Action Secrets or passed as args
    USERNAME = email or os.getenv("FLOWSCAPE_USER")
    PASSWORD = password or os.getenv("FLOWSCAPE_PASS")

    try:
        # 2. Enter Microsoft Email
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "loginfmt")))
        email_field.send_keys(USERNAME)
        driver.find_element(By.ID, "idSIButton9").click()  # The "Next" button

        # 3. Enter Microsoft Password
        # Sometimes there is a delay while it redirects to your company's login page
        password_field = wait.until(EC.element_to_be_clickable((By.NAME, "passwd")))
        password_field.send_keys(PASSWORD)

        # 4. Click "Sign in"
        wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()

        # 5. Handle seat selection and confirmation
        seat_identifier = "ID-6F-277 (UK)"

        # Locate the seat using a partial attribute match (most reliable)
        my_seat = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//*[@aria-label='{seat_identifier}' or @title='{seat_identifier}']")
            )
        )

        # Click the seat (even if it's an SVG or Canvas element)
        driver.execute_script("arguments[0].click();", my_seat)  # Bypasses common 'obscured' errors
        print(f"Successfully clicked {seat_identifier}")

        # Confirm the booking
        confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Confirm')]")))
        confirm_btn.click()

        return True

    except Exception as e:
        print(f"Failed during login/booking flow: {e}")
        try:
            driver.save_screenshot("layout_error.png")
        except Exception:
            pass
        return False
