"""อ่านชีท "ถูกทั้งหมด รอ Confirm" (ไฟล์ Bill Auto) คอลัมน์ C:AP (40 คอลัมน์) มาวางที่ชีท
"บิลถูกต้อง" (ไฟล์ "Bill Auto Cal") คอลัมน์ A:AN (40 คอลัมน์)

โครงสร้างปลายทาง "บิลถูกต้อง": header แถว 2, ข้อมูลเริ่มแถว 3, คอลัมน์ A="PO DATE" ตรงกับ
คอลัมน์ C="PO DATE" ของต้นทางเป๊ะ (เลื่อนซ้าย 2 คอลัมน์ เพราะต้นทางมี Phy/ID นำหน้าที่ปลายทาง
ไม่มี)

⚠️ ห้ามแตะคอลัมน์ AO ("Comment ที่ได้จากการ Match Comment UFUND") และ AP ("สถานะบัญชี") ของ
ปลายทางเด็ดขาด — ไม่ได้อยู่ในช่วงคอลัมน์ที่คัดลอกมา (นอกเหนือ A:AN) น่าจะเป็นคอลัมน์กรอกเอง/
สูตรสดของตัวเอง เหมือนกับ AO ของ "สถานะ Approve"/"สถานะ Rework"
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client

BILL_AUTO_CONFIRM_TAB_GID = 857579518  # "ถูกทั้งหมด รอ Confirm" (ไฟล์ Bill Auto ต้นทาง)
BILL_AUTO_CAL_BIL_TUKTONG_TAB_GID = 72020192  # "บิลถูกต้อง" (ไฟล์ Bill Auto Cal ปลายทาง)

SOURCE_START_ROW = 6  # ชีท ถูกทั้งหมด รอ Confirm เริ่มข้อมูลที่แถว 6
SOURCE_START_COL = 3  # C
NUM_COLS = 40  # C(3) ถึง AP(42)
DEST_START_ROW = 3  # ชีท บิลถูกต้อง เริ่มข้อมูลที่แถว 3 (header แถว 2)
DEST_START_COL = 1  # A


def get_bill_auto_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def get_bill_auto_cal_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def main():
    source_ws = get_bill_auto_worksheet(BILL_AUTO_CONFIRM_TAB_GID)
    dest_ws = get_bill_auto_cal_worksheet(BILL_AUTO_CAL_BIL_TUKTONG_TAB_GID)

    print("[bil-tuktong] กำลังอ่านชีท ถูกทั้งหมด รอ Confirm คอลัมน์ C:AP ...", flush=True)
    values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, SOURCE_START_COL, NUM_COLS)

    # ตัดแถวว่างท้ายๆ ทิ้ง
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    print(f"[bil-tuktong] อ่านได้ {len(values)} แถว", flush=True)

    if not values:
        print("[bil-tuktong] ไม่มีข้อมูลให้วาง จบการทำงาน", flush=True)
        return

    normalized = [row + [""] * (NUM_COLS - len(row)) for row in values]
    df = pd.DataFrame(normalized)

    needed_rows = DEST_START_ROW + len(df) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[bil-tuktong] ขยายชีท บิลถูกต้อง จาก {dest_ws.row_count} เป็น {needed_rows} แถว ...",
              flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[bil-tuktong] กำลังวาง {len(df)} แถว ที่ชีท บิลถูกต้อง (ไฟล์ Bill Auto Cal) คอลัมน์ A:AN ...",
          flush=True)
    sheets_client.clear_and_paste_range(dest_ws, df, DEST_START_ROW, DEST_START_COL)

    print("[bil-tuktong] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
