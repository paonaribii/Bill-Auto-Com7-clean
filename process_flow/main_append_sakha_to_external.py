"""สเตจสุดท้ายของ pipeline (6.1): เอาแถวจากชีท "สาขาเปิดบิลใน ITec ผิด" (ไฟล์ Sakha, gid=0) ไปวาง
**ต่อท้าย** ชีท "สาขาเปิดบิลใน ITec ผิด" ของสเปรดชีทภายนอก (SAKHA_EXTERNAL_SPREADSHEET_ID)
(gid=0) — ยืนยันจากผู้ใช้ (2026-10-05):
  - เอาทั้งแถว (A:BG ซึ่งตรงกับหัวคอลัมน์ปลายทางเป๊ะ; BH:BN ของปลายทางเป็นคอลัมน์เพิ่มของผู้ใช้ ไม่แตะ)
  - ไม่เอาแถวที่เลข APPLICATION NUMBER (คอลัมน์ AR) ซ้ำกับที่มีอยู่ในปลายทางแล้ว (และซ้ำกันเองในชุดนี้)
  - **ห้ามลบ/ล้าง/เขียนทับของเดิมในปลายทางเด็ดขาด** วางต่อท้ายแถวสุดท้ายเท่านั้น (ค่านิ่ง)
แถวที่ App No ว่าง: ใช้ key Phy+ID แทนเพื่อกันซ้ำ

คอลัมน์ BH (ชื่อลูกค้า) ของปลายทาง: เติมให้เฉพาะแถวที่วางต่อท้ายใหม่ ด้วยชื่อที่แยกจาก Comment ของแท็บ ITec
(logic เดียวกับ main_fill_billkill_customer_name.py — join ผ่าน Phy-ID ก่อน แล้ว fallback ด้วย Application
Number) ไม่เจอก็ปล่อยว่าง ไม่เดา (ยืนยันจากผู้ใช้ 2026-10-05)
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import config
import sheets_client
import main_fill_billkill_customer_name as cn

SRC_TAB_GID = 0
DEST_SPREADSHEET_ID = config.SAKHA_EXTERNAL_SPREADSHEET_ID
DEST_TAB_GID = 0
START_ROW = 8  # ทั้งต้นทางและปลายทาง header แถว 7 ข้อมูลเริ่มแถว 8
NUM_COLS = 59  # A:BG
APPNO_COL_IDX = 43  # AR (0-based)
APPNO_COL_LETTER = "AR"


def _norm_appno(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _read_appnos(ws, n_rows: int) -> list[str]:
    vals = sheets_client.with_retry(
        lambda: ws.get_values(f"{APPNO_COL_LETTER}{START_ROW}:{APPNO_COL_LETTER}{START_ROW + n_rows - 1}",
                              value_render_option="UNFORMATTED_VALUE")
    )
    out = [_norm_appno(r[0]) if r else "" for r in vals]
    return out + [""] * (n_rows - len(out))


def _read_block(ws) -> list[list[str]]:
    rows = sheets_client.read_range_values(ws, START_ROW, 1, NUM_COLS)
    while rows and not any((c or "").strip() for c in rows[-1]):
        rows.pop()
    return rows


def _key(row: list[str], appno: str) -> str:
    if appno:
        return f"APP|{appno}"
    phy = (row[0] if len(row) > 0 else "").strip()
    id_ = (row[1] if len(row) > 1 else "").strip()
    return f"PHYID|{phy}|{id_}"


def _build_name_lookup():
    invoice_to_name = cn._build_invoice_to_name_map()
    invoice_to_phyid = cn._build_invoice_to_phyid_map()
    phyid_to_name = {}
    for invoice, name in invoice_to_name.items():
        phy, branch_id = invoice_to_phyid.get(invoice, ("", ""))
        if phy and branch_id:
            phyid_to_name.setdefault(cn._normalize_phyid_key(phy, branch_id), name)
    appno_to_name = cn._build_appno_to_name_map()

    def lookup(row: list[str], appno: str) -> str:
        phy = (row[0] if len(row) > 0 else "").strip()
        branch = (row[1] if len(row) > 1 else "").strip()
        name = phyid_to_name.get(cn._normalize_phyid_key(phy, branch), "") if phy and branch else ""
        return name or (appno_to_name.get(appno, "") if appno else "")

    return lookup


def main() -> None:
    client = sheets_client.get_client()
    src_ws = client.open_by_key(config.BILL_AUTO_SAKHA_SPREADSHEET_ID).get_worksheet_by_id(SRC_TAB_GID)
    dst_ws = client.open_by_key(DEST_SPREADSHEET_ID).get_worksheet_by_id(DEST_TAB_GID)

    if (dst_ws.cell(7, 1).value or "").strip() != "Phy":
        raise RuntimeError("ปลายทางแถว 7 ไม่ใช่ header (Phy) — โครงสร้างเปลี่ยน หยุดไม่เขียน")

    src_rows = _read_block(src_ws)
    dst_rows = _read_block(dst_ws)
    print(f"[append-ext] ต้นทาง {len(src_rows)} แถว, ปลายทางมีอยู่แล้ว {len(dst_rows)} แถว", flush=True)
    if not src_rows:
        print("[append-ext] ต้นทางว่าง จบการทำงาน", flush=True)
        return

    src_app = _read_appnos(src_ws, len(src_rows))
    dst_app = _read_appnos(dst_ws, len(dst_rows))

    dst_keys = [_key(r, a) for r, a in zip(dst_rows, dst_app)]
    if len(dst_keys) != len(set(dst_keys)):
        # ผู้ใช้สั่ง (2026-10-06): ห้ามมีเลขที่ใบคำขอซ้ำ — สเตจนี้ไม่ลบของเดิมเอง แต่เตือนให้เห็นถ้ามีคนวางซ้ำเอง
        print(f"[append-ext] !!! เตือน: ปลายทางมีเลขที่ใบคำขอซ้ำ {len(dst_keys) - len(set(dst_keys))} แถว "
              f"(ไม่ได้มาจากสเตจนี้ — ต้องลบเอง/สั่งให้ลบ)", flush=True)
    existing = set(dst_keys)
    to_append = []
    new_appnos = []
    for r, a in zip(src_rows, src_app):
        k = _key(r, a)
        if k in existing:
            continue
        existing.add(k)
        to_append.append(r + [""] * (NUM_COLS - len(r)))
        new_appnos.append(a)

    if to_append:
        lookup = _build_name_lookup()
        names = [lookup(r, a) for r, a in zip(to_append, new_appnos)]
        to_append = [r + [n] for r, n in zip(to_append, names)]  # คอลัมน์ที่ 60 = BH ชื่อลูกค้า
        print(f"[append-ext] หาชื่อลูกค้าเจอ {sum(1 for n in names if n)}/{len(names)} แถว", flush=True)

    print(f"[append-ext] ตัดซ้ำแล้วเหลือ {len(to_append)} แถวใหม่ (ซ้ำ {len(src_rows) - len(to_append)} แถว)",
          flush=True)
    if not to_append:
        return

    next_row = START_ROW + len(dst_rows)
    needed = next_row + len(to_append) - 1
    if dst_ws.row_count < needed:
        sheets_client.with_retry(lambda: dst_ws.resize(rows=needed))
    print(f"[append-ext] วางต่อท้ายแถว {next_row}-{needed} (A:BG + ชื่อลูกค้า BH)", flush=True)
    sheets_client.with_retry(
        lambda: dst_ws.update(to_append, f"A{next_row}", value_input_option="USER_ENTERED")
    )
    print("[append-ext] เสร็จสิ้น", flush=True)


if __name__ == "__main__":
    main()
