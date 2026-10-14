"""จุดรันหลักของ Flow Clean เส้น iTEC (Sale Inv View) -> แท็บ Cal

ดึงทั้งช่วงวันที่ 1 ของเดือนนี้ถึงเมื่อวานทีเดียว (po_date_range) ทำ 4 รอบค้นหาตามที่ยืนยัน
จาก Flow:
  1) Branch=0, Customer Name="ธันเดอร์ ฟินฟิน", ไม่มี Comment filter (ยืนยันจากผู้ใช้
     2026-09-17: ค้นด้วยชื่อเต็ม "ธันเดอร์ ฟินฟิน" แทน "ธันเดอร์" เฉยๆ)
  2) Branch=0, Customer Name="ยูฟัน", ไม่มี Comment filter
  3) Branch=0, Customer Name=ว่าง, Comment="UFund"
  4) Branch=0, Customer Name=ว่าง, Comment="Personal"
แต่ละรอบ append ต่อท้ายกันเข้าแท็บ Cal ตามลำดับ (ยืนยันจากผู้ใช้ว่า "วางต่อกันเลย") เฉพาะ
คอลัมน์ Invoice NO + Comment เท่านั้น (ดู clean.build_cal_dataframe)

⚠️ ยืนยันจากผู้ใช้ (2026-09-16): บริษัทเปลี่ยนชื่อจาก "บริษัท ธันเดอร์ ฟินฟิน" เป็น "ยูฟัน"
มีผลตั้งแต่ 15/9/2026 เป็นต้นไป — ข้อมูลวันที่ 1-14/9 ยังใช้ชื่อ "ธันเดอร์" เดิมอยู่ (ค้นเจอ
ด้วยรอบที่ 1) ส่วนวันที่ 15/9 เป็นต้นไปจะขึ้นชื่อ "ยูฟัน" แทน (ต้องเพิ่มรอบที่ 2 ใหม่นี้ไปค้นหา
ด้วย ไม่งั้นบิลของบริษัทใหม่จะหลุดหายไปจากแท็บ Cal ทั้งหมด) — คงรอบเดิม "ธันเดอร์" ไว้ด้วย
เพราะข้อมูลย้อนหลังในเดือนเดียวกัน (1-14/9) ยังต้องดึงติดมาด้วย

⚠️ ยืนยันเพิ่ม (2026-09-16 รอบ 2): แต่ละรอบ "ธันเดอร์"/"ยูฟัน" ใช้ **ช่วงวันที่ของตัวเอง**
ไม่ใช่ช่วงเดียวกันทั้งหมด — "ธันเดอร์" ยังค้นทั้งช่วง 1-Day-1 เหมือนเดิม (เพราะมีข้อมูลย้อนหลัง
ทั้งเดือนก่อน 15/9) ส่วน "ยูฟัน" ค้นเฉพาะตั้งแต่ COMPANY_RENAME_DATE (15/9) เป็นต้นไปเท่านั้น
(ไม่ค้นย้อนไปก่อนนั้น เพราะชื่อนี้ยังไม่มีอยู่จริงในระบบก่อนวันเปลี่ยนชื่อ) — ถ้าเดือนนี้ยังไม่ถึง
วันที่ 15 เลย (end < COMPANY_RENAME_DATE) จะข้ามรอบ "ยูฟัน" ไปทั้งรอบ ไม่ต้องเสียเวลา login
ค้นหาช่วงที่รู้อยู่แล้วว่างเปล่าแน่ๆ

ปิดโปรแกรม iTEC แล้วเปิดใหม่ทุกรอบค้นหา (login ใหม่ทุกครั้ง) กันปัญหาโปรแกรมค้างสะสมจากใช้
งานต่อเนื่อง (เจอจริง: หน้าต่างค้าง Not Responding พอทำต่อรอบที่ 2 ในหน้าต่างเดียวกัน —
เหมือนปัญหาที่เคยเจอกับ itec_desktop.py มาก่อน แก้ด้วยวิธีเดียวกันคือ kill แล้วเปิดใหม่)
"""

import csv
import re
import sys as _sys
from datetime import date, timedelta
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

import config
from clean import build_cal_dataframe
from date_utils import po_date_range
from itec_scraper import login_and_open_sale_inv_view, search_sale_inv_view, set_doc_date_range
from sheets_client import append_dataframe, clear_data_rows, get_cal_worksheet, get_headers


