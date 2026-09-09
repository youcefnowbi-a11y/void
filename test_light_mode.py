from playwright.sync_api import sync_playwright
import time
import os

artifact_dir = r"C:\Users\youcef cheriet\.gemini\antigravity\brain\4e7eee61-778d-4005-916a-ab2cfa2f345f"
os.makedirs(artifact_dir, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://localhost:5173')
    page.wait_for_load_state('networkidle')
    time.sleep(1.5)
    
    # 1. Dark Mode Console
    # Open workbench by clicking the '>_' terminal button
    term_btn = page.locator('button:has-text(">_")')
    if term_btn.count() > 0:
        term_btn.first.click()
        time.sleep(1)
        page.screenshot(path=os.path.join(artifact_dir, 'dark_mode_console_after.png'))
        print("Captured dark_mode_console_after.png")
        
    # 2. Switch to Light Mode (Aurore)
    # The theme toggle button is in header
    page.evaluate("document.documentElement.setAttribute('data-theme', 'aurore')")
    time.sleep(1)
    page.screenshot(path=os.path.join(artifact_dir, 'light_mode_console_after.png'))
    print("Captured light_mode_console_after.png")
    
    # 3. Light Mode home view (close console)
    close_btn = page.locator('button[title*="Refermer"], button[title*="fermer"]')
    if close_btn.count() > 0:
        close_btn.first.click()
        time.sleep(0.5)
    page.screenshot(path=os.path.join(artifact_dir, 'light_mode_home_after.png'))
    print("Captured light_mode_home_after.png")

    browser.close()
print("All verifications complete!")
