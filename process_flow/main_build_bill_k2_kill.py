"""คัดลอกคอลัมน์ C:AH (32 คอลัมน์) จากชีท "Match" (ไฟล์ Bill Auto) ไปวางที่ชีท "Bill K2 Kill"
(ไฟล์ "Bill Auto Cal") คอลัมน์ B:AG — เอาทุกแถวของ Match ไม่กรอง (รวมทั้ง K2 และ ITOS)

โครงสร้างปลายทางตรงกับต้นทางเป๊ะ (B=PO DATE ตรงกับ Match!C=PO DATE ไปจนถึง AG=TAX DATE ตรงกับ
Match!AH=TAX DATE) ไม่แตะคอลัมน์ A (Company) และ AH (Branch ID ซ้ำท้ายตาราง) ของปลายทาง

ลบข้อมูลเก่าออกก่อนวางทุกครั้ง (clear_and_paste_range)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client

BILL_AUTO_MATCH_TAB_GID = 899495725  # "Match" (ไฟล์ Bill Auto ต้นทาง)
BILL_AUTO_CAL_K2_KILL_TAB_GID = 1018276173  # "Bill K2 Kill" (ไฟล์ Bill Auto Cal ปลายทาง)

SOURCE_START_ROW = 6  # ชีท Match เริ่มข้อมูลที่แถว 6
SOURCE_START_COL = 3  # C
NUM_COLS = 32  # C(3) ถึง AH(34)
DEST_START_ROW = 2  # ชีท Bill K2 Kill เริ่มข้อมูลที่แถว 2 (header แถว 1)
DEST_START_COL = 2  # B


def get_bill_auto_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def get_bill_auto_cal_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def main():
    source_ws = get_bill_auto_worksheet(BILL_AUTO_MATCH_TAB_GID)
    dest_ws = get_bill_auto_cal_worksheet(BILL_AUTO_CAL_K2_KILL_TAB_GID)

    print("[bill-k2-kill] กำลังอ่านชีท Match คอลัมน์ C:AH ...", flush=True)
    values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, SOURCE_START_COL, NUM_COLS)

    # ตัดแถวว่างท้ายๆ ทิ้ง
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    print(f"[bill-k2-kill] อ่านได้ {len(values)} แถว", flush=True)

    if not values:
        print("[bill-k2-kill] ไม่มีข้อมูลให้วาง จบการทำงาน", flush=True)
        return

    old_row_count = dest_ws.row_count

    normalized = [row + [""] * (NUM_COLS - len(row)) for row in values]
    df = pd.DataFrame(normalized)

    needed_rows = DEST_START_ROW + len(df) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[bill-k2-kill] ขยายชีท Bill K2 Kill จาก {dest_ws.row_count} เป็น {needed_rows} แถว ...",
              flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[bill-k2-kill] กำลังลบของเก่า + วาง {len(df)} แถว ที่ชีท Bill K2 Kill คอลัมน์ B:AG ...",
          flush=True)
    sheets_client.clear_and_paste_range(dest_ws, df, DEST_START_ROW, DEST_START_COL)

    # ⚠️ แก้บั๊ก (2026-10-01): คอลัมน์ A, AH:AK (Company/Branch ID ซ้ำ/Application Status
    # ก่อนคลีน/ชื่อลูกค้า/Branch ID จาก Phy-ID — เติมโดยสเตจ 4.21/4.215/4.216 ภายหลัง) ไม่ได้
    # ถูกคลีนตรงนี้ ถ้ารอบก่อนหน้ามีแถวมากกว่ารอบนี้ (เช่น เพิ่งรันช่วงกว้างแล้วกลับมารันวันนี้)
    # ข้อมูลเก่าที่เกินแถวใหม่จะค้างอยู่ ทำให้สคริปต์ปลายทาง (main_copy_billkill_to_external.py)
    # อ่านแถว "ผี" ที่มีแค่บางคอลัมน์ไม่ว่างติดมาด้วย ต้องเคลียร์ส่วนเกินทิ้งทุกครั้ง
    if old_row_count > needed_rows:
        extra_start = needed_rows + 1
        print(f"[bill-k2-kill] กำลังเคลียร์แถวเก่าที่เกิน (A, AH:AK) แถว {extra_start}-{old_row_count} "
              f"กันข้อมูลค้าง ...", flush=True)
        sheets_client.with_retry(
            lambda: dest_ws.batch_clear([
                f"A{extra_start}:A{old_row_count}",
                f"AH{extra_start}:AK{old_row_count}",
            ])
        )

    print("[bill-k2-kill] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
