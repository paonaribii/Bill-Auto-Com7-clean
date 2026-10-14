"""คัดลอกคอลัมน์ APPLICATION NUMBER จากชีท "Etax" (ไฟล์ Bill Auto Cal, คอลัมน์ X) ไปวางที่ชีท
"Confirm เลข Application" (ไฟล์ Bill Auto Cal เช่นกัน, คอลัมน์ B) — คัดลอกแค่คอลัมน์เดียว

โครงสร้างปลายทาง: header แถว 4, ข้อมูลเริ่มแถว 5, คอลัมน์ B = APPLICATION NUMBER
โครงสร้างต้นทาง: header แถว 2, ข้อมูลเริ่มแถว 3, คอลัมน์ X (24) = APPLICATION NUMBER

⚠️ Etax เป็นสูตรสด (FILTER จาก 'บิลถูกต้อง') ที่ Google Sheets recalculate แบบ async — เจอจริง:
อ่านผ่าน gspread (values.get) ทันทีหลังสเตจก่อนหน้าเพิ่งเขียน 'บิลถูกต้อง' เสร็จ สูตรอาจยังไม่
recalculate ทัน ได้ค่าเก่าค้าง (stale) แทนที่จะเป็นค่าล่าสุด (เจอเคสจริง: Etax จริงว่าง 0 แถว
แต่อ่านได้ 1,242 แถว)

ลองดาวน์โหลดทั้งไฟล์เป็น Excel ก่อนเผื่อ trigger recalculate แล้ว — **ทดสอบแล้วไม่ช่วย** (อ่าน
ผ่าน API ยังได้ค่าเก่าค้างเหมือนเดิม export กับ values.get คนละกลไกกัน ไม่เกี่ยวกัน) และวิธี
"อ่านซ้ำจนจำนวนแถวนิ่ง" ก็ทดสอบแล้วว่าใช้ไม่ได้ผลเช่นกัน (ยืนยันด้วยการเช็คค่าจริงสดๆ ตรง ๆ ว่า
Etax = 0 แถว แต่สคริปต์อ่านได้ 1,242 แถว "นิ่ง" ครบ 3 รอบ — ค่ามันนิ่งแต่นิ่งผิด ไม่ใช่แค่ recalculate
ไม่ทันชั่วคราว) ตามคำสั่งผู้ใช้ (2026-09-02) ตัดวิธีรออ่านซ้ำจนนิ่งออก เหลืออ่านครั้งเดียวตรง ๆ

ขั้นดาวน์โหลด Excel ทั้งไฟล์ (ที่คงไว้เฉยๆ ตอนแรก) ภายหลังพบว่าไฟล์ Bill Auto Cal ใหญ่เกินกว่า
Google Drive export API จะดาวน์โหลดได้แล้ว (APIError 403 "This file is too large to be exported")
ทำให้ pipeline ทั้งชุดพังกลางทาง — ตามคำสั่งผู้ใช้ (2026-09-02) **ตัดขั้นตอนนี้ออกทั้งหมด**

ประวัติ: ช่วง 2026-09-03 ถึง 2026-09-09 เคยเปลี่ยนเป็นวางต่อท้าย (append) ไม่ลบของเก่า

⚠️ ยืนยันจากผู้ใช้ (2026-09-10): **เปลี่ยนกลับเป็น clear-before-write** — ลบคอลัมน์ B
(APPLICATION NUMBER) + D (DATE) ตั้งแต่แถว 5 ลงไปทั้งหมดก่อน แล้ววางข้อมูลใหม่ทับตั้งแต่แถว 5
ไม่วางต่อท้ายแล้ว คอลัมน์ D ยังเขียนวันที่จริง ณ ตอนรัน (dd/mm/yyyy ปี ค.ศ.) กำกับทุกแถวเหมือนเดิม
"""
import sys as _sys
from datetime import date as _date
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client
from date_utils import format_thai_style
from date_utils import _today as _today_override

BILL_AUTO_CAL_ETAX_TAB_GID = 1283294933  # "Etax" (ต้นทาง)
BILL_AUTO_CAL_CONFIRM_TAB_GID = 477977929  # "Confirm เลข Application" (ปลายทาง)

