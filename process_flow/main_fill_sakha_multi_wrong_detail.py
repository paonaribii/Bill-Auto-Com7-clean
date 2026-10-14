"""เติมคอลัมน์ S (Ufund Update) และ T (รายละเอียด) ของชีท "สาขาเปิดบิลใน ITec ผิด" (ไฟล์ Sakha,
gid=0) — ยืนยันจากผู้ใช้ (2026-09-29): แถวที่เหลืออยู่ในชีทนี้ (หลังสเตจ 4.47 ย้ายบิลที่ผิด
"จุดเดียว" ออกไปหน้า "ผลที่ผิด iTec" แล้ว) คือบิลที่ผิด **มากกว่า 1 จุดพร้อมกัน** ทั้งหมด —
S ต้องบอกว่า "ผิดมากกว่า 1 อย่าง" และ T ต้องแจกแจงให้ครบว่าผิดอะไรบ้าง (เช่น ราคาก็เอามาเทียบ
K2/ITOS vs iTEC ให้เห็นตัวเลขจริง ไม่ใช่แค่บอกว่า "ผิด" เฉยๆ)

คอลัมน์ที่ใช้ตรวจสอบ (ตรงกับ main_build_itec_only_wrong_bill.py): Comment(I), ราคา(J),
Customer(Code)(K), Member Code(L), Customer(Name)(M), สำนักงานใหญ่(N), สถานะรับเงิน(O)
ค่าอ้างอิงจริงฝั่ง iTEC-MIS อยู่บล็อก 2 ท้ายแถว (idx50-56: comment, ราคา, Customer(Code),
Member Code, Customer(Name), สำนักงานใหญ่, สถานะรับเงิน (Finish)) — ใช้โชว์ค่าจริงเทียบให้เห็น
ส่วนราคาฝั่ง K2/ITOS ใช้ SUMPRICE (idx31)

ค่าที่ "ควรจะเป็น" ของแต่ละช่อง (ยืนยันจาก logic เดิมที่มีอยู่แล้วใน cal.py/
main_flag_company_name_anomalies.py):
  Customer(Code) ควรเป็นหนึ่งใน UFUND STUDENT/UFUND PERSONAL/UFUND UNIDAYS
  Member Code ควรเป็น AEE0201777774 (เลขประจำตัวผู้เสียภาษีคงที่)
  สำนักงานใหญ่ ควรเป็น "สำนักงานใหญ่"
  สถานะรับเงิน ควรเป็น "ยังรับเงินไม่ครบ"

⚠️ แก้เพิ่ม (2026-09-29 รอบ 6): แถวที่ผิด "แค่ราคาอย่างเดียว" (J="แก้ไข" แต่ K:O ทุกช่อง
"ถูกต้อง" หมด — ราคาถูกตัดออกจากการนับ "ผิดมากกว่า 1 อย่าง" ไปแล้วตามที่ยืนยันไว้ก่อนหน้า)
ผู้ใช้ให้เติม S/T ด้วยเหมือนกัน ใช้ป้าย "ราคาสองระบบไม่ตรงกัน / ต้องเปิดบิลให้ตรงกับระบบ"
(ข้อความมาตรฐานเดิมที่เคยใช้ในสูตร S ของชีทนี้เอง) + รายละเอียดราคาเทียบ K2/ITOS vs iTEC ใน T
"""
import re
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
import sheets_client

SOURCE_TAB_GID = 0  # "สาขาเปิดบิลใน ITec ผิด"
SOURCE_START_ROW = 8
READ_COLS = 57  # A ถึง BE (idx0-56) — ครอบคลุมบล็อก 2 ที่ต้องใช้อ้างอิงค่าจริง

COMMENT_COL_IDX = 8
PRICE_COL_IDX = 9
CUSTOMER_CODE_COL_IDX = 10
MEMBER_CODE_COL_IDX = 11
CUSTOMER_NAME_COL_IDX = 12
HQ_COL_IDX = 13
PAYMENT_STATUS_COL_IDX = 14
SUMMARY_COL_IDX = 15
UFUND_UPDATE_COL_IDX = 18  # S
DETAIL_COL_IDX = 19  # T

