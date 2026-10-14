"""เติมคอลัมน์ "Application Status (ก่อนคลีน)" เข้าชีท "Bill K2 Kill" (ไฟล์ Bill Auto Cal)
คอลัมน์ AI (ว่างเดิม ไม่เคยถูกใช้) — ยืนยันจากผู้ใช้ (2026-09-17): Application Status ที่อยู่ใน
Bill K2 Kill ตอนนี้ (คอลัมน์ AD) เป็นค่าที่ผ่าน apply_application_status_approve() แปลง/ลบแล้ว
(เหลือแค่ "ลูกหนี้ปกติ"/"Approve"/"ยกเลิกการขอสินเชื่อ") อยากเห็นค่าดิบก่อนแปลงด้วย

ที่มาของค่าดิบ: K2+ITOS คอลัมน์ "Application Status (ก่อนคลีน)" (คอลัมน์ AG — เดิมเป็นคอลัมน์
"Application Status" ซ้ำท้ายสุดที่ไม่เคยถูกใช้งาน เอามา repurpose แทนที่จะเพิ่มคอลัมน์ใหม่ —
ดู RAW_STATUS_COLUMN ใน clean.py) จับคู่ด้วย Phy ID (ใบกำกับภาษีอย่างย่อ) แบบ exact string
match ตรงๆ (ไม่ต้อง normalize เพราะ Bill K2 Kill ก็อปมาจาก Match ซึ่งก็อปมาจาก K2+ITOS ตรงๆ
อยู่แล้ว ข้อความควรจะตรงกันเป๊ะ)

⚠️ เจอจริง (2026-09-17): บิลที่สถานะดิบเป็น "ยกเลิกการขอสินเชื่อ"/"รอลงทะเบียนสินค้า" **ไม่มี
Phy-ID เลย** (ช่องว่างเปล่าทั้งฝั่ง K2+ITOS และ Bill K2 Kill) — ตอนแรกเข้าใจผิดคิดว่าบิลพวกนี้
หายไปจาก Bill K2 Kill เลย แต่จริงๆ **แถวมันอยู่ใน Bill K2 Kill อยู่แล้ว** (ไปต่อจาก Match ตามปกติ
แม้ Phy-ID จะว่างก็ตาม) ปัญหาจริงคือ dict join ด้านบนนี้ข้ามคีย์ Phy-ID ว่างไปเลย (กันชนกันเพราะ
Phy ว่างไม่ unique) เลยไม่เคยเติม AI ให้แถวพวกนี้ — แก้โดยเพิ่ม fallback คีย์สำรองด้วย PO NUMBER
เฉพาะตอน Phy-ID ว่าง (PO NUMBER ไม่ซ้ำกันในกลุ่มนี้ เช็คแล้ว)

⚠️ เจอบั๊กจริงอีกจุด (2026-09-17 รอบ 2): Phy-ID **ไม่ unique เสมอไป** — เจอเคสจริง Phy-ID
"30330-552" มี 2 แถวใน K2+ITOS คนละ PO Number คนละสถานะ (PO26-232230="รอดำเนินการ MDM",
PO26-232512="ลูกหนี้ปกติ") แต่โค้ดเดิม join ด้วย Phy-ID อย่างเดียว (เก็บค่าแรกที่เจอ) เอาสถานะ
ของแถวแรกไปแปะทับทั้ง 2 แถวใน Bill K2 Kill ผิด (ทำให้ "รอดำเนินการ MDM" เกิน 1 และ "ลูกหนี้ปกติ"
หาย 1) — แก้โดยเปลี่ยนคีย์หลักเป็น **(Phy-ID, PO NUMBER) คู่กัน** แทน (แม่นกว่า ไม่มีทางชนกัน
เพราะ PO Number ไม่ซ้ำ) เหลือ Phy-ID เดี่ยวๆ ไว้เป็น fallback สำรองเฉพาะตอน Phy-ID นั้น unique
จริงในทั้งชีท (ไม่มีแถวอื่นแชร์ Phy-ID เดียวกัน) เท่านั้น
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import gspread

import config
import sheets_client

BILL_AUTO_CAL_K2_KILL_TAB_GID = 1018276173  # "Bill K2 Kill" (ไฟล์ Bill Auto Cal)
DEST_START_ROW = 2
PHY_ID_COL = "H"  # Phy ID (ใบกำกับภาษีอย่างย่อ) ใน Bill K2 Kill
PO_NUMBER_COL = "C"  # PO NUMBER ใน Bill K2 Kill — คีย์สำรองเฉพาะตอน Phy-ID ว่าง
RAW_STATUS_DEST_COL = "AI"  # คอลัมน์ว่างเดิม เอามาใช้เก็บค่าดิบ (เก็บซ้ำไว้เผื่อใช้อ้างอิง)
RAW_STATUS_HEADER = "Application Status (ก่อนคลีน)"
# ยืนยันจากผู้ใช้ (2026-09-17): ให้คอลัมน์ "Application Status" หลัก (AD) ของ Bill K2 Kill เอง
# เขียนทับด้วยค่าดิบก่อนคลีนไปเลยด้วย (เดิม AD มาจาก Match!AE ซึ่งเป็นค่าคลีนแล้ว) — แก้แค่ที่
# ชีท Bill K2 Kill นี้เท่านั้น ไม่แตะ Match!AE ต้นทาง (Match ยังต้องใช้ค่าคลีนอยู่ เพราะ "หน้าร้าน
# แก้ไข"/สเตจ 1.15 อื่นๆ อ้างอิง Match!AE="ลูกหนี้ปกติ" อยู่ — เปลี่ยนตรงนั้นจะพังของเดิมทั้งระบบ)
APPLICATION_STATUS_DEST_COL = "AD"


def _get_k2_kill_worksheet():
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(BILL_AUTO_CAL_K2_KILL_TAB_GID)


def _build_lookup_maps() -> tuple[dict[tuple[str, str], str], dict[str, str], dict[str, str]]:
    """อ่านชีท K2+ITOS คืน (composite_map, phy_unique_map, po_number_to_raw_for_blank_phy)
    - composite_map: คีย์หลัก (Phy-ID, PO NUMBER) คู่กัน -> สถานะดิบ — แม่นสุด ไม่มีทางชนกัน
      เพราะ PO Number ไม่ซ้ำ (เจอจริง 2026-09-17: Phy-ID เดียวกันมีได้หลาย PO Number/สถานะต่างกัน
      จริง — join ด้วย Phy-ID เดี่ยวๆ แบบเดิมเคยเอาค่าผิดแถวมาแปะ)
    - phy_unique_map: คีย์สำรอง Phy-ID เดี่ยวๆ -> สถานะดิบ **เฉพาะ Phy-ID ที่ unique จริงทั้งชีท**
      เท่านั้น (ไม่มีแถวอื่นแชร์ Phy-ID เดียวกัน) ใช้เผื่อ PO Number ฝั่ง Bill K2 Kill กับ K2+ITOS
      เขียนไม่ตรงกันเป๊ะ (format ต่าง) แต่ Phy-ID เดี่ยวๆ ยังปลอดภัยเพราะไม่ซ้ำใคร
    - po_number_to_raw_for_blank_phy: คีย์สำรอง PO NUMBER -> สถานะดิบ **เฉพาะแถวที่ Phy-ID
      ว่าง** เท่านั้น (เจอจริง 2026-09-17: บิล "ยกเลิกการขอสินเชื่อ"/"รอลงทะเบียนสินค้า" ไม่มี
      Phy-ID เลย ต้องพึ่ง PO NUMBER แทน) — ถ้า PO NUMBER ซ้ำกันเองในกลุ่มนี้ ตัดทิ้งไม่ใช้เลย
      กันจับคู่ผิดแถว"""
    ws = sheets_client.get_k2_itos_worksheet()
    header = ws.row_values(1)
    phy_idx = header.index("Phy ID (ใบกำกับภาษีอย่างย่อ)")
    raw_status_idx = header.index(RAW_STATUS_HEADER)
    po_number_idx = header.index("PO NUMBER")
    last_col_idx = max(phy_idx, raw_status_idx, po_number_idx)
    last_col_letter = gspread.utils.rowcol_to_a1(1, last_col_idx + 1).rstrip("1")
    vals = sheets_client.with_retry(
        lambda: ws.get(f"A2:{last_col_letter}{ws.row_count}"),
        tries=6, delay=20,
    )
    composite_map = {}
    phy_counts = {}
    phy_first_status = {}
    po_number_counts = {}
    po_number_map = {}
    for r in vals:
        phy = r[phy_idx].strip() if len(r) > phy_idx else ""
        raw_status = r[raw_status_idx].strip() if len(r) > raw_status_idx else ""
        po_number = r[po_number_idx].strip() if len(r) > po_number_idx else ""
        if phy:
            phy_counts[phy] = phy_counts.get(phy, 0) + 1
            phy_first_status.setdefault(phy, raw_status)
            if po_number:
                composite_map.setdefault((phy, po_number), raw_status)
        elif po_number:
            po_number_counts[po_number] = po_number_counts.get(po_number, 0) + 1
            po_number_map.setdefault(po_number, raw_status)
    # Phy-ID เดี่ยวๆ ใช้ได้ปลอดภัยเฉพาะตอน unique จริง (ไม่มีแถวอื่นแชร์กัน)
    phy_unique_map = {k: v for k, v in phy_first_status.items() if phy_counts[k] == 1}
    # ตัด PO NUMBER ที่ซ้ำกันเองในกลุ่ม Phy-ID ว่างทิ้ง กันจับคู่ผิดแถว
    po_number_map = {k: v for k, v in po_number_map.items() if po_number_counts[k] == 1}
    return composite_map, phy_unique_map, po_number_map


def main() -> None:
    print("[fill-raw-status] กำลังอ่าน K2+ITOS เพื่อสร้าง (Phy-ID,PO)/Phy-ID/PO-Number -> "
          "Application Status (ก่อนคลีน) ...", flush=True)
    composite_map, phy_unique_map, po_number_to_raw = _build_lookup_maps()
    print(f"[fill-raw-status] เจอคีย์คู่ (Phy,PO) {len(composite_map)} คู่, Phy-ID unique สำรอง "
          f"{len(phy_unique_map)} คีย์, PO NUMBER สำรอง (Phy-ID ว่าง) {len(po_number_to_raw)} คีย์",
          flush=True)

    ws = _get_k2_kill_worksheet()
    phy_vals = sheets_client.with_retry(
        lambda: ws.get(f"{PHY_ID_COL}{DEST_START_ROW}:{PHY_ID_COL}{ws.row_count}"), tries=6, delay=20
    )
    po_vals = sheets_client.with_retry(
        lambda: ws.get(f"{PO_NUMBER_COL}{DEST_START_ROW}:{PO_NUMBER_COL}{ws.row_count}"), tries=6, delay=20
    )
    print(f"[fill-raw-status] อ่าน Bill K2 Kill คอลัมน์ {PHY_ID_COL}/{PO_NUMBER_COL} ได้ "
          f"{len(phy_vals)} แถว", flush=True)

    # เขียนหัวคอลัมน์ (ครั้งแรกที่รัน — เขียนซ้ำก็ไม่เป็นไร ค่าเดิม)
    sheets_client.with_retry(
        lambda: ws.update([[RAW_STATUS_HEADER]], f"{RAW_STATUS_DEST_COL}1", value_input_option="USER_ENTERED")
    )

    end_row_for_ad = DEST_START_ROW + len(phy_vals) - 1
    existing_ad = sheets_client.with_retry(
        lambda: ws.get(f"{APPLICATION_STATUS_DEST_COL}{DEST_START_ROW}:{APPLICATION_STATUS_DEST_COL}{end_row_for_ad}"),
        tries=6, delay=20,
    )

    out_values = []
    ad_values = []
    found = 0
    found_via_po_fallback = 0
    found_via_phy_unique_fallback = 0
    for i, row in enumerate(phy_vals):
        phy = row[0].strip() if row else ""
        po_number = po_vals[i][0].strip() if i < len(po_vals) and po_vals[i] else ""
        raw_status = ""
        if phy and po_number:
            raw_status = composite_map.get((phy, po_number), "")
        if not raw_status and phy:
            raw_status = phy_unique_map.get(phy, "")
            if raw_status:
                found_via_phy_unique_fallback += 1
        if not raw_status and not phy:
            raw_status = po_number_to_raw.get(po_number, "")
            if raw_status:
                found_via_po_fallback += 1
        if raw_status:
            found += 1
        out_values.append([raw_status])
        # AD: เขียนทับด้วยค่าดิบเฉพาะตอนหาเจอจริง — ถ้าหาไม่เจอ คงค่าเดิมของ AD ไว้ (ไม่เบลอออก)
        old_ad = existing_ad[i][0] if i < len(existing_ad) and existing_ad[i] else ""
        ad_values.append([raw_status if raw_status else old_ad])

    if not out_values:
        print("[fill-raw-status] ไม่มีแถวให้เติม จบการทำงาน", flush=True)
        return

    end_row = DEST_START_ROW + len(out_values) - 1
    print(f"[fill-raw-status] กำลังเขียนค่าดิบ {found}/{len(out_values)} แถวที่จับคู่ได้ (ในนั้นเจอผ่าน "
          f"Phy-ID unique fallback {found_via_phy_unique_fallback} แถว, PO NUMBER fallback "
          f"{found_via_po_fallback} แถว) ลงคอลัมน์ "
          f"{RAW_STATUS_DEST_COL}{DEST_START_ROW}:{RAW_STATUS_DEST_COL}{end_row} และ "
          f"{APPLICATION_STATUS_DEST_COL}{DEST_START_ROW}:{APPLICATION_STATUS_DEST_COL}{end_row} ...",
          flush=True)
    sheets_client.with_retry(
        lambda: ws.update(out_values, f"{RAW_STATUS_DEST_COL}{DEST_START_ROW}:{RAW_STATUS_DEST_COL}{end_row}",
                           value_input_option="USER_ENTERED")
    )
    sheets_client.with_retry(
        lambda: ws.update(
            ad_values,
            f"{APPLICATION_STATUS_DEST_COL}{DEST_START_ROW}:{APPLICATION_STATUS_DEST_COL}{end_row}",
            value_input_option="USER_ENTERED",
        )
    )
    print("[fill-raw-status] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
