"""สเตจ 1.15 (หลัง 1.1 คำนวณ Match เสร็จ, ก่อน 4.25/4.3 ที่อ่าน "หน้าร้านแก้ไข"): แก้ Match!AU/AY
ตรงๆ ให้บิลที่มี anomaly เปลี่ยนชื่อบริษัท (ธันเดอร์/ยูฟัน) ที่เจอจากสเตจ 0.2 กลายเป็น "แก้ไข"
จริงในตัว Match เอง — เพื่อให้ "หน้าร้านแก้ไข" (สูตร FILTER ที่กรอง Match!AY="แก้ไข") ดึงบิลพวกนี้
ไปแสดงเองอัตโนมัติ ไม่ต้องพึ่งสเตจ 4.45 (append เข้า สาขาเปิดบิลใน ITec ผิด) อีกต่อไป

ยืนยันจากผู้ใช้ (2026-09-16): "ไปเพิ่มในหน้าร้านแก้ไข" ("ทำไงก็ได้ให้ 10 บิลนั้นไปอยู่หน้าร้านแก้ไข")
— "หน้าร้านแก้ไข" เขียนตรงๆ ไม่ได้ (สูตร FILTER ล้วน ไม่มีเซลล์ค่านิ่งให้แทรก) แต่ Match!AY/AU
เป็นค่านิ่งที่ Python เขียนเอง (ไม่ใช่สูตร) เขียนทับตรงๆ ได้ปลอดภัยกว่า

ทำไม Match ไม่ flag บิลพวกนี้เป็น "แก้ไข" เอง (ทั้งที่แก้ cal.py AU แล้ว): เจอว่า 10 บิลนี้ติด
ปัญหาคนละเรื่อง — Application Number ของบิลพวกนี้ไปตรงกับ ITEC-MIS มากกว่า 1 แถว (AI=2 ไม่ใช่ 1)
ทำให้สูตรเดิม (ซึ่งมีมาก่อนวันนี้ ไม่เกี่ยวกับเรื่องเปลี่ยนชื่อบริษัทเลย) ป้องกันการจับคู่ผิดโดย
ตั้งเป็น "Match ไม่เจอ" ไปเลยทั้งแถว (AJ="xxx") ก่อนจะถึงจุดที่ cal.py เช็คชื่อบริษัทด้วยซ้ำ —
สเตจนี้เลยต้อง "เขียนทับ" AU/AY ตรงๆ แทนที่จะพึ่งให้สูตรคำนวณเองให้ถูก

วิธีทำ:
  1. อ่านไฟล์ anomaly CSV จากสเตจ 0.2 (Invoice NO ที่ Customer Name ไม่ตรงกับที่ควรเป็นตามวันที่)
  2. Join Invoice NO -> Phy/Branch-ID ผ่านชีท ITEC-MIS (ข้อมูลจริง) — ใช้เป็นคีย์หลักหาแถวใน Match
  3. ⚠️ เจอจริง (2026-09-17): บางบิล Phy-ID ที่ iTEC MIS เก็บเอง **ไม่ตรงกับ Phy-ID ที่ K2 เก็บ**
     (ตัวอย่างจริง: Invoice 6909-BR45-00838 — iTEC MIS บอก Phy=526226 แต่ K2/Match ใช้ Phy=526280
     ทั้งที่ Application Number/PO Number/ทุกอย่างอื่นตรงกันหมด — เป็นความไม่ตรงกันของข้อมูลจริง
     ระหว่างระบบ K2 กับ iTEC เอง ไม่ใช่บั๊กจากฝั่งเรา) เลยเพิ่ม **fallback จับคู่ด้วย Application
     Number แทน** เมื่อจับคู่ด้วย Phy/Branch-ID ไม่เจอ — Application Number ดึงจากคอลัมน์
     "SellBillView Comment"/"FullTax Comment" ของ ITEC-MIS (เก็บเลข Application Number เดียวกับ
     K2 ไว้เป็น string ล้วนๆ พอดี ยืนยันจากตัวอย่างจริงข้างต้น) เทียบกับ Match!AA (APPLICATION
     NUMBER) ตรงๆ
  4. อ่านคอลัมน์ A:B (Phy,ID) + AA (Application Number) + AE (Application Status) ของชีท Match
     ทั้งหมด หาแถวที่ตรงกับ Phy/Branch-ID ก่อน ถ้าไม่เจอค่อยลอง Application Number — ข้ามถ้า
     Application Status ไม่ใช่ "ลูกหนี้ปกติ" (เงื่อนไขเดียวกับที่ "หน้าร้านแก้ไข" กรองอยู่แล้ว
     ไม่งั้นเขียนไปก็ไม่โชว์อยู่ดี)
  5. เขียนทับ AU{row}="แก้ไข" และ AY{row}="แก้ไข" เฉพาะแถวที่เจอ — ไม่แตะคอลัมน์อื่นเลย

⚠️ ข้อจำกัด: ผลนี้จะอยู่แค่จนกว่า pipeline จะรัน stage 1.1 ใหม่ (ซึ่งคำนวณ Match ใหม่ทั้งหมด
ทับของเก่า) เพราะฉะนั้นสเตจนี้ต้องรันซ้ำทุกครั้งหลัง 1.1 เสมอ (อยู่ใน main_run_full_pipeline.py
เป็นสเตจถาวรแล้ว ไม่ต้องรันมือ)
"""
import csv
import re
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
_sys.path.insert(0, str(_ROOT))
_sys.path.insert(0, str(_ROOT / "clean_flow"))

