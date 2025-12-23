from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
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

options = Options()
options.add_argument("--headless") # Required for GitHub Actions
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options) 
try:
    # Go to Flowscape login page
    driver.get("https://central-prod.flowscape.se/login/realm")

    time.sleep(2)

    # Enter username
    driver.find_element(By.ID, "username").send_keys(USERNAME)

    # Enter password
    driver.find_element(By.ID, "password").send_keys(PASSWORD)

    # Login button
    driver.find_element(By.ID, "login").click()
    time.sleep(4)

    # Navigate to workspace booking page
    driver.get("https://wsp.flowscape.se/webapp/")
    time.sleep(3)

    # Pick the seat from list
    driver.find_element(By.XPATH, f"//div[contains(text(), '{SEAT_NAME}')]").click()
    time.sleep(2)

    # Select the date 4 days later
    driver.find_element(By.XPATH, f"//button[@data-date='{booking_date}']").click()
    time.sleep(2)

    # Confirm booking
    driver.find_element(By.XPATH, "//button[contains(text(), 'Book')]").click()

    print("Seat booked successfully for:", booking_date)

except Exception as e:
    print("Booking failed due to:", e)

finally:
    driver.quit()