def _month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """แบ่งช่วง [start, end] เป็นก้อนตามเดือนปฏิทิน (ยืนยันจากผู้ใช้ 2026-09-30: ช่วงกว้างเกิน
    1 เดือน เช่นดึงย้อนหลังหลายเดือนพร้อมกัน — Sale Inv View ของ iTEC คืนแค่ไม่กี่แถวถ้าช่วง
    วันที่กว้างเกินไป (เจอจริง: ขอ 3 เดือนรวด ได้แค่ 3 แถว/รอบ ทั้งที่ควรมีหลักหมื่น) ต้องแบ่ง
    ดึงทีละเดือนปฏิทินแทนช่วงเดียวยาวๆ"""
    chunks = []
    cur = start
    while cur <= end:
        if cur.month == 12:
            next_month_start = date(cur.year + 1, 1, 1)
        else:
            next_month_start = date(cur.year, cur.month + 1, 1)
        chunk_end = min(next_month_start - timedelta(days=1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks

CAL_SHEET_URL = config.CAL_SHEET_URL

# ยืนยันจากผู้ใช้ (2026-09-16 รอบ 3): "อิงจาก iTEC" เป็นตัวตัดสิน ต้องดึงทุกวัน — เก็บผล
# เทียบ Customer(Name) จริงจากหน้า iTEC (คอลัมน์ที่มีอยู่แล้วในผลลัพธ์ดิบทุกรอบ แค่ไม่เคยเก็บไว้
# ก่อนหน้านี้ เพราะ build_cal_dataframe() กรองเหลือแค่ Invoice NO+Comment) กับชื่อที่ควรจะเป็น
# ตามวันที่ (ก่อน 15/9=ธันเดอร์, ตั้งแต่ 15/9=ยูฟัน) — ถ้าไม่ตรงกัน บันทึกไว้เป็น anomaly ลงไฟล์
# CSV ให้สเตจถัดไป (main_flag_company_name_anomalies.py) เอาไปต่อรวมเข้า "หน้าร้านแก้ไข" เอง
# (ไม่แตะ Cal/ITec/Match เลยจุดนี้ — แค่บันทึกผลเทียบไว้เฉยๆ)
ANOMALY_CSV_PATH = config.DOWNLOAD_DIR / "itec_company_name_anomalies.csv"

_THAI_DOC_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _parse_doc_date(doc_date_str: str) -> date | None:
    """แปลง Doc Date รูปแบบ 'อ. 15/09/2569 09:54:53' (วันย่อไทย + วัน/เดือน/ปี พ.ศ. + เวลา)
    เป็น date (ค.ศ.) — คืน None ถ้าแปลงไม่ได้ (กันพัง ไม่ throw)"""
    if not doc_date_str:
        return None
    m = _THAI_DOC_DATE_RE.search(str(doc_date_str))
    if not m:
        return None
    day, month, year_be = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year_be - 543, month, day)
    except ValueError:
        return None


def _expected_company_name(doc_date: date) -> str:
    """⚠️ เจอจริง 2026-09-16 (บั๊กรอบ 2 — flag ผิดหมดทุกแถวอีกรอบ): Customer(Name) จริงจากหน้า
    iTEC ถูก mask ตัด ณ ความยาวตัวอักษรคงที่ (ไม่ใช่ตัดตามคำ) ผลคือ "ธันเดอร์" กลายเป็น "ธันเดอร"
    (ตัวสุดท้าย "์" หายไปพอดี) เช่น "บริษัท ธันเดอร *****" — ใช้ "ธันเดอร" (ไม่มี ์) เทียบแทน
    กันโดนตัดคำผิดแบบนี้อีก (ยังพอเป็นคำเฉพาะพอที่จะไม่ชนกับชื่ออื่นโดยบังเอิญ)"""
    return "ยูฟัน" if doc_date >= COMPANY_RENAME_DATE else "ธันเดอร"


def find_company_name_anomalies(raw_df) -> list[dict]:
    """เทียบ Customer(Name) จริง (จากผลลัพธ์ดิบของรอบค้นหานี้) กับชื่อที่ควรจะเป็นตาม Doc Date
    ของแถวนั้นเอง — คืนลิสต์ของแถวที่ไม่ตรง (anomaly) เก็บเฉพาะคอลัมน์ที่จำเป็นต่อการตามหาแถว
    ต่อ (Invoice NO, Doc Date, Customer(Name) จริง, ชื่อที่ควรเป็น) — ข้ามแถวที่ Customer(Name)
    ว่าง/parse Doc Date ไม่ได้ (ไม่ใช่ anomaly แค่ข้อมูลไม่ครบเฉยๆ)

    ⚠️ เจอจริง 2026-09-16 (บั๊กรอบ 1 — flag ผิดไป ~20,000 แถว): เช็คนี้ใช้ได้แค่กับลูกค้า
    ที่เป็น**บริษัทเช่าซื้อ** (Customer(Name) ขึ้นต้นด้วย "บริษัท") เท่านั้น — แถวส่วนใหญ่เป็น
    ลูกค้า Personal/บุคคลทั่วไป (ชื่อคน ไม่ใช่ชื่อบริษัท) ซึ่งไม่มีทางมีคำว่า "ธันเดอร"/"ยูฟัน"
    อยู่แล้วโดยธรรมชาติ ถ้าไม่กรองตรงนี้ก่อนจะโดน flag เป็น anomaly ผิดหมดทุกแถว — ต้องข้าม
    แถวที่ Customer(Name) ไม่ได้ขึ้นต้นด้วย "บริษัท" ไปเลย ไม่เช็คต่อ

    ⚠️ เจอเพิ่ม (2026-09-16 รอบ 3 — ทดสอบยิงจริงเจอ false positive 2 แถว): มีบริษัทอื่นที่ไม่ใช่
    ธันเดอร์/ยูฟันเลย (เช่น "บริษัท ทริ้ปเปิล ธ *****") หลุดเข้ามาในผลค้นหาด้วย (ค้นหาฝั่ง iTEC
    เอง match แบบกว้างกว่าที่คิด) — ถ้าเช็คแค่ "ขึ้นต้นด้วยบริษัท" จะโดน flag ผิดว่า "ควรเป็น
    ธันเดอร" ทั้งที่จริงเป็นบริษัทอื่นที่ไม่เกี่ยวกันเลย ต้องเช็คเพิ่มว่าชื่อนั้น**มีคำว่า "ธันเดอร"
    หรือ "ยูฟัน" อยู่จริงๆ** ก่อน ถึงจะถือว่าเกี่ยวกับการเปลี่ยนชื่อบริษัทนี้ ไม่งั้นข้ามไปเลย"""
    if "Customer(Name)" not in raw_df.columns or "Doc Date" not in raw_df.columns:
        return []
    anomalies = []
    for _, row in raw_df.iterrows():
        customer_name = str(row.get("Customer(Name)", "") or "").strip()
        if not customer_name.startswith("บริษัท"):
            continue  # ลูกค้า Personal/บุคคลทั่วไป — ไม่เกี่ยวกับชื่อบริษัทเช่าซื้อเลย ข้ามไป
        if "ธันเดอร" not in customer_name and "ยูฟัน" not in customer_name:
            continue  # บริษัทอื่นที่ไม่เกี่ยวกับการเปลี่ยนชื่อนี้เลย (เช่น หลุดมาจากการค้นหากว้าง)
        doc_date = _parse_doc_date(row.get("Doc Date", ""))
        if doc_date is None:
            continue
        expected = _expected_company_name(doc_date)
        if expected not in customer_name:
            anomalies.append({
                "Invoice NO": str(row.get("Invoice NO", "") or "").strip(),
                "Doc Date": doc_date.isoformat(),
                "Customer Name (จริง)": customer_name,
                "ควรจะเป็น": expected,
            })
    return anomalies


def _write_anomalies_csv(anomalies: list[dict]) -> None:
    ANOMALY_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ANOMALY_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["Invoice NO", "Doc Date", "Customer Name (จริง)", "ควรจะเป็น"])
        w.writeheader()
        w.writerows(anomalies)
    print(f"[iTEC] บันทึก company-name anomaly {len(anomalies)} รายการไว้ที่ {ANOMALY_CSV_PATH}", flush=True)

