"""เติมคอลัมน์ AK ("Branch ID (ดึงจาก Phy-ID)") ของชีท "Bill K2 Kill" (ไฟล์ Bill Auto Cal) —
ยืนยันจากผู้ใช้ (2026-09-18): บิลที่คอลัมน์ D (Branch ID) ว่าง (889 แถว ที่เจอจริง) ส่วนใหญ่
(888/889) ยังมี Phy-ID (คอลัมน์ H) อยู่ในรูปแบบ "<Phy>-<Branch ID>" (เช่น "16386-708") — ดึง
ตัวเลขหลังขีดสุดท้ายออกมาเป็น Branch ID แทนได้ ไม่ต้องเดา

⚠️ เจอเพิ่ม (2026-09-18 รอบ 2): บางแถว Phy-ID ไม่มีขีด "-" เลย มาแค่ตัวเลขล้วนๆ (เช่น "2798")
— ยืนยันจากผู้ใช้ให้เอาค่าตรงๆ นั้นใส่ช่อง AK ไปเลย (ไม่ต้องแยก Phy/Branch เพราะไม่มีขีดให้แยก)

⚠️ คอลัมน์ AK เดิมชื่อ "Application Sub Status" (ว่างเปล่า ไม่เคยถูกใช้งานมาก่อน — เอามา
repurpose ตามที่ผู้ใช้ขอโดยตรง ไม่ใช่เพิ่มคอลัมน์ใหม่) เปลี่ยนหัวคอลัมน์เป็น "Branch ID
(ดึงจาก Phy-ID)" แล้ว

⚠️ แก้เพิ่ม (2026-09-18 รอบ 3): ตอนแรกเขียนแค่แถวที่ D ว่างเท่านั้น ที่เหลือปล่อยว่างไว้ —
ผู้ใช้เจอว่าสเปรดชีทปลายทาง (แท็บ "Data" ของไฟล์ "สถานะ PO ที่ Approve...") มีคอลัมน์ชื่อ "ID"
รออยู่แล้ว ต้องการให้ AK เป็นคอลัมน์ Branch ID **แบบสมบูรณ์ทุกแถว** (ไม่ใช่แค่แถวที่ D ว่าง) —
แก้เป็น: **AK = D ถ้า D มีค่าอยู่แล้ว, ถ้า D ว่างค่อยดึงจาก Phy-ID (H) แทน** ทำให้ AK มีค่าครบ
ทุกแถวที่หาได้ (ยกเว้นแถวที่ทั้ง D และ H ว่างจริงๆ)

⚠️ แก้เพิ่ม (2026-09-18 รอบ 4-5): ยืนยันจากผู้ใช้ให้เติม AK **เฉพาะแถวที่ Application Status
(คอลัมน์ AD) ไม่ใช่ "ลูกหนี้ปกติ"/"Approve"/"ยกเลิกการขอสินเชื่อ"** (บิลกลุ่มที่ยังต้องติดตาม/
แก้ไขจริงๆ เท่านั้น) — 3 สถานะนี้ (ปกติดี/อนุมัติแล้ว/ยกเลิกไปแล้ว ไม่ต้องสนใจอีก) ให้เว้นว่างไว้
เสมอ ไม่ว่า D/H จะมีค่าหรือไม่ก็ตาม

⚠️ แก้เพิ่ม (2026-09-18 รอบ 6): ยืนยันจากผู้ใช้ให้เอา "ยกเลิกการขอสินเชื่อ" กลับเข้ามาเติม AK
ด้วย (ยังต้องรู้ ID สาขาของบิลที่ยกเลิกไปแล้วเช่นกัน) — เหลือข้อยกเว้นแค่ "ลูกหนี้ปกติ"/"Approve"
เท่านั้นที่ไม่เติม (คนละชุดกับสเตจเติมชื่อลูกค้า main_fill_billkill_customer_name.py ซึ่งยังคง
ยกเว้น "ยกเลิกการขอสินเชื่อ" เหมือนเดิม — ผู้ใช้ระบุเฉพาะคอลัมน์ ID เท่านั้น)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
import sheets_client

BILL_AUTO_CAL_K2_KILL_TAB_GID = 1018276173  # "Bill K2 Kill" (ไฟล์ Bill Auto Cal)
DEST_START_ROW = 2
BRANCH_ID_COL = "D"
PHY_ID_COL = "H"
APPLICATION_STATUS_COL = "AD"
# ข้ามแถวสถานะเหล่านี้ ไม่เติม AK ให้ (ยืนยันจากผู้ใช้ 2026-09-18) — บิลปกติดี/อนุมัติแล้ว
# ไม่ต้องติดตามต่อ ("ยกเลิกการขอสินเชื่อ" เอากลับเข้ามาแล้ว — ยังอยากรู้ ID สาขาของบิลที่ยกเลิก)
EXCLUDED_APPLICATION_STATUSES = {"ลูกหนี้ปกติ", "Approve"}
DEST_COL = "AK"
DEST_HEADER = "Branch ID (ดึงจาก Phy-ID)"


def _get_k2_kill_worksheet():
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(BILL_AUTO_CAL_K2_KILL_TAB_GID)


def main() -> None:
    ws = _get_k2_kill_worksheet()

    print(f"[branch-from-phy] กำลังอ่านคอลัมน์ {BRANCH_ID_COL}:{APPLICATION_STATUS_COL} ...", flush=True)
    vals = sheets_client.with_retry(
        lambda: ws.get(f"{BRANCH_ID_COL}{DEST_START_ROW}:{APPLICATION_STATUS_COL}{ws.row_count}"),
        tries=6, delay=20,
    )
    print(f"[branch-from-phy] อ่านได้ {len(vals)} แถว", flush=True)

    sheets_client.with_retry(
        lambda: ws.update([[DEST_HEADER]], f"{DEST_COL}1", value_input_option="USER_ENTERED")
    )

    out_values = []
    found = 0
    skipped_status = 0
    for r in vals:
        branch = r[0].strip() if len(r) > 0 else ""
        phy = r[4].strip() if len(r) > 4 else ""
        status = r[26].strip() if len(r) > 26 else ""  # AD คือคอลัมน์ที่ 27 นับจาก D (D=1)
        if status in EXCLUDED_APPLICATION_STATUSES:
            skipped_status += 1
            out_values.append([""])
            continue
        if branch:
            value = branch
        elif phy:
            value = phy.rsplit("-", 1)[-1].strip() if "-" in phy else phy
        else:
            value = ""
        if value:
            found += 1
        out_values.append([value])

    if not out_values:
        print("[branch-from-phy] ไม่มีแถวให้เติม จบการทำงาน", flush=True)
        return

    end_row = DEST_START_ROW + len(out_values) - 1
    print(f"[branch-from-phy] ข้าม {skipped_status} แถวที่สถานะอยู่ใน {EXCLUDED_APPLICATION_STATUSES} — "
          f"กำลังเขียน {found} แถวที่ดึงได้ ลงคอลัมน์ {DEST_COL}"
          f"{DEST_START_ROW}:{DEST_COL}{end_row} ...", flush=True)
    sheets_client.with_retry(
        lambda: ws.update(out_values, f"{DEST_COL}{DEST_START_ROW}:{DEST_COL}{end_row}",
                           value_input_option="USER_ENTERED")
    )
    print("[branch-from-phy] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
