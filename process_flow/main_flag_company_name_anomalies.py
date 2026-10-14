"""สเตจ 4.46: เอา anomaly ที่ main_itec.py (สเตจ 0.2) เจอไว้ — บิลที่ Doc Date ในระบบ iTEC
ควรจะขึ้นชื่อบริษัทใหม่ "ยูฟัน" (ตั้งแต่ 15/9/2026) แต่ Customer(Name) จริงในระบบยังค้างชื่อเก่า
"ธันเดอร์" อยู่ (หรือกลับกัน) — เอามารวมเข้า "สาขาเปิดบิลใน ITec ผิด" (หน้าร้านแก้ไข) ด้วย ตามที่
ยืนยันจากผู้ใช้ (2026-09-16): "อิงจาก iTEC ... ช่วยรวมบิลพวกนี้ไปหน้าร้านแก้ไขด้วย ... ต้องดึงทุกวัน"
และภายหลัง: "ทำแบบเต็มระบบเลย" — ให้เติมคอลัมน์ผลเช็คอื่นๆ ให้ครบเหมือนแถวที่ Match คำนวณจริง
ไม่ใช่ปล่อยว่างแค่ Customer(Name)/สรุปผลการตรวจสอบ

วิธีทำ (ไม่แตะ Cal/ITec/Match/cal.py เลย — เป็นสเตจเสริมแยกต่างหาก กันความเสี่ยงกระทบของเดิม):
  1. อ่านไฟล์ anomaly CSV ที่สเตจ 0.2 บันทึกไว้ (Invoice NO, Doc Date, Customer Name จริง,
     ชื่อที่ควรเป็น)
  2. Join Invoice NO -> ทั้งแถวของชีท "ITEC-MIS" (ไฟล์ Bill Auto, 36 คอลัมน์เต็ม — ข้อมูลจริง
     ไม่ใช่ค่าที่เราสังเคราะห์) ได้ Phy/Branch-ID/Customer Code/Member Code/สำนักงานใหญ่/
     E-TAX Status/ราคา/Finish (สถานะรับเงิน) มาครบ
  3. Join Phy-ID ("<Phy>-<Branch-ID>") -> SUMPRICE ผ่านชีท K2+ITOS (ไฟล์ Bill Auto Data) เอาไว้
     เทียบราคากับ ITEC-MIS (เหมือนที่ cal.py โซน 2 ทำกับแถว Match ปกติ) — บางแถวอาจหาไม่เจอ
     (เช่น ลูกค้า Personal ที่ไม่ผ่าน K2/ITOS โดยตรง) ปล่อยช่องราคาว่างไว้ถ้าหาไม่เจอ ไม่เดา
  4. คำนวณผลเช็คแต่ละคอลัมน์แบบเดียวกับ cal.py โซน 2 จริง (ดู _verdict_* ด้านล่าง) จากข้อมูลจริง
     ที่ join มาได้ — ไม่มีคอลัมน์ไหนเป็นค่าสมมติ
  5. หา BU/RM/AM ของแต่ละ ID (รหัสสาขา) จากข้อมูลที่มีอยู่แล้วใน สาขาเปิดบิลใน ITec ผิด เอง (สร้าง
     lookup ID -> (BU, RM, AM) จากแถวที่มีอยู่แล้ว — เพราะไม่มี branch master แยกให้ใช้ตรงๆ)
  6. กันซ้ำกับ Phy/ID ที่มีอยู่แล้วในหน้าร้านแก้ไขวันนี้ (ไม่งั้นซ้ำ 2 รอบ)
  7. Append ต่อท้ายแถวสุดท้ายที่มีอยู่แล้วในชีท "สาขาเปิดบิลใน ITec ผิด" (ห้ามลบของเก่า
     — pattern เดียวกับ main_copy_new_bill_gaeikai_to_mdm.py)

⚠️ ประวัติแก้ไข (2026-09-16): เดิมใส่ "แก้ไข" ผิดคอลัมน์ (ใส่ที่ "สำนักงานใหญ่" N ซึ่งเป็นผลเช็ค
คนละเรื่อง) ที่ถูกต้องคือคอลัมน์ "Customer(Name)" (M) — แก้แล้ว ตอนนี้ทั้ง 2 คอลัมน์มีความหมาย
ถูกต้องครบ (M = ผลเช็คชื่อบริษัท, N = ผลเช็คสำนักงานใหญ่ จริงจาก ITEC-MIS)

⚠️ ข้อจำกัด: หา BU/RM/AM ไม่ได้ครบทุกแถว (ไม่มี branch master แยกให้ join ตรงๆ) และคอลัมน์ราคา
อาจว่างถ้าหา SUMPRICE ใน K2+ITOS ไม่เจอ (ไม่เดาค่า) — ทั้งสองกรณีไม่ error แค่เว้นว่างไว้

⚠️ ยืนยันจากผู้ใช้ (2026-09-17): ไม่ append บิลที่ Application Status (ค่าคลีนแล้วใน K2+ITOS)
ไม่ใช่ "ลูกหนี้ปกติ" เลย (ให้เงื่อนไขตรงกับที่ "หน้าร้านแก้ไข" กรองอยู่แล้ว Match!AE="ลูกหนี้ปกติ")
— ดู VALID_APPLICATION_STATUS/_build_phyid_to_application_status() ด้านล่าง
"""
import csv
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
_sys.path.insert(0, str(_ROOT))
_sys.path.insert(0, str(_ROOT / "clean_flow"))