SUMPRICE_COL_IDX = 31  # ราคาฝั่ง K2/ITOS (SUMPRICE)
# บล็อก 2 (ค่าจริงฝั่ง iTEC-MIS) — idx50-56
ITEC_COMMENT_IDX = 50
ITEC_PRICE_IDX = 51
ITEC_CUSTOMER_CODE_IDX = 52
ITEC_MEMBER_CODE_IDX = 53
ITEC_CUSTOMER_NAME_IDX = 54
ITEC_HQ_IDX = 55
ITEC_PAYMENT_STATUS_IDX = 56

CORRECT_VALUE = "ถูกต้อง"
MULTI_WRONG_NOTE = "มีบิลผิดมากกว่า 1 จุด"  # ผู้ใช้เปลี่ยนข้อความ 2026-10-05 (เดิม "ผิดมากกว่า 1 อย่าง")
PRICE_ONLY_WRONG_NOTE = "ราคาสองระบบไม่ตรงกัน / ต้องเปิดบิลให้ตรงกับระบบ"
PAYMENT_ONLY_WRONG_NOTE = "สถานะรับเงินต้องเป็นค้างรับ"  # ผู้ใช้เปลี่ยนข้อความ 2026-10-05 (เดิม "สถานะรับเงินไม่ตรง")
EXPECTED_CUSTOMER_CODE = "UFUND STUDENT / UFUND PERSONAL / UFUND UNIDAYS"
EXPECTED_MEMBER_CODE = "AEE0201777774"
EXPECTED_HQ = "สำนักงานใหญ่"
EXPECTED_PAYMENT_STATUS = "ยังรับเงินไม่ครบ"


def _get_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SAKHA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def _cell(row: list[str], idx: int) -> str:
    return row[idx].strip() if len(row) > idx else ""


def _to_num(x: str):
    cleaned = re.sub(r"[^\d.\-]", "", str(x))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _price_really_wrong(row: list[str]) -> bool:
    """ราคา "ผิดจริง" = คอลัมน์ผลตรวจสอบไม่ใช่ถูกต้อง **และ** ตัวเลข SUMPRICE กับราคา iTEC ต่างกันจริง —
    เจอจริง (ผู้ใช้ชี้ 2026-10-05): บางแถวเช็คขึ้น "แก้ไข" ทั้งที่ตัวเลขเท่ากัน (เช่น "฿24,100" vs 24100
    รูปแบบข้อความต่างกัน) ไม่ถือเป็นจุดผิด"""
    if _cell(row, PRICE_COL_IDX) in ("", CORRECT_VALUE):
        return False
    a, b = _to_num(_cell(row, SUMPRICE_COL_IDX)), _to_num(_cell(row, ITEC_PRICE_IDX))
    return not (a is not None and b is not None and a == b)


def _count_wrong(row: list[str]) -> int:
    idxs = [COMMENT_COL_IDX, CUSTOMER_CODE_COL_IDX, MEMBER_CODE_COL_IDX,
            CUSTOMER_NAME_COL_IDX, HQ_COL_IDX, PAYMENT_STATUS_COL_IDX]
    return sum(1 for i in idxs if _cell(row, i) and _cell(row, i) != CORRECT_VALUE)


