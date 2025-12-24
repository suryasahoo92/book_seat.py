from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import os
import time

# Credentials stored as GitHub Action Secrets
USERNAME = os.getenv("FLOWSCAPE_USER")
PASSWORD = os.getenv("FLOWSCAPE_PASS")

# Seat ID or seat name (update as per your Flowscape UI)
SEAT_NAME = "M2-6F-275"

# Calculate date 4 days from today
booking_date = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=opts)
    return driver

def log_driver_info(driver):
    try:
        caps = driver.capabilities
        print("=== Driver Capabilities ===")
        print(caps)
    except Exception:
        print("Could not read capabilities")
        pass

def main():
    try:
        driver = make_driver()
        log_driver_info(driver)

        # ... your booking steps ...
        # e.g., driver.get(LOGIN_URL); driver.find_element(...).click()

    except Exception as e:
        print("=== PYTHON EXCEPTION ===")
        print(type(e).__name__, str(e))
        print("=== TRACEBACK ===")
        traceback.print_exc()
    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main()


