"""คัดลอกคอลัมน์ Phy กับ ID จากชีท "หน้าร้านแก้ไข" (ไฟล์ Bill Auto) ไปวางที่ชีท
"สาขาเปิดบิลใน ITec ผิด" (ไฟล์แยกต่างหาก) คอลัมน์ A:B

ลบข้อมูลเก่าออกก่อนวางทุกครั้ง (clear_and_paste_range) ไม่แตะคอลัมน์ C:E (Store Name, BU, RM)
ของปลายทางเด็ดขาด เพราะเป็นข้อมูลที่กรอก/คำนวณแยกต่างหาก ไม่เกี่ยวกับคอลัมน์ A:B นี้
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client

BILL_AUTO_HNARAN_TAB_GID = 674516319  # "หน้าร้านแก้ไข" (ไฟล์ Bill Auto ต้นทาง)
SAKHA_TAB_GID = 0  # "สาขาเปิดบิลใน ITec ผิด" (ไฟล์ปลายทาง)

SOURCE_START_ROW = 6  # ชีท หน้าร้านแก้ไข เริ่มข้อมูลที่แถว 6
SOURCE_START_COL = 1  # A (Phy)
NUM_COLS = 2  # A:B (Phy, ID)
DEST_START_ROW = 8  # ชีท สาขาเปิดบิลใน ITec ผิด เริ่มข้อมูลที่แถว 8 (header แถว 7)
DEST_START_COL = 1  # A


def get_bill_auto_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def get_sakha_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SAKHA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def main():
    source_ws = get_bill_auto_worksheet(BILL_AUTO_HNARAN_TAB_GID)
    dest_ws = get_sakha_worksheet(SAKHA_TAB_GID)

    print("[sakha-phy-id] กำลังอ่านชีท หน้าร้านแก้ไข คอลัมน์ Phy, ID ...", flush=True)
    values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, SOURCE_START_COL, NUM_COLS)

    # ตัดแถวว่างท้ายๆ ทิ้ง
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    print(f"[sakha-phy-id] อ่านได้ {len(values)} แถว", flush=True)

    if not values:
        print("[sakha-phy-id] ไม่มีข้อมูลให้วาง จบการทำงาน", flush=True)
        return

    normalized = [row + [""] * (NUM_COLS - len(row)) for row in values]
    df = pd.DataFrame(normalized)

    needed_rows = DEST_START_ROW + len(df) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[sakha-phy-id] ขยายชีท สาขาเปิดบิลใน ITec ผิด จาก {dest_ws.row_count} เป็น "
              f"{needed_rows} แถว ...", flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[sakha-phy-id] กำลังลบของเก่า + วาง {len(df)} แถว ที่ชีท สาขาเปิดบิลใน ITec ผิด "
          f"คอลัมน์ A:B ...", flush=True)
    sheets_client.clear_and_paste_range(dest_ws, df, DEST_START_ROW, DEST_START_COL)

    print("[sakha-phy-id] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
