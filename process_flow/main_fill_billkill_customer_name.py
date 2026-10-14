"""เติมชื่อ-นามสกุลลูกค้าเข้าคอลัมน์ AJ ของชีท "Bill K2 Kill" (ไฟล์ Bill Auto Cal) —
ยืนยันจากผู้ใช้ (2026-09-18): พบว่าคอลัมน์ Comment ของแท็บ "ITec" (ไฟล์ Bill Auto Data —
ดึงมาจาก iTEC Sale Inv View เองอยู่แล้วทุกวัน สเตจ 0.3) มีชื่อ-นามสกุลลูกค้าจริงฝังอยู่ในข้อความ
เช่น "UFUND STUDENT/9999202600001/สมชาย ใจดี/ เงินดาวน์(1272.00)" — ไม่ต้องเปิดเบราว์เซอร์
ค้นทีละใบเหมือนที่เคยลองใน K2 (ช้ามาก 21,000+ ใบ) ใช้ text parsing ได้เลย เร็วกว่ามาก

รูปแบบ Comment (สำรวจจริง ~22,000 ตัวอย่าง แม่นยำ 99.5%): แยกด้วย "/" ปกติชื่อจะอยู่ตำแหน่งที่ 3
(index 2) เช่น "UFUND STUDENT / เลขที่สัญญา:X / ชื่อ:Y / เงินดาวน์:Z" — บางรูปแบบชื่อสลับมาอยู่
ตำแหน่งที่ 2 (index 1) แทน (เช่น เลข Application ไปติดกับ type label แทนที่จะแยกเป็นคนละ token)
เลยลอง index 2 ก่อน ถ้าไม่ผ่าน sanity check (ไม่ใช่ตัวเลขล้วน/ไม่ใช่คำว่าเงินดาวน์) ค่อย fallback
ไป index 1 — ตัดคำนำหน้า "ชื่อ:"/"ชื่อ :" ออกด้วย (คำนำหน้าอื่นเช่น "นาย"/"นางสาว"/"คุณ"/"น.ส."
เป็นส่วนหนึ่งของชื่อจริง เก็บไว้ตามเดิม)

วิธี join เข้า Bill K2 Kill: Invoice NO (ITec) -> Phy/Branch-ID ผ่าน ITEC-MIS (เหมือนสเตจ 1.15) ->
Phy-ID -> แถวใน Bill K2 Kill (คอลัมน์ H) — เขียนเฉพาะแถวที่จับคู่ได้ ไม่แตะคอลัมน์อื่นเลย

⚠️ ข้อจำกัด: ~0.5% ของ Comment แยกชื่อไม่ได้จริงๆ (comment รูปแบบแปลกไป หรือไม่มีชื่อในนั้นเลย
เช่น เลขโทรศัพท์ล้วนๆ หรือ comment ของบิลบริษัท) ปล่อยว่างไว้ ไม่เดา

⚠️ แก้ขอบเขต (2026-09-18 รอบ 3-4): ยืนยันจากผู้ใช้ให้เติมชื่อ **เฉพาะแถวที่ Application Status
(คอลัมน์ AD) ไม่ใช่ "ลูกหนี้ปกติ"/"Approve"/"ยกเลิกการขอสินเชื่อ"** เท่านั้น (บิลกลุ่มที่ยังต้อง
ติดตาม/แก้ไขจริงๆ) — 3 สถานะนี้ (ปกติดี/อนุมัติแล้ว/ยกเลิกไปแล้ว) ให้เว้นว่างไว้เสมอ

⚠️ แก้บั๊ก (2026-09-18 รอบ 5): ผู้ใช้เจอ Application No 202601-000002 ที่มี Comment จริงใน
ITec ("Personal/202601-000002/สมหญิง ใจงาม/...") แต่ระบบดึงไม่ได้ — สาเหตุคือ Phy-ID ของ
Bill K2 Kill แถวนี้เป็น "PHY344-2496" (มีตัวอักษร "PHY" นำหน้าติดมาด้วย เจอเฉพาะสาขา Franchise
Partner บางแห่ง) แต่ ITEC-MIS เก็บ Phy-ID เป็นตัวเลขล้วน "344" ไม่มี "PHY" — คีย์เลยไม่ตรงกัน
แก้โดยตัดตัวอักษรนำหน้า Phy-ID ออกก่อน join เสมอ (ดู _normalize_phyid_key/_LEADING_LETTERS_RE)

⚠️ เพิ่ม fallback (2026-09-18 รอบ 6): ผู้ใช้ให้ลองดูแถวที่ชื่อยังว่างอยู่ดีๆ อีกรอบ — พบว่าหลาย
แถว (ส่วนใหญ่คือกลุ่ม "รอลงทะเบียนสินค้า" ที่ไม่มี Phy-ID เลย + บางแถวที่ Phy-ID ไม่มีใน ITEC-MIS
เพราะเป็นบิลจาก K2 ล้วนๆ ไม่เคยผ่าน iTEC) หา Comment เจอจริงถ้าค้นด้วย **Application Number
โดยตรง** แทน (เจอ Application Number ฝังอยู่ใน Comment เองอยู่แล้ว ไม่ต้องพึ่ง Phy-ID/ITEC-MIS
เป็นตัวกลางเลย) — เพิ่มเป็นคีย์ join ที่ 2 (สำรองเวลา Phy-ID join ไม่เจอ) กู้เพิ่มได้ 17/59 แถว
ตอนทดสอบ (ที่เหลือยังหาไม่เจอจริงๆ เพราะ Application Number ไม่ปรากฏใน Comment ของ ITec เลย)
"""
import re
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
_sys.path.insert(0, str(_ROOT))
_sys.path.insert(0, str(_ROOT / "clean_flow"))

