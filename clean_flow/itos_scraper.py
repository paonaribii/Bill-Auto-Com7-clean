"""
Automation ฝั่ง ITOS (Flow Clean ขั้น B1-B6)

Selector การ login + เลือก Company/Head Office เอามาจาก
C:\\Users\\Comseven\\Desktop\\CRM\\qa_automation\\iloan.py (ทดสอบแล้วว่าใช้งานได้จริงกับ
เว็บนี้ในโปรเจกต์อื่น) ส่วนขั้นตอน "รายงาน > Export Report PO > ตั้งวันที่ > CREATE EXCEL"
ยังไม่เคย record มาก่อน — ถ้า selector ด้านล่างใช้ไม่ได้ ให้รัน record_itos.py แล้วเอา
โค้ดที่ record ได้มาแทนที่ส่วนนั้น

ฟอร์มวันที่ของ ITOS ใช้ปี พ.ศ. (เช่น 24/08/2569 = ค.ศ. 2026) ใช้ date_utils.format_thai_be()
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

import re
from datetime import date
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

import config
from date_utils import po_date_range, format_thai_be

LOGIN_URL = config.ITOS_LOGIN_URL
# ⚠️ เจอจริง 2026-09-16: ค่าเดิมพิมพ์ "จํากัด" (สระ ำ แบบแยกอักขระ นิคหิต ํ + า, U+0E4D+U+0E32)
# แต่ข้อความจริงบนปุ่มในเว็บเป็น "จำกัด" (สระ ำ ตัวเดียวสำเร็จรูป, U+0E33) — หน้าตาเหมือนกันเป๊ะ
# บนหน้าจอแต่เป็นคนละ Unicode code point กัน ทำให้ page.get_by_text(..., exact=True) หาปุ่มไม่เจอ
# เลยค้างรอตรงหน้า SelectCompany ไม่ไปต่อ (ไม่เกี่ยวกับเรื่องเปลี่ยนชื่อบริษัทเป็นยูฟันเลย)
COMPANY_NAME = "บริษัท ธันเดอร์ ฟิน ฟิน จำกัด"
BRANCH_NAME = "Head Office"

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]


def _parse_thai_calendar_header(text: str) -> tuple[int, int] | None:
    """แปลงหัวปฏิทิน เช่น 'สิงหาคม 2569' (เดือน+ปี พ.ศ.) -> (ปี ค.ศ., เดือน)"""
    parts = text.strip().split()
    if len(parts) != 2 or parts[0] not in THAI_MONTHS or not parts[1].isdigit():
        return None
    month = THAI_MONTHS.index(parts[0]) + 1
    year_ad = int(parts[1]) - 543
    return year_ad, month


def _select_calendar_date(page: Page, field_label: str, target: date, max_clicks: int = 36) -> None:
    """เปิด datepicker ของช่อง field_label (เช่น 'Date From') แล้วเลื่อน/คลิกวันที่เป้าหมาย
    เป็น bootstrap-datepicker ทั่วไป: header .datepicker-switch, ปุ่มเดือนก่อน/ถัดไป .prev/.next,
    วันที่เลือกได้จริง td.day (ไม่ใช่ .old/.new ซึ่งเป็นวันของเดือนก่อน/ถัดไปที่จางไว้)"""
    # ข้อความ "*Date From :" เป็นแค่ label ธรรมดา ไม่ได้ผูกกับ input ผ่าน for/id
    # (get_by_label หาไม่เจอ) เลยหา input ที่อยู่ถัดจากข้อความ label แทน
    field = page.get_by_text(field_label, exact=False).locator("xpath=following::input[1]")
    field.click(timeout=10000)

    header = page.locator(".datepicker-switch").first
    header.wait_for(state="visible", timeout=10000)

    for _ in range(max_clicks):
        parsed = _parse_thai_calendar_header(header.inner_text())
        if parsed is None:
            raise RuntimeError(f"อ่านหัวปฏิทินไม่ได้: {header.inner_text()!r}")
        current_year, current_month = parsed
        if (current_year, current_month) == (target.year, target.month):
            break
        if (current_year, current_month) < (target.year, target.month):
            page.locator(".next").first.click(timeout=5000)
        else:
            page.locator(".prev").first.click(timeout=5000)
        page.wait_for_timeout(200)
    else:
        raise RuntimeError(f"เลื่อนปฏิทินไปเดือน {target:%Y-%m} ไม่สำเร็จภายใน {max_clicks} ครั้ง")

    # has_text ทำ substring match (เช่น "1" จะชน "11","21" ด้วย) เลยใช้ regex anchor ให้ตรงเป๊ะ
    day_cell = page.locator(
        "td.day:not(.old):not(.new)", has_text=re.compile(rf"^{target.day}$")
    ).first
    day_cell.click(timeout=5000)


def _get_company_page(context, page: Page) -> Page:
    """รอหน้า SelectCompany — อาจเป็น page เดิมหรือ popup ใหม่ (เหมือน iloan.py)"""
    try:
        page.wait_for_url("**/SelectCompany**", timeout=8000)
        return page
    except Exception:
        pass

    try:
        with context.expect_page(timeout=5000) as new_page_info:
            pass
        new_page = new_page_info.value
        new_page.wait_for_load_state("domcontentloaded")
        return new_page
    except Exception:
        pass

    select_url = config.ITOS_SELECT_COMPANY_URL
    page.goto(select_url, wait_until="domcontentloaded")
    return page


def _fill_login_form(page: Page) -> None:
    """กรอก User/Pass + กด Login — แยกเป็นฟังก์ชันเพื่อเรียกซ้ำได้ (ทั้งตอน login ครั้งแรก
    และตอนเว็บเด้งกลับมาหน้า login เอง โดยไม่ต้องปิดแท็บ/เปิดเบราว์เซอร์ใหม่)"""
    page.get_by_role("textbox", name="User Login").fill(config.ITOS_USER)
    page.get_by_role("textbox", name="Password").fill(config.ITOS_PASS)
    page.get_by_role("button", name="Login").click()
    page.wait_for_timeout(2000)

    for _ in range(3):
        try:
            btn = page.get_by_role("button", name="ตกลง")
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            break


def open_itos_report_page(p, start, end):
    """Login -> เลือก Company/Head Office -> รายงาน > Export Report PO -> ตั้งวันที่
    คืนค่า (browser, page) พร้อมกดปุ่ม CREATE EXCEL ให้ผู้เรียกจัดการ expect_download เอง
    """
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    # --- Login ---
    print("[ITOS] กำลังเปิดหน้า login ...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    _fill_login_form(page)
    print("[ITOS] Login สำเร็จ กำลังจัดการ popup (ถ้ามี) ...")

    # --- เลือก Company -> Head Office ---
    # ⚠️ เจอจริง 2026-09-17: บางรอบหลังกรอก user/pass กด Login แล้ว เว็บดันเด้ง**กลับมาหน้า
    # login เอง** (ไม่ใช่ error แค่หาการ์ดบริษัทไม่เจอเฉยๆ) — ก่อนหน้านี้โค้ดจะปล่อยให้
    # exception หลุดออกไปให้ download_itos_export_report() จับแล้วปิดเบราว์เซอร์ทั้งอัน เปิด
    # ใหม่ทั้งชุด (login ใหม่หมด) ซึ่งเสียเวลาโดยไม่จำเป็น — ยืนยันจากผู้ใช้ให้แก้เป็น: ถ้าเจอ
    # ว่าเด้งกลับมาหน้า login (เช็คจากช่อง User Login โผล่มาอีกรอบ) ก็แค่กรอก user/pass ใหม่
    # แล้วกด Login ซ้ำใน**แท็บเดิม**เลย ไม่ต้องปิดแท็บ/เปิดเบราว์เซอร์ใหม่
    print("[ITOS] กำลังเลือก Company / Head Office ...")
    max_relogin_attempts = 3
    for relogin_attempt in range(1, max_relogin_attempts + 1):
        page = _get_company_page(context, page)

        # ⚠️ เจอจริง 2026-09-16: เดิมลอง li:nth-child(2) (การ์ดใบที่ 2) ก่อนเสมอ สมมติว่ามีการ์ด
        # อย่างน้อย 2 ใบ — แต่หน้า SelectCompany ตอนนี้มีการ์ดบริษัทใบเดียว ("nth-child(2)" เลยหาไม่
        # เจอทุกครั้ง) ต้องรอ timeout 20 วิเปล่าๆ ก่อนไปลอง fallback ทุกรอบที่รัน (ดูค้างแต่จริงๆ
        # กำลังรอ timeout ปกติ) — สลับลำดับเป็นลองคลิกด้วยชื่อบริษัทตรงๆ ก่อน (เร็วกว่า ตรงกับ
        # การ์ดที่มีอยู่จริงตอนนี้) แล้วค่อย fallback ไปคลิกการ์ดใบแรกแบบ generic ถ้าหาไม่เจอ
        try:
            page.get_by_text(COMPANY_NAME).click(timeout=15000)
            page.wait_for_timeout(1000)
            break
        except Exception:
            pass

        try:
            page.locator(".cardlist .details").first.click(timeout=20000)
            page.wait_for_timeout(1000)
            break
        except Exception:
            pass

        # หาการ์ดบริษัทไม่เจอทั้ง 2 ทาง — เช็คว่าเด้งกลับมาหน้า login หรือเปล่า
        try:
            back_at_login = page.get_by_role("textbox", name="User Login").is_visible(timeout=3000)
        except Exception:
            back_at_login = False

        if back_at_login and relogin_attempt < max_relogin_attempts:
            print(f"[ITOS]   เด้งกลับมาหน้า login (รอบ {relogin_attempt}/{max_relogin_attempts}) "
                  "— กรอก user/pass ใหม่ในแท็บเดิม ไม่ปิดแท็บ ...", flush=True)
            _fill_login_form(page)
            continue

        raise RuntimeError(
            f"หาการ์ดบริษัท '{COMPANY_NAME}' ไม่เจอ หลังลอง {relogin_attempt} รอบ "
            f"(เด้งกลับหน้า login: {back_at_login})"
        )

    try:
        page.get_by_text(BRANCH_NAME, exact=True).click(timeout=20000)
        page.wait_for_timeout(2000)
    except Exception:
        page.locator("div").filter(has_text=BRANCH_NAME).last.click(timeout=20000)
        page.wait_for_timeout(2000)

    # --- เลือกระบบงาน "ระบบงานสินเชื่อ" ก่อนถึงจะเห็นเมนู รายงาน ---
    print("[ITOS] กำลังกด 'ระบบงานสินเชื่อ' ...")
    page.get_by_text("ระบบงานสินเชื่อ", exact=True).click(timeout=20000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)

    # --- รายงาน > Export Report PO ---
    print("[ITOS] กำลังไปหน้า รายงาน > Export Report PO ...")
    page.get_by_text("รายงาน", exact=True).click(timeout=20000)
    page.wait_for_timeout(1000)
    page.get_by_text("Export Report PO", exact=True).click(timeout=20000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)

    # --- ตั้งค่าวันที่ (calendar widget พ.ศ. — ต้องคลิกเลือกวัน ไม่ใช่พิมพ์ข้อความ) ---
    print(f"[ITOS] กำลังตั้งวันที่ From={format_thai_be(start)} ...")
    _select_calendar_date(page, "Date From", start)
    page.wait_for_timeout(300)

    print(f"[ITOS] กำลังตั้งวันที่ To={format_thai_be(end)} ...")
    _select_calendar_date(page, "Date To", end)
    page.wait_for_timeout(300)

    print("[ITOS] ตั้งวันที่เสร็จแล้ว พร้อมกด CREATE EXCEL")
    return browser, page


def download_itos_export_report() -> Path:
    """เจอจริง: บางครั้งเบราว์เซอร์/หน้าเว็บปิดตัวเองกลางคัน (TargetClosedError) ระหว่างคลิก
    Company/Head Office หรือขั้นอื่นๆ ก่อนจะถึง CREATE EXCEL — ไม่ใช่บั๊กโค้ด เป็นความไม่
    เสถียรของเว็บ/เบราว์เซอร์ชั่วคราว — ยืนยันจากผู้ใช้ให้ปิดแล้วเปิดใหม่ทั้งหมด (instance
    ใหม่) สัก 2-3 รอบก่อนยอมแพ้จริง"""
    start, end = po_date_range()

    last_error: Exception | None = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        browser = None
        try:
            with sync_playwright() as p:
                browser, page = open_itos_report_page(p, start, end)

                print("[ITOS] กำลังกด CREATE EXCEL (รอสร้างไฟล์ อาจใช้เวลาสักครู่) ...")
                with page.expect_download(timeout=60000) as download_info:
                    # timeout ของปุ่มนี้เจอจริงว่าบางทีคลิกแล้วค้าง >15s ทั้งที่ element พร้อม
                    # คลิกแล้ว (เจอ TimeoutError ทั้งที่ log บอก "element is visible, enabled
                    # and stable") เลยขยายให้เท่ากับ expect_download กันพังก่อนดาวน์โหลดจะเริ่มจริง
                    page.get_by_role("button", name="CREATE EXCEL").click(timeout=60000)
                download = download_info.value
                print("[ITOS] ดาวน์โหลดไฟล์สำเร็จ")

                dest = config.DOWNLOAD_DIR / f"itos_export_{start:%Y%m%d}_{end:%Y%m%d}.xlsx"
                download.save_as(dest)

                browser.close()
                return dest
        except Exception as exc:
            last_error = exc
            print(f"[ITOS] !!! รอบที่ {attempt}/{max_attempts} ล้มเหลว ({exc.__class__.__name__}: "
                  f"{exc}) — ปิดเบราว์เซอร์แล้วเปิดใหม่ลองอีกที ...", flush=True)
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
    raise RuntimeError(
        f"ดึงรายงาน ITOS ไม่สำเร็จหลังลอง {max_attempts} รอบ (ปิดเปิดเบราว์เซอร์ใหม่ทุกรอบแล้ว)"
    ) from last_error


if __name__ == "__main__":
    path = download_itos_export_report()
    print(f"ดาวน์โหลดไฟล์ ITOS เสร็จ: {path}")
