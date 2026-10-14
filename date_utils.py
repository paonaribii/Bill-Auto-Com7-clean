"""คำนวณช่วงวันที่ตามกติกาที่ใช้ทั้งฝั่ง K-2 และ ITOS:
วันที่ 1 ของเดือนนี้ ถึง เมื่อวาน (Day-1) ของวันที่รันสคริปต์
"""
import os
from datetime import date, timedelta


def _today() -> date:
    """ค่าเริ่มต้นของ 'วันนี้' ทุกฟังก์ชันในไฟล์นี้ — ปกติคือ date.today() จริง แต่ถ้าตั้ง
    env var BILL_AUTO_TODAY_OVERRIDE (รูปแบบ YYYY-MM-DD) ไว้ จะใช้ค่านั้นแทน — ใช้สำหรับ
    ย้อนรัน pipeline ทั้งชุดเสมือนวันนั้นเป็น 'วันนี้' โดยไม่ต้องแก้โค้ด (ยืนยันจากผู้ใช้
    2026-09-02: ต้องการย้อนไปทำของเมื่อวาน)"""
    override = os.getenv("BILL_AUTO_TODAY_OVERRIDE")
    if override:
        return date.fromisoformat(override)
    return date.today()


def _start_override() -> date | None:
    """ถ้าตั้ง env var BILL_AUTO_START_DATE_OVERRIDE (YYYY-MM-DD) ไว้ จะบังคับใช้เป็นวันเริ่มต้น
    แทน "วันที่ 1 ของเดือนนี้" — ใช้สำหรับดึงย้อนหลังข้ามหลายเดือน (เช่น 1 ส.ค. ถึงปัจจุบัน) โดย
    ยังใช้ตรรกะ Day-1 เดิมกับวันสิ้นสุดตามวันที่จริง (ยืนยันจากผู้ใช้ 2026-09-08)"""
    override = os.getenv("BILL_AUTO_START_DATE_OVERRIDE")
    return date.fromisoformat(override) if override else None


def po_date_range(today: date | None = None) -> tuple[date, date]:
    today = today or _today()
    start = _start_override() or today.replace(day=1)
    end = today - timedelta(days=1)
    # ถ้ารันวันที่ 1 ของเดือน end จะย้อนไปเดือนก่อนหน้า ซึ่งจะน้อยกว่า start (เจอจริง
    # 2026-09-01: ได้ start=2026-09-01 > end=2026-08-31 กลับกัน ทำให้ K2/ITOS พังทั้งคู่)
    # กรณีนี้ยังไม่มีข้อมูลของเดือนนี้เลย (เมื่อวานเป็นเดือนก่อน) — ยืนยันจากผู้ใช้ให้ใช้
    # "วันที่ 1 ของเดือนที่แล้ว ถึง วันสุดท้ายของเดือนที่แล้ว" แทน (เดือนที่แล้วเต็มเดือนพอดี)
    # (ถ้ามี start override อยู่แล้วจะไม่โดนเงื่อนไขนี้ทับ เพราะ override ไม่มีทางเกิน end จริง)
    if end < start:
        start = end.replace(day=1)
    return start, end


def format_thai_style(d: date) -> str:
    """แปลงเป็น string dd/mm/yyyy ตามที่ฟอร์มเว็บส่วนใหญ่ใช้ - ปรับ format ตรงนี้ถ้าเว็บจริงต้องการรูปแบบอื่น"""
    return d.strftime("%d/%m/%Y")


def itec_daily_range(today: date | None = None) -> tuple[date, date]:
    """สำหรับ iTEC Sale Inv View (แท็บ Cal) — ดึงแค่ 'เมื่อวาน' วันเดียวต่อรอบ (ไม่ใช่
    ทั้งเดือน) เพราะข้อมูลทั้งเดือนมีเป็นหมื่นแถว Select All Rows ในโปรแกรม iTEC ค้างนานมาก
    ต้องรันเป็น scheduled task ทุกวันแทน ดึงทีละวันแทน"""
    today = today or _today()
    yesterday = today - timedelta(days=1)
    return yesterday, yesterday


def chunk_date_range(start: date, end: date, chunk_days: int = 10) -> list[tuple[date, date]]:
    """แบ่งช่วงวันที่ [start, end] เป็นก้อนๆ ละ chunk_days วัน (ก้อนสุดท้ายอาจสั้นกว่า) —
    ใช้กับ iTEC Sale Inv View เพราะดึงทั้งเดือนทีเดียวมีเป็นหมื่นแถว Select All Rows
    ค้างนานมาก แบ่งเล็กลงให้แต่ละรอบเร็วขึ้น"""
    chunks = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


def itec_mis_date_range(today: date | None = None) -> tuple[date, date]:
    """iTEC Mis ใช้ช่วงวันที่ 1 ของเดือนนี้ ถึง วันนี้ (ไม่ใช่ Day-1 แบบ K-2/ITOS)

    ⚠️ เจอจริง 2026-09-01: ขอ startDate=endDate=2026-09-01 (วันแรกของเดือนใหม่ วันเดียว)
    แล้ว API ต้นทางตอบ 500 Internal Server Error ซ้ำๆ ไม่ใช่ปัญหาชั่วคราว — ยืนยันจากผู้ใช้
    ให้ตกไปใช้ "วันที่ 1 ของเดือนที่แล้ว ถึง วันสุดท้ายของเดือนที่แล้ว" แทน เหมือนกับที่แก้
    po_date_range() (K-2/ITOS/iTEC) ไปแล้ว"""
    today = today or _today()
    override = _start_override()
    if override:
        return override, today
    start = today.replace(day=1)
    if today == start:  # วันนี้เป็นวันที่ 1 พอดี ยังไม่มีข้อมูลของเดือนนี้เลย
        end = start - timedelta(days=1)  # วันสุดท้ายของเดือนที่แล้ว
        start = end.replace(day=1)
        return start, end
    return start, today


def format_iso(d: date) -> str:
    """แปลงเป็น YYYY-MM-DD ตามที่ query param startDate/endDate ของ iTEC Mis API ใช้"""
    return d.strftime("%Y-%m-%d")


def format_thai_be(d: date) -> str:
    """แปลงเป็น dd/mm/YYYY แบบปี พ.ศ. (ITOS ใช้ฟอร์แมตนี้ เช่น 24/08/2569 = ค.ศ. 2026)"""
    return f"{d.day:02d}/{d.month:02d}/{d.year + 543}"
