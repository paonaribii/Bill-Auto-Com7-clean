"""ก็อปข้อมูลดิบจากชีท "ITec" (ไฟล์ "Bill Auto Data" — ย้ายมาจากไฟล์ Bill Auto เดิมเพราะเต็ม)
ไปวางที่ชีท "ITEC MANNUAL" (ไฟล์ Bill Auto เดิม) ตรงๆ ไม่มีการแปลงค่าใดๆ (ตามที่ยืนยันไว้:
"ITEC MANNUAL อันนี้ดึงมาจาก ITec แบบดิบๆเลยไม่มีสูตร")

เป็นข้อมูลอ้างอิง (reference/lookup table) ที่ ITEC-MIS ใช้จับคู่คอลัมน์ C เลยก็อปมาทั้งหมด
ไม่จำกัดจำนวนแถว (ต่างจาก ITEC-MIS/Match ที่จำกัดไว้ทดสอบก่อน)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
import sheets_client

BILL_AUTO_DATA_ITEC_TAB_GID = 846598990  # "ITec" (ไฟล์ Bill Auto Data ต้นทาง: Invoice NO, Comment)
BILL_AUTO_ITEC_MANNUAL_TAB_GID = 1038840941  # "ITEC MANNUAL" (ไฟล์ Bill Auto เดิม ปลายทาง)


def get_bill_auto_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def get_bill_auto_data_worksheet(gid: int):
    """ITec ย้ายไปอยู่ไฟล์ "Bill Auto Data" แยกต่างหากแล้ว"""
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_DATA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def main():
    print("[itec-mannual] กำลังอ่านข้อมูลจากชีท ITec (ไฟล์ Bill Auto Data) ...", flush=True)
    itec_ws = get_bill_auto_data_worksheet(BILL_AUTO_DATA_ITEC_TAB_GID)
    last_row = itec_ws.row_count
    # ⚠️ ยืนยันจากผู้ใช้ (2026-09-16): เพิ่มคอลัมน์ C (Customer(Name)) เข้ามาด้วย จากเดิม A:B
    # เท่านั้น — เพื่อดึงชื่อลูกค้า/บริษัทจริงจาก iTEC ไปตรวจ anomaly เปลี่ยนชื่อบริษัทต่อ
    values = sheets_client.with_retry(lambda: itec_ws.get(f"A2:C{last_row}"))
    # ตัดแถวว่างท้ายๆ ทิ้ง
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    print(f"[itec-mannual] อ่านได้ {len(values)} แถว", flush=True)

    if not values:
        print("[itec-mannual] ไม่มีข้อมูลให้ก็อป จบการทำงาน", flush=True)
        return

    print("[itec-mannual] กำลังลบข้อมูลเก่าใน ITEC MANNUAL ...", flush=True)
    manual_ws = get_bill_auto_worksheet(BILL_AUTO_ITEC_MANNUAL_TAB_GID)
    sheets_client.clear_data_rows(manual_ws)

    print(f"[itec-mannual] กำลังวางข้อมูลใหม่ {len(values)} แถว ...", flush=True)
    sheets_client.with_retry(
        lambda: manual_ws.update(values, "A2", value_input_option="USER_ENTERED")
    )
    print("[itec-mannual] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
