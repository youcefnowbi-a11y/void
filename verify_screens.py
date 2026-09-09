from playwright.sync_api import sync_playwright
import time
import os

artifact_dir = r"C:\Users\youcef cheriet\.gemini\antigravity\brain\4e7eee61-778d-4005-916a-ab2cfa2f345f"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://localhost:5173')
    page.wait_for_load_state('networkidle')
    time.sleep(1.5)
    
    # Click the terminal button in header
    for b in page.locator('button').all():
        title = b.get_attribute('title') or ''
        if 'console' in title.lower():
            b.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(artifact_dir, 'redacted_cyber_console.png'))
            print("Captured redacted_cyber_console.png")
            break
            
    browser.close()
