"""คัดกรองบิลจากชีท "สาขาเปิดบิลใน ITec ผิด" (ไฟล์ Sakha, gid=0) เอาเฉพาะแถวที่ **มีจุดที่ผิดอยู่
"แค่จุดเดียวจริงๆ" ในบรรดาคอลัมน์ผลตรวจสอบทั้งหมด** ไปวางที่ชีท "ผลที่ผิด iTec" (ไฟล์ Sakha
เดียวกัน) แบบค่านิ่ง (ไม่ใช่สูตร — ยืนยันจากผู้ใช้ 2026-09-29 "ไม่เอาแบบผูกสูตร")

นิยาม "ผิด" (ยืนยันจากผู้ใช้): ค่าในคอลัมน์เป็น "แก้ไข" หรือ "Match ไม่เจอ" (คอลัมน์นี้มีได้ 3 ค่า
คือ ถูกต้อง/แก้ไข/Match ไม่เจอ)

⚠️ แก้บั๊กสำคัญ (2026-09-29 รอบ 3): ตอนแรกเช็คแค่ 2 คอลัมน์ (Comment กับ สำนักงานใหญ่) เท่านั้น
— ผู้ใช้เจอเคสจริงที่ Comment ถูกต้อง แต่ ราคา/Customer(Code)/Member Code/Customer(Name)/
สำนักงานใหญ่/สถานะรับเงิน ผิดพร้อมกันตั้ง 6 คอลัมน์! (ไม่ใช่ผิดแค่จุดเดียวจริง) แต่ระบบเดิมมองแค่
2 คอลัมน์เลยตัดสินผิดว่า "ผิดแค่จุดเดียว" (สำนักงานใหญ่) ทั้งที่จริงผิดหลายจุด — ต้องเช็คให้ครบ
ทุกคอลัมน์ผลตรวจสอบ (VERDICT_COL_INDICES ด้านล่าง) ไม่ใช่แค่ I/N

เงื่อนไขสุดท้าย (ยืนยันจากผู้ใช้ 2026-09-29 รอบ 4): นับจำนวนคอลัมน์ผลตรวจสอบ (Comment,
Customer(Code), Member Code, Customer(Name), สำนักงานใหญ่, สถานะรับเงิน — **ไม่รวมราคา**) ที่
ไม่ใช่ "ถูกต้อง" — เอาเฉพาะแถวที่มีจำนวนนับได้เท่ากับ 1 พอดี ("ผิดจุดเดียวจริงๆ" ไม่รวมราคา) ไม่นับ
คอลัมน์ "สรุปผลการตรวจสอบ" (เป็นค่ารวม ไม่ใช่จุดตรวจสอบจริง) — **ข้อยกเว้น**: ถ้า Comment =
"Match ไม่เจอ" ให้เอาเสมอไม่ว่ากี่คอลัมน์จะเป็น "Match ไม่เจอ" ตามไปด้วยก็ตาม (Match ล้มทั้งแถว
นับแบบปกติไม่ได้)

⚠️ ยืนยันจากผู้ใช้เพิ่ม (2026-09-29): ต้องเป็นการ "ย้าย" ไม่ใช่แค่ก็อป — ลบแถวที่ย้ายไปแล้วออกจาก
"สาขาเปิดบิลใน ITec ผิด" (ต้นทาง) ด้วย ไม่งั้นแถวเดียวกันจะซ้ำอยู่ทั้ง 2 ที่ — เพราะต้นทางถูก
เขียนทับใหม่ทั้งหมดทุกวันโดยสเตจ 4.3/4.4/4.45 (Python คำนวณใหม่จาก "หน้าร้านแก้ไข" + anomaly
bolt-on) สคริปต์นี้เลยต้องรันเป็นสเตจถาวร **หลัง 4.45 เสมอ** ในทุกรอบ pipeline ไม่ใช่รันครั้งเดียว
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
import sheets_client

SOURCE_TAB_GID = 0  # "สาขาเปิดบิลใน ITec ผิด"
DEST_TAB_GID = 526078975  # "ผลที่ผิด iTec"
SOURCE_START_ROW = 8
DEST_START_ROW = 8
# ⚠️ ต้องใช้ความกว้างเต็ม A:BU (73 คอลัมน์) ไม่ใช่แค่ A:S — สาขาเปิดบิลใน ITec ผิด มีข้อมูล
# บล็อก 2 อยู่ที่ U:BE ด้วย (เขียนโดย main_build_sakha_details.py) ถ้าย้าย/เขียนทับด้วยแค่ A:S
# จะทำข้อมูลบล็อก 2 ของแถวที่เหลือ (ไม่ได้ย้าย) หายไปหมด
NUM_COLS = 73  # A:BU (เท่ากับ archive_sakha_to_yesterday.py ใช้)

COMMENT_COL_IDX = 8  # I (0-based)
PRICE_COL_IDX = 9  # J (0-based) — ยืนยันจากผู้ใช้ (2026-09-29 รอบ 4): "ราคาผิด" ไม่นับเป็นเหตุผล
# ให้ย้ายเข้าหน้านี้เลย (มีหน้า/ขั้นตอนอื่นดูแลเรื่องราคาแยกต่างหากอยู่แล้ว — ดูโน้ต
# "***ดูเทียบราคาช่อง Sumprice(AE) กับราคา ITec ช่อง (AY)" ในชีทต้นทางเอง)
HQ_COL_IDX = 13  # N (0-based)
PAYMENT_STATUS_COL_IDX = 14  # O (0-based)
UFUND_UPDATE_COL_IDX = 18  # S (0-based)
# คอลัมน์ผลตรวจสอบที่ใช้นับ "ผิดจุดเดียว" (ยืนยันจากผู้ใช้ 2026-09-29 รอบ 4) — Comment(I),
# Customer(Code)(K), Member Code(L), Customer(Name)(M), สำนักงานใหญ่(N)
# **ไม่รวมราคา (J)** เลย (ผิดแค่ราคาอย่างเดียวไม่ต้องย้ายมาหน้านี้) และไม่รวม "สรุปผลการตรวจสอบ"
# (P, idx15) เพราะเป็นค่ารวม ไม่ใช่จุดตรวจสอบจริงจุดหนึ่ง
#
# ⚠️ ยืนยันจากผู้ใช้ (2026-10-05 ย้ำสุดท้าย): ผิดแค่ "สถานะรับเงิน" (O, idx14) อย่างเดียว **ต้องอยู่หน้า
# สาขาเปิดบิลใน ITec ผิด ไม่ย้ายมาหน้านี้** — เลยไม่นับสถานะรับเงินในเงื่อนไข (เหมือนราคา) ห้ามเอากลับมานับอีก
VERDICT_COL_INDICES = [8, 10, 11, 12, 13]
CORRECT_VALUE = "ถูกต้อง"
WRONG_VALUE = "แก้ไข"
MATCH_NOT_FOUND_VALUE = "Match ไม่เจอ"
# ยืนยันจากผู้ใช้ (2026-09-29 รอบ 2): เติมโน้ต "สำนักงานใหญ่ผิด" ลง S **เฉพาะตอน N="แก้ไข"
# เป๊ะๆ เท่านั้น** (ไม่ใช่ N="Match ไม่เจอ" ด้วย — คนละความหมายกัน) ก่อนหน้านี้เขียนทับ S แบบ
# ไม่แยกแยะ ทำให้ 53 แถวที่จริงๆ เป็น "Match ไม่เจอ" คู่กัน (ไม่ใช่ "แก้ไข") โดนเขียนทับข้อความ
# เดิมทิ้งไปผิดๆ — กู้คืนด้วยข้อความมาตรฐานที่สูตร S เดิมของต้นทางเคยให้ไว้แทน (ยืนยันจากตัวอย่าง
# จริงที่ยังมีอยู่ตอนทดสอบสูตรครั้งก่อน)
HQ_WRONG_NOTE = "สำนักงานใหญ่ผิด"
MATCH_NOT_FOUND_NOTE = "ไม่พบบิลใน ITec คอมเมนท์เลข Application ผิด // ไม่ใส่เลข Application ที่ช่องคอมเมนท์"


def _get_worksheet(gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(config.BILL_AUTO_SAKHA_SPREADSHEET_ID)
    return sh.get_worksheet_by_id(gid)


def _count_wrong_verdicts(row: list[str]) -> int:
    count = 0
    for idx in VERDICT_COL_INDICES:
        value = row[idx].strip() if len(row) > idx else ""
        if value and value != CORRECT_VALUE:
            count += 1
    return count


def _should_include(row: list[str]) -> bool:
    """ยืนยันจากผู้ใช้ (2026-09-29 รอบ 4):
    1) Comment = "Match ไม่เจอ" -> เอาเสมอ (กรณีนี้ Match ล้มทั้งแถว ทุกคอลัมน์ผลตรวจสอบเลย
       พลอยกลายเป็น "Match ไม่เจอ" ไปด้วยกันหมด นับแบบ "ผิดจุดเดียว" ปกติไม่ได้ ต้อง bypass)
    2) นอกนั้น เอาเฉพาะแถวที่ผิด "จุดเดียวจริง" ในบรรดา VERDICT_COL_INDICES (ไม่รวมราคา)"""
    comment = row[COMMENT_COL_IDX].strip() if len(row) > COMMENT_COL_IDX else ""
    if comment == MATCH_NOT_FOUND_VALUE:
        return True
    return _count_wrong_verdicts(row) == 1


def _with_hq_note(row: list[str]) -> list[str]:
    """เติมโน้ตลงคอลัมน์ S (Ufund Update) ของแถวที่ย้ายไป ตามสถานะจริงของ สำนักงานใหญ่ (N):
    - N="แก้ไข" เป๊ะๆ -> "สำนักงานใหญ่ผิด"
    - N="Match ไม่เจอ" -> ข้อความมาตรฐานเดิม (ไม่ใช่ "สำนักงานใหญ่ผิด" — คนละความหมาย)
    - N="ถูกต้อง" (แปลว่าแถวนี้ย้ายมาเพราะ Comment ผิดแทน) -> ไม่แตะ S เลย คงค่าเดิมไว้
    ยืนยันจากผู้ใช้ 2026-09-29 รอบ 2"""
    hq = row[HQ_COL_IDX].strip() if len(row) > HQ_COL_IDX else ""
    if hq == CORRECT_VALUE:
        return row
    note = HQ_WRONG_NOTE if hq == WRONG_VALUE else MATCH_NOT_FOUND_NOTE if hq == MATCH_NOT_FOUND_VALUE else None
    if note is None:
        return row
    new_row = list(row)
    while len(new_row) <= UFUND_UPDATE_COL_IDX:
        new_row.append("")
    new_row[UFUND_UPDATE_COL_IDX] = note
    return new_row


def _col_letter(idx1: int) -> str:
    """1-based column index -> ตัวอักษรคอลัมน์ (A, B, ..., Z, AA, ...)"""
    letters = ""
    while idx1 > 0:
        idx1, rem = divmod(idx1 - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


# ⚠️ ยืนยันจากผู้ใช้ (2026-10-05): คอลัมน์ C:G และ BF:BG ของทั้ง 2 ชีท (ต้นทาง+ปลายทาง) ผู้ใช้ผูกสูตรไว้เอง
# ห้ามล้าง/เขียนเด็ดขาด — ล้างและเขียนเฉพาะบล็อกด้านล่างนี้ (0-based, ครึ่งเปิด): A:B, H:BE, BH:BU
WRITE_BLOCKS = [(0, 2), (7, 57), (59, 73)]  # ปลายทาง "ผลที่ผิด iTec": A:B, H:BE, BH:BU
# ต้นทางใช้บล็อกเดียวกัน (A:B, H:BE, BH:BU) — คอลัมน์ที่ผู้ใช้ผูกสูตรไว้คือ C:G และ BF:BG เท่านั้น (ไม่ใช่ B)
SRC_WRITE_BLOCKS = WRITE_BLOCKS


def _clear_blocks(ws, start_row: int, last_row: int, blocks=None) -> None:
    ranges = [f"{_col_letter(a + 1)}{start_row}:{_col_letter(b)}{last_row}" for a, b in (blocks or WRITE_BLOCKS)]
    sheets_client.with_retry(lambda: ws.batch_clear(ranges))


def _write_blocks(ws, rows: list[list[str]], start_row: int, blocks=None) -> None:
    for a, b in (blocks or WRITE_BLOCKS):
        block = [r[a:b] for r in rows]
        sheets_client.with_retry(
            lambda block=block, a=a: ws.update(block, f"{_col_letter(a + 1)}{start_row}",
                                               value_input_option="USER_ENTERED")
        )


def main() -> None:
    src_ws = _get_worksheet(SOURCE_TAB_GID)
    dst_ws = _get_worksheet(DEST_TAB_GID)
    last_col_letter = _col_letter(NUM_COLS)

    print(f"[itec-only-wrong] กำลังอ่านชีท สาขาเปิดบิลใน ITec ผิด คอลัมน์ A:{last_col_letter} ...",
          flush=True)
    values = sheets_client.read_range_values(src_ws, SOURCE_START_ROW, 1, NUM_COLS)
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    print(f"[itec-only-wrong] อ่านได้ {len(values)} แถว", flush=True)

    moved = [row for row in values if _should_include(row)]
    kept = [row for row in values if not _should_include(row)]
    print(f"[itec-only-wrong] เจอ {len(moved)} แถวที่ผิดอย่างใดอย่างเดียว (ตัดกรณีผิดพร้อมกัน "
          f"'แก้ไข'+'แก้ไข' ออกแล้ว) — เหลือ {len(kept)} แถวในต้นทาง", flush=True)

    # ล้างปลายทางเก่าทิ้งก่อน (เขียนทับใหม่ทั้งหมดทุกรอบ ไม่สะสมซ้ำ)
    dest_last_row = max(dst_ws.row_count, DEST_START_ROW + len(moved) - 1, 2000)
    _clear_blocks(dst_ws, DEST_START_ROW, dest_last_row)

    if moved:
        needed_rows = DEST_START_ROW + len(moved) - 1
        if dst_ws.row_count < needed_rows:
            sheets_client.with_retry(lambda: dst_ws.resize(rows=needed_rows))
        normalized_moved = []
        for row in moved:
            noted = _with_hq_note(row)
            normalized_moved.append(noted + [""] * (NUM_COLS - len(noted)))
        print(f"[itec-only-wrong] กำลังวาง {len(normalized_moved)} แถว ที่ชีท ผลที่ผิด iTec "
              f"(ข้าม C:G, BF:BG) ...", flush=True)
        _write_blocks(dst_ws, normalized_moved, DEST_START_ROW)
    else:
        print("[itec-only-wrong] ไม่มีแถวให้ย้าย", flush=True)

    # ลบแถวที่ย้ายไปแล้วออกจากต้นทาง — เขียนทับด้วยเฉพาะแถวที่เหลือ (kept) แล้วเคลียร์ส่วนท้าย
    src_last_row = max(src_ws.row_count, SOURCE_START_ROW + len(values) - 1)
    _clear_blocks(src_ws, SOURCE_START_ROW, src_last_row, SRC_WRITE_BLOCKS)
    if kept:
        normalized_kept = [row + [""] * (NUM_COLS - len(row)) for row in kept]
        print(f"[itec-only-wrong] กำลังเขียนทับต้นทางด้วย {len(normalized_kept)} แถวที่เหลือ "
              f"(ลบแถวที่ย้ายไปแล้วออก, ข้าม C:G, BF:BG) ...", flush=True)
        _write_blocks(src_ws, normalized_kept, SOURCE_START_ROW, SRC_WRITE_BLOCKS)
    print("[itec-only-wrong] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
