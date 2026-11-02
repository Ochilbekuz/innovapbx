"""M2a proof skrinshotlari: /settings/feature-codes, /conference, /blacklist (uz) va
/blacklist (ru), ext drawerʼning «Qoʻngʻiroqlar» boʻlimi. Fake klient (demo ma'lumot) bilan."""
import subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "replica" / "clone-screens"
PORT = 4319
URL = f"http://127.0.0.1:{PORT}"


def wait_up(url: str, timeout: float = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    sys.exit(f"dev server ishga tushmadi: {url}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(
        ["npx", "vite", "--port", str(PORT), "--strictPort", "--host", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_up(URL)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page.route("**/api/v1/**", lambda route: route.abort())
            page.goto(f"{URL}/setup", wait_until="networkidle")
            page.get_by_label("Login").fill("admin")
            page.get_by_label("Toʻliq ism").fill("Admin")
            page.get_by_label("Parol").fill("Admin12345!")
            page.get_by_role("button", name="Davom etish").click()
            page.get_by_role("button", name="PBXʼni ishga tushirish").click()
            page.wait_for_url("**/dashboard", timeout=10000)

            page.locator('a[href="/settings/feature-codes"]').click()
            page.wait_for_url("**/settings/feature-codes", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "m2a-featurecodes.png"), full_page=True)

            page.locator('a[href="/conference"]').click()
            page.wait_for_url("**/conference", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "m2a-conferences.png"), full_page=True)

            page.locator('a[href="/blacklist"]').click()
            page.wait_for_url("**/blacklist", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "m2a-blacklist.png"), full_page=True)

            page.locator('a[href="/extensions"]').click()
            page.wait_for_url("**/extensions", timeout=10000)
            page.wait_for_load_state("networkidle")
            row = page.locator("table tbody tr").first
            row.locator('button[aria-label$="tahrirlash"]').wait_for(state="visible", timeout=10000)
            row.dblclick()
            dialog = page.get_by_role("dialog")
            dialog.wait_for(state="visible", timeout=5000)
            dialog.get_by_text("Qoʻngʻiroqlar", exact=True).scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "m2a-ext-calls.png"), full_page=True)
            page.keyboard.press("Escape")

            page.get_by_role("radio", name="RU").click()
            page.wait_for_timeout(400)
            page.locator('a[href="/blacklist"]').click()
            page.wait_for_url("**/blacklist", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "m2a-blacklist-ru.png"), full_page=True)

            browser.close()
        print("tayyor:", OUT)
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