import config
import sheets_client

BILL_AUTO_CAL_K2_KILL_TAB_GID = 1018276173  # "Bill K2 Kill" (ไฟล์ Bill Auto Cal)
DEST_START_ROW = 2
PHY_ID_COL = "H"
APPLICATION_STATUS_COL = "AD"
# ข้ามแถวสถานะเหล่านี้ ไม่เติมชื่อให้ (ยืนยันจากผู้ใช้ 2026-09-18)
EXCLUDED_APPLICATION_STATUSES = {"ลูกหนี้ปกติ", "Approve", "ยกเลิกการขอสินเชื่อ"}
DEST_COL = "AJ"
DEST_HEADER = "ชื่อ-นามสกุลลูกค้า (ดึงจาก Comment)"

_LABEL_PREFIX_RE = re.compile(r"^ชื่อ\s*:?\s*")
_PURE_NUMERIC_RE = re.compile(r"^[0-9.,\s]+$")
_MONEY_WORD_RE = re.compile(r"เงินดาวน์|^ดาวน์|วางดาวน์")
_LABEL_LEAK_RE = re.compile(r"เลขที่|สัญญา|ใบคำขอ")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"[0-9]")
_THAI_LETTER_RE = re.compile(r"[฀-๿]")


def _looks_like_name(s: str) -> bool:
    """เกณฑ์ชื่อลูกค้าที่ยอมรับ — ยืนยันจากผู้ใช้ (2026-09-18):
    1) เอาเฉพาะชื่อภาษาไทยเท่านั้น (บาง Comment ดึงชื่อมหาวิทยาลัยภาษาอังกฤษมาผิด เช่น
       "Pibulsongkram Rajabhat University") ต้องมีตัวอักษรไทยอยู่ ห้ามมีตัวอักษรอังกฤษปนเลย
    2) ห้ามมีตัวเลขปนอยู่เลย (เจอจริง: บางแถวชื่อมีเบอร์โทรต่อท้ายติดมาด้วย เช่น
       "สมศักดิ์ ตัวอย่าง 0812345678" หรือหลุดเป็นเลขที่สัญญา/ใบคำขอไปเลยแทนชื่อจริง)"""
    if not s:
        return False
    if _PURE_NUMERIC_RE.match(s):
        return False
    if _MONEY_WORD_RE.search(s):
        return False
    if _LABEL_LEAK_RE.search(s):
        return False
    if _LATIN_LETTER_RE.search(s):
        return False
    if _DIGIT_RE.search(s):
        return False
    if not _THAI_LETTER_RE.search(s):
        return False
    return True


