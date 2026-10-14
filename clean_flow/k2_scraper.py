"""
Automation ฝั่ง K-2 (Flow Clean ขั้น A1-A5)

Login ของ K-2 เป็น HTTP Basic Auth / Windows Authentication (popup ของเบราว์เซอร์เอง
ไม่ใช่ฟอร์มเว็บ) เลยส่ง credentials ผ่าน browser context (http_credentials) แทน
การ page.fill() ธรรมดา

Selector ของขั้นตอน "ไปหน้า Purchase Order Report / ตั้งวันที่ / Search / Export"
มาจาก record จริงด้วย record_k2.py แล้ว (2026-08-20) — ถ้าเว็บ K-2 เปลี่ยนหน้าตาในอนาคต
ให้รัน record_k2.py ใหม่อีกรอบเพื่ออัปเดต selector

ชื่อ iframe เป็น GUID สุ่มใหม่ทุก session (ยืนยันจาก 2 รอบ record ที่ได้ชื่อไม่เหมือนกัน)
เลยใช้ page.frame_locator("iframe").first แทนการอ้างชื่อ iframe ตรงๆ
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

import re
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import Frame, sync_playwright

import config
from date_utils import po_date_range

MONTH_FORMATS = ("%B %Y", "%b %Y")  # "August 2026" หรือ "Aug 2026"


def _parse_calendar_header(text: str) -> tuple[int, int] | None:
    text = text.strip()
    for fmt in MONTH_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.year, parsed.month
        except ValueError:
            continue
    return None


def navigate_calendar_to_month(frame: Frame, target: date, max_clicks: int = 36) -> None:
    """เลื่อนปฏิทิน (ที่เปิดอยู่) ไปให้ตรงเดือน/ปีเป้าหมาย โดยเทียบ header แล้วกด
    .top-calendar-right / .top-calendar-left จนกว่าจะตรง

    หมายเหตุ: header selector เดาจาก pattern ทั่วไป (ข้อความรูปแบบ "Month YYYY")
    ถ้าเว็บจริงแสดงหัวปฏิทินเป็นรูปแบบอื่น ต้องปรับ regex/format ในนี้เพิ่ม
    """
    header = frame.get_by_text(re.compile(r"^[A-Za-z]+\.?\s+\d{4}$")).first

    for _ in range(max_clicks):
        parsed = _parse_calendar_header(header.inner_text())
        if parsed is None:
            raise RuntimeError(
                f"อ่านหัวปฏิทินไม่ได้ (ข้อความ: {header.inner_text()!r}) "
                "— ต้องปรับ MONTH_FORMATS/regex ใน navigate_calendar_to_month ให้ตรงกับรูปแบบจริง"
            )
        current_year, current_month = parsed
        if (current_year, current_month) == (target.year, target.month):
            return
        if (current_year, current_month) < (target.year, target.month):
            frame.locator(".top-calendar-right").click()
        else:
            frame.locator(".top-calendar-left").click()

    raise RuntimeError(f"เลื่อนปฏิทินไปเดือน {target:%Y-%m} ไม่สำเร็จภายใน {max_clicks} ครั้ง")


def open_k2_report_page(p, start: date, end: date):
    """ทำตั้งแต่ login จนถึงกด Search แล้วเปิดหน้ารายงานสำเร็จ
    คืนค่า (browser, report_page) — เรียกใช้ทั้งจาก download_k2_po_report()
    และ record_k2_export.py (ตัว record selector เฉพาะขั้น export)
    """
    browser = p.chromium.launch(headless=False)  # headless=False ไว้ก่อนตอน debug
    context = browser.new_context(
        accept_downloads=True,
        http_credentials={"username": config.K2_USER, "password": config.K2_PASS},
    )
    page = context.new_page()

    # --- Login (HTTP Basic Auth ใช้ credentials จาก context ด้านบนอัตโนมัติ ไม่ต้อง fill ฟอร์ม) ---
    print("[K2] กำลังเปิดหน้า login ...")
    page.goto(config.K2_LOGIN_URL)
    page.wait_for_load_state("domcontentloaded")
    print("[K2] เข้าหน้า dashboard แล้ว")

    # --- ไปหน้า Purchase Order Report ---
    print("[K2] กำลังคลิก 'Purchase Order Report' ...")
    page.get_by_role("link", name="Purchase Order Report").click(timeout=15000)
    print("[K2] คลิกเมนูสำเร็จ กำลังหา iframe ฟอร์ม ...")

    # เนื้อหาฟอร์มทั้งหมดอยู่ใน iframe นี้ ชื่อ iframe สุ่มใหม่ทุก session และหน้านี้อาจมี
    # iframe มากกว่า 1 ตัว เลยค้นหาจาก "ตัวที่มีข้อความ PO Create Date อยู่ข้างใน" แทนการเดา index
    frame = None
    for _ in range(20):  # รอสูงสุด ~10 วิ (20 x 0.5s)
        for f in page.frames:
            if f == page.main_frame or f.is_detached():
                continue
            try:
                if f.get_by_text("PO Create Date").count() > 0:
                    frame = f
                    break
            except Exception:
                # เฟรมหลุด/reload พอดีตอนกำลังเช็ค ข้ามไปลองเฟรมถัดไป/รอบถัดไป
                continue
        if frame:
            break
        page.wait_for_timeout(500)
    if frame is None:
        raise RuntimeError("หา iframe ของฟอร์ม Purchase Order Report ไม่เจอ (ไม่มี iframe ไหนมีข้อความ 'PO Create Date')")

    # --- ตั้งค่าวันที่ From = วันที่ 1 ของเดือน ---
    print(f"[K2] กำลังตั้งวันที่ From = {start:%Y-%m-%d} ...")
    frame.get_by_role("link", name="...").first.click(timeout=15000)
    navigate_calendar_to_month(frame, start)
    frame.get_by_role("link", name=f"{start.day:02d}", exact=True).first.click()

    # --- ตั้งค่าวันที่ To = Day-1 ---
    print(f"[K2] กำลังตั้งวันที่ To = {end:%Y-%m-%d} ...")
    frame.get_by_role("cell", name="Select a date").get_by_role("link").click(timeout=15000)
    navigate_calendar_to_month(frame, end)
    # ปฏิทินโชว์วันของเดือนก่อน/หลังจางๆ ด้วย (class "not-of-current-month") บางเดือนเลข
    # วันชนกับเดือนปัจจุบันพอดี (เจอจริง: 27 ก.ค. กับ 27 ส.ค.) get_by_role หา name ตรงกัน
    # 2 element เลย strict mode violation — ต้องเลือกอันแรก (.first) เหมือนบล็อก From ด้านบน
    frame.get_by_role("link", name=f"{end.day:02d}", exact=True).first.click()

    # --- กด Search -> เปิดหน้ารายงานใน popup ---
    print("[K2] กำลังกด Search ...")
    with page.expect_popup() as report_popup_info:
        frame.get_by_role("link", name="Search").click(timeout=15000)
    report_page = report_popup_info.value
    report_page.wait_for_load_state("domcontentloaded")
    print("[K2] หน้ารายงานเปิดแล้ว")

    return browser, report_page


# ยืนยันจากผู้ใช้ (2026-08-28): รายงาน Purchase Order เป็น SSRS report ตรงๆ
# (ReportServer/Pages/ReportViewer.aspx) รับพารามิเตอร์วันที่ผ่าน URL ได้เลย
# (PODateFromInput/PODateToInput แบบ YYYY-MM-DD, ปีเป็น ค.ศ. ไม่ใช่ พ.ศ.) — เข้าตรงๆ ด้วย
# Basic Auth เดียวกับที่ใช้ทั้งเว็บโดยไม่ต้อง login ผ่านเมนูเลย และเติม rs:Format=EXCELOPENXML
# ต่อท้ายให้ดาวน์โหลด Excel ทันทีโดยไม่ต้องคลิกปุ่ม Save ผ่าน UI เลย — เชื่อถือได้กว่าและเร็วกว่า
# การคลิกผ่านปฏิทิน/เมนู/ปุ่ม Export แบบเดิมมาก (ของเดิมเจอปัญหาค้นหาได้ 0 แถวอยู่บ่อยครั้ง โดยที่
# ไม่มี error ให้เห็นเลย เพราะ UI ค้นหาจริงบางทีก็เงียบๆ ไม่ error แต่ได้ผลลัพธ์ว่างแทน)
# ตั้งใน .env (K2_PO_REPORT_URL) เป็น URL ReportViewer เต็ม ที่มีพารามิเตอร์
# PODateFromInput={start:%Y-%m-%d}&PODateToInput={end:%Y-%m-%d}&rs:Format=EXCELOPENXML
_K2_PO_REPORT_URL = config.K2_PO_REPORT_URL or ""


def download_k2_po_report() -> Path:
    start, end = po_date_range()
    url = _K2_PO_REPORT_URL.format(start=start, end=end)

    print(f"[K2] กำลังเปิดรายงาน Purchase Order ตรงๆ ผ่าน URL (วันที่ {start:%Y-%m-%d} ถึง "
          f"{end:%Y-%m-%d}) ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            accept_downloads=True,
            http_credentials={"username": config.K2_USER, "password": config.K2_PASS},
        )
        page = context.new_page()

        # การเข้า URL ที่ต่อท้ายด้วย rs:Format=EXCELOPENXML จะทำให้เบราว์เซอร์เริ่มดาวน์โหลด
        # ไฟล์ทันทีระหว่างโหลดหน้า ทำให้ page.goto() เองโยน exception "Download is starting"
        # ออกมา (พฤติกรรมปกติของ Playwright ไม่ใช่ error จริง) — ต้องดัก exception นี้ทิ้งแล้ว
        # อ่าน download จาก expect_download context แทน
        with page.expect_download(timeout=30000) as download_info:
            try:
                page.goto(url, timeout=30000)
            except Exception:
                pass
        download = download_info.value
        print("[K2] ดาวน์โหลดไฟล์สำเร็จ")

        dest = config.DOWNLOAD_DIR / f"k2_po_report_{start:%Y%m%d}_{end:%Y%m%d}.xlsx"
        download.save_as(dest)

        browser.close()
        return dest


if __name__ == "__main__":
    path = download_k2_po_report()
    print(f"ดาวน์โหลดไฟล์ K-2 เสร็จ: {path}")
