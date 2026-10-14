"""อ่านชีท "Match Approve" (ไฟล์ Bill Auto) มาวางที่ชีท "สถานะ Approve" (ไฟล์ "Bill Auto Cal"
— แยกออกมาจากไฟล์ Bill Auto เดิมแล้วเพราะเต็ม) เป็น 2 บล็อกแยกกัน:
  1. Match Approve คอลัมน์ C:AP (40 คอลัมน์)  -> สถานะ Approve คอลัมน์ A:AN
  2. Match Approve คอลัมน์ AQ:BK (21 คอลัมน์) -> สถานะ Approve คอลัมน์ AP:BJ

⚠️ ห้ามแตะคอลัมน์ AO ของสถานะ Approve เด็ดขาด — เป็นสูตรสดของตัวเอง (อ้างอิงแท็บ "Confirm
เลข Application"/"Check Bill Approve") ไม่ได้มาจาก Match Approve เลย เว้นคอลัมน์นี้ไว้ระหว่าง
2 บล็อกด้านบน (บล็อก 1 หยุดที่ AN, บล็อก 2 เริ่มที่ AP ข้าม AO ไปเลย)

ก็อปแบบไม่แตะข้อมูลอื่น เพราะ clear_and_paste_range clear เฉพาะช่วงคอลัมน์ตามความกว้างของ
DataFrame ที่ส่งเข้าไปเท่านั้น เรียก 2 รอบแยกกัน แต่ละรอบจึงไม่กระทบคอลัมน์นอกช่วงของตัวเองเลย
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client

BILL_AUTO_MATCH_APPROVE_TAB_GID = 986278133  # "Match Approve" (ไฟล์ Bill Auto เดิม ต้นทาง)
BILL_AUTO_CAL_STATUS_APPROVE_TAB_GID = 0  # "สถานะ Approve" (ไฟล์ Bill Auto Cal ปลายทาง)

SOURCE_START_ROW = 6  # ชีท Match Approve เริ่มข้อมูลที่แถว 6
DEST_START_ROW = 6  # ชีท สถานะ Approve เริ่มข้อมูลที่แถว 6 (ยืนยันจาก header แถว 5)

# (คอลัมน์เริ่มต้นต้นทาง 1-based, จำนวนคอลัมน์, คอลัมน์เริ่มต้นปลายทาง 1-based)
BLOCKS = [
    (3, 40, 1),   # Match Approve C(3):AP(42)  -> สถานะ Approve A(1):AN(40)
    (43, 21, 42), # Match Approve AQ(43):BK(63) -> สถานะ Approve AP(42):BJ(62) — ข้าม AO(41)
]


def get_bill_auto_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def get_bill_auto_cal_worksheet(gid: int):
    """สถานะ Approve/Rework/Check Bill Approve ย้ายไปอยู่ไฟล์ "Bill Auto Cal" แยกต่างหากแล้ว"""
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def main():
    source_ws = get_bill_auto_worksheet(BILL_AUTO_MATCH_APPROVE_TAB_GID)
    dest_ws = get_bill_auto_cal_worksheet(BILL_AUTO_CAL_STATUS_APPROVE_TAB_GID)

    for source_start_col, num_cols, dest_start_col in BLOCKS:
        print(f"[status-approve] กำลังอ่าน Match Approve คอลัมน์เริ่มที่ {source_start_col} "
              f"({num_cols} คอลัมน์) ...", flush=True)
        values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, source_start_col, num_cols)

        # ตัดแถวว่างท้ายๆ ทิ้ง
        while values and not any((cell or "").strip() for cell in values[-1]):
            values.pop()
        print(f"[status-approve] อ่านได้ {len(values)} แถว", flush=True)

        if not values:
            print("[status-approve] ไม่มีข้อมูลให้วางในบล็อกนี้ ข้ามไป", flush=True)
            continue

        normalized = [row + [""] * (num_cols - len(row)) for row in values]
        df = pd.DataFrame(normalized)

        needed_rows = DEST_START_ROW + len(df) - 1
        if dest_ws.row_count < needed_rows:
            print(f"[status-approve] ขยายชีท สถานะ Approve จาก {dest_ws.row_count} เป็น "
                  f"{needed_rows} แถว ...", flush=True)
            sheets_client.with_retry(lambda dest_ws=dest_ws, needed_rows=needed_rows: dest_ws.resize(rows=needed_rows))

        print(f"[status-approve] กำลังวาง {len(df)} แถว ที่ สถานะ Approve คอลัมน์เริ่มที่ "
              f"{dest_start_col} ...", flush=True)
        sheets_client.clear_and_paste_range(dest_ws, df, DEST_START_ROW, dest_start_col)

    print("[status-approve] เสร็จสิ้นทั้ง 2 บล็อก", flush=True)


if __name__ == "__main__":
    main()
