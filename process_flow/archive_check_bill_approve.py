"""ก่อนที่ step4 (main_process_step4.py) จะล้าง+วางข้อมูลใหม่ทับ "สถานะ Approve" (ซึ่งทำให้
สูตรในชีท Check Bill Approve คำนวณใหม่และข้อมูล "วันนี้" ในคอลัมน์ C:E หาย) ต้อง copy ค่า
C:E (APPLICATION NUMBER, ผลการตรวจสอบ, PHY-ID) ของวันนี้ไปเก็บเป็นค่านิ่งไว้ที่ H:J (ของเมื่อวาน)
ก่อน ไม่งั้นการเทียบ "Match กับของเมื่อวาน" (คอลัมน์ G) ของรอบถัดไปจะไม่มีอะไรให้เทียบ

เขียนเป็นค่านิ่ง (ไม่ใช่สูตร) เหมือนกับหลักการเดียวกับ Apps Script step4
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import sheets_client
from main_check_k2_status import DATA_START_ROW, get_check_bill_approve_worksheet

COL_SOURCE_START = 3  # C (APPLICATION NUMBER, ผลการตรวจสอบ, PHY-ID = C:E)
COL_DEST_START = 8  # H (ของเมื่อวาน เลขสัญญา, ผลการตรวจสอบ, PHY-ID = H:J)
NUM_COLS = 3


def archive_today_to_yesterday() -> int:
    """copy ค่า C:E ของวันนี้ -> H:J (ของเมื่อวาน) แบบค่านิ่ง คืนจำนวนแถวที่ copy"""
    ws = get_check_bill_approve_worksheet()

    print("[archive] กำลังอ่านคอลัมน์ C:E (วันนี้) จาก Check Bill Approve ...", flush=True)
    values = sheets_client.read_range_values(ws, DATA_START_ROW, COL_SOURCE_START, NUM_COLS)

    # ตัดแถวว่างท้ายๆ ทิ้ง (read_range_values อ่านยาวถึงท้ายชีทเผื่อไว้เสมอ)
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()

    if not values:
        print("[archive] ไม่มีข้อมูลให้ archive (คอลัมน์ C:E ว่างทั้งหมด)", flush=True)
        return 0

    # ปรับทุกแถวให้มีครบ 3 คอลัมน์ (แถวที่ cell ท้ายว่างอาจถูกตัดสั้นมาตอนอ่าน)
    normalized = [row + [""] * (NUM_COLS - len(row)) for row in values]

    end_row = DATA_START_ROW + len(normalized) - 1
    dest_range = f"H{DATA_START_ROW}:J{end_row}"
    print(f"[archive] กำลัง copy {len(normalized)} แถว C:E -> {dest_range} ...", flush=True)
    sheets_client.with_retry(
        lambda: ws.update(normalized, dest_range, value_input_option="USER_ENTERED")
    )
    print("[archive] archive สำเร็จ", flush=True)
    return len(normalized)


def main() -> None:
    archive_today_to_yesterday()


if __name__ == "__main__":
    main()
