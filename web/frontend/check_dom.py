"""Diagnostic DOM complet : structure du root, présence des sections."""
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        pg = await b.new_page(viewport={"width": 1400, "height": 2400})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        await pg.goto("http://localhost:5173", timeout=45000, wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        info = await pg.evaluate("""() => {
          const q = s => document.querySelectorAll(s).length;
          return {
            sections: q('section'),
            provider_inputs: q('#pf-base, #pf-key, #pf-model'),
            snapshots_li: q('ul div li') + Array.from(document.querySelectorAll('li')).filter(li => li.textContent.includes('.json')).length,
            all_text_len: document.body.innerText.length,
            has_provider_label: document.body.innerText.includes('provider IA'),
            has_03: document.body.innerText.includes('snapshots terrain'),
            last_text: document.body.innerText.slice(-300),
          }
        }""")
        print(json.dumps({"dom": info, "pageerrors": errs[:4]}, indent=1, ensure_ascii=False))
        await b.close()

asyncio.run(main())