def _build_detail(row: list[str]) -> str:
    """ยืนยันจากผู้ใช้ (2026-09-29 รอบ 5): เอาแบบสั้นๆ เป็น bullet (ขึ้นบรรทัดใหม่ต่อ 1 จุด
    ไม่ต้องพูดซ้ำคำว่า iTEC มี/ควรเป็น ทุกจุด — ใช้ลูกศร -> แทน)"""
    parts = []
    if _price_really_wrong(row):
        sumprice = _cell(row, SUMPRICE_COL_IDX)
        itec_price = _cell(row, ITEC_PRICE_IDX)
        parts.append(f"ราคา: {sumprice} -> {itec_price}")
    if _cell(row, CUSTOMER_CODE_COL_IDX) != CORRECT_VALUE:
        parts.append(f"Customer(Code): {_cell(row, ITEC_CUSTOMER_CODE_IDX)} -> "
                      f"STUDENT/PERSONAL/UNIDAYS")
    if _cell(row, MEMBER_CODE_COL_IDX) != CORRECT_VALUE:
        parts.append(f"Member Code: {_cell(row, ITEC_MEMBER_CODE_IDX)} -> {EXPECTED_MEMBER_CODE}")
    if _cell(row, CUSTOMER_NAME_COL_IDX) != CORRECT_VALUE:
        parts.append(f"Customer(Name): {_cell(row, ITEC_CUSTOMER_NAME_IDX)}")
    if _cell(row, HQ_COL_IDX) != CORRECT_VALUE:
        parts.append(f"สำนักงานใหญ่: {_cell(row, ITEC_HQ_IDX)} -> {EXPECTED_HQ}")
    if _cell(row, PAYMENT_STATUS_COL_IDX) != CORRECT_VALUE:
        parts.append(f"สถานะรับเงิน: {_cell(row, ITEC_PAYMENT_STATUS_IDX)} -> "
                      f"{EXPECTED_PAYMENT_STATUS}")
    if _cell(row, COMMENT_COL_IDX) != CORRECT_VALUE:
        parts.append(f"Comment: {_cell(row, COMMENT_COL_IDX)}")
    return "\n".join(f"• {p}" for p in parts)


MATCH_NOT_FOUND_VALUE = "Match ไม่เจอ"
MATCH_NOT_FOUND_NOTE = "ไม่พบบิลใน ITec คอมเมนท์เลข Application ผิด // ไม่ใส่เลข Application ที่ช่องคอมเมนท์"
# ป้าย S ของแถวที่ผิดจุดเดียว (ไม่ใช่ราคา/สถานะรับเงิน): "สำนักงานใหญ่ผิด" มาจากผู้ใช้ (2026-09-29);
# ที่เหลือตั้งตามรูปแบบเดียวกัน "<ช่อง>ผิด" (ยังไม่เคยมีผู้ใช้กำหนดเป็นพิเศษ)
_SINGLE_LABELS = {
    COMMENT_COL_IDX: "Comment ผิด",
    CUSTOMER_CODE_COL_IDX: "Customer(Code) ผิด",
    MEMBER_CODE_COL_IDX: "Member Code ผิด",
    CUSTOMER_NAME_COL_IDX: "Customer(Name) ผิด",
    HQ_COL_IDX: "สำนักงานใหญ่ผิด",
}


