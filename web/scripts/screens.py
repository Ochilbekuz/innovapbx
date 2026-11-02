"""/design sahifasining to'liq skrinshotlari (light + dark). vite preview ni o'zi ko'taradi va o'chiradi."""
import subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "replica" / "design" / "screens"
PORT = 4317
URL = f"http://127.0.0.1:{PORT}/design"


def wait_up(url: str, timeout: float = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    sys.exit(f"preview ishga tushmadi: {url}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(["npx", "vite", "preview", "--port", str(PORT), "--strictPort", "--host", "127.0.0.1"], cwd=ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_up(URL)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for theme in ("light", "dark"):
                page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda m: m.type == "error" and errors.append(m.text))
                page.goto(f"{URL}?theme={theme}", wait_until="networkidle")
                page.wait_for_timeout(3000)
                target = OUT / f"design-{theme}.png"
                page.screenshot(path=str(target), full_page=True)
                print(theme, target, "xatolar:", errors or "yo'q")
                page.close()
            browser.close()
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
