"""คัดลอกคอลัมน์ C:K และ L:AV จากชีท "หน้าร้านแก้ไข" (ไฟล์ Bill Auto) ไปวางที่ชีท
"สาขาเปิดบิลใน ITec ผิด" (ไฟล์แยกต่างหาก) คอลัมน์ H:P และ U:BE ตามลำดับ

  - C:K (9 คอลัมน์: Etax Detail, Comment, ราคา, Customer(Code), Member Code, Customer(Name),
    สำนักงานใหญ่, สถานะรับเงิน(Finish), สรุปผลการตรวจสอบ) -> H:P
  - L:AV (37 คอลัมน์: PO DATE ... สถานะรับเงิน(Finish) ชุดที่ 2) -> U:BE

ทั้งสองบล็อกมาจากแถวเดียวกันกับที่ main_build_sakha_phy_id.py ใช้ (Phy/ID) เพราะต้นทางเป็นชีท
เดียวกัน ("หน้าร้านแก้ไข") แถวจึงตรงกันพอดีอยู่แล้ว ไม่ต้อง join ด้วย VLOOKUP

⚠️ ยืนยันจากผู้ใช้ (2026-09-08): ปลายทางเดิมคือ T:BD แต่ผู้ใช้แทรกคอลัมน์ใหม่ "รายละเอียด"
เข้ามาที่ตำแหน่ง T ในชีทปลายทาง ทำให้ทุกอย่างตั้งแต่ PO DATE เป็นต้นไปเลื่อนขวาไป 1 ช่อง —
แก้ปลายทางบล็อก 2 จาก T(20) เป็น U(21) ตามที่เลื่อนจริง ไม่แตะคอลัมน์ "รายละเอียด" ที่เพิ่มมาใหม่

ลบข้อมูลเก่าออกก่อนวางทุกครั้ง (clear_and_paste_range) เหมือน main_build_sakha_phy_id.py
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
DEST_START_ROW = 8  # ชีท สาขาเปิดบิลใน ITec ผิด เริ่มข้อมูลที่แถว 8

# (คอลัมน์เริ่มต้นต้นทาง 1-based, จำนวนคอลัมน์, คอลัมน์เริ่มต้นปลายทาง 1-based)
BLOCKS = [
    (3, 9, 8),    # C(3):K(11)  -> H(8):P(16)
    (12, 37, 21), # L(12):AV(48) -> U(21):BE(57) — เลื่อนจาก T เพราะแทรกคอลัมน์ "รายละเอียด" ใหม่
]


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

    for source_start_col, num_cols, dest_start_col in BLOCKS:
        print(f"[sakha-details] กำลังอ่าน หน้าร้านแก้ไข คอลัมน์เริ่มที่ {source_start_col} "
              f"({num_cols} คอลัมน์) ...", flush=True)
        values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, source_start_col, num_cols)

        # ตัดแถวว่างท้ายๆ ทิ้ง
        while values and not any((cell or "").strip() for cell in values[-1]):
            values.pop()
        print(f"[sakha-details] อ่านได้ {len(values)} แถว", flush=True)

        if not values:
            print("[sakha-details] ไม่มีข้อมูลให้วางในบล็อกนี้ ข้ามไป", flush=True)
            continue

        normalized = [row + [""] * (num_cols - len(row)) for row in values]
        df = pd.DataFrame(normalized)

        needed_rows = DEST_START_ROW + len(df) - 1
        if dest_ws.row_count < needed_rows:
            print(f"[sakha-details] ขยายชีท สาขาเปิดบิลใน ITec ผิด จาก {dest_ws.row_count} เป็น "
                  f"{needed_rows} แถว ...", flush=True)
            sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

        print(f"[sakha-details] กำลังลบของเก่า + วาง {len(df)} แถว ที่คอลัมน์เริ่มที่ "
              f"{dest_start_col} ...", flush=True)
        sheets_client.clear_and_paste_range(dest_ws, df, DEST_START_ROW, dest_start_col)

    print("[sakha-details] เสร็จสิ้นทั้ง 2 บล็อก", flush=True)


if __name__ == "__main__":
    main()