def compute_s_t(row: list[str]) -> tuple[str, str]:
    """คำนวณ (S = Ufund Update, T = รายละเอียด) ของแถวหนึ่ง ตามกติกาเดียวทุกหน้า (ยืนยันจากผู้ใช้
    2026-10-06 ให้ใช้ logic เดียวกับ สาขาเปิดบิลใน ITec ผิด / ผลที่ผิด iTec):
      - Comment = Match ไม่เจอ -> ข้อความมาตรฐาน (T ว่าง ไม่มีข้อมูล iTEC ให้เทียบ)
      - จุดผิดรวม (6 ช่องผลตรวจ + ราคาที่ผิดจริง) >= 2 -> "มีบิลผิดมากกว่า 1 จุด" + T แจกแจงทุกจุด
      - ผิดจุดเดียว: ราคา / สถานะรับเงิน / สำนักงานใหญ่ / ช่องอื่น -> ป้ายและรายละเอียดของจุดนั้น
      - ไม่มีจุดผิด -> ว่างทั้งคู่"""
    if _cell(row, COMMENT_COL_IDX) == MATCH_NOT_FOUND_VALUE:
        return MATCH_NOT_FOUND_NOTE, ""
    price_wrong = _price_really_wrong(row)
    points = _count_wrong(row) + (1 if price_wrong else 0)
    if points >= 2:
        return MULTI_WRONG_NOTE, _build_detail(row)
    if points == 0:
        return "", ""
    if price_wrong:
        return PRICE_ONLY_WRONG_NOTE, (f"K2/ITOS: {_cell(row, SUMPRICE_COL_IDX)} vs "
                                       f"ITEC: {_cell(row, ITEC_PRICE_IDX)} // แก้ไขบิลใน ITEC")
    if _cell(row, PAYMENT_STATUS_COL_IDX) not in ("", CORRECT_VALUE):
        return PAYMENT_ONLY_WRONG_NOTE, (f"สถานะรับเงิน: {_cell(row, ITEC_PAYMENT_STATUS_IDX)} -> "
                                         f"{EXPECTED_PAYMENT_STATUS}")
    if _cell(row, HQ_COL_IDX) not in ("", CORRECT_VALUE):
        return _SINGLE_LABELS[HQ_COL_IDX], f"สำนักงานใหญ่: {_cell(row, ITEC_HQ_IDX)} -> {EXPECTED_HQ}"
    if _cell(row, CUSTOMER_CODE_COL_IDX) not in ("", CORRECT_VALUE):
        return _SINGLE_LABELS[CUSTOMER_CODE_COL_IDX], (f"Customer(Code): {_cell(row, ITEC_CUSTOMER_CODE_IDX)} -> "
                                                       f"STUDENT/PERSONAL/UNIDAYS")
    if _cell(row, MEMBER_CODE_COL_IDX) not in ("", CORRECT_VALUE):
        return _SINGLE_LABELS[MEMBER_CODE_COL_IDX], (f"Member Code: {_cell(row, ITEC_MEMBER_CODE_IDX)} -> "
                                                     f"{EXPECTED_MEMBER_CODE}")
    if _cell(row, CUSTOMER_NAME_COL_IDX) not in ("", CORRECT_VALUE):
        return _SINGLE_LABELS[CUSTOMER_NAME_COL_IDX], f"Customer(Name): {_cell(row, ITEC_CUSTOMER_NAME_IDX)}"
    return _SINGLE_LABELS[COMMENT_COL_IDX], f"Comment: {_cell(row, COMMENT_COL_IDX)}"


def main() -> None:
    ws = _get_worksheet(SOURCE_TAB_GID)
    print("[multi-wrong-detail] กำลังอ่านชีท สาขาเปิดบิลใน ITec ผิด ...", flush=True)
    values = sheets_client.read_range_values(ws, SOURCE_START_ROW, 1, READ_COLS)
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    print(f"[multi-wrong-detail] อ่านได้ {len(values)} แถว", flush=True)

    s_values = []
    t_values = []
    multi_count = 0
    price_only_count = 0
    for row in values:
        s_val, t_val = compute_s_t(row)
        s_values.append([s_val])
        t_values.append([t_val])
        multi_count += s_val == MULTI_WRONG_NOTE
        price_only_count += s_val == PRICE_ONLY_WRONG_NOTE

    print(f"[multi-wrong-detail] เจอ {multi_count} แถวที่ผิดมากกว่า 1 จุด, "
          f"{price_only_count} แถวที่ผิดแค่ราคาอย่างเดียว", flush=True)
    if not values:
        print("[multi-wrong-detail] ไม่มีแถวให้เติม จบการทำงาน", flush=True)
        return

    end_row = SOURCE_START_ROW + len(values) - 1
    sheets_client.with_retry(
        lambda: ws.update(s_values, f"S{SOURCE_START_ROW}:S{end_row}", value_input_option="USER_ENTERED")
    )
    sheets_client.with_retry(
        lambda: ws.update(t_values, f"T{SOURCE_START_ROW}:T{end_row}", value_input_option="USER_ENTERED")
    )
    print("[multi-wrong-detail] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