import config
import sheets_client
from main_itec import ANOMALY_CSV_PATH  # noqa: E402 (path ต้อง insert sys.path ก่อน)

SAKHA_TAB_GID = 0  # "สาขาเปิดบิลใน ITec ผิด"
SOURCE_START_ROW = 8
NUM_COLS = 74  # A:BV

# ตำแหน่งคอลัมน์ปลายทาง (0-based, ตรงกับ read_range_values) — ดู header จริง H7:P7 ที่ยืนยันแล้ว:
# Etax Detail, Comment, ราคา, Customer(Code), Member Code, Customer(Name), สำนักงานใหญ่,
# สถานะรับเงิน (Finish), สรุปผลการตรวจสอบ
ETAX_DETAIL_COL_IDX = 7
COMMENT_COL_IDX = 8
PRICE_COL_IDX = 9
CUSTOMER_CODE_COL_IDX = 10
MEMBER_CODE_COL_IDX = 11
CUSTOMER_NAME_COL_IDX = 12
HQ_COL_IDX = 13
PAYMENT_STATUS_COL_IDX = 14
SUMMARY_COL_IDX = 15
DETAIL_COL_IDX = 19  # T = รายละเอียด

VALID_CUSTOMER_CODES = ("UFUND STUDENT", "UFUND PERSONAL", "UFUND UNIDAYS")
FIXED_TAX_ID = "AEE0201777774"
# ยืนยันจาก cal.py จริง (_build_fallback_indices / BM check): ค่าที่ถือว่า "ถูกต้อง" ของสถานะ
# รับเงินคือ "ยังรับเงินไม่ครบ" (ไม่ใช่ "รับเงินครบแล้ว" อย่างที่คิดตามสัญชาตญาณ — logic เดิมของ
# ระบบตั้งไว้แบบนี้ ไม่ได้เดาเอง)
EXPECTED_PAYMENT_STATUS = "ยังรับเงินไม่ครบ"


