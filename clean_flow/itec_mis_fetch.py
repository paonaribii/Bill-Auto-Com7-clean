"""
Automation ฝั่ง iTEC Mis (Flow Clean ขั้น D1-D6)

endpoint นี้เป็น GET request ที่ trigger ดาวน์โหลดไฟล์ทันที (ไม่ใช่หน้าเว็บที่ต้องคลิก)
เลยใช้ requests ดึงตรงๆ แทน Playwright — เร็วกว่าและเสถียรกว่าการเปิดเบราว์เซอร์

วันที่ที่ใช้: startDate = วันที่ 1 ของเดือนนี้, endDate = วันนี้ (ไม่ใช่ Day-1 แบบ K-2/ITOS)

⚠️ เจอจริง 2026-09-08: ตอนดึงย้อนหลังยาวๆ (~40 วัน, BILL_AUTO_START_DATE_OVERRIDE=2026-08-01)
API ตอบ 504 Gateway Timeout — ฝั่ง server เองสร้างรายงานไม่ทันสำหรับช่วงวันที่กว้างขนาดนี้
(ไม่ใช่แค่ client timeout สั้นไปเหมือนที่คิดตอนแรก ขยาย client timeout เป็น 300 วิแล้วก็ยังพัง)
แก้โดย**แบ่งดึงเป็นก้อนๆ ละ 15 วัน** (เหมือนที่ทำกับ iTEC Sale Inv) แล้วรวมผลลัพธ์เป็นไฟล์เดียว
ก่อนส่งต่อให้ clean_itec_mis() ตามปกติ

⚠️ เจอจริง 2026-09-08 (รอบถัดมา): การแบ่งก้อนแบบไม่คาบเกี่ยวกัน (chunk_date_range เดิม) ทำให้
ข้อมูลของ "วันสุดท้ายของแต่ละก้อน" หายไปเกือบหมด (เจอจริง: 15/8 กับ 30/8 ซึ่งเป็นวันสุดท้ายของ
ก้อน 1 และก้อน 2 พอดี มีแถวหาย ~1,300-1,900 แถว) — คาดว่า API ตัด endDate แบบไม่รวมเต็มวันหรือ
มีปัญหา pagination ที่ขอบก้อน แก้โดย**ให้แต่ละก้อนคาบเกี่ยวกับก้อนถัดไป 1 วัน** (ก้อนถัดไปเริ่ม
ที่วันเดียวกับที่ก้อนก่อนจบ ไม่ใช่วันถัดไป) แล้ว drop_duplicates() ทิ้งแถวซ้ำจากการคาบเกี่ยวกัน
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

from datetime import timedelta
from pathlib import Path

import pandas as pd
import requests

import config
from date_utils import chunk_date_range, format_iso, itec_mis_date_range

CHUNK_DAYS = 15


def _overlapping_chunks(start, end, chunk_days=CHUNK_DAYS):
    """เหมือน chunk_date_range แต่ให้แต่ละก้อนคาบเกี่ยวกับก้อนถัดไป 1 วัน (ก้อนถัดไปเริ่มที่
    วันเดียวกับที่ก้อนก่อนจบ) กันข้อมูลของวันขอบก้อนหายไปถ้า API ตัด endDate ไม่รวมเต็มวัน"""
    chunks = chunk_date_range(start, end, chunk_days=chunk_days)
    overlapped = []
    for i, (c_start, c_end) in enumerate(chunks):
        if i > 0:
            c_start = c_start - timedelta(days=1)
        overlapped.append((c_start, c_end))
    return overlapped


def _fetch_chunk(start, end) -> pd.DataFrame:
    params = {
        "startDate": format_iso(start),
        "endDate": format_iso(end),
        "key": config.ITEC_MIS_API_KEY,
    }
    print(f"[iTEC Mis]   กำลังดึงก้อน {params['startDate']} ถึง {params['endDate']} ...", flush=True)
    resp = requests.get(config.ITEC_MIS_BASE_URL, params=params, timeout=120)
    resp.raise_for_status()

    tmp = config.DOWNLOAD_DIR / f"itec_mis_chunk_{params['startDate']}_{params['endDate']}.xlsx"
    tmp.write_bytes(resp.content)
    df = pd.read_excel(tmp)
    print(f"[iTEC Mis]   ก้อนนี้ได้ {len(df)} แถว", flush=True)
    return df


def download_itec_mis_export() -> Path:
    if not config.ITEC_MIS_API_KEY:
        raise RuntimeError("ไม่พบ ITEC_MIS_API_KEY ใน .env — เพิ่มก่อนรัน")

    start, end = itec_mis_date_range()
    chunks = _overlapping_chunks(start, end, chunk_days=CHUNK_DAYS)

    # ⚠️ แก้บั๊ก (2026-10-01): endDate ของ "ก้อนสุดท้าย" (= end จริงที่ต้องการ) มักได้ข้อมูลของ
    # วันนั้นมาไม่ครบ/หายไปทั้งวัน — ยืนยันจากการทดสอบจริง: ขอ endDate=2026-09-30 ได้ข้อมูลแค่ถึง
    # 29/9 (30/9 หายทั้งวัน) แต่พอขยายไปขอ endDate=2026-10-01 แทน กลับได้ข้อมูลของ 30/9 มาครบ
    # (1,696 แถว) — ไม่ใช่ปัญหาข้อมูลขอบก้อนระหว่างก้อน (ที่ overlap 1 วันแก้ไปแล้ว) แต่เป็นเพราะ
    # วันสุดท้ายของคำขอ "ทั้งหมด" ไม่มีก้อนถัดไปมาคาบให้ แก้โดยขอ endDate ของก้อนสุดท้ายเกินจริง
    # ไปอีก 1 วันเสมอ แล้วกรอง Doc date ที่เกิน `end` จริงทิ้งก่อนบันทึกไฟล์
    padded_chunks = list(chunks)
    last_start, last_end = padded_chunks[-1]
    padded_chunks[-1] = (last_start, last_end + timedelta(days=1))

    print(f"[iTEC Mis] กำลังดึงไฟล์ startDate={format_iso(start)} endDate={format_iso(end)} "
          f"แบ่งเป็น {len(chunks)} ก้อน (ก้อนละ {CHUNK_DAYS} วัน คาบเกี่ยวกัน 1 วัน + ก้อนสุดท้าย "
          f"ขอเกินจริง 1 วัน กันข้อมูลขอบก้อน/วันสุดท้ายหาย) ...")

    all_dfs = [_fetch_chunk(c_start, c_end) for c_start, c_end in padded_chunks]
    combined = pd.concat(all_dfs, ignore_index=True, sort=False)
    before_dedupe = len(combined)
    combined = combined.drop_duplicates().reset_index(drop=True)
    print(f"[iTEC Mis]   ก่อน dedupe {before_dedupe} แถว -> หลัง dedupe {len(combined)} แถว "
          f"(ตัดแถวซ้ำจากการคาบเกี่ยวกันของก้อน)", flush=True)

    doc_dates = pd.to_datetime(combined["Doc date"], dayfirst=True, errors="coerce")
    before_date_filter = len(combined)
    combined = combined[doc_dates.dt.date <= end].reset_index(drop=True)
    if len(combined) != before_date_filter:
        print(f"[iTEC Mis]   ตัดแถวเกิน {format_iso(end)} ทิ้ง {before_date_filter - len(combined)} "
              f"แถว (มาจากการขอ endDate เกินจริง 1 วันของก้อนสุดท้าย)", flush=True)

    dest = config.DOWNLOAD_DIR / f"itec_mis_{format_iso(start)}_{format_iso(end)}.xlsx"
    combined.to_excel(dest, index=False)
    print(f"[iTEC Mis] รวม {len(chunks)} ก้อนเสร็จ — รวมทั้งหมด {len(combined)} แถว บันทึกที่ {dest}")
    return dest


if __name__ == "__main__":
    path = download_itec_mis_export()
    print(f"ดาวน์โหลดไฟล์ iTEC Mis เสร็จ: {path}")
