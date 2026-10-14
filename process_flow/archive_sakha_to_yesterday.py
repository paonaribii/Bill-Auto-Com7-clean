"""ก่อนที่ main_build_sakha_phy_id.py / main_build_sakha_details.py จะล้าง+วางข้อมูลใหม่ทับ
ชีท "สาขาเปิดบิลใน ITec ผิด" (ไฟล์ Sakha, gid=0) ทุกครั้งที่เปลี่ยนวัน — ต้อง copy ข้อมูลทั้งหมด
(A:BU, 73 คอลัมน์) ของวันนี้ไปเก็บเป็นค่านิ่งไว้ที่ชีท "ของเมื่อวาน" ก่อนเสมอ
ไม่งั้นข้อมูลของวันก่อนหน้าจะหายไปตอนถูกเขียนทับ (ยืนยันจากผู้ใช้ 2026-09-03)

โครงสร้างต้นทาง (สาขาเปิดบิลใน ITec ผิด): header แถว 7, ข้อมูลเริ่มแถว 8, คอลัมน์ A:BU (73 คอลัมน์)
โครงสร้างปลายทาง (ของเมื่อวาน): header แถว 4, ข้อมูลเริ่มแถว 5, คอลัมน์ A:BU เหมือนกัน

เขียนเป็นค่านิ่ง (ไม่ใช่สูตร) — ลบของเก่าใน "ของเมื่อวาน" ก่อนวางใหม่ทุกครั้ง (เป็น snapshot ของ
วันก่อนหน้าเท่านั้น ไม่สะสม)

⚠️ ยืนยันจากผู้ใช้ (2026-09-08): ถ้ารัน pipeline หลายรอบในวันปฏิทินเดียวกัน (เช่น ทดสอบซ้ำๆ)
"ของเมื่อวาน" จะถูกทับซ้ำกลายเป็น "ของรอบก่อนหน้า" แทนที่จะเป็นของเมื่อวานจริง — แก้โดย**เก็บ
วันที่ archive ล่าสุดไว้ในเซลล์ BW1 ของชีท "ของเมื่อวาน" เอง** แล้วเช็คก่อนทุกครั้ง ถ้า archive
ไปแล้ววันนี้ (ตามวันปฏิทินจริง) จะข้ามไปเลย ไม่ทับซ้ำ
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd

import config
import sheets_client
from date_utils import _today, format_iso

SAKHA_TAB_GID = 0  # "สาขาเปิดบิลใน ITec ผิด" (ต้นทาง — ข้อมูล "วันนี้" ก่อนจะถูกเขียนทับ)
SAKHA_YESTERDAY_TAB_GID = 998909771  # "ของเมื่อวาน" (ปลายทาง)

SOURCE_START_ROW = 8  # สาขาเปิดบิลใน ITec ผิด เริ่มข้อมูลที่แถว 8
DEST_START_ROW = 5  # ของเมื่อวาน เริ่มข้อมูลที่แถว 5
NUM_COLS = 73  # A:BU
LAST_ARCHIVED_MARKER_CELL = "M2"  # เซลล์เก็บวันที่ archive ล่าสุด (แถว 2 ว่างอยู่แล้วทั้งแถว
# เช็คแล้วจริง — ไม่ใช้คอลัมน์เกิน col_count เดิม (73) เหมือน BW ที่เกินขอบเขต grid จริง)


def get_sakha_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SAKHA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def _already_archived_today(dest_ws) -> bool:
    """เช็ควันที่ archive ล่าสุด (เก็บไว้ที่ LAST_ARCHIVED_MARKER_CELL) ว่าเป็นวันนี้แล้วหรือยัง
    ตามวันปฏิทินจริง (เที่ยงคืนตัดรอบ) — กัน archive ซ้ำถ้ารัน pipeline หลายรอบในวันเดียวกัน"""
    last = sheets_client.with_retry(lambda: dest_ws.acell(LAST_ARCHIVED_MARKER_CELL).value)
    return (last or "").strip() == format_iso(_today())


def _mark_archived_today(dest_ws) -> None:
    sheets_client.with_retry(
        lambda: dest_ws.update([[format_iso(_today())]], LAST_ARCHIVED_MARKER_CELL,
                                value_input_option="USER_ENTERED")
    )


def archive_today_to_yesterday() -> int:
    """copy ค่า A:BU ของวันนี้จาก สาขาเปิดบิลใน ITec ผิด -> ของเมื่อวาน แบบค่านิ่ง
    คืนจำนวนแถวที่ copy — archive แค่ครั้งแรกของแต่ละวันปฏิทินเท่านั้น (ยืนยันจากผู้ใช้
    2026-09-08) ถ้าวันนี้ archive ไปแล้ว จะข้ามเลย ไม่ทับซ้ำ"""
    source_ws = get_sakha_worksheet(SAKHA_TAB_GID)
    dest_ws = get_sakha_worksheet(SAKHA_YESTERDAY_TAB_GID)

    if _already_archived_today(dest_ws):
        print("[archive-sakha] วันนี้ archive ไปแล้ว (เช็คจาก BW1) ข้ามไปเลย ไม่ทับซ้ำ",
              flush=True)
        return -1

    print("[archive-sakha] กำลังอ่าน สาขาเปิดบิลใน ITec ผิด คอลัมน์ A:BU (วันนี้) ...", flush=True)
    values = sheets_client.read_range_values(source_ws, SOURCE_START_ROW, 1, NUM_COLS)

    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()

    if not values:
        print("[archive-sakha] ไม่มีข้อมูลให้ archive (สาขาเปิดบิลใน ITec ผิด ว่างทั้งหมด)",
              flush=True)
        _mark_archived_today(dest_ws)
        return 0

    normalized = [row + [""] * (NUM_COLS - len(row)) for row in values]
    df = pd.DataFrame(normalized)

    needed_rows = DEST_START_ROW + len(df) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[archive-sakha] ขยายชีท ของเมื่อวาน จาก {dest_ws.row_count} เป็น "
              f"{needed_rows} แถว ...", flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[archive-sakha] กำลังลบของเก่า + วาง {len(df)} แถว ที่ชีท ของเมื่อวาน "
          f"คอลัมน์ A:BU ...", flush=True)
    sheets_client.clear_and_paste_range(dest_ws, df, DEST_START_ROW, 1)

    _mark_archived_today(dest_ws)
    print("[archive-sakha] archive สำเร็จ", flush=True)
    return len(df)


def main() -> None:
    archive_today_to_yesterday()


if __name__ == "__main__":
    main()