SOURCE_START_ROW = 3  # ชีท Etax เริ่มข้อมูลที่แถว 3
SOURCE_COL = 24  # X (APPLICATION NUMBER)
DEST_START_ROW = 5  # ชีท Confirm เลข Application เริ่มข้อมูลที่แถว 5
DEST_COL = 2  # B (APPLICATION NUMBER)
DEST_DATE_COL = 4  # D (DATE)


def get_bill_auto_cal_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def _read_etax_application_numbers(source_ws) -> list[list[str]]:
    """อ่านคอลัมน์ APPLICATION NUMBER จากชีท Etax ครั้งเดียวตรง ๆ (ไม่ต้องรออ่านซ้ำจนนิ่ง —
    ทดสอบแล้วว่าการรอไม่ช่วยแก้ปัญหาค่าค้าง (stale) ของ Etax ตามคำสั่งผู้ใช้)"""
    values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, SOURCE_COL, 1)
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    return values


def _find_next_empty_row(dest_ws) -> int:
    """หาแถวว่างแรกในคอลัมน์ B ต่อจากแถวสุดท้ายที่มีข้อมูลอยู่แล้ว (เริ่มค้นจาก DEST_START_ROW)"""
    existing = sheets_client.with_retry(
        lambda: dest_ws.get(f"B{DEST_START_ROW}:B{dest_ws.row_count}")
    )
    while existing and not (existing[-1] and str(existing[-1][0]).strip()):
        existing.pop()
    return DEST_START_ROW + len(existing)


def main():
    dest_ws = get_bill_auto_cal_worksheet(BILL_AUTO_CAL_CONFIRM_TAB_GID)

    source_ws = get_bill_auto_cal_worksheet(BILL_AUTO_CAL_ETAX_TAB_GID)
    print("[confirm-appnum] กำลังอ่านชีท Etax คอลัมน์ APPLICATION NUMBER ...", flush=True)
    values = _read_etax_application_numbers(source_ws)
    print(f"[confirm-appnum] อ่านได้ {len(values)} แถว", flush=True)

    # ยืนยันจากผู้ใช้ (2026-09-10): เปลี่ยนกลับเป็น "ลบของเก่าแล้ววางทับ" ไม่วางต่อท้ายแล้ว
    # -> เคลียร์คอลัมน์ B (APPLICATION NUMBER) + D (DATE) ตั้งแต่ DEST_START_ROW ลงไปทั้งหมดก่อนเสมอ
    last_row = max(dest_ws.row_count, DEST_START_ROW)
    print(f"[confirm-appnum] กำลังลบของเก่า B{DEST_START_ROW}:B{last_row} + "
          f"D{DEST_START_ROW}:D{last_row} ...", flush=True)
    sheets_client.with_retry(
        lambda: dest_ws.batch_clear([f"B{DEST_START_ROW}:B{last_row}",
                                     f"D{DEST_START_ROW}:D{last_row}"])
    )

    if not values:
        print("[confirm-appnum] Etax ว่าง (0 แถว) ลบของเก่าแล้วไม่มีอะไรวางทับ จบการทำงาน",
              flush=True)
        return

    df = pd.DataFrame(values)

    needed_rows = DEST_START_ROW + len(df) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[confirm-appnum] ขยายชีท Confirm เลข Application จาก {dest_ws.row_count} เป็น "
              f"{needed_rows} แถว ...", flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[confirm-appnum] กำลังวางทับ {len(df)} แถว ที่คอลัมน์ B เริ่มแถว {DEST_START_ROW} ...",
          flush=True)
    values_list = df.astype(object).where(pd.notnull(df), "").values.tolist()
    sheets_client.with_retry(
        lambda: dest_ws.update(values_list, f"B{DEST_START_ROW}", value_input_option="USER_ENTERED")
    )

    # กำกับวันที่ (คอลัมน์ D) ทุกแถว — เป็นวันที่จริง ณ ตอนรัน
    today_str = format_thai_style(_today_override())
    print(f"[confirm-appnum] กำลังเขียนวันที่ {today_str} ลงคอลัมน์ D ให้ {len(df)} แถว ...",
          flush=True)
    date_values = [[today_str]] * len(df)
    sheets_client.with_retry(
        lambda: dest_ws.update(date_values, f"D{DEST_START_ROW}", value_input_option="USER_ENTERED")
    )

    print("[confirm-appnum] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
