"""ขั้น Check Bill Approve (ส่วน K2): อ่าน APPLICATION NUMBER รูปแบบ K2 (ตัวเลขล้วน) จากชีท
"Check Bill Approve" (ไฟล์ "Bill Auto Cal") แล้วเช็คสถานะทีละตัวผ่าน K2 > Management & Report
(AEE) > รายงานบิลขายเทียบสัญญาเช่าซื้อ จากนั้นเขียนผลกลับเข้าคอลัมน์ ผลการตรวจสอบ (D)

โครงสร้างชีท Check Bill Approve (ไฟล์ Bill Auto Cal, tab "Check Bill Approve" gid=444408138):
  header อยู่แถว 6, ข้อมูลเริ่มแถว 7
  B = PO NUMBER, C = APPLICATION NUMBER, D = ผลการตรวจสอบ, E = PHY-ID, F = Note
  (คอลัมน์ G เป็นต้นไปเป็นข้อมูล "เมื่อวาน" (ห้ามลบ) ไม่แตะเด็ดขาด)

APPLICATION NUMBER มี 2 รูปแบบ:
  - ตัวเลขล้วน เช่น 99992026500002 -> เช็คใน K2 (ทำในไฟล์นี้)
  - รูปแบบ YYYYMM-XXXXXX เช่น 202601-000001 -> เช็คใน ITOS (ยังไม่ทำ ข้ามไปก่อน)

ใช้ check_k2_application()/open_k2_aee_report() จาก check_k2_status.py (เทสแล้วว่าใช้งานได้จริง
กับเลขตัวอย่าง 99992026500001 -> ได้ "ไม่ Asset deliver" ตรงกับที่ควรเป็น)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import re

from playwright.sync_api import sync_playwright

import config
import sheets_client
from check_k2_status import check_k2_application, open_k2_aee_report

BILL_AUTO_CAL_CHECK_BILL_APPROVE_TAB_GID = 444408138  # "Check Bill Approve" (ไฟล์ Bill Auto Cal)
DATA_START_ROW = 7
COL_APPLICATION = 3  # C
COL_RESULT = 4  # D (ผลการตรวจสอบ)

K2_APPLICATION_RE = re.compile(r"^\d+$")


def get_check_bill_approve_worksheet():
    """Check Bill Approve ย้ายไปอยู่ไฟล์ "Bill Auto Cal" แยกต่างหากแล้ว (ไฟล์ Bill Auto เดิมเต็ม)"""
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(BILL_AUTO_CAL_CHECK_BILL_APPROVE_TAB_GID)


def find_k2_targets(ws) -> list[tuple[int, str]]:
    """คืนลิสต์ (เลขแถวในชีท, APPLICATION NUMBER) เฉพาะที่เป็นรูปแบบ K2 (ตัวเลขล้วน)"""
    values = sheets_client.read_range_values(ws, DATA_START_ROW, COL_APPLICATION, 1)
    targets = []
    for i, row in enumerate(values):
        application_number = (row[0] if row else "").strip()
        if application_number and K2_APPLICATION_RE.match(application_number):
            targets.append((DATA_START_ROW + i, application_number))
    return targets


def main():
    ws = get_check_bill_approve_worksheet()

    print("[check-k2] กำลังอ่านคอลัมน์ APPLICATION NUMBER จาก Check Bill Approve ...", flush=True)
    targets = find_k2_targets(ws)
    print(f"[check-k2] เจอ APPLICATION NUMBER แบบ K2 (ตัวเลขล้วน) ทั้งหมด {len(targets)} รายการ", flush=True)
    if not targets:
        print("[check-k2] ไม่มีรายการต้องเช็ค จบการทำงาน", flush=True)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={"username": config.K2_USER, "password": config.K2_PASS},
        )
        page = context.new_page()
        open_k2_aee_report(page)

        updates = []
        skipped = []
        for idx, (row_number, application_number) in enumerate(targets, start=1):
            status = check_k2_application(page, application_number)
            print(f"[check-k2] ({idx}/{len(targets)}) {application_number} -> {status}", flush=True)
            if status == "ไม่พบข้อมูล":
                # ช่อง "ผลการตรวจสอบ" เป็น dropdown ที่ล็อกรายการค่าไว้ — "ไม่พบข้อมูล" ไม่ใช่
                # ตัวเลือกที่มีอยู่จริง เขียนไปแล้วชีทจะขึ้น warning ค่าไม่ถูกต้อง เลยข้ามแถว
                # นี้ไป (ปล่อยค่าเดิมไว้) แทนการเขียนค่าที่ไม่ใช่ตัวเลือกจริง
                skipped.append((row_number, application_number))
                continue
            updates.append({"range": f"D{row_number}", "values": [[status]]})

        browser.close()

    if skipped:
        print(f"[check-k2] ข้าม {len(skipped)} แถวที่หาข้อมูลไม่เจอ (ไม่แตะค่าเดิม): "
              f"{', '.join(f'{app}(แถว {row})' for row, app in skipped)}", flush=True)

    if not updates:
        print("[check-k2] ไม่มีผลลัพธ์ที่เขียนได้เลย จบการทำงาน", flush=True)
        return

    print(f"[check-k2] กำลังเขียนผลกลับเข้าชีท {len(updates)} แถว ...", flush=True)
    sheets_client.with_retry(lambda: ws.batch_update(updates, value_input_option="USER_ENTERED"))
    print("[check-k2] เขียนผลสำเร็จ", flush=True)


if __name__ == "__main__":
    main()
