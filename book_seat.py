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

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080") # Helps prevent elements being "hidden" off-screen

driver = webdriver.Chrome(options=options)
try:
    driver.get("YOUR_FLOWSCAPE_URL_HERE")

    # 2. Use Explicit Wait for the username field (Wait up to 20 seconds)
    wait = WebDriverWait(driver, 20)
    username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
    
    # 3. Proceed with login
    username_field.send_keys("YOUR_USERNAME")
    driver.find_element(By.ID, "password").send_keys("YOUR_PASSWORD")
    driver.find_element(By.ID, "login-button-id").click() # Update this ID if it's different

    print("Login successful!")

except Exception as e:
    print(f"Booking failed due to: {e}")
    # Optional: Save a screenshot to debug what the script "saw"
    driver.save_screenshot("error_screenshot.png")
finally:
    driver.quit()