def _parse_customer_name(comment: str) -> str:
    """แยกชื่อลูกค้าจาก Comment ของ ITec — ดู docstring บนสุดของไฟล์นี้สำหรับรูปแบบที่เจอจริง"""
    if not comment:
        return ""
    parts = [p.strip() for p in comment.split("/")]
    if len(parts) < 2:
        return ""
    candidates = []
    if len(parts) >= 3:
        candidates.append(parts[2])
    candidates.append(parts[1])
    for c in candidates:
        cleaned = _LABEL_PREFIX_RE.sub("", c).strip()
        if _looks_like_name(cleaned):
            return cleaned
    return ""


def _build_invoice_to_name_map() -> dict[str, str]:
    ws = sheets_client.get_itec_tab_worksheet()
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:B{ws.row_count}"), tries=6, delay=20)
    mapping = {}
    for r in vals:
        invoice = r[0].strip() if len(r) > 0 else ""
        comment = r[1].strip() if len(r) > 1 else ""
        if not invoice or invoice in mapping:
            continue
        name = _parse_customer_name(comment)
        if name:
            mapping[invoice] = name
    return mapping


_APPNO_TOKEN_RE = re.compile(r"\d{6}-\d{6}|\d{8,20}")


def _extract_appno_and_name(comment: str) -> tuple[str, str]:
    """หา token ที่ "เป็น Application Number" ในตัว Comment เอง (รูปแบบ K2 ตัวเลขล้วน 8-20 หลัก
    หรือ ITOS มีขีด XXXXXX-XXXXXX) แล้วเดาว่าชื่อลูกค้าอยู่ token ถัดไปทันที — ใช้เป็นคีย์ join
    สำรอง (ดู fallback รอบ 6 ด้านบน) ไม่ต้องพึ่ง Phy-ID/ITEC-MIS เป็นตัวกลางเลย"""
    if not comment:
        return "", ""
    parts = [p.strip() for p in comment.split("/")]
    for i, p in enumerate(parts):
        m = _APPNO_TOKEN_RE.search(p)
        if not m or i + 1 >= len(parts):
            continue
        name_candidate = _LABEL_PREFIX_RE.sub("", parts[i + 1]).strip()
        if _looks_like_name(name_candidate):
            return m.group(0), name_candidate
    return "", ""


def _build_appno_to_name_map() -> dict[str, str]:
    ws = sheets_client.get_itec_tab_worksheet()
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:B{ws.row_count}"), tries=6, delay=20)
    mapping = {}
    for r in vals:
        comment = r[1].strip() if len(r) > 1 else ""
        appno, name = _extract_appno_and_name(comment)
        if appno and name and appno not in mapping:
            mapping[appno] = name
    return mapping


_LEADING_LETTERS_RE = re.compile(r"^[A-Za-z]+")


def _normalize_phyid_key(phy: str, branch_id: str) -> str:
    """เจอจริง (2026-09-18): บาง Phy-ID ในชีท Bill K2 Kill/K2+ITOS มีตัวอักษรนำหน้าติดมาด้วย
    (เช่น "PHY344-2496" แทนที่จะเป็น "344-2496" เฉยๆ — เจอเฉพาะสาขา Franchise Partner บางแห่ง)
    แต่ฝั่ง ITEC-MIS เก็บเป็นตัวเลขล้วนเสมอ ("344") — ตัดตัวอักษรนำหน้าออกก่อน join กันคีย์ไม่ตรง"""
    phy_clean = _LEADING_LETTERS_RE.sub("", phy.strip())
    return f"{phy_clean}-{branch_id.strip()}"


def _build_invoice_to_phyid_map() -> dict[str, tuple[str, str]]:
    ws = sheets_client.get_itec_mis_worksheet()
    vals = sheets_client.with_retry(lambda: ws.get(f"A2:I{ws.row_count}"), tries=6, delay=20)
    mapping = {}
    for r in vals:
        invoice = r[4].strip() if len(r) > 4 else ""
        phy = r[0].strip() if len(r) > 0 else ""
        branch_id = r[1].strip() if len(r) > 1 else ""
        if invoice and invoice not in mapping:
            mapping[invoice] = (phy, branch_id)
    return mapping


