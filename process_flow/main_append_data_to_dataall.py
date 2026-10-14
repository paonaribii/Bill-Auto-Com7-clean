"""สเตจ 4.23: คัดลอกแถวจากแท็บ "Data" (gid=1733585806) ไปวาง**ต่อท้าย**แท็บ "DataAll" (gid=671322146)
ในสเปรดชีทภายนอกเดียวกัน (PO_APPROVED_SPREADSHEET_ID) — ยืนยันจากผู้ใช้ (2026-10-05):
  - เอาทั้งแถว A:AK (หัวคอลัมน์ Data/DataAll ตรงกันเป๊ะ)
  - ไม่เอาแถวที่เลข APPLICATION NUMBER (คอลัมน์ Z) ซ้ำกับที่มีอยู่ใน DataAll แล้ว (และซ้ำกันเองในชุดนี้)
  - DataAll เป็นแท็บสะสม: วางต่อท้ายเท่านั้น **ห้ามลบ/ล้าง/เขียนทับของเดิม**
  - เอาเฉพาะแถวที่ Application Status (คอลัมน์ AD) เป็นหนึ่งใน ALLOWED_APP_STATUSES ด้านล่าง ที่เหลือไม่เอา
    (ยืนยันจากผู้ใช้ 2026-10-05 — เปลี่ยนจาก "ไม่เอาลูกหนี้ปกติ" เป็นแบบเอาเฉพาะ 4 สถานะ)
ต้องรัน**หลัง 4.22** (4.22 เขียนทับ Data ใหม่ทุกรอบ) แถวที่ App No ว่างใช้ PO NUMBER (คอลัมน์ C) กันซ้ำแทน
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
import sheets_client

EXTERNAL_SPREADSHEET_ID = config.PO_APPROVED_SPREADSHEET_ID
DATA_TAB_GID = 1733585806
DATAALL_TAB_GID = 671322146
START_ROW = 2  # header แถว 1
NUM_COLS = 37  # A:AK
APPNO_COL_LETTER = "Z"
PO_NUMBER_COL_IDX = 2  # C
APP_STATUS_COL_IDX = 29  # AD
ALLOWED_APP_STATUSES = {"รอดำเนินการ MDM", "ลูกค้ารีวิวสัญญา", "ลูกค้ารีวิวสัญญาแนบท้าย", "รอลงทะเบียนสินค้า"}
CHUNK = 5000


def _norm(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _read_block(ws) -> list[list[str]]:
    rows = sheets_client.read_range_values(ws, START_ROW, 1, NUM_COLS)
    while rows and not any((c or "").strip() for c in rows[-1]):
        rows.pop()
    return rows


def _read_appnos(ws, n_rows: int) -> list[str]:
    vals = sheets_client.with_retry(
        lambda: ws.get_values(f"{APPNO_COL_LETTER}{START_ROW}:{APPNO_COL_LETTER}{START_ROW + n_rows - 1}",
                              value_render_option="UNFORMATTED_VALUE")
    )
    out = [_norm(r[0]) if r else "" for r in vals]
    return out + [""] * (n_rows - len(out))


def _key(row: list[str], appno: str) -> str:
    if appno:
        return f"APP|{appno}"
    return f"PO|{(row[PO_NUMBER_COL_IDX] if len(row) > PO_NUMBER_COL_IDX else '').strip()}"


def main() -> None:
    client = sheets_client.get_client()
    sh = client.open_by_key(EXTERNAL_SPREADSHEET_ID)
    src_ws = sh.get_worksheet_by_id(DATA_TAB_GID)
    dst_ws = sh.get_worksheet_by_id(DATAALL_TAB_GID)

    if (dst_ws.cell(1, 2).value or "").strip() != (src_ws.cell(1, 2).value or "").strip():
        raise RuntimeError("หัวคอลัมน์ Data/DataAll ไม่ตรงกัน — โครงสร้างเปลี่ยน หยุดไม่เขียน")

    src_rows = _read_block(src_ws)
    dst_rows = _read_block(dst_ws)
    print(f"[append-dataall] Data {len(src_rows)} แถว, DataAll มีอยู่แล้ว {len(dst_rows)} แถว", flush=True)
    if not src_rows:
        return

    src_app = _read_appnos(src_ws, len(src_rows))
    dst_app = _read_appnos(dst_ws, len(dst_rows)) if dst_rows else []

    existing = {_key(r, a) for r, a in zip(dst_rows, dst_app)}
    to_append = []
    skipped_status = 0
    for r, a in zip(src_rows, src_app):
        if (r[APP_STATUS_COL_IDX] if len(r) > APP_STATUS_COL_IDX else "").strip() not in ALLOWED_APP_STATUSES:
            skipped_status += 1
            continue
        k = _key(r, a)
        if k in existing:
            continue
        existing.add(k)
        to_append.append(r + [""] * (NUM_COLS - len(r)))
    print(f"[append-dataall] ข้าม {skipped_status} แถวที่ AD ไม่อยู่ใน 4 สถานะที่เอา — เหลือ {len(to_append)} แถวใหม่ "
          f"(ซ้ำ App No {len(src_rows) - skipped_status - len(to_append)} แถว)", flush=True)
    if not to_append:
        return

    next_row = START_ROW + len(dst_rows)
    needed = next_row + len(to_append) - 1
    if dst_ws.row_count < needed:
        print(f"[append-dataall] ขยาย DataAll จาก {dst_ws.row_count} เป็น {needed} แถว", flush=True)
        sheets_client.with_retry(lambda: dst_ws.resize(rows=needed))

    for off in range(0, len(to_append), CHUNK):
        chunk = to_append[off:off + CHUNK]
        row_no = next_row + off
        sheets_client.with_retry(lambda: dst_ws.update(chunk, f"A{row_no}", value_input_option="USER_ENTERED"))
        print(f"[append-dataall] วางแล้ว {min(off + CHUNK, len(to_append))}/{len(to_append)} แถว", flush=True)
    print("[append-dataall] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
