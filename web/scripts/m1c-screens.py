"""M1c proof skrinshotlari: /voicemail (uz) va /sip TLS kartasi (ru). Fake klient (demo ma'lumot) bilan."""
import subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "replica" / "clone-screens"
PORT = 4318
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
            # `src/lib/i18n.ts`dagi `persistLanguage()` VITE_API tanlovidan qat'i nazar har doim
            # `realClient.updateMe(...)` chaqiradi (mavjud, biz tegmaydigan xato) — bu yerda haqiqiy
            # `/api/v1/auth/*`ga chiqib 401 oladi va umumiy sessiyani (fake bo'lsa ham) tozalaydi.
            # Shu sababli haqiqiy backend so'rovlarini butunlay bloklaymiz — fake klient hech qachon
            # tarmoqqa chiqmaydi, shuning uchun bu xavfsiz.
            page.route("**/api/v1/**", lambda route: route.abort())
            # Yangi fake klient har doim "sozlash kerak" holatida boshlanadi —
            # /login emas, /setup ochiladi. Sehrgarni toʻldiramiz: muvaffaqiyatli
            # submit darhol sessiyani ochadi va /dashboard'ga oʻtkazadi (login shart emas).
            page.goto(f"{URL}/setup", wait_until="networkidle")
            page.get_by_label("Login").fill("admin")
            page.get_by_label("Toʻliq ism").fill("Admin")
            page.get_by_label("Parol").fill("Admin12345!")
            page.get_by_role("button", name="Davom etish").click()
            page.get_by_role("button", name="PBXʼni ishga tushirish").click()
            page.wait_for_url("**/dashboard", timeout=10000)

            # Eslatma: `page.goto` bu yerda toʻliq sahifa reload qiladi — bu esa
            # xotiradagi fake klientni (va u bilan "setup kerak" holatini) qaytadan
            # boshidan boshlaydi. Shu sababli keyingi sahifalarga SPA ichidagi
            # navigatsiya (sidebar havolasini bosish) orqali oʻtamiz.
            page.locator('a[href="/voicemail"]').click()
            page.wait_for_url("**/voicemail", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / "m1c-voicemail.png"), full_page=True)

            page.get_by_role("radio", name="RU").click()
            page.wait_for_timeout(500)
            page.locator('a[href="/settings/sip"]').click()
            page.wait_for_url("**/settings/sip", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            tls_section = page.get_by_text("TLS-сертификат").locator("xpath=ancestor::section[1]")
            tls_section.scroll_into_view_if_needed()
            page.screenshot(path=str(OUT / "m1c-sip-tls-ru.png"), full_page=True)

            browser.close()
        print("tayyor:", OUT / "m1c-voicemail.png", OUT / "m1c-sip-tls-ru.png")
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
