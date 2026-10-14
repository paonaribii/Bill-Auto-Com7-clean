"""ขั้น Check Bill Approve (ส่วน ITOS): อ่าน APPLICATION NUMBER รูปแบบ ITOS (มีขีด เช่น
202601-000001) จากชีท "Check Bill Approve" แล้วจับคู่กับไฟล์ ITOS ที่ดาวน์โหลดไว้แล้ว
(clean_flow/itos_scraper.py) ด้วยคอลัมน์ "Application Number" จากนั้นเอาค่า "Application
Status" ในไฟล์นั้น (ผ่าน STATUS_MAP ก่อน) มาเขียนกลับเข้าคอลัมน์ ผลการตรวจสอบ (D)
ค่าไหนไม่มีใน STATUS_MAP ก็ใส่ค่าดิบจากไฟล์ ITOS ไปตรงๆ (ตามที่ตกลงไว้)

ไม่ต้องเปิด browser เลย เพราะข้อมูลอยู่ในไฟล์ .xlsx ที่ดาวน์โหลดไว้แล้ว แค่ pandas อ่าน+จับคู่
เร็วกว่า K2 มาก (K2 ต้องเปิดเว็บค้นหาทีละเลขเพราะไม่มีไฟล์ export ให้ใช้)

โครงสร้างชีท Check Bill Approve เหมือนกับที่ใช้ในฝั่ง K2 (main_check_k2_status.py):
  header อยู่แถว 6, ข้อมูลเริ่มแถว 7, C = APPLICATION NUMBER, D = ผลการตรวจสอบ
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import re
from pathlib import Path

import pandas as pd

import config
import sheets_client
from main_check_k2_status import DATA_START_ROW, COL_APPLICATION, get_check_bill_approve_worksheet

ITOS_APPLICATION_RE = re.compile(r"^\d{6}-\d{6}$")

# ค่า Application Status ดิบจากไฟล์ ITOS -> ค่าที่ตรงกับ dropdown ในชีท Check Bill Approve
STATUS_MAP = {
    "ลูกหนี้ปกติ": "เสร็จสมบูรณ์",
    "ยกเลิกการขอสินเชื่อ": "ยกเลิกการขอสินเชื่อ",
    "Asset Deliver": "ไม่ Asset deliver",
    "ยกเลิกการขอสินเชื่อตาม Policy": "ยกเลิกการขอสินเชื่อตาม Policy",
}


def find_latest_itos_export() -> Path:
    """หาไฟล์ itos_export_*.xlsx ที่ดาวน์โหลดล่าสุดใน downloads/

    ⚠️ แก้บั๊ก (2026-09-30): เดิมเรียงตามชื่อไฟล์ (ซึ่งฝังช่วงวันที่ START_END ไว้) แล้วเอาตัว
    สุดท้ายตามลำดับตัวอักษร — ใช้ได้เฉพาะตอนรันวันต่อวันตามลำดับปฏิทินจริงเท่านั้น พอรันข้ามไป
    ดึงย้อนหลังเดือนอื่น (เช่น BILL_AUTO_START_DATE_OVERRIDE=2026-01-01) ไฟล์ชื่อ
    "..._20260101_20260331" จะเรียงมาก่อน "..._20260901_20260929" ตามตัวอักษร (01 < 09) ทั้งที่
    ไฟล์ 20260101_20260331 เพิ่งดาวน์โหลดจริงล่าสุด ทำให้หยิบไฟล์เก่าผิดช่วงมาเช็ค (ได้ 0/3
    ไม่ตรงกันเลย) — เปลี่ยนมาเรียงตามเวลาแก้ไขไฟล์จริง (mtime) แทน ถูกต้องไม่ว่าจะรันตามลำดับ
    ปฏิทินหรือย้อนหลังข้ามเดือนก็ตาม"""
    candidates = sorted(config.DOWNLOAD_DIR.glob("itos_export_*.xlsx"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise RuntimeError(
            f"ไม่พบไฟล์ itos_export_*.xlsx ใน {config.DOWNLOAD_DIR} — ต้องรัน "
            "clean_flow/itos_scraper.py เพื่อดาวน์โหลดไฟล์ก่อน"
        )
    return candidates[-1]


def build_itos_status_lookup(xlsx_path: Path) -> dict[str, str]:
    """อ่านไฟล์ ITOS export คืน dict {Application Number: Application Status}"""
    df = pd.read_excel(xlsx_path)
    # ตัดแถวที่ Application Number หรือ Application Status ว่าง (เจอจริง 2026-09-10: ไฟล์ ITOS
    # มีบางแถว Application Status เป็นค่าว่าง/NaN — ถ้าปล่อยผ่านจะกลายเป็น float nan หลุดไปใน
    # payload ของ ws.batch_update() แล้ว JSON serialize พัง "Out of range float values ... nan")
    df = df[["Application Number", "Application Status"]].dropna(
        subset=["Application Number", "Application Status"]
    )
    df["Application Number"] = df["Application Number"].astype(str).str.strip()
    df["Application Status"] = df["Application Status"].astype(str).str.strip()
    df = df[(df["Application Number"] != "") & (~df["Application Status"].isin(["", "nan", "<NA>", "None"]))]
    return dict(zip(df["Application Number"], df["Application Status"]))


def find_itos_targets(ws) -> list[tuple[int, str]]:
    """คืนลิสต์ (เลขแถวในชีท, APPLICATION NUMBER) เฉพาะที่เป็นรูปแบบ ITOS (มีขีด)"""
    values = sheets_client.read_range_values(ws, DATA_START_ROW, COL_APPLICATION, 1)
    targets = []
    for i, row in enumerate(values):
        application_number = (row[0] if row else "").strip()
        if application_number and ITOS_APPLICATION_RE.match(application_number):
            targets.append((DATA_START_ROW + i, application_number))
    return targets


def main():
    xlsx_path = find_latest_itos_export()
    print(f"[check-itos] ใช้ไฟล์ ITOS: {xlsx_path}", flush=True)
    status_lookup = build_itos_status_lookup(xlsx_path)
    print(f"[check-itos] โหลด Application Number จากไฟล์ ITOS ได้ {len(status_lookup)} รายการ", flush=True)

    ws = get_check_bill_approve_worksheet()
    print("[check-itos] กำลังอ่านคอลัมน์ APPLICATION NUMBER จาก Check Bill Approve ...", flush=True)
    targets = find_itos_targets(ws)
    print(f"[check-itos] เจอ APPLICATION NUMBER แบบ ITOS (มีขีด) ทั้งหมด {len(targets)} รายการ", flush=True)
    if not targets:
        print("[check-itos] ไม่มีรายการต้องเช็ค จบการทำงาน", flush=True)
        return

    updates = []
    not_found = []
    for row_number, application_number in targets:
        raw_status = status_lookup.get(application_number)
        if not raw_status:
            not_found.append((row_number, application_number))
            continue
        status = STATUS_MAP.get(raw_status, raw_status)
        status = "" if status is None else str(status).strip()
        if not status or status.lower() in ("nan", "<na>", "none"):
            not_found.append((row_number, application_number))
            continue
        updates.append({"range": f"D{row_number}", "values": [[status]]})

    print(f"[check-itos] จับคู่ได้ {len(updates)}/{len(targets)} รายการ", flush=True)
    if not_found:
        print(f"[check-itos] หาไม่เจอในไฟล์ ITOS {len(not_found)} รายการ (ไม่แตะค่าเดิม): "
              f"{', '.join(f'{app}(แถว {row})' for row, app in not_found)}", flush=True)

    if not updates:
        print("[check-itos] ไม่มีผลลัพธ์ที่เขียนได้เลย จบการทำงาน", flush=True)
        return

    print(f"[check-itos] กำลังเขียนผลกลับเข้าชีท {len(updates)} แถว ...", flush=True)
    sheets_client.with_retry(lambda: ws.batch_update(updates, value_input_option="USER_ENTERED"))
    print("[check-itos] เขียนผลสำเร็จ", flush=True)


if __name__ == "__main__":
    main()