def _get_k2_kill_worksheet():
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_CAL_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(BILL_AUTO_CAL_K2_KILL_TAB_GID)


def main() -> None:
    print("[fill-customer-name] กำลังอ่านชีท ITec (Comment) แยกชื่อลูกค้า ...", flush=True)
    invoice_to_name = _build_invoice_to_name_map()
    print(f"[fill-customer-name] แยกชื่อได้ {len(invoice_to_name)} Invoice NO", flush=True)

    print("[fill-customer-name] กำลังอ่านชีท ITEC-MIS หา Phy-ID ของแต่ละ Invoice NO ...", flush=True)
    invoice_to_phyid = _build_invoice_to_phyid_map()

    # รวมเป็น phyid -> name โดยตรง (ถ้า Phy-ID เดียวมีหลาย Invoice ชื่อไม่ตรงกัน เก็บตัวแรกที่เจอ)
    phyid_to_name = {}
    for invoice, name in invoice_to_name.items():
        phy, branch_id = invoice_to_phyid.get(invoice, ("", ""))
        if phy and branch_id:
            key = _normalize_phyid_key(phy, branch_id)
            phyid_to_name.setdefault(key, name)
    print(f"[fill-customer-name] รวมเป็น Phy-ID -> ชื่อ ได้ {len(phyid_to_name)} คีย์ไม่ซ้ำ", flush=True)

    print("[fill-customer-name] กำลังสร้างคีย์สำรอง Application Number -> ชื่อ จาก Comment โดยตรง ...",
          flush=True)
    appno_to_name = _build_appno_to_name_map()
    print(f"[fill-customer-name] เจอคีย์สำรอง {len(appno_to_name)} Application Number", flush=True)

    ws = _get_k2_kill_worksheet()
    phy_vals = sheets_client.with_retry(
        lambda: ws.get(f"{PHY_ID_COL}{DEST_START_ROW}:{APPLICATION_STATUS_COL}{ws.row_count}"),
        tries=6, delay=20,
    )
    print(f"[fill-customer-name] อ่าน Bill K2 Kill คอลัมน์ {PHY_ID_COL}:{APPLICATION_STATUS_COL} ได้ "
          f"{len(phy_vals)} แถว", flush=True)

    sheets_client.with_retry(
        lambda: ws.update([[DEST_HEADER]], f"{DEST_COL}1", value_input_option="USER_ENTERED")
    )

    out_values = []
    found = 0
    found_via_appno_fallback = 0
    skipped_status = 0
    for row in phy_vals:
        phy = row[0].strip() if row else ""
        appno = row[18].strip() if len(row) > 18 else ""  # APPLICATION NUMBER คือคอลัมน์ที่ 19 นับจาก H
        status = row[22].strip() if len(row) > 22 else ""  # AD คือคอลัมน์ที่ 23 นับจาก H (H=1)
        if status in EXCLUDED_APPLICATION_STATUSES:
            skipped_status += 1
            out_values.append([""])
            continue
        name = phyid_to_name.get(_LEADING_LETTERS_RE.sub("", phy), "") if phy else ""
        if not name and appno:
            name = appno_to_name.get(appno, "")
            if name:
                found_via_appno_fallback += 1
        if name:
            found += 1
        out_values.append([name])

    if not out_values:
        print("[fill-customer-name] ไม่มีแถวให้เติม จบการทำงาน", flush=True)
        return

    end_row = DEST_START_ROW + len(out_values) - 1
    print(f"[fill-customer-name] ข้าม {skipped_status} แถวที่สถานะอยู่ใน {EXCLUDED_APPLICATION_STATUSES} — "
          f"กำลังเขียนชื่อ {found}/{len(out_values)} แถวที่จับคู่ได้ (ในนั้นเจอผ่าน Application Number "
          f"fallback {found_via_appno_fallback} แถว) ลงคอลัมน์ "
          f"{DEST_COL}{DEST_START_ROW}:{DEST_COL}{end_row} ...", flush=True)
    sheets_client.with_retry(
        lambda: ws.update(out_values, f"{DEST_COL}{DEST_START_ROW}:{DEST_COL}{end_row}",
                           value_input_option="USER_ENTERED")
    )
    print("[fill-customer-name] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
