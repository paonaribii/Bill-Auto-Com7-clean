"""อ่านชีท "Match" (ไฟล์ Bill Auto, คำนวณด้วย cal.py ไปแล้ว) มาสร้างชีท "ถูกทั้งหมด รอ Confirm"
(ไฟล์ Bill Auto เช่นกัน, gid=857579518) ด้วย cal.build_confirm_from_match()

⚠️ คนละแท็บกับ "Match Approve"/"Match Rework" โดยสิ้นเชิง — ไม่ได้กรองด้วย Application Status
แต่กรองด้วย Match!AY=="ถูกต้องทั้งหมด" AND Match!"Application Status"=="ลูกหนี้ปกติ" (ยืนยันจาก
สูตรจริงในไฟล์ต้นฉบับ (Bill Auto) แท็บ "ถูกทั้งหมด รอ Confirm")

มี 2 บล็อกอิสระ ยาวไม่เท่ากัน เขียนแยกช่วงคอลัมน์กันคนละครั้ง (เริ่มแถวเดียวกันแต่ไม่ทับกัน):
  1. main (A:BL, 64 คอลัมน์) — กรอง AY+AE
  2. bm (BM, 1 คอลัมน์)      — กรอง AY เงื่อนไขเดียว
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client
from cal import build_confirm_from_match

BILL_AUTO_MATCH_TAB_GID = 899495725  # "Match" (ต้นทาง)
BILL_AUTO_CONFIRM_TAB_GID = 857579518  # "ถูกทั้งหมด รอ Confirm" (ปลายทาง)

SOURCE_START_ROW = 6  # ชีท Match เริ่มข้อมูลที่แถว 6
DEST_START_ROW = 6  # ชีท ถูกทั้งหมด รอ Confirm เริ่มข้อมูลที่แถว 6 (header แถว 5 เหมือน Match Approve)

# ลำดับคอลัมน์เต็มของชีท Match (A ถึง BU) — ต้องตรงกับที่ main_build_match_bill_auto.py เขียนไว้
FULL_MATCH_COLUMN_ORDER = [
    "Phy", "ID", "PO DATE", "PO NUMBER", "Branch ID", "PRODUCT BRAND", "PRODUCT CATEGORY",
    "PRODUCT SERIES", "Phy ID (ใบกำกับภาษีอย่างย่อ)", "Serial Number", "Contract Start",
    "Contract Number", "SUM AMOUNT \n(ราคาเครื่อง)", "ACSPRICE \n(ราคาอุปกรณ์เสริม)", "SUMPRICE",
    "AMOUNT", "VAT AMOUNT", "เงินดาวน์ก่อน VAT", "เงินดาวน์ VAT\n", "ยอดรวมเงินดาวน์",
    "Trade in ก่อน VAT", "Trade in\nVAT", "ยอดรวม Trade in", "ยอดรวมหักเงินดาวน์ก่อน VAT",
    "ยอดรวมหักเงินดาวน์ VAT", "ยอดรวม\nหักเงินดาวน์", "APPLICATION NUMBER", "_blank28", "APP ID",
    "PO Status", "Application Status", "Contract Status", "INV PN NUMBER (ใบกำกับภาษีเต็มรูปแบบ)",
    "TAX DATE",
    "AI", "AJ", "AK", "AL", "AM", "AN", "AO", "AP", "AQ", "AR", "AS", "AT", "AU", "AV", "AW",
    "AX", "AY", "AZ", "BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK", "BL",
    "BM", "BN", "BO", "BP", "BQ", "BR", "BS", "BT", "BU",
]


def get_bill_auto_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def _col_letter(n: int) -> str:
    letters = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def main():
    print("[confirm] กำลังอ่านชีท Match (ไฟล์ Bill Auto) ...", flush=True)
    source_ws = get_bill_auto_worksheet(BILL_AUTO_MATCH_TAB_GID)
    raw = sheets_client.with_retry(
        lambda: source_ws.get(f"A{SOURCE_START_ROW}:BU{source_ws.row_count}"), tries=6, delay=20
    )
    normalized = [row + [""] * (73 - len(row)) for row in raw]
    match_df = pd.DataFrame(normalized, columns=FULL_MATCH_COLUMN_ORDER)
    print(f"[confirm] อ่านได้ {len(match_df)} แถว", flush=True)

    print("[confirm] กำลังกรอง AY=ถูกต้องทั้งหมด + AE=ลูกหนี้ปกติ + จัดเรียงคอลัมน์ ...", flush=True)
    blocks = build_confirm_from_match(match_df)
    dest_ws = get_bill_auto_worksheet(BILL_AUTO_CONFIRM_TAB_GID)

    # กันชีท ถูกทั้งหมด รอ Confirm grid เล็กเกินไปแล้ว paste ทับพัง (เจอจริง 2026-09-08: Max
    # rows 40005 ตอนข้อมูลย้อนหลังยาว ๆ ทำให้ Match ใหญ่กว่าเดิมมาก)
    max_block_rows = max(len(blocks[name]) for name in ("main", "bm"))
    needed_rows = DEST_START_ROW + max_block_rows - 1
    if dest_ws.row_count < needed_rows:
        print(f"[confirm] ขยายชีท ถูกทั้งหมด รอ Confirm จาก {dest_ws.row_count} เป็น "
              f"{needed_rows} แถว ...", flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    for name, start_col, num_cols in (("main", 1, 64), ("bm", 65, 1)):
        df_block = blocks[name]
        full_columns = [_col_letter(i) for i in range(start_col, start_col + num_cols)]
        ordered = df_block.reindex(columns=full_columns, fill_value="")
        print(f"[confirm] เหลือ {len(ordered)} แถวในบล็อก {name} "
              f"({full_columns[0]}:{full_columns[-1]})", flush=True)
        sheets_client.clear_and_paste_range(dest_ws, ordered, DEST_START_ROW, start_col)

    print("[confirm] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
