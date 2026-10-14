"""ดึงข้อมูลจากชีท "K2+ITOS" (ไฟล์ Bill Auto) มาคำนวณคอลัมน์ Phy/ID + จับคู่กับ ITEC MIS
ด้วย cal.py (แทนสูตร Google Sheets ที่หนักมาก) แล้ววางผลลัพธ์ที่ชีท "Match" ของไฟล์ Bill Auto
(ตอนนี้ว่างอยู่ — เป็นแท็บใหม่สำหรับ pipeline นี้โดยเฉพาะ)

ตัวเลข ROW_LIMIT ควบคุมว่าจะทำกี่แถว (ใช้ทดสอบก่อนด้วยจำนวนน้อยๆ ก่อนขยายเป็นทั้งหมด)
ITEC MIS ที่ใช้จับคู่ยังคงอ่านจากไฟล์ Match เดิม (MATCH_FILE_ID) เพราะเป็นต้นฉบับที่สูตรอ้างอิง
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client
from cal import (
    add_itec_mis_fallback_match_columns,
    add_itec_mis_primary_match_columns,
    add_phy_id_columns,
    build_itec_mis_lookup_frame,
    compute_ax,
    compute_ay,
    compute_source_system,
)

ROW_LIMIT = None  # None = ดึงทั้งหมด (ดูจาก row_count จริงของชีทต้นทาง)

BILL_AUTO_MATCH_TAB_GID = 899495725
BILL_AUTO_K2_ITOS_TAB_GID = 0
DEST_START_ROW = 6  # ชีท Match เริ่มข้อมูลที่แถว 6 (ยืนยันแล้ว)

# ลำดับคอลัมน์เต็มของชีท Match (A ถึง BU) — ต้องวางตามลำดับนี้เป๊ะ
FULL_COLUMN_ORDER = [
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


def get_bill_auto_data_worksheet(gid: int):
    """K2+ITOS ย้ายไปอยู่ไฟล์ "Bill Auto Data" แยกต่างหากแล้ว (ไฟล์ Bill Auto เดิมจะเต็ม)"""
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_DATA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


BILL_AUTO_ITEC_MIS_TAB_GID = 1505175949  # "ITEC-MIS" (สร้างจาก main_build_itec_mis.py)


def main():
    k2itos_ws = get_bill_auto_data_worksheet(BILL_AUTO_K2_ITOS_TAB_GID)
    headers = k2itos_ws.row_values(1)
    end_row = (1 + ROW_LIMIT) if ROW_LIMIT else k2itos_ws.row_count
    print(f"[build] กำลังอ่าน K2+ITOS แถว 2 ถึง {end_row} ...", flush=True)
    raw_full = sheets_client.with_retry(lambda: k2itos_ws.get(f"A2:AG{end_row}"), tries=6, delay=20)
    df = pd.DataFrame(
        [row + [""] * (len(headers) - len(row)) for row in raw_full], columns=headers
    )
    # K2+ITOS มีคอลัมน์ "Application Status" ซ้ำท้ายสุด (คอลัมน์เปล่า ไม่ได้ใช้งาน) —
    # ตัดทิ้งกันชื่อคอลัมน์ซ้ำ (เก็บตัวแรกไว้) ไม่งั้น reindex ท้ายสุดจะ error
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    print(f"[build] อ่านได้ {len(df)} แถว", flush=True)

    print("[build] กำลังอ่าน ITEC-MIS (ไฟล์ Bill Auto) เพื่อใช้จับคู่ ...", flush=True)
    itec_mis_ws = get_bill_auto_worksheet(BILL_AUTO_ITEC_MIS_TAB_GID)
    # ⚠️ ยืนยันจากผู้ใช้ (2026-09-16): อ่านถึง AK แทน AJ — คอลัมน์ AK ใหม่เก็บ Customer(Name)
    # จริงจาก iTEC ไว้ตรวจ anomaly เปลี่ยนชื่อบริษัท (ดู _customer_name_check() ใน cal.py)
    itec_mis_raw = sheets_client.with_retry(
        lambda: itec_mis_ws.get(f"A6:AK{itec_mis_ws.row_count}"), tries=6, delay=20
    )
    itec_mis = build_itec_mis_lookup_frame(itec_mis_raw, num_cols=37)
    print(f"[build] อ่าน ITEC-MIS ได้ {len(itec_mis)} แถว", flush=True)

    print("[build] กำลังคำนวณคอลัมน์ Phy/ID ...", flush=True)
    df = add_phy_id_columns(df)

    print("[build] กำลังคำนวณจับคู่หลักกับ ITEC MIS ...", flush=True)
    df = add_itec_mis_primary_match_columns(df, itec_mis)
    df["AX"] = df.apply(
        lambda r: compute_ax(r["AI"], {k: r[k] for k in ["AQ", "AR", "AS", "AT", "AU", "AV", "AW"]}),
        axis=1,
    )

    print("[build] กำลังคำนวณจับคู่สำรองกับ ITEC MIS ...", flush=True)
    df = add_itec_mis_fallback_match_columns(df, itec_mis)
    df["AY"] = df.apply(lambda r: compute_ay(r["AX"], r["BN"]), axis=1)

    df["BU"] = df["Contract Number"].map(compute_source_system)
    df["_blank28"] = ""

    print("[build] กำลังจัดเรียงคอลัมน์ให้ตรงกับชีท Match ...", flush=True)
    ordered = df.reindex(columns=FULL_COLUMN_ORDER, fill_value="")

    dest_ws = get_bill_auto_worksheet(BILL_AUTO_MATCH_TAB_GID)

    # กันชีท Match grid เล็กเกินไปแล้ว paste ทับพัง (เจอจริง: Max rows: 5005 ตอนข้อมูลเยอะขึ้น)
    needed_rows = DEST_START_ROW + len(ordered) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[build] ขยายชีท Match จาก {dest_ws.row_count} เป็น {needed_rows} แถว ...",
              flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[build] กำลังวางผลลัพธ์ {len(ordered)} แถว ที่ชีท Match (ไฟล์ Bill Auto) ...", flush=True)
    sheets_client.clear_and_paste_range(dest_ws, ordered, DEST_START_ROW, 1)

    print("[build] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
