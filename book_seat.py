from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time

def login_flowscape(driver, email, password):
   try:
        # --- PUT YOUR URL HERE ---
        target_url = "https://wsp.flowscape.se/webapp/" 
        driver.get(target_url)
        wait = WebDriverWait(driver, 20)
        
        # 1. Click "Sign in with Microsoft"
        # Note: Replace 'button-id' with the actual ID or text of that button
        microsoft_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Microsoft')]")))
        microsoft_btn.click()
    except Exception as e:
        print(f"Booking failed: {e}")

    # Credentials stored as GitHub Action Secrets
    USERNAME = os.getenv("FLOWSCAPE_USER")
    PASSWORD = os.getenv("FLOWSCAPE_PASS")


    # 2. Enter Microsoft Email
    email_field = wait.until(EC.presence_of_element_located((By.NAME, "loginfmt")))
    email_field.send_keys(USERNAME)
    driver.find_element(By.ID, "idSIButton9").click() # The "Next" button

    # 3. Enter Microsoft Password
    # Sometimes there is a delay while it redirects to your company's login page
    password_field = wait.until(EC.element_to_be_clickable((By.NAME, "passwd")))
    password_field.send_keys(PASSWORD)
    
    # 4. Click "Sign in"
    wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()

    # 5. Handle "Stay signed in?" prompt (Standard in 2025)
    try:
        stay_signed_in_btn = wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9")))
        stay_signed_in_btn.click()
    except:
        pass # This screen doesn't always appearfrom selenium import webdriver
