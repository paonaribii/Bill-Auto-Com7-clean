"""คัดลอกข้อมูลทั้งหมดจากชีท "Bill K2 Kill" (ไฟล์ Bill Auto Cal) คอลัมน์ A:AK (37 คอลัมน์)
ไปวางที่แท็บ "Data" ของสเปรดชีทภายนอก "สถานะ PO ที่ Approve แล้วยังไม่เกิดสัญญา"
(PO_APPROVED_SPREADSHEET_ID ใน .env) —
ยืนยันจากผู้ใช้ (2026-09-18): เอาข้อมูลจาก Bill K2 Kill มาใส่ คอลัมน์เหมือนกันเป๊ะ

โครงสร้างต้นทางและปลายทางตรงกันเป๊ะทั้ง 37 คอลัมน์ (เช็คแล้ว: Company, PO DATE, ..., TAX DATE,
Branch ID(ซ้ำ), Application Status (ก่อนคลีน), '', Application Sub Status) เลยคัดลอกแบบ 1:1
column-for-column ไม่ต้อง mapping ใดๆ

ลบข้อมูลเก่าออกก่อนวางทุกครั้ง (clear_and_paste_range) — ปลายทางนี้เป็นสเปรดชีทคนละไฟล์กับ
Bill Auto Cal แต่ sheets_client.get_client() ใช้ credential เดียวกัน เปิดข้ามไฟล์ได้ตรงๆ
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client

BILL_AUTO_CAL_K2_KILL_TAB_GID = 1018276173  # "Bill K2 Kill" (ไฟล์ Bill Auto Cal ต้นทาง)
EXTERNAL_SPREADSHEET_ID = config.PO_APPROVED_SPREADSHEET_ID
EXTERNAL_DATA_TAB_GID = 1733585806  # "Data" (ปลายทาง)

SOURCE_START_ROW = 2  # Bill K2 Kill เริ่มข้อมูลที่แถว 2 (header แถว 1)
SOURCE_START_COL = 1  # A
NUM_COLS = 37  # A ถึง AK
DEST_START_ROW = 2  # Data เริ่มข้อมูลที่แถว 2 (header แถว 1) — โครงสร้างตรงกันเป๊ะ
DEST_START_COL = 1  # A


def _get_source_worksheet():
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(BILL_AUTO_CAL_K2_KILL_TAB_GID)


def _get_dest_worksheet():
    client = sheets_client.get_client()
    sh = client.open_by_key(EXTERNAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(EXTERNAL_DATA_TAB_GID)


def main() -> None:
    source_ws = _get_source_worksheet()
    dest_ws = _get_dest_worksheet()

    print("[copy-billkill-external] กำลังอ่านชีท Bill K2 Kill คอลัมน์ A:AK ...", flush=True)
    values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, SOURCE_START_COL, NUM_COLS)

    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    print(f"[copy-billkill-external] อ่านได้ {len(values)} แถว", flush=True)

    if not values:
        print("[copy-billkill-external] ไม่มีข้อมูลให้วาง จบการทำงาน", flush=True)
        return

    normalized = [row + [""] * (NUM_COLS - len(row)) for row in values]
    df = pd.DataFrame(normalized)

    needed_rows = DEST_START_ROW + len(df) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[copy-billkill-external] ขยายชีท Data จาก {dest_ws.row_count} เป็น {needed_rows} แถว ...",
              flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[copy-billkill-external] กำลังลบของเก่า + วาง {len(df)} แถว ที่ชีท Data (สเปรดชีทภายนอก) "
          f"คอลัมน์ A:AK ...", flush=True)
    sheets_client.clear_and_paste_range(dest_ws, df, DEST_START_ROW, DEST_START_COL)

    print("[copy-billkill-external] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
