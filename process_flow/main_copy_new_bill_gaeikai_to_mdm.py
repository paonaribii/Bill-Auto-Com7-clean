"""คัดลอกแถว "บิลแก้ไข" ที่เพิ่งถูกเพิ่มเข้ามาใหม่วันนี้ ในชีท "สาขาเปิดบิลใน ITec ผิด"
(ไฟล์ Sakha, gid=0) ไปวางต่อท้ายที่ปลายทางหลายจุด (ดู DESTINATIONS ด้านล่าง) แบบ**ถอดสูตร
(ค่านิ่ง)** เท่านั้น — ตามคำสั่งผู้ใช้ (2026-09-09):

    "หลังจากจบโฟลแล้วช่วยเพิ่ม ขั้นตอนการคัดลอก [สาขาเปิดบิลใน ITec ผิด] บิลแก้ไข
    ที่เพิ่มเข้ามาแถวไหนบ้างมาวางใน [บันทึกความผิดของ MDM] แบบถอดสูตรนะ
    ห้ามลบหน้านี้นะมีแต่เพิ่ม พอเข้าใจไหม"

และภายหลัง (2026-09-09 อีกรอบ): "ช่วยเอาข้อมูลพวกนี้เพิ่มต่อไปใน [สาขาเปิดบิลใน ITec ผิด
(ค้างเก่า), gid=1625083142] หน้านี้ด้วยได้ไหม แบบเดียวกันเลย" -> เพิ่มเป็นปลายทางที่ 2
(ปลายทางทั้งสองใช้ชุดแถวใหม่ "วันนี้" ชุดเดียวกัน แค่กันซ้ำ (dedup) แยกกันต่อปลายทาง)

วิธีหา "แถวที่เพิ่มเข้ามาใหม่วันนี้": เทียบ key (Phy + ID) ของข้อมูล "วันนี้" ใน สาขาเปิดบิลใน
ITec ผิด (gid=0, หลังสเตจ 4.4 เขียนทับเสร็จแล้ว) กับ key ในชีท "ของเมื่อวาน" (gid=998909771)
— ของเมื่อวาน ถูก archive ไว้ตอนสเตจ 4.25 (ก่อน 4.3/4.4 เขียนทับ gid=0) ดังนั้นตอนนี้ ของเมื่อวาน
= สแนปช็อตข้อมูล "ก่อนรอบรันวันนี้" พอดี ใช้ pattern diff เดียวกับที่เคยใช้สำรวจ "บิลแก้ไขเยอะขนาด
นี้เลยหรอ" ก่อนหน้านี้ (today_keys - yesterday_keys)

key ที่ไม่มีใน ของเมื่อวาน = แถวใหม่ของวันนี้ -> เอาแถวเต็ม (A:BV, ค่าที่อ่านมาจาก ws.get()
เป็นค่าที่ถูกคำนวณแล้ว ไม่ใช่ตัวสูตรอยู่แล้ว = "ถอดสูตร" ตามที่ผู้ใช้ขอ) ไปวางต่อท้ายแถวสุดท้ายที่
มีข้อมูลอยู่แล้วในแต่ละปลายทาง **ห้ามลบ/เคลียร์ปลายทางเด็ดขาด มีแต่เพิ่มต่อท้ายเท่านั้น** และ
กันซ้ำ key กับของที่มีอยู่แล้วในปลายทางนั้นๆ ก่อนวางทุกครั้ง (เผื่อรันซ้ำ/รันหลายรอบในวันเดียวกัน)

โครงสร้างต้นทาง (สาขาเปิดบิลใน ITec ผิด): header แถว 7, ข้อมูลเริ่มแถว 8, คอลัมน์ A:BV (74 คอลัมน์)
โครงสร้างเทียบ (ของเมื่อวาน): header แถว 4, ข้อมูลเริ่มแถว 5, คอลัมน์ A:BV เหมือนกัน
โครงสร้างปลายทางทั้งสอง: header แถว 7, ข้อมูลเริ่มแถว 8, คอลัมน์ A:BV เหมือนกันทั้งคู่
(ยืนยันจาก header ตรงกัน: Phy, ID, Store Name, BU, RM, AM, ... — เป็น mirror โครงสร้างเดียวกัน)

⚠️ หมายเหตุ: gid ใน DESTINATIONS ของไฟล์ MDM ผูกกับเดือนปัจจุบันเท่านั้น (ตอนนี้ "Oct" 248757607 — เดิม "Sep"
738145572 ถูกเปลี่ยนเมื่อ 2026-10-05 ตามที่ผู้ใช้สั่ง ย้ายแถวเดือน 10 ออกจาก Sep ไป Oct แล้ว) — ถ้าขึ้นเดือน
ถัดไปและมีการสร้างแท็บเดือนใหม่ในไฟล์ บันทึกความผิดของ MDM ต้องมาอัปเดต gid นี้เอง (ยังไม่มี
กลไก auto-detect แท็บเดือนปัจจุบัน)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
import sheets_client
import main_fill_sakha_multi_wrong_detail as fill_detail

SAKHA_TAB_GID = 0  # "สาขาเปิดบิลใน ITec ผิด" (ต้นทาง — ข้อมูล "วันนี้" หลังเขียนทับเสร็จแล้ว)
SAKHA_YESTERDAY_TAB_GID = 998909771  # "ของเมื่อวาน" (ใช้เทียบหา key ใหม่เท่านั้น ไม่แก้ไข)

SOURCE_START_ROW = 8  # สาขาเปิดบิลใน ITec ผิด เริ่มข้อมูลที่แถว 8
YESTERDAY_START_ROW = 5  # ของเมื่อวาน เริ่มข้อมูลที่แถว 5
NUM_COLS = 74  # A:BV
DEST_START_ROW = 8  # ทุกปลายทาง เริ่มข้อมูลที่แถว 8 (header แถว 7 เหมือนต้นทาง)

MDM_SPREADSHEET_ID = config.MDM_ERROR_LOG_SPREADSHEET_ID  # "บันทึกความผิดของ MDM"

# ปลายทางทั้งหมดที่ต้อง append แถวใหม่ชุดเดียวกันนี้ไปวาง — (label, spreadsheet_id, gid)
DESTINATIONS = [
    ("Oct (บันทึกความผิดของ MDM)", MDM_SPREADSHEET_ID, 248757607),  # เดือน 10 (ย้ายจาก Sep 2026-10-05)
    # ปลายทาง "สาขาเปิดบิลใน ITec ผิด (ค้างเก่า)" gid=1625083142 ถูกถอดออก (ผู้ใช้สั่ง 2026-10-06: จะลบหน้านั้นทิ้ง ไม่ต้องอัปแล้ว)
]


# ⚠️ ยืนยันจากผู้ใช้ (2026-10-06): คอลัมน์ C:G (idx 2-6) และ BF:BG (idx 57-58, 0-based) ของแท็บ Sep/Oct ในไฟล์
# "บันทึกความผิดของ MDM" ผู้ใช้ผูกสูตรไว้เอง ห้ามล้าง/เขียนตอนวางต่อท้าย — ข้ามคอลัมน์เหล่านี้
# (เขียนเป็นก้อนต่อเนื่อง A:B, H:BE, BH:BV)
_MDM_PROTECTED_COLS = {2, 3, 4, 5, 6, 57, 58}
SKIP_COLS_BY_TAB = {
    (MDM_SPREADSHEET_ID, 738145572): _MDM_PROTECTED_COLS,  # Sep
    (MDM_SPREADSHEET_ID, 248757607): _MDM_PROTECTED_COLS,  # Oct
}


def _col_a1(idx1: int) -> str:
    letters = ""
    while idx1 > 0:
        idx1, rem = divmod(idx1 - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _write_rows_skipping(ws, rows: list[list[str]], row_no: int, skip: set[int]) -> None:
    """เขียนแถวเป็นก้อนคอลัมน์ต่อเนื่อง ข้ามคอลัมน์ใน skip (0-based) — ไม่แตะเซลล์ที่ข้าม"""
    n = len(rows[0]) if rows else 0
    start = None
    for i in range(n + 1):
        keep = i < n and i not in skip
        if keep and start is None:
            start = i
        if not keep and start is not None:
            block = [r[start:i] for r in rows]
            sheets_client.with_retry(
                lambda block=block, start=start: ws.update(block, f"{_col_a1(start + 1)}{row_no}",
                                                           value_input_option="USER_ENTERED")
            )
            start = None


def _get_worksheet(spreadsheet_id: str, gid: int):
    client = sheets_client.get_client()
    sh = client.open_by_key(spreadsheet_id)
    return sh.get_worksheet_by_id(gid)


def _read_rows(ws, start_row: int) -> list[list[str]]:
    values = sheets_client.read_range_values(ws, start_row, 1, NUM_COLS)
    while values and not any((cell or "").strip() for cell in values[-1]):
        values.pop()
    return values


def _row_key(row: list[str]) -> str:
    """key = Phy (A) + ID (B) — เหมือน pattern ที่ใช้เทียบ key ที่อื่นในโปรเจกต์นี้"""
    phy = (row[0] if len(row) > 0 else "").strip()
    id_ = (row[1] if len(row) > 1 else "").strip()
    return f"{phy}|{id_}"


def _compute_unique_new_rows_today() -> list[list[str]]:
    """เทียบ key วันนี้ (สาขาเปิดบิลใน ITec ผิด) กับ ของเมื่อวาน คืนแถวใหม่ที่เพิ่มเข้ามาวันนี้
    (กันซ้ำภายในชุดเดียวกันแล้ว) — ใช้ร่วมกันทุกปลายทาง"""
    source_ws = _get_worksheet(config.BILL_AUTO_SAKHA_SPREADSHEET_ID, SAKHA_TAB_GID)
    yesterday_ws = _get_worksheet(config.BILL_AUTO_SAKHA_SPREADSHEET_ID, SAKHA_YESTERDAY_TAB_GID)

    print("[copy-mdm] กำลังอ่าน สาขาเปิดบิลใน ITec ผิด (วันนี้) ...", flush=True)
    today_rows = _read_rows(source_ws, SOURCE_START_ROW)
    print(f"[copy-mdm] อ่านได้ {len(today_rows)} แถว (วันนี้)", flush=True)

    print("[copy-mdm] กำลังอ่าน ของเมื่อวาน (ไว้เทียบ key) ...", flush=True)
    yesterday_rows = _read_rows(yesterday_ws, YESTERDAY_START_ROW)
    print(f"[copy-mdm] อ่านได้ {len(yesterday_rows)} แถว (เมื่อวาน)", flush=True)

    yesterday_keys = {_row_key(row) for row in yesterday_rows}
    new_rows = [row for row in today_rows if _row_key(row) not in yesterday_keys]

    # กันซ้ำภายในชุดวันนี้เอง (เผื่อ key ซ้ำในต้นทาง เอาแถวแรกที่เจอ)
    seen: set[str] = set()
    unique_new_rows = []
    for row in new_rows:
        key = _row_key(row)
        if key not in seen:
            seen.add(key)
            unique_new_rows.append(row)

    print(f"[copy-mdm] พบแถวใหม่ที่เพิ่มเข้ามาวันนี้ {len(new_rows)} แถว "
          f"(เทียบ key Phy+ID กับของเมื่อวาน) -> เหลือ {len(unique_new_rows)} แถวหลังตัด key ซ้ำ",
          flush=True)
    return unique_new_rows


def _append_to_destination(label: str, spreadsheet_id: str, gid: int,
                            unique_new_rows: list[list[str]]) -> int:
    """วางต่อท้าย unique_new_rows ที่ปลายทางเดียว (กันซ้ำกับของเดิมในปลายทางนั้นก่อนเสมอ,
    ไม่ลบ/เคลียร์ของเก่าเด็ดขาด) — คืนจำนวนแถวที่ append จริง"""
    dest_ws = _get_worksheet(spreadsheet_id, gid)

    existing_dest_rows = _read_rows(dest_ws, DEST_START_ROW)
    existing_dest_keys = {_row_key(row) for row in existing_dest_rows}
    to_append = [row for row in unique_new_rows if _row_key(row) not in existing_dest_keys]

    skipped = len(unique_new_rows) - len(to_append)
    if skipped:
        print(f"[copy-mdm][{label}] ตัด {skipped} แถวที่มี key ซ้ำกับที่มีอยู่แล้วออก", flush=True)

    if not to_append:
        print(f"[copy-mdm][{label}] ไม่มีแถวใหม่ (แบบยูนีค) ให้เพิ่ม ข้ามปลายทางนี้", flush=True)
        return 0

    normalized = [row + [""] * (NUM_COLS - len(row)) for row in to_append]

    next_row = DEST_START_ROW + len(existing_dest_rows)
    print(f"[copy-mdm][{label}] แถวว่างแรกต่อท้ายของเก่าคือแถว {next_row} ...", flush=True)

    needed_rows = next_row + len(normalized) - 1
    if dest_ws.row_count < needed_rows:
        print(f"[copy-mdm][{label}] ขยายชีทจาก {dest_ws.row_count} เป็น {needed_rows} แถว ...",
              flush=True)
        sheets_client.with_retry(lambda: dest_ws.resize(rows=needed_rows))

    print(f"[copy-mdm][{label}] กำลังวางต่อท้าย {len(normalized)} แถว เริ่มแถว {next_row} "
          f"(ค่านิ่ง ไม่ใช่สูตร, ไม่ลบของเก่า) ...", flush=True)
    skip = SKIP_COLS_BY_TAB.get((spreadsheet_id, gid), set())
    if skip:
        # แท็บ MDM: เติม S (Ufund Update) / T (รายละเอียด) ให้แถวใหม่ด้วย logic เดียวกับ สาขาเปิดบิลใน ITec ผิด /
        # ผลที่ผิด iTec (ยืนยันจากผู้ใช้ 2026-10-06) — 4.46 รันก่อน 4.48 แถวต้นทางจึงยังไม่มี S/T ตอน copy
        for row in normalized:
            row[18], row[19] = fill_detail.compute_s_t(row)
        _write_rows_skipping(dest_ws, normalized, next_row, skip)
    else:
        sheets_client.with_retry(
            lambda: dest_ws.update(normalized, f"A{next_row}", value_input_option="USER_ENTERED")
        )

    print(f"[copy-mdm][{label}] เสร็จสิ้น", flush=True)
    return len(normalized)


# ---- ปลายทางพิเศษ: ไฟล์ "แก้ไข Comment Itec" แท็บ "แก้ไขบิลผิดใน iTec" (แทนหน้า "ค้างเก่า" — ผู้ใช้สั่ง 2026-10-06)
# เอาเฉพาะ (1) Comment = "Match ไม่เจอ" (2) สำนักงานใหญ่ = "แก้ไข" **กรณีเดียว** (ช่องผลตรวจอื่น
# Comment/Customer(Code)/Member Code/Customer(Name) ถูกต้องหมด — logic เดียวกับสเตจ 4.47) กันซ้ำด้วย
# เลข APPLICATION NUMBER (AR) วางต่อท้ายเท่านั้น ไม่ลบของเดิม — เขียนเฉพาะ A:BF (ข้าม BG ที่เป็น
# ARRAYFORMULA กับ BH ขึ้นไปที่ผู้ใช้กรอก/ผูกสูตรเอง เช่น BJ) พร้อมเติม S/T ด้วยข้อความเดิมที่ผู้ใช้ใช้ในหน้านั้น
FLAGGED_SPREADSHEET_ID = config.FLAGGED_SPREADSHEET_ID
FLAGGED_TAB_GID = 0
FLAGGED_WRITE_COLS = 58  # A:BF (0-based ครึ่งเปิด 0..58)
FLAGGED_LABEL = "แก้ไขบิลผิดใน iTec (ไฟล์ แก้ไข Comment Itec)"
_FLAGGED_S_T = {
    "match": (fill_detail.MATCH_NOT_FOUND_NOTE, "แก้ไข Comment ใน Sale Bill view and Full Inv View"),
    "hq": ("สำนักงานใหญ่ผิด", "ทำการยกเลิกบิลแล้วออกใหม่"),
}
_APPNO_COL_IDX = 43  # AR


def _flagged_kind(row: list[str]) -> str:
    """"match" / "hq" / "" — ดูคำอธิบายด้านบน"""
    cell = lambda i: (row[i] if len(row) > i else "").strip()
    if cell(8) == "Match ไม่เจอ":
        return "match"
    if cell(13) == "แก้ไข" and all(cell(i) in ("", "ถูกต้อง") for i in (8, 10, 11, 12)):
        return "hq"
    return ""


def _append_flagged_rows(unique_new_rows: list[list[str]]) -> int:
    ws = _get_worksheet(FLAGGED_SPREADSHEET_ID, FLAGGED_TAB_GID)
    picked = [(r, _flagged_kind(r)) for r in unique_new_rows]
    picked = [(r, k) for r, k in picked if k]
    print(f"[copy-mdm][{FLAGGED_LABEL}] แถวใหม่ที่เข้าเงื่อนไข (Match ไม่เจอ/สำนักงานใหญ่ผิดอย่างเดียว) "
          f"{len(picked)} จาก {len(unique_new_rows)} แถว", flush=True)
    if not picked:
        return 0

    existing_rows = _read_rows(ws, DEST_START_ROW)
    existing_app = sheets_client.with_retry(
        lambda: ws.get_values(f"AR{DEST_START_ROW}:AR{DEST_START_ROW + len(existing_rows) - 1}",
                              value_render_option="UNFORMATTED_VALUE"))
    def norm(v):
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v).strip()
    seen = {norm(r[0]) for r in existing_app if r and norm(r[0])}
    seen_phyid = {_row_key(r) for r in existing_rows}
    out = []
    for r, k in picked:
        r = r + [""] * (NUM_COLS - len(r))
        app = r[_APPNO_COL_IDX].strip()
        if app:
            if app in seen:
                continue
            seen.add(app)
        else:
            if _row_key(r) in seen_phyid:
                continue
            seen_phyid.add(_row_key(r))
        r[18], r[19] = _FLAGGED_S_T[k]
        out.append(r[:FLAGGED_WRITE_COLS])
    print(f"[copy-mdm][{FLAGGED_LABEL}] ตัดซ้ำ App No แล้วเหลือ {len(out)} แถว", flush=True)
    if not out:
        return 0
    next_row = DEST_START_ROW + len(existing_rows)
    needed = next_row + len(out) - 1
    if ws.row_count < needed:
        sheets_client.with_retry(lambda: ws.resize(rows=needed))
    sheets_client.with_retry(lambda: ws.update(out, f"A{next_row}", value_input_option="USER_ENTERED"))
    print(f"[copy-mdm][{FLAGGED_LABEL}] วางต่อท้ายแถว {next_row}-{needed} (A:BF)", flush=True)
    return len(out)


def copy_new_gaeikai_rows_to_mdm() -> dict[str, int]:
    """หาแถวใหม่ของวันนี้ครั้งเดียว แล้ววางต่อท้ายทุกปลายทางใน DESTINATIONS
    (แต่ละปลายทางกันซ้ำแยกกันเอง) — คืน dict {label: จำนวนแถวที่ append จริง}"""
    unique_new_rows = _compute_unique_new_rows_today()

    if not unique_new_rows:
        print("[copy-mdm] ไม่มีแถวใหม่เลยวันนี้ ไม่ต้องวางอะไรเพิ่มที่ปลายทางไหนเลย", flush=True)
        return {**{label: 0 for label, _, _ in DESTINATIONS}, FLAGGED_LABEL: 0}

    results = {}
    for label, spreadsheet_id, gid in DESTINATIONS:
        results[label] = _append_to_destination(label, spreadsheet_id, gid, unique_new_rows)
    results[FLAGGED_LABEL] = _append_flagged_rows(unique_new_rows)
    return results


def main() -> None:
    copy_new_gaeikai_rows_to_mdm()


if __name__ == "__main__":
    main()
