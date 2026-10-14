"""ตรวจสอบ APPLICATION NUMBER รูปแบบ K2 (ตัวเลขล้วน) ผ่านหน้า K2 > Management & Report (AEE)

Login แบบ HTTP Basic Auth เหมือน clean_flow/k2_scraper.py คลิกแท็บ "Management & Report (AEE)"
แล้วใช้ช่อง Quick Search กรองด้วย APPLICATION NUMBER ทีละตัว อ่านคอลัมน์ ABM NUMBER / CONTRACT
เพื่อสรุปสถานะตามเงื่อนไข (ต้องเช็ค ABM NUMBER ก่อน CONTRACT เสมอ):
  - ABM NUMBER ว่าง (ไม่ว่า CONTRACT จะมีหรือไม่ก็ตาม) -> "ไม่ส่ง MDM"
  - ABM NUMBER มี แต่ CONTRACT ว่าง                    -> "ไม่ Asset deliver"
  - มีครบทั้งคู่                                       -> "เสร็จสมบูรณ์"

รันไฟล์นี้ตรงๆ จะเทสกับเลขตัวอย่าง (EXAMPLE_APPLICATION_NUMBER) ก่อน ยังไม่ได้ต่อกับ
Google Sheets จริง — รอผลเทสให้ผ่านก่อนค่อยต่อ step ถัดไป (อ่าน/เขียนชีท Check Bill Approve)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
from playwright.sync_api import Page, sync_playwright

EXAMPLE_APPLICATION_NUMBER = "99992026500001"  # เลขสมมติสำหรับรันเทสด้วยมือ — ใส่เลข Application จริงของคุณเองตอนจะทดสอบ


def open_k2_aee_report(page: Page) -> None:
    """login + คลิกเข้าไปที่รายงาน Management & Report (AEE) ค้างไว้ให้พร้อมค้นหา"""
    print("[k2-status] กำลังเปิดหน้า login ...", flush=True)
    page.goto(config.K2_AEE_REPORT_URL)
    page.wait_for_load_state("domcontentloaded")

    print("[k2-status] รอเมนูโหลด ...", flush=True)
    page.wait_for_timeout(8000)

    print("[k2-status] กำลังคลิก 'Management & Report (AEE)' เพื่อเปิด submenu ...", flush=True)
    # เจอจริง: บางครั้งเมนูโหลดช้ากว่า 8 วิ (เจอ TimeoutError ที่ hover ทั้งที่เคยรันผ่านมา
    # แล้วในรอบก่อนหน้า) — retry สั้นๆ ก่อนยอมแพ้จริง
    last_err = None
    for attempt in range(3):
        try:
            page.get_by_role("link", name="Management & Report (AEE)").hover(timeout=20000)
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            print(f"[k2-status]   เมนูยังไม่พร้อม รออีกแล้วลองใหม่ (รอบ {attempt + 1}/3) ...", flush=True)
            page.wait_for_timeout(5000)
    if last_err is not None:
        # ก่อนยอมแพ้จริง เก็บสถานะหน้าจอตอนนั้นไว้ debug (URL/title/screenshot) — ไม่งั้นไม่รู้
        # เลยว่าตอนพังค้างอยู่หน้าไหนจริงๆ
        try:
            print(f"[k2-status]   !!! เมนูหาไม่เจอ — URL ปัจจุบัน: {page.url}", flush=True)
            print(f"[k2-status]   !!! title ปัจจุบัน: {page.title()}", flush=True)
            shot_path = str(_Path(__file__).resolve().parent / "k2_fail_screenshot.png")
            page.screenshot(path=shot_path)
            print(f"[k2-status]   !!! เซฟภาพหน้าจอไว้ที่ {shot_path}", flush=True)
        except Exception as debug_exc:
            print(f"[k2-status]   (เก็บ debug info ไม่สำเร็จ: {debug_exc})", flush=True)
        raise last_err
    page.wait_for_timeout(1000)

    print("[k2-status] กำลังคลิก submenu 'รายงานบิลขายเทียบสัญญาเช่าซื้อ' ...", flush=True)
    page.get_by_role("link", name="รายงานบิลขายเทียบสัญญาเช่าซื้อ").click(timeout=15000)
    page.wait_for_timeout(3000)


def _find_quick_search_input(page: Page):
    """หาช่อง Quick Search ที่ "มองเห็นได้จริง" — ลองทั้ง main page และทุก iframe เพราะ
    หน้ารายงานของ K2 มักฝังฟอร์มไว้ใน iframe (ชื่อ iframe สุ่มใหม่ทุก session)

    คืนค่าเป็น (space, locator) แทนที่จะคืนแค่ locator เพราะขั้นตอนต่อไป (หาแถวผลลัพธ์)
    ต้องค้นหาใน "เฟรมเดียวกัน" กับช่องค้นหานี้ ไม่ใช่หน้าหลักเสมอไป — จุดนี้เป็นบั๊กที่เจอจริง
    (หาช่องค้นหาเจอในเฟรม แต่ไปหาแถวผลลัพธ์จาก page หลัก เลยได้ 0 แถวเสมอทั้งที่มีข้อมูลจริง)
    """
    search_spaces = [page] + list(page.frames)

    # id จริงที่เจอจาก Inspect Element เป็น GUID + "_quick..." (เช่น "..._quickSearchInput")
    for space in search_spaces:
        try:
            by_id = space.locator("input[id*='_quick']")
            for i in range(by_id.count()):
                el = by_id.nth(i)
                if el.is_visible():
                    return space, el
        except Exception:
            continue

    for space in search_spaces:
        try:
            after_label = space.get_by_text("Quick Search", exact=False).locator(
                "xpath=following::input[@type='text']"
            )
            for i in range(after_label.count()):
                el = after_label.nth(i)
                if el.is_visible():
                    return space, el
        except Exception:
            continue

    for space in search_spaces:
        try:
            by_id = space.locator("input[id*='FindValueTextBox']")
            for i in range(by_id.count()):
                el = by_id.nth(i)
                if el.is_visible():
                    return space, el
        except Exception:
            continue

    page.screenshot(path="scratch_k2_status_debug.png", full_page=True)
    print(f"[k2-status] หาไม่เจอ — จำนวน frame ทั้งหมดในหน้า: {len(page.frames)}", flush=True)
    for fi, frame in enumerate(page.frames):
        try:
            inputs = frame.locator("input[type='text'], input:not([type])")
            print(f"  frame[{fi}] url={frame.url!r} จำนวน text-input={inputs.count()}", flush=True)
            for i in range(inputs.count()):
                el = inputs.nth(i)
                try:
                    print(f"    [{i}] id={el.get_attribute('id')!r} visible={el.is_visible()} box={el.bounding_box()}", flush=True)
                except Exception as e:
                    print(f"    [{i}] <error {e}>", flush=True)
        except Exception as e:
            print(f"  frame[{fi}] <error {e}>", flush=True)
    raise RuntimeError("หาช่อง Quick Search ที่มองเห็นได้ไม่เจอเลยแม้ลองทุก frame — เช็คไฟล์ scratch_k2_status_debug.png และ list ด้านบน")


def check_k2_application(page: Page, application_number: str) -> str:
    """ค้นหา APPLICATION NUMBER 1 ตัวในหน้า AEE ที่เปิดค้างไว้ (open_k2_aee_report มาก่อนแล้ว)
    คืนค่าสถานะเป็น string: "ไม่ Asset deliver" / "ไม่ส่ง MDM" / "เสร็จสมบูรณ์" / "ไม่พบข้อมูล"
    """
    space, search_box = _find_quick_search_input(page)
    search_box.click()
    search_box.fill("")
    search_box.fill(application_number)
    page.keyboard.press("Enter")

    # รอกริดกรองผล — poll ทีละ 1 วิ สูงสุด 6 ครั้ง (6 วิ) แทนรอเฉยๆ ครั้งเดียว เผื่อกริดช้า
    row = None
    for _ in range(6):
        page.wait_for_timeout(1000)
        candidate = space.locator("tr", has_text=application_number).first
        if candidate.count() > 0:
            row = candidate
            break

    if row is None:
        debug_path = f"scratch_k2_notfound_{application_number}.png"
        page.screenshot(path=debug_path, full_page=True)
        try:
            search_value = search_box.input_value()
        except Exception:
            search_value = "<อ่านไม่ได้>"
        row_count_in_space = space.locator("tr").count()
        print(f"[k2-status] ({application_number}) ไม่พบแถว — screenshot: {debug_path}, "
              f"ค่าที่พิมพ์จริงในช่องค้นหา: {search_value!r}, จำนวน <tr> ทั้งหมดในเฟรม: {row_count_in_space}",
              flush=True)
        return "ไม่พบข้อมูล"

    cells = row.locator("td").all_inner_texts()
    # ลำดับคอลัมน์จากที่สำรวจ: APPLICATION, DATE, PHY-ID, PO NUMBER, SERIAL NUMBER, ABM NUMBER, CONTRACT
    if len(cells) < 7:
        print(f"[k2-status] ({application_number}) เจอแถวแต่คอลัมน์ไม่ครบ (ได้ {len(cells)} คอลัมน์): {cells}", flush=True)
        return "ไม่พบข้อมูล"

    abm_number = cells[5].strip()
    contract = cells[6].strip()

    # ต้องเช็ค ABM NUMBER ก่อน CONTRACT เสมอ — กรณีไม่มีทั้งคู่ต้องได้ "ไม่ส่ง MDM"
    # (ยืนยันจากตัวอย่างจริง ไม่ใช่ "ไม่ Asset deliver" แบบที่เขียนไว้ผิดตอนแรก)
    if not abm_number:
        return "ไม่ส่ง MDM"
    if not contract:
        return "ไม่ Asset deliver"
    return "เสร็จสมบูรณ์"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={"username": config.K2_USER, "password": config.K2_PASS},
        )
        page = context.new_page()

        open_k2_aee_report(page)

        print(f"[k2-status] ทดสอบค้นหา {EXAMPLE_APPLICATION_NUMBER} ...", flush=True)
        status = check_k2_application(page, EXAMPLE_APPLICATION_NUMBER)
        print(f"[k2-status] ผลลัพธ์: {status}", flush=True)
        print("[k2-status] คำตอบที่ควรจะได้ (จากชีทที่มีอยู่แล้ว): ไม่ Asset deliver", flush=True)

        page.wait_for_timeout(10000)
        browser.close()


if __name__ == "__main__":
    main()
