"""จุดรันหลักของ Flow Clean เส้น iTEC Mis"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

from clean import build_itec_mis_dataframe
from itec_mis_fetch import download_itec_mis_export
from sheets_client import append_dataframe, clear_data_rows, get_headers, get_itec_mis_worksheet


def main():
    print("1) ดึงไฟล์ iTEC Mis ...")
    itec_mis_path = download_itec_mis_export()

    print("2) เชื่อมต่อ Google Sheet 'Bill Auto' แท็บ ITec Mis ...")
    ws = get_itec_mis_worksheet()
    headers = get_headers(ws)

    print("3) คลีนข้อมูล iTEC Mis ...")
    combined = build_itec_mis_dataframe(itec_mis_path, headers)

    print("4) ลบข้อมูลเก่าออกก่อน (กันสะสมซ้ำทุกรอบที่รัน) ...")
    clear_data_rows(ws)

    print("5) เติมข้อมูลใหม่เข้า Google Sheet ...")
    append_dataframe(ws, combined)

    print("เสร็จสิ้น")


if __name__ == "__main__":
    main()
