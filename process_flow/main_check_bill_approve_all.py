"""รันเช็ค Check Bill Approve ทั้ง 2 ระบบในคำสั่งเดียว:
  1. K2 (APPLICATION NUMBER แบบตัวเลขล้วน) — main_check_k2_status.py
  2. ITOS (APPLICATION NUMBER แบบ YYYYMM-XXXXXX) — main_check_itos_status.py

ทั้งคู่เขียนผลลงคอลัมน์เดียวกัน (ผลการตรวจสอบ) ในชีท Check Bill Approve (ไฟล์ Bill Auto Cal)
แต่คนละแถวกันเสมอ (กรองด้วยรูปแบบ APPLICATION NUMBER คนละแบบ) จึงรันต่อกันได้อย่างปลอดภัย
ไม่ชนกัน

⚠️ ยืนยันจากผู้ใช้ (2026-09-30): เคยปิดการเช็ค K2 ไปชั่วคราว แล้วเปิดกลับมาใช้เหมือนเดิมอีกครั้ง
(2026-10-01)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import main_check_itos_status
import main_check_k2_status


def main():
    print("========== ขั้น 1/2: เช็ค K2 ==========", flush=True)
    main_check_k2_status.main()

    print("\n========== ขั้น 2/2: เช็ค ITOS ==========", flush=True)
    main_check_itos_status.main()

    print("\n========== เช็คครบทั้ง 2 ระบบแล้ว ==========", flush=True)


if __name__ == "__main__":
    main()
