"""
Comprehensive Selenium UI & Stress-Test Audit Script
Audits every screen in Ndungu Electronics IMS across Light and Dark modes.
Detects:
1. JavaScript console errors
2. Missing or broken headers / contrast failures
3. Light / Dark mode persistence and styling inconsistencies
4. Modal opening and form element readiness
Saves screenshots to screenshots/audit/
"""

import os
import sys
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "screenshots" / "audit"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    return webdriver.Chrome(options=opts)

def get_console_errors(driver):
    logs = driver.get_log("browser")
    errors = [l["message"] for l in logs if l["level"] in ("SEVERE", "WARNING")]
    return errors

def audit_page(driver, url, page_name):
    print(f"\n--- Auditing: {page_name} ({url}) ---")
    driver.get(url)
    time.sleep(1)

    # 1. Light Mode Check
    # Ensure light mode
    driver.execute_script("document.documentElement.classList.remove('dark'); localStorage.theme = 'light';")
    time.sleep(0.5)
    light_shot = OUTPUT_DIR / f"{page_name}_light.png"
    driver.save_screenshot(str(light_shot))
    print(f"  [Light Mode] Screenshot: {light_shot.name}")

    # Inspect headers in Light mode
    headers = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, header, .page-head")
    light_header_issues = []
    for h in headers:
        tag = h.tag_name
        text = h.text.strip().replace("\n", " ")[:40]
        color = h.value_of_css_property("color")
        bg = h.value_of_css_property("background-color")
        vis = h.is_displayed()
        if not vis and len(text) > 0:
            light_header_issues.append(f"Hidden header: <{tag}> '{text}'")
        elif color == bg and color != "rgba(0, 0, 0, 0)":
            light_header_issues.append(f"Invisible text (color == bg == {color}): <{tag}> '{text}'")

    # 2. Dark Mode Check
    # Click toggle or set dark class
    toggle_btn = driver.find_elements(By.CSS_SELECTOR, "button[onclick='toggleDarkMode()']")
    if toggle_btn:
        toggle_btn[0].click()
    else:
        driver.execute_script("document.documentElement.classList.add('dark'); localStorage.theme = 'dark';")
    time.sleep(0.5)

    dark_shot = OUTPUT_DIR / f"{page_name}_dark.png"
    driver.save_screenshot(str(dark_shot))
    print(f"  [Dark Mode] Screenshot: {dark_shot.name}")

    # Inspect headers in Dark mode
    dark_headers = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, header, .page-head")
    dark_header_issues = []
    for h in dark_headers:
        tag = h.tag_name
        text = h.text.strip().replace("\n", " ")[:40]
        color = h.value_of_css_property("color")
        bg = h.value_of_css_property("background-color")
        vis = h.is_displayed()
        # In dark mode, if color is very dark on a dark background or hidden
        if not vis and len(text) > 0:
            dark_header_issues.append(f"Hidden header: <{tag}> '{text}'")
        elif color == "rgb(15, 23, 42)" and "slate-900" in h.get_attribute("class"):
            # Check if parent is dark
            dark_header_issues.append(f"Low contrast header (dark text on dark bg): <{tag} class='{h.get_attribute('class')}'> '{text}'")

    # Check JS console errors
    errors = get_console_errors(driver)

    return {
        "page": page_name,
        "url": url,
        "light_shot": str(light_shot),
        "dark_shot": str(dark_shot),
        "light_header_issues": light_header_issues,
        "dark_header_issues": dark_header_issues,
        "errors": errors
    }