# วันที่บริษัทเปลี่ยนชื่อ "บริษัท ธันเดอร์ ฟินฟิน" -> "ยูฟัน" (ยืนยันจากผู้ใช้ 2026-09-16)
# ต้องตรงกับ ITEC_MIS_MEMBER_NAME_CUTOFF ใน clean.py (คนละที่ คนละชนิดตัวแปร เลยแยกนิยามไว้)
COMPANY_RENAME_DATE = date(2026, 9, 15)

# "start_override" (ถ้ามี) = บังคับวันเริ่มของรอบนั้นเป็นค่านี้แทน start ของ po_date_range()
# ไม่ใส่ = ใช้ค่า start ปกติ (เต็มช่วง 1-Day-1)
SEARCHES = [
    {"customer_name": "ธันเดอร์ ฟินฟิน", "comment": ""},
    {"customer_name": "ยูฟัน", "comment": "", "start_override": COMPANY_RENAME_DATE},
    {"customer_name": "", "comment": "UFund"},
    {"customer_name": "", "comment": "Personal"},
]


def main():
    print("=" * 60)
    print("1) เชื่อมต่อ Google Sheet 'Bill Auto' แท็บ Cal ...")
    ws = get_cal_worksheet()
    headers = get_headers(ws)
    print(f"   เชื่อมต่อสำเร็จ (หัวตาราง {len(headers)} คอลัมน์)")

    start, end = po_date_range()
    print(f"ช่วงวันที่: {start} ถึง {end} — ทำทั้งหมด {len(SEARCHES)} รอบ")

    print("2) ลบข้อมูลเก่าออกก่อน (กันสะสมซ้ำทุกรอบที่รัน — ลบครั้งเดียวก่อน 3 รอบค้นหา "
          "ไม่ใช่ลบทุกรอบ ไม่งั้นรอบหลังจะลบรอบก่อนหน้าในรันเดียวกันทิ้ง) ...")
    clear_data_rows(ws)

    total_appended = 0
    all_anomalies: list[dict] = []
    for i, params in enumerate(SEARCHES, start=1):
        print("=" * 60)
        print(f"รอบ {i}/{len(SEARCHES)}: Customer Name={params['customer_name']!r} "
              f"Comment={params['comment']!r}")

        round_start = max(start, params.get("start_override", start))
        if round_start > end:
            print(f"   ข้ามรอบนี้ไปเลย — ช่วงวันที่ของรอบนี้เริ่มหลัง Day-1 ({round_start} > {end}) "
                  f"แปลว่ายังไม่ถึงวันที่ที่ชื่อนี้เริ่มมีข้อมูลจริงในเดือนนี้")
            continue

        month_chunks = _month_chunks(round_start, end)
        if len(month_chunks) > 1:
            print(f"   ช่วงวันที่รอบนี้กว้างเกิน 1 เดือน — แบ่งดึงทีละเดือนปฏิทิน "
                  f"({len(month_chunks)} ก้อน) กันข้อมูลหาย", flush=True)

        for ci, (chunk_start, chunk_end) in enumerate(month_chunks, start=1):
            if len(month_chunks) > 1:
                print(f"   -- ก้อนเดือนที่ {ci}/{len(month_chunks)}: {chunk_start} ถึง {chunk_end} --",
                      flush=True)

            print("2) Login iTEC + เปิด Sale Inv View (instance ใหม่) ...")
            app, win = login_and_open_sale_inv_view()
            print("   เปิดสำเร็จ พร้อมค้นหา")

            try:
                set_doc_date_range(win, chunk_start, chunk_end)

                raw_df = search_sale_inv_view(
                    win, customer_name=params["customer_name"], comment=params["comment"]
                )
                print(f"   >> ค้นหา+คัดลอกสำเร็จ: เจอ {len(raw_df)} แถว (ยังไม่วางลงชีท)")

                round_anomalies = find_company_name_anomalies(raw_df)
                if round_anomalies:
                    print(f"   !! พบ Customer(Name) ไม่ตรงกับที่ควรเป็นตามวันที่ {len(round_anomalies)} "
                          f"รายการ ในรอบนี้", flush=True)
                all_anomalies.extend(round_anomalies)

                df = build_cal_dataframe(raw_df, headers)
                print(f"3) กำลังวางข้อมูลลง Google Sheet แท็บ Cal ({len(df)} แถว) ...")
                append_dataframe(ws, df)
                total_appended += len(df)
                print(f"   >> วางลงชีทสำเร็จแล้ว! (สะสม {total_appended} แถวจนถึงตอนนี้)")
            finally:
                print("   ปิดโปรแกรม iTEC (จะเปิดใหม่รอบ/ก้อนถัดไป) ...")
                app.kill()

    _write_anomalies_csv(all_anomalies)

    print("=" * 60)
    print(f"เสร็จสิ้นทั้งหมด — เติมข้อมูลรวม {total_appended} แถวลงแท็บ Cal แล้ว")
    print(f"เช็คผลได้ที่: {CAL_SHEET_URL}")


if __name__ == "__main__":
    main()
