"""จุดรันหลักของ Flow Clean (เฉพาะเส้น K-2 + ITOS ตอนนี้)"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

import config
import sheets_client
from clean import build_k2_itos_dataframe
from date_utils import _today, format_thai_style
from itos_scraper import download_itos_export_report
from k2_scraper import download_k2_po_report
from sheets_client import append_dataframe, clear_data_rows, get_headers, get_k2_itos_worksheet

# ยืนยันจากผู้ใช้ (2026-09-08): ต้องเขียนทับตาราง "สถานะ PO ที่ Approve แล้วยังไม่เกิดสัญญา"
# ที่มีอยู่แล้วในชีท "Summary" (ไฟล์ Bill Auto Cal — ไม่ใช่ "สรุป" ในไฟล์ Bill Auto) ตรงแถว
# 17-24 เลย (เดิมกรอกมือ) ไม่ใช่สร้างตารางใหม่แยกต่างหาก — เพิ่มแถว 24 "รอลงทะเบียนสินค้า"
# เข้ามาด้วย (2026-09-09) หลังพบว่ายอดรวม Approve ไม่ตรงเพราะไม่เคย track แถวนี้มาก่อน
#
# ⚠️ ยืนยันจากผู้ใช้ (2026-09-17): เจอว่าค่าที่ Python เขียนตรงๆ (นับดิบจาก K2+ITOS "ก่อนเข้า
# Match") กับตัวเลขจริงใน "Bill K2 Kill" (หลัง Match dedup แล้ว) ไม่ตรงกัน — เช่น "ลูกหนี้ปกติ"
# 20,120 (K2+ITOS ดิบ มีแถวซ้ำ 1 แถวจริงๆ จากไฟล์ K2 ดิบ) vs 20,119 (Bill K2 Kill หลัง dedup)
# แก้โดยเปลี่ยนแถว 17,18,19,20,21,22,23,25 (ทุกแถวยกเว้น Reject) ให้เป็นสูตร Google Sheets
# COUNTIFS('Bill K2 Kill'!$AD:$AD, ...) อ้างอิงจาก Bill K2 Kill โดยตรงแทน (เหมือนตารางด้านบน
# "Com7 รวม" ที่ทำอยู่แล้ว) — Python เลยไม่ต้องเขียนแถวพวกนี้อีกต่อไป
#
# ⚠️ ข้อยกเว้น: แถว "Reject" (24) ยังต้องให้ Python เขียนอยู่ เพราะบิล Reject **ถูกลบทิ้งจาก
# K2+ITOS/Match/Bill K2 Kill ไปเลย** ตาม apply_application_status_approve() (ดู clean.py) —
# ไม่มีที่ไหนให้สูตร COUNTIFS อ้างอิงได้อีกแล้วหลังจากขั้นตอนนี้ ต้องนับตอนอยู่ในหน่วยความจำ
# ก่อนถูกลบเท่านั้น (count_summary_table_rows() ใน clean.py)
BILL_AUTO_CAL_SUMMARY_TAB_GID = 1595770846  # "Summary" (ไฟล์ Bill Auto Cal)
SUMMARY_TABLE_DATE_CELL = "D14"  # วันที่ "ณ ปัจจุบัน" กำกับหัวตาราง
SUMMARY_TABLE_REJECT_ROW = 24  # แถวเดียวที่ยังเขียนด้วย Python (ค่า Reject ก่อนถูกลบทิ้ง)
SUMMARY_TABLE_COUNT_COL = "E"  # คอลัมน์ "จำนวนบิล"


def _write_summary_table(counts: dict) -> None:
    """อัปเดตวันที่กำกับหัวตาราง (D14) + เขียนเฉพาะ E24 (Reject) ด้วยค่านิ่งจาก Python —
    แถวอื่นๆ ในตารางนี้เป็นสูตร COUNTIFS อ้างอิง 'Bill K2 Kill'!AD โดยตรงแล้ว (ยืนยันจากผู้ใช้
    2026-09-17) ไม่ต้องเขียนทับอีก"""
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    ws = sh.get_worksheet_by_id(BILL_AUTO_CAL_SUMMARY_TAB_GID)

    today_str = format_thai_style(_today())
    sheets_client.with_retry(
        lambda: ws.update([[today_str]], SUMMARY_TABLE_DATE_CELL, value_input_option="USER_ENTERED")
    )

    sheets_client.with_retry(
        lambda: ws.update(
            [[counts.get("Reject", 0)]],
            f"{SUMMARY_TABLE_COUNT_COL}{SUMMARY_TABLE_REJECT_ROW}",
            value_input_option="USER_ENTERED",
        )
    )


def main():
    print("1) ดาวน์โหลดไฟล์ K-2 ...")
    k2_path = download_k2_po_report()

    print("2) ดาวน์โหลดไฟล์ ITOS ...")
    itos_path = download_itos_export_report()

    print("3) เชื่อมต่อ Google Sheet 'Bill Auto' แท็บ K2+ITOS ...")
    ws = get_k2_itos_worksheet()
    headers = get_headers(ws)

    print("4) คลีน + รวมข้อมูล K-2 กับ ITOS ...")
    combined, summary_counts = build_k2_itos_dataframe(k2_path, itos_path, headers)

    print(f"4.5) บันทึกค่า Reject ของวันนี้ลงตาราง Summary (E24 เท่านั้น แถวอื่นเป็นสูตรแล้ว): "
          f"{summary_counts.get('Reject', 0)} ...")
    _write_summary_table(summary_counts)

    print("5) ลบข้อมูลเก่าออกก่อน (กันสะสมซ้ำทุกรอบที่รัน) ...")
    clear_data_rows(ws)

    print("6) เติมข้อมูลใหม่เข้า Google Sheet ...")
    append_dataframe(ws, combined)

    print("เสร็จสิ้น")


if __name__ == "__main__":
    main()
