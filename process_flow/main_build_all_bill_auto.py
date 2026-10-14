"""รันทั้ง pipeline ตามลำดับ (ไฟล์ Bill Auto ทั้งหมด):
  1. ITec         -> ITEC MANNUAL   (ก็อปดิบ ไม่จำกัดแถว — เป็นข้อมูลอ้างอิง)
  2. ITec Mis     -> ITEC-MIS       (คำนวณ A,B,C ด้วย cal.py, จำกัด ROW_LIMIT แถวไว้ทดสอบ)
  3. K2+ITOS      -> Match          (คำนวณ Phy/ID + จับคู่ ITEC-MIS ด้วย cal.py, จำกัด ROW_LIMIT)

รันคำสั่งเดียวจบทั้ง 3 ขั้น เรียงลำดับตามที่ต้องพึ่งพากัน (ทำผิดลำดับจะจับคู่ไม่ได้)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import main_build_itec_mannual
import main_build_itec_mis
import main_build_match_bill_auto


def main():
    print("========== ขั้น 1/3: ITec -> ITEC MANNUAL ==========", flush=True)
    main_build_itec_mannual.main()

    print("\n========== ขั้น 2/3: ITec Mis -> ITEC-MIS ==========", flush=True)
    main_build_itec_mis.main()

    print("\n========== ขั้น 3/3: K2+ITOS -> Match ==========", flush=True)
    main_build_match_bill_auto.main()

    print("\n========== เสร็จสิ้นทั้ง pipeline ==========", flush=True)


if __name__ == "__main__":
    main()
