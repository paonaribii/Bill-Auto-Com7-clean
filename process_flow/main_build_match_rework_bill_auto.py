"""อ่านชีท "Match" (ไฟล์ Bill Auto, คำนวณด้วย cal.py ไปแล้ว) มากรอง Application Status =
"Rework" + จัดเรียงคอลัมน์ใหม่ด้วย cal.build_match_approve_from_match(status="Rework") แล้ว
วางผลลัพธ์ที่ชีท "Match Rework" (ไฟล์ Bill Auto เช่นกัน)

เหมือนกับ main_build_match_approve_bill_auto.py เป๊ะ ต่างกันแค่สถานะที่กรอง (Rework แทน Approve)
และปลายทางคนละแท็บ
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client
from cal import build_match_approve_from_match

BILL_AUTO_MATCH_TAB_GID = 899495725  # "Match" (ต้นทาง)
BILL_AUTO_MATCH_REWORK_TAB_GID = 1911390378  # "Match Rework" (ปลายทาง)

SOURCE_START_ROW = 6  # ชีท Match เริ่มข้อมูลที่แถว 6
DEST_START_ROW = 6  # ให้ตรงกับโครงสร้างเดิมของ Match Rework (ปรับได้ถ้าจริงไม่ตรง)

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
    print("[match-rework] กำลังอ่านชีท Match (ไฟล์ Bill Auto) ...", flush=True)
    source_ws = get_bill_auto_worksheet(BILL_AUTO_MATCH_TAB_GID)
    raw = sheets_client.with_retry(
        lambda: source_ws.get(f"A{SOURCE_START_ROW}:BU{source_ws.row_count}"), tries=6, delay=20
    )
    normalized = [row + [""] * (73 - len(row)) for row in raw]
    match_df = pd.DataFrame(normalized, columns=FULL_MATCH_COLUMN_ORDER)
    print(f"[match-rework] อ่านได้ {len(match_df)} แถว", flush=True)

    print("[match-rework] กำลังกรอง Application Status = Rework + จัดเรียงคอลัมน์ ...", flush=True)
    result = build_match_approve_from_match(match_df, status="Rework")
    print(f"[match-rework] เหลือ {len(result)} แถวที่ Rework", flush=True)

    # จัดลำดับคอลัมน์ A ถึง BM (65 คอลัมน์) ให้ตรงกับชีทปลายทาง
    full_columns = [_col_letter(i) for i in range(1, 66)]  # A..BM
    ordered = result.reindex(columns=full_columns, fill_value="")

    dest_ws = get_bill_auto_worksheet(BILL_AUTO_MATCH_REWORK_TAB_GID)

    # กันชีท Match Rework grid เล็กเกินไปแล้ว paste ทับพัง
    needed_rows = DEST_START_ROW + len(ordered) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[match-rework] ขยายชีท Match Rework จาก {dest_ws.row_count} เป็น "
              f"{needed_rows} แถว ...", flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[match-rework] กำลังวางผลลัพธ์ {len(ordered)} แถว ที่ชีท Match Rework (ไฟล์ Bill Auto) ...", flush=True)
    sheets_client.clear_and_paste_range(dest_ws, ordered, DEST_START_ROW, 1)

    print("[match-rework] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