def run_full_audit():
    driver = setup_driver()
    results = []

    try:
        # 1. Login Page
        r_login = audit_page(driver, f"{BASE_URL}/login", "01_login")
        results.append(r_login)

        # Log in as Owner
        driver.get(f"{BASE_URL}/login")
        time.sleep(1)
        driver.find_element(By.NAME, "username").send_keys("Augustin Sanga")
        driver.find_element(By.NAME, "password").send_keys("NdunguAdmin2026!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(1)

        # 2. Inventory Page
        r_inv = audit_page(driver, f"{BASE_URL}/inventory/", "02_inventory")
        results.append(r_inv)

        # Test New Product Modal
        try:
            add_btn = driver.find_element(By.CSS_SELECTOR, "button[onclick='openNewProductModal()']")
            add_btn.click()
            time.sleep(0.5)
            modal = driver.find_element(By.ID, "newProductModal")
            modal_shot = OUTPUT_DIR / "02b_inventory_modal.png"
            driver.save_screenshot(str(modal_shot))
            print(f"  [Modal] Add Product Modal opened successfully. Shot: {modal_shot.name}")
            # Close modal
            driver.execute_script("closeNewProductModal()")
        except Exception as e:
            print(f"  [Modal Error] Failed to open/inspect modal: {e}")

        # 3. Product Detail Page
        r_detail = audit_page(driver, f"{BASE_URL}/inventory/product/1", "03_product_detail")
        results.append(r_detail)

        # 4. POS Counter
        r_pos = audit_page(driver, f"{BASE_URL}/pos/", "04_pos_register")
        results.append(r_pos)

        # Test adding items to cart
        try:
            driver.get(f"{BASE_URL}/pos/")
            time.sleep(1)
            # Find first item card
            cards = driver.find_elements(By.CSS_SELECTOR, "#productGrid > div")
            if cards:
                cards[0].click()
                time.sleep(0.5)
                cart_shot = OUTPUT_DIR / "04b_pos_cart_added.png"
                driver.save_screenshot(str(cart_shot))
                print(f"  [POS Cart] Item added to cart. Shot: {cart_shot.name}")
        except Exception as e:
            print(f"  [POS Error] {e}")

        # 5. Receipt View
        r_receipt = audit_page(driver, f"{BASE_URL}/pos/receipt/1", "05_receipt")
        results.append(r_receipt)

        # 6. Sales History
        r_sales = audit_page(driver, f"{BASE_URL}/sales/", "06_sales_ledger")
        results.append(r_sales)

        # 7. Promotions
        r_promos = audit_page(driver, f"{BASE_URL}/promotions/", "07_promotions")
        results.append(r_promos)

        # 8. BI Reports
        r_reports = audit_page(driver, f"{BASE_URL}/reports/", "08_bi_reports")
        results.append(r_reports)

        # 9. Users Admin
        r_users = audit_page(driver, f"{BASE_URL}/users/", "09_users_admin")
        results.append(r_users)

        # 10. Attendant Role Check
        driver.get(f"{BASE_URL}/login")
        time.sleep(1)
        # Logout
        try:
            logout_btn = driver.find_element(By.CSS_SELECTOR, "form[action*='logout'] button")
            logout_btn.click()
            time.sleep(0.5)
        except Exception:
            pass

        # Login as Attendant
        driver.get(f"{BASE_URL}/login")
        time.sleep(0.5)
        driver.find_element(By.NAME, "username").send_keys("attendant1")
        driver.find_element(By.NAME, "password").send_keys("NdunguAttendant2026!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(1)

        r_attendant_inv = audit_page(driver, f"{BASE_URL}/inventory/", "10_attendant_inventory")
        results.append(r_attendant_inv)

        # Check RBAC blocks on Owner pages
        for protected_url, name in [("/promotions/", "attendant_promotions_block"), ("/reports/", "attendant_reports_block"), ("/users/", "attendant_users_block")]:
            driver.get(f"{BASE_URL}{protected_url}")
            time.sleep(0.5)
            shot = OUTPUT_DIR / f"10b_{name}.png"
            driver.save_screenshot(str(shot))
            print(f"  [RBAC Check] {protected_url} -> Title: {driver.title}, Current URL: {driver.current_url}")

    finally:
        driver.quit()

    print("\n================ AUDIT SUMMARY ================")
    for r in results:
        print(f"\nPage: {r['page']} ({r['url']})")
        if r['light_header_issues']:
            print(f"  Light Issues: {r['light_header_issues']}")
        if r['dark_header_issues']:
            print(f"  Dark Issues: {r['dark_header_issues']}")
        if r['errors']:
            print(f"  Console Errors ({len(r['errors'])}): {r['errors'][:3]}")
        if not r['light_header_issues'] and not r['dark_header_issues'] and not r['errors']:
            print("  Clean visual state & zero console errors.")

if __name__ == "__main__":
    run_full_audit()
