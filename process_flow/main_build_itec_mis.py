"""ดึงข้อมูลจากชีท "ITec Mis" (ไฟล์ "Bill Auto Data" — ย้ายมาจากไฟล์ Bill Auto เดิมเพราะเต็ม,
คอลัมน์ A-AG) มาวางที่คอลัมน์ D-AJ ของชีท "ITEC-MIS" (ไฟล์ Bill Auto เดิม) แล้วคำนวณคอลัมน์
A, B, C ด้วย cal.py แทนสูตร Google Sheets

คอลัมน์ A-AG ของ "ITec Mis" เลื่อนไปตรงๆ 3 ตำแหน่งกลายเป็น D-AJ ของ "ITEC-MIS"
(A->D, B->E, ..., AG->AJ) ไม่มีการแปลงค่าใดๆ เป็นการก็อปดิบๆ
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client
from cal import (
    add_itec_mis_derived_columns,
    build_itec_manual_customer_lookup,
    build_itec_manual_lookup,
    build_itec_mis_lookup_frame,
)

ROW_LIMIT = None  # None = ดึงทั้งหมด (ดูจาก row_count จริงของชีทต้นทาง)

BILL_AUTO_DATA_ITEC_MIS_RAW_TAB_GID = 758708639  # "ITec Mis" (ไฟล์ Bill Auto Data ต้นทาง คอลัมน์ A-AG)
BILL_AUTO_ITEC_MIS_DEST_TAB_GID = 1505175949  # "ITEC-MIS" (ไฟล์ Bill Auto เดิม ปลายทาง)
BILL_AUTO_ITEC_MANUAL_TAB_GID = 1038840941  # "ITEC MANNUAL" (ไฟล์ Bill Auto เดิม สำหรับ lookup คอลัมน์ C)

DEST_START_ROW = 2  # header อยู่แค่แถว 1 เท่านั้น ข้อมูลเริ่มแถว 2 เลย ไม่มีแถวเว้น
SHIFT = 3  # A(1) -> D(4)


def get_bill_auto_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def get_bill_auto_data_worksheet(gid: int):
    """ITec Mis ย้ายไปอยู่ไฟล์ "Bill Auto Data" แยกต่างหากแล้ว"""
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_DATA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def shift_columns(df: pd.DataFrame, shift: int) -> pd.DataFrame:
    """เปลี่ยนชื่อคอลัมน์ตัวอักษร A,B,C... ให้เลื่อนไป `shift` ตำแหน่ง (เช่น A->D ถ้า shift=3)"""
    from cal import _col_letter

    old_letters = list(df.columns)
    new_letters = [_col_letter(i + 1 + shift) for i in range(len(old_letters))]
    return df.rename(columns=dict(zip(old_letters, new_letters)))


def main():
    source_ws = get_bill_auto_data_worksheet(BILL_AUTO_DATA_ITEC_MIS_RAW_TAB_GID)
    end_row = (1 + ROW_LIMIT) if ROW_LIMIT else source_ws.row_count
    print(f"[itec-mis] กำลังอ่าน 'ITec Mis' แถว 2 ถึง {end_row} (คอลัมน์ A-AG) ...", flush=True)
    raw = sheets_client.with_retry(lambda: source_ws.get(f"A2:AG{end_row}"), tries=6, delay=20)
    source_df = build_itec_mis_lookup_frame(raw, num_cols=33)  # A..AG = 33 คอลัมน์
    print(f"[itec-mis] อ่านได้ {len(source_df)} แถว", flush=True)

    shifted = shift_columns(source_df, SHIFT)  # A->D, B->E, ..., AG->AJ

    print("[itec-mis] กำลังอ่าน 'ITEC MANNUAL' สำหรับจับคู่คอลัมน์ C + AK ...", flush=True)
    manual_ws = get_bill_auto_worksheet(BILL_AUTO_ITEC_MANUAL_TAB_GID)
    manual_raw = sheets_client.with_retry(lambda: manual_ws.get(f"A2:C{manual_ws.row_count}"))
    manual_df = pd.DataFrame(
        [row + [""] * (3 - len(row)) for row in manual_raw], columns=["A", "B", "C"]
    )
    manual_lookup = build_itec_manual_lookup(manual_df)
    # ⚠️ ยืนยันจากผู้ใช้ (2026-09-16): เพิ่ม lookup Customer(Name) จริงจาก iTEC (คอลัมน์ C ของ
    # ITEC MANNUAL) ไปเติมคอลัมน์ AK ของ ITEC-MIS ด้วย — ใช้ตรวจ anomaly เปลี่ยนชื่อบริษัท
    # (ธันเดอร์/ยูฟัน) ใน cal.py โซน 2 (ดู _customer_name_check())
    manual_customer_lookup = build_itec_manual_customer_lookup(manual_df)
    print(f"[itec-mis] อ่าน ITEC MANNUAL ได้ {len(manual_df)} แถว", flush=True)

    print("[itec-mis] กำลังคำนวณคอลัมน์ A, B, C, AK ...", flush=True)
    result = add_itec_mis_derived_columns(shifted, manual_lookup, manual_customer_lookup)

    # จัดลำดับคอลัมน์ A,B,C,D,...,AJ,AK (37 คอลัมน์) ให้ตรงกับชีทปลายทาง — AK เพิ่มเข้ามา
    # 2026-09-16 (Customer(Name) จริงจาก iTEC สำหรับตรวจ anomaly เปลี่ยนชื่อบริษัท)
    from cal import _col_letter

    full_columns = [_col_letter(i) for i in range(1, 38)]  # A..AK
    ordered = result.reindex(columns=full_columns, fill_value="")

    print(f"[itec-mis] กำลังวางผลลัพธ์ {len(ordered)} แถว ที่ชีท ITEC-MIS (ไฟล์ Bill Auto) ...", flush=True)
    dest_ws = get_bill_auto_worksheet(BILL_AUTO_ITEC_MIS_DEST_TAB_GID)
    sheets_client.clear_and_paste_range(dest_ws, ordered, DEST_START_ROW, 1)

    print("[itec-mis] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
