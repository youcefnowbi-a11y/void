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
    
    # 1. Capture default home view
    page.screenshot(path=os.path.join(artifact_dir, 'final_dark_mode_home.png'))
    print("Saved final_dark_mode_home.png")
    
    # 2. Open Console
    term_btn = page.locator('button:has-text(">_")')
    if term_btn.count() > 0:
        term_btn.first.click()
        time.sleep(1)
        page.screenshot(path=os.path.join(artifact_dir, 'final_dark_mode_console.png'))
        print("Saved final_dark_mode_console.png")
        
    # 3. Click Chaîne tab
    for b in page.locator('button').all():
        txt = b.inner_text().strip().lower()
        if 'chaîne' in txt or 'chaine' in txt:
            b.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(artifact_dir, 'final_dark_mode_chain.png'))
            print("Saved final_dark_mode_chain.png")
            break

    browser.close()
print("Done!")
