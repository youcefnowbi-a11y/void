"""Charge http://localhost:5173 dans Chromium headless et capture console/erreurs."""
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        pg = await b.new_page(viewport={"width": 1400, "height": 900})
        errors, logs = [], []
        pg.on("console", lambda m: logs.append(f"[{m.type}] {m.text[:200]}"))
        pg.on("pageerror", lambda e: errors.append(str(e)[:400]))
        try:
            await pg.goto("http://localhost:5173", timeout=45000, wait_until="networkidle")
        except Exception as ex:
            print("goto:", str(ex)[:150])
        await pg.wait_for_timeout(3000)
        # contenu renderé ?
        txt = await pg.evaluate("() => document.body ? document.body.innerText.slice(0, 1200) : ''")
        has_canvas = await pg.evaluate("() => !!document.querySelector('canvas')")
        root_children = await pg.evaluate("() => document.getElementById('root')?.children.length || 0")
        title = await pg.title()
        print(json.dumps({
            "title": title,
            "root_children": root_children,
            "canvas_3d_present": has_canvas,
            "rendered_text": txt.replace("\n", " | ")[:300],
            "console_errors": errors[:8],
            "console_log_tail": logs[-12:],
        }, indent=1, ensure_ascii=False))
        await b.close()

asyncio.run(main())