def _get_sakha_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SAKHA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def _read_anomalies() -> list[dict]:
    if not ANOMALY_CSV_PATH.exists():
        print(f"[flag-company] ไม่พบไฟล์ anomaly ({ANOMALY_CSV_PATH}) — ข้ามสเตจนี้ไปเลย", flush=True)
        return []
    with open(ANOMALY_CSV_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _build_invoice_to_mis_row() -> dict[str, list[str]]:
    """อ่านชีท ITEC-MIS (ไฟล์ Bill Auto) ทั้ง 36 คอลัมน์ คืน dict {Invoice NO: แถวเต็ม}
    ใช้ join หาทุกฟิลด์จริงที่ต้องใช้คำนวณผลเช็ค (Phy, Branch-ID, Customer Code, Member Code,
    สำนักงานใหญ่/สาขา, E-TAX Status, Total Price After VAT, Finish)"""
    ws = sheets_client.get_itec_mis_worksheet()
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:AJ{ws.row_count}"))
    mapping = {}
    for r in vals:
        invoice = r[4].strip() if len(r) > 4 else ""
        if invoice and invoice not in mapping:
            mapping[invoice] = r
    return mapping


def _build_phyid_to_sumprice() -> dict[str, str]:
    """อ่านชีท K2+ITOS (ไฟล์ Bill Auto Data) คืน dict {"<Phy>-<Branch-ID>": SUMPRICE} — ใช้เทียบ
    ราคากับ ITEC-MIS เหมือนที่ cal.py โซน 2 ทำกับ Match ปกติ (บางแถวอาจหาไม่เจอ เช่น ลูกค้า
    Personal ที่ไม่ได้มาจาก K2/ITOS โดยตรง — ผู้เรียกต้องรับมือกรณีไม่เจอเอง)"""
    ws = sheets_client.get_k2_itos_worksheet()
    hdr = sheets_client.with_retry(lambda: ws.get("A1:BF1"))[0]
    phyid_idx = hdr.index("Phy ID (ใบกำกับภาษีอย่างย่อ)")
    sumprice_idx = hdr.index("SUMPRICE")
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:BF{ws.row_count}"))
    mapping = {}
    for r in vals:
        phyid = r[phyid_idx].strip() if len(r) > phyid_idx else ""
        sumprice = r[sumprice_idx] if len(r) > sumprice_idx else ""
        if phyid and phyid not in mapping:
            mapping[phyid] = sumprice
    return mapping


# ยืนยันจากผู้ใช้ (2026-09-17): "เราจะไม่เอา ที่ไม่ใช่ลูกหนี้ปกติ" — บิล anomaly ที่ Application
# Status (ค่าคลีนแล้วใน K2+ITOS/Match!AE) ไม่ใช่ "ลูกหนี้ปกติ" ไม่ต้อง append เข้า สาขาเปิดบิลใน
# ITec ผิด เลย ต่อให้แก้ที่ Match ไม่ได้ก็ตาม เพราะ "หน้าร้านแก้ไข" เองก็กรองด้วยเงื่อนไขเดียวกัน
# (Match!AE="ลูกหนี้ปกติ") อยู่แล้ว — ถ้า append ไปจะกลายเป็นข้อมูลที่ไม่สอดคล้องกับ "หน้าร้านแก้ไข"
VALID_APPLICATION_STATUS = "ลูกหนี้ปกติ"


def _build_phyid_to_application_status() -> dict[str, str]:
    """อ่านชีท K2+ITOS คืน dict {"<Phy>-<Branch-ID>": Application Status} (ค่าคลีนแล้ว — ผ่าน
    apply_application_status_approve() มาแล้วตั้งแต่สเตจ 0.1) ใช้กรองไม่ให้ append แถวที่สถานะ
    ไม่ใช่ "ลูกหนี้ปกติ" เข้า สาขาเปิดบิลใน ITec ผิด"""
    ws = sheets_client.get_k2_itos_worksheet()
    hdr = sheets_client.with_retry(lambda: ws.get("A1:BF1"))[0]
    phyid_idx = hdr.index("Phy ID (ใบกำกับภาษีอย่างย่อ)")
    status_idx = hdr.index("Application Status")
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:BF{ws.row_count}"))
    mapping = {}
    for r in vals:
        phyid = r[phyid_idx].strip() if len(r) > phyid_idx else ""
        status = r[status_idx].strip() if len(r) > status_idx else ""
        if phyid and phyid not in mapping:
            mapping[phyid] = status
    return mapping


def _build_branch_lookup(source_ws) -> dict[str, tuple[str, str, str, str]]:
    """สร้าง lookup {ID สาขา: (Store Name, BU, RM, AM)} จากแถวที่มีอยู่แล้วในสาขาเปิดบิลใน
    ITec ผิด เอง (ไม่มี branch master แยกให้ join ตรงๆ) — เก็บแถวแรกที่เจอของแต่ละ ID"""
    vals = sheets_client.with_retry(lambda: source_ws.get(f"A{SOURCE_START_ROW}:F3303"))
    lookup = {}
    for r in vals:
        if len(r) < 6:
            continue
        branch_id = r[1].strip()
        if branch_id and branch_id not in lookup:
            lookup[branch_id] = (r[2], r[3], r[4], r[5])
    return lookup


def _find_next_empty_row(dest_ws) -> int:
    existing = sheets_client.with_retry(
        lambda: dest_ws.get(f"A{SOURCE_START_ROW}:A{dest_ws.row_count}")
    )
    while existing and not (existing[-1] and str(existing[-1][0]).strip()):
        existing.pop()
    return SOURCE_START_ROW + len(existing)


def _verdict_price(sumprice: str, mis_price: str) -> str:
    if not sumprice:
        return ""  # หา SUMPRICE ใน K2+ITOS ไม่เจอ — ไม่เดา ปล่อยว่าง
    try:
        a = float(str(sumprice).replace(",", ""))
        b = float(str(mis_price).replace(",", ""))
        return "ถูกต้อง" if a - b == 0 else "แก้ไข"
    except (TypeError, ValueError):
        return "แก้ไข"


def flag_company_name_anomalies() -> int:
    anomalies = _read_anomalies()
    print(f"[flag-company] อ่าน anomaly จากสเตจ 0.2 ได้ {len(anomalies)} รายการ", flush=True)
    if not anomalies:
        return 0

    print("[flag-company] กำลังอ่านชีท ITEC-MIS เต็มแถวสำหรับ join ...", flush=True)
    mis_map = _build_invoice_to_mis_row()
    print("[flag-company] กำลังอ่านชีท K2+ITOS หา SUMPRICE เทียบราคา ...", flush=True)
    sumprice_map = _build_phyid_to_sumprice()
    print("[flag-company] กำลังอ่านชีท K2+ITOS หา Application Status กรองเฉพาะลูกหนี้ปกติ ...", flush=True)
    status_map = _build_phyid_to_application_status()

    sakha_ws = _get_sakha_worksheet(SAKHA_TAB_GID)
    print("[flag-company] กำลังสร้าง branch lookup (BU/RM/AM) จากข้อมูลที่มีอยู่แล้ว ...", flush=True)
    branch_lookup = _build_branch_lookup(sakha_ws)

    existing_rows = sheets_client.with_retry(lambda: sakha_ws.get(f"A{SOURCE_START_ROW}:B3303"))
    existing_keys = {
        f"{r[0].strip()}|{r[1].strip()}" for r in existing_rows if len(r) >= 2 and r[0].strip()
    }

    new_rows = []
    unmatched = 0
    price_unmatched = 0
    skipped_status = 0
    for a in anomalies:
        invoice = a["Invoice NO"].strip()
        mis_row = mis_map.get(invoice)
        if not mis_row:
            unmatched += 1
            continue
        phy = mis_row[0].strip() if len(mis_row) > 0 else ""
        branch_id = mis_row[1].strip() if len(mis_row) > 1 else ""
        branch_name_mis = mis_row[2].strip() if len(mis_row) > 2 else ""
        customer_code = mis_row[6].strip() if len(mis_row) > 6 else ""
        member_code = mis_row[7].strip() if len(mis_row) > 7 else ""
        hq = mis_row[9].strip() if len(mis_row) > 9 else ""
        etax_status = mis_row[10].strip() if len(mis_row) > 10 else ""
        mis_price = mis_row[20] if len(mis_row) > 20 else ""
        finish = mis_row[29].strip() if len(mis_row) > 29 else ""

        if not phy or not branch_id:
            unmatched += 1
            continue
        key = f"{phy}|{branch_id}"
        if key in existing_keys:
            continue  # มีอยู่แล้วในหน้าร้านแก้ไข (Match เจอ+แสดงเองอยู่แล้ว) ไม่ต้องเพิ่มซ้ำ

        # ยืนยันจากผู้ใช้ (2026-09-17): ไม่เอาบิลที่ Application Status ไม่ใช่ "ลูกหนี้ปกติ" —
        # ให้เงื่อนไขตรงกับที่ "หน้าร้านแก้ไข" กรองอยู่แล้ว (Match!AE="ลูกหนี้ปกติ")
        app_status = status_map.get(f"{phy}-{branch_id}", "")
        if app_status != VALID_APPLICATION_STATUS:
            skipped_status += 1
            continue

        store_name, bu, rm, am = branch_lookup.get(branch_id, (branch_name_mis, "", "", ""))
        detail = f"Customer Name ในระบบ iTEC ยังไม่เปลี่ยนเป็น \"{a['ควรจะเป็น']}\" (ยังเป็น {a['Customer Name (จริง)']})"

        sumprice = sumprice_map.get(f"{phy}-{branch_id}", "")
        price_verdict = _verdict_price(sumprice, mis_price)
        if not price_verdict:
            price_unmatched += 1

        row = [""] * NUM_COLS
        row[0] = phy
        row[1] = branch_id
        row[2] = store_name
        row[3] = bu
        row[4] = rm
        row[5] = am
        row[ETAX_DETAIL_COL_IDX] = etax_status  # ข้อมูลจริง ไม่ใช่ verdict (เหมือนแถว Match ปกติ)
        row[COMMENT_COL_IDX] = "ถูกต้อง"  # หาแถวใน ITEC-MIS เจอจริง (join ผ่าน Invoice NO ตรงๆ)
        row[PRICE_COL_IDX] = price_verdict
        row[CUSTOMER_CODE_COL_IDX] = "ถูกต้อง" if customer_code in VALID_CUSTOMER_CODES else "แก้ไข"
        row[MEMBER_CODE_COL_IDX] = "ถูกต้อง" if member_code == FIXED_TAX_ID else "แก้ไข"
        row[CUSTOMER_NAME_COL_IDX] = "แก้ไข"  # verdict ของ anomaly นี้จริงๆ (ชื่อบริษัทไม่ตรง)
        row[HQ_COL_IDX] = "ถูกต้อง" if hq == "สำนักงานใหญ่" else "แก้ไข"
        row[PAYMENT_STATUS_COL_IDX] = "ถูกต้อง" if finish == EXPECTED_PAYMENT_STATUS else "แก้ไข"
        row[SUMMARY_COL_IDX] = "แก้ไข"  # verdict รวมของแถวนี้ (มีอย่างน้อย 1 จุดผิดเสมอ — ชื่อบริษัท)
        row[DETAIL_COL_IDX] = detail
        new_rows.append(row)
        existing_keys.add(key)  # กันซ้ำกันเองภายในชุดนี้ด้วย

    print(f"[flag-company] หาแถวใน ITEC-MIS ไม่เจอ {unmatched} รายการ (ข้ามไป)", flush=True)
    if skipped_status:
        print(f"[flag-company] ข้าม {skipped_status} รายการที่ Application Status ไม่ใช่ "
              f"'{VALID_APPLICATION_STATUS}' (ไม่ append ตามที่ยืนยันจากผู้ใช้ 2026-09-17)", flush=True)
    if price_unmatched:
        print(f"[flag-company] หา SUMPRICE ใน K2+ITOS ไม่เจอ {price_unmatched} รายการ "
              f"(เว้นช่องราคาว่างไว้ ไม่เดา)", flush=True)
    print(f"[flag-company] แถวใหม่ที่จะเพิ่ม (หลังกันซ้ำ) {len(new_rows)} แถว", flush=True)

    if not new_rows:
        print("[flag-company] ไม่มีอะไรต้องเพิ่ม จบการทำงาน", flush=True)
        return 0

    next_row = _find_next_empty_row(sakha_ws)
    needed_rows = next_row + len(new_rows) - 1
    if sakha_ws.row_count < needed_rows:
        sheets_client.with_retry(lambda: sakha_ws.resize(rows=needed_rows))

    print(f"[flag-company] กำลังวางต่อท้าย {len(new_rows)} แถว ที่แถว {next_row} "
          f"(ไม่ลบของเก่า) ...", flush=True)
    # ⚠️ ยืนยันจากผู้ใช้ (2026-10-05): คอลัมน์ C:G ของชีทนี้ผู้ใช้ผูกสูตรไว้เอง ห้ามเขียนทับ —
    # เขียนเฉพาะ A:B, H:BE, BH เป็นต้นไป (ข้าม BF:BG ที่ผูกสูตรไว้เช่นกัน ยืนยัน 2026-10-05)
    left_block = [r[0:2] for r in new_rows]
    mid_block = [r[7:57] for r in new_rows]  # H:BE
    tail_block = [r[59:] for r in new_rows]  # BH เป็นต้นไป (ข้าม BF:BG ที่ผู้ใช้ผูกสูตรไว้)
    end_row = next_row + len(new_rows) - 1
    sheets_client.with_retry(
        lambda: sakha_ws.update(left_block, f"A{next_row}:B{end_row}", value_input_option="USER_ENTERED")
    )
    sheets_client.with_retry(
        lambda: sakha_ws.update(mid_block, f"H{next_row}", value_input_option="USER_ENTERED")
    )
    sheets_client.with_retry(
        lambda: sakha_ws.update(tail_block, f"BH{next_row}", value_input_option="USER_ENTERED")
    )
    print("[flag-company] เสร็จสิ้น", flush=True)
    return len(new_rows)


def main() -> None:
    flag_company_name_anomalies()


if __name__ == "__main__":
    main()