import config
import sheets_client
from main_itec import ANOMALY_CSV_PATH  # noqa: E402

BILL_AUTO_MATCH_TAB_GID = 899495725
MATCH_START_ROW = 6
AA_COL = "AA"  # APPLICATION NUMBER
AU_COL = "AU"
AY_COL = "AY"
AE_COL = "AE"  # Application Status
VALID_APPLICATION_STATUS = "ลูกหนี้ปกติ"  # เงื่อนไขเดียวกับที่ หน้าร้านแก้ไข กรองอยู่แล้ว
APPLICATION_NUMBER_RE = re.compile(r"^\d{8,20}$")  # เลข Application Number K2 ล้วนๆ ไม่มีตัวอักษร


def _get_match_worksheet():
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(BILL_AUTO_MATCH_TAB_GID)


def _read_anomalies() -> list[dict]:
    if not ANOMALY_CSV_PATH.exists():
        print(f"[fix-match-cn] ไม่พบไฟล์ anomaly ({ANOMALY_CSV_PATH}) — ข้ามสเตจนี้ไปเลย", flush=True)
        return []
    with open(ANOMALY_CSV_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _build_invoice_to_phyid_map() -> dict[str, tuple[str, str]]:
    ws = sheets_client.get_itec_mis_worksheet()
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:I{ws.row_count}"))
    mapping = {}
    for r in vals:
        invoice = r[4].strip() if len(r) > 4 else ""
        phy = r[0].strip() if len(r) > 0 else ""
        branch_id = r[1].strip() if len(r) > 1 else ""
        if invoice and invoice not in mapping:
            mapping[invoice] = (phy, branch_id)
    return mapping


def _build_invoice_to_application_number_map() -> dict[str, str]:
    """fallback สำหรับกรณี Phy-ID ที่ iTEC MIS เก็บไม่ตรงกับที่ K2 ใช้จริง (เจอจริง 2026-09-17) —
    ดึง Application Number จากคอลัมน์ FullTax Comment (AA, idx26) / SellBillView Comment
    (AB, idx27) ของ ITEC-MIS เก็บเฉพาะค่าที่เป็นเลขล้วนๆ (ตรงกับรูปแบบ Application Number ของ K2)"""
    ws = sheets_client.get_itec_mis_worksheet()
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:AB{ws.row_count}"))
    mapping = {}
    for r in vals:
        invoice = r[4].strip() if len(r) > 4 else ""
        if not invoice or invoice in mapping:
            continue
        for idx in (26, 27):
            candidate = r[idx].strip() if len(r) > idx else ""
            if APPLICATION_NUMBER_RE.match(candidate):
                mapping[invoice] = candidate
                break
    return mapping


def fix_match_company_name_anomalies() -> int:
    anomalies = _read_anomalies()
    print(f"[fix-match-cn] อ่าน anomaly จากสเตจ 0.2 ได้ {len(anomalies)} รายการ", flush=True)
    if not anomalies:
        return 0

    print("[fix-match-cn] กำลัง join Invoice NO -> Phy/Branch-ID ผ่าน ITEC-MIS ...", flush=True)
    invoice_map = _build_invoice_to_phyid_map()
    target_keys = set()
    for a in anomalies:
        phy, branch_id = invoice_map.get(a["Invoice NO"].strip(), ("", ""))
        if phy and branch_id:
            target_keys.add(f"{phy}|{branch_id}")
    print(f"[fix-match-cn] หา Phy/Branch-ID ได้ {len(target_keys)} คีย์ไม่ซ้ำ", flush=True)

    print("[fix-match-cn] กำลัง join Invoice NO -> Application Number ผ่าน ITEC-MIS (fallback) ...",
          flush=True)
    appno_map = _build_invoice_to_application_number_map()
    target_appnos = set()
    for a in anomalies:
        appno = appno_map.get(a["Invoice NO"].strip(), "")
        if appno:
            target_appnos.add(appno)
    print(f"[fix-match-cn] หา Application Number (fallback) ได้ {len(target_appnos)} เลขไม่ซ้ำ", flush=True)

    if not target_keys and not target_appnos:
        return 0

    match_ws = _get_match_worksheet()
    print(f"[fix-match-cn] กำลังอ่านชีท Match คอลัมน์ A:B + {AA_COL} + {AE_COL} ทั้งหมด "
          f"({match_ws.row_count} แถว) ...", flush=True)
    ab_vals = sheets_client.with_retry(
        lambda: match_ws.get(f"A{MATCH_START_ROW}:B{match_ws.row_count}"), tries=6, delay=20
    )
    aa_vals = sheets_client.with_retry(
        lambda: match_ws.get(f"{AA_COL}{MATCH_START_ROW}:{AA_COL}{match_ws.row_count}"), tries=6, delay=20
    )
    ae_vals = sheets_client.with_retry(
        lambda: match_ws.get(f"{AE_COL}{MATCH_START_ROW}:{AE_COL}{match_ws.row_count}"), tries=6, delay=20
    )

    matched_rows = []
    skipped_status = 0
    matched_by_appno_fallback = 0
    for i, r in enumerate(ab_vals):
        phy = r[0].strip() if len(r) > 0 else ""
        branch_id = r[1].strip() if len(r) > 1 else ""
        key = f"{phy}|{branch_id}"
        appno = aa_vals[i][0].strip() if i < len(aa_vals) and aa_vals[i] else ""
        matched_via_fallback = key not in target_keys and appno in target_appnos
        if key not in target_keys and not matched_via_fallback:
            continue
        row_num = MATCH_START_ROW + i
        status = ae_vals[i][0].strip() if i < len(ae_vals) and ae_vals[i] else ""
        if status != VALID_APPLICATION_STATUS:
            skipped_status += 1
            continue
        if matched_via_fallback:
            matched_by_appno_fallback += 1
        matched_rows.append(row_num)

    print(f"[fix-match-cn] เจอในชีท Match {len(matched_rows)} แถว (ในนั้นเจอผ่าน Application Number "
          f"fallback {matched_by_appno_fallback} แถว, ข้าม {skipped_status} แถวที่ Application Status "
          f"ไม่ใช่ '{VALID_APPLICATION_STATUS}')", flush=True)

    if not matched_rows:
        print("[fix-match-cn] ไม่มีแถวให้แก้ จบการทำงาน", flush=True)
        return 0

    # เขียนทับ AU กับ AY ตรงๆ แยกทีละคอลัมน์ (ไม่แตะ AV-AX ตรงกลางเลย)
    real_updates = []
    for row_num in matched_rows:
        real_updates.append({"range": f"{AU_COL}{row_num}", "values": [["แก้ไข"]]})
        real_updates.append({"range": f"{AY_COL}{row_num}", "values": [["แก้ไข"]]})

    print(f"[fix-match-cn] กำลังเขียนทับ {AU_COL}/{AY_COL} = \"แก้ไข\" ให้ {len(matched_rows)} "
          f"แถวใน Match ...", flush=True)
    sheets_client.with_retry(
        lambda: match_ws.batch_update(real_updates, value_input_option="USER_ENTERED")
    )
    print("[fix-match-cn] เสร็จสิ้น", flush=True)
    return len(matched_rows)


def main() -> None:
    fix_match_company_name_anomalies()


if __name__ == "__main__":
    main()
