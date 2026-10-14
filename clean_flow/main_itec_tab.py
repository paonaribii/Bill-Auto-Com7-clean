"""จุดรันหลักของ Flow Clean เส้น Cal -> ITec

อ่านข้อมูลจากแท็บ Cal เอาแค่ Invoice NO (unique) + Comment (เคลียร์ '"' ออก) ไปวางแท็บ ITec
พร้อมตั้ง format คอลัมน์ Comment เป็นตัวเลข custom "0"
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

from clean import build_itec_tab_dataframe
from sheets_client import get_itec_tab_worksheet, read_cal_dataframe, write_itec_tab


def main():
    print("1) อ่านข้อมูลจากแท็บ Cal ...")
    cal_df = read_cal_dataframe()
    print(f"   อ่านสำเร็จ {len(cal_df)} แถว")

    print("2) คัดเฉพาะ Invoice NO (unique) + Comment ...")
    df = build_itec_tab_dataframe(cal_df)
    print(f"   เหลือ {len(df)} แถว (หลังตัดซ้ำ)")

    print("3) เขียนลงแท็บ ITec ...")
    ws = get_itec_tab_worksheet()
    write_itec_tab(ws, df)

    print("เสร็จสิ้น")


if __name__ == "__main__":
    main()
