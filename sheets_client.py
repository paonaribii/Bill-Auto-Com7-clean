import datetime
import time

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    # ต้องมี scope นี้เพิ่มถึงจะเรียก client.export() (ดาวน์โหลดชีทเป็นไฟล์ Excel ผ่าน Drive
    # API ได้) — ใช้กับ Etax->Confirm เลข Application เพื่อกันปัญหาสูตรสด recalculate ไม่ทัน
    "https://www.googleapis.com/auth/drive.readonly",
]

K2_ITOS_TAB = "K2+ITOS"
ITEC_MIS_TAB = "ITec Mis"
CAL_TAB = "Cal"
ITEC_TAB = "ITec"

MATCH_FILE_ID = config.MATCH_FILE_ID
BILL_UFUND_CORRECT_FILE_ID = config.BILL_UFUND_CORRECT_FILE_ID


def with_retry(fn, tries: int = 5, delay: int = 15):
    """ชีทที่มีสูตรผูกไว้เยอะ (เช่น Match Approve) บางทีตอบ 503 Service Unavailable ตอน
    กำลังคำนวณหนักๆ — retry รอสักพักแล้วลองใหม่ แทนที่จะพังทันที"""
    last_err = None
    for i in range(tries):
        try:
            return fn()
        except gspread.exceptions.APIError as e:
            last_err = e
            print(f"[with_retry] Sheets API error ({e}) รอ {delay} วิแล้วลองใหม่ (ครั้งที่ {i + 1}/{tries}) ...", flush=True)
            time.sleep(delay)
    raise last_err


def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(str(config.GOOGLE_SERVICE_ACCOUNT_JSON), scopes=SCOPES)
    return gspread.authorize(creds)


def download_spreadsheet_as_xlsx(spreadsheet_id: str, dest_path) -> "Path":  # noqa: F821
    """ดาวน์โหลดทั้งไฟล์ Google Sheets เป็น .xlsx จริง (ผ่าน Drive API export) — ต่างจากอ่านผ่าน
    gspread ตรงๆ ตรงที่ Google บังคับ recalculate สูตรทุกตัวให้เสร็จก่อน export เสมอ (export
    เป็นการ "render" สแนปช็อตล่าสุดจริง) กันปัญหาสูตรสด (เช่น Etax ที่เป็น FILTER จาก
    'บิลถูกต้อง') ยังคำนวณไม่ทันตอนอ่านผ่าน API ตรงๆ (values.get) แบบที่เจอมาก่อน

    ต้องมี scope "drive.readonly" (ดู SCOPES ด้านบน) และเปิด Google Drive API ในโปรเจกต์ก่อน
    ถึงจะใช้ได้ (ยืนยันจากผู้ใช้ว่าเปิดแล้ว 2026-09-02)"""
    from pathlib import Path

    client = get_client()
    data = client.export(spreadsheet_id, format=gspread.utils.ExportFormat.EXCEL)
    dest_path = Path(dest_path)
    dest_path.write_bytes(data)
    return dest_path


# ย้ายมาไฟล์ "Bill Auto Data" (BILL_AUTO_DATA_SPREADSHEET_ID) แล้ว — ไฟล์ Bill Auto เดิม
# (BILL_AUTO_SPREADSHEET_ID) จะเต็ม เลยแยกเฉพาะส่วน Flow Clean (ข้อมูลดิบ) มาไว้ไฟล์นี้แทน
def get_k2_itos_worksheet():
    client = get_client()
    sh = client.open_by_key(config.BILL_AUTO_DATA_SPREADSHEET_ID)
    return sh.worksheet(K2_ITOS_TAB)


def get_itec_mis_worksheet():
    client = get_client()
    sh = client.open_by_key(config.BILL_AUTO_DATA_SPREADSHEET_ID)
    return sh.worksheet(ITEC_MIS_TAB)


def get_cal_worksheet():
    client = get_client()
    sh = client.open_by_key(config.BILL_AUTO_DATA_SPREADSHEET_ID)
    return sh.worksheet(CAL_TAB)


def get_itec_tab_worksheet():
    client = get_client()
    sh = client.open_by_key(config.BILL_AUTO_DATA_SPREADSHEET_ID)
    return sh.worksheet(ITEC_TAB)


def read_cal_dataframe() -> pd.DataFrame:
    """อ่านข้อมูลทั้งหมดในแท็บ Cal คืนเป็น DataFrame (ใช้แถว 1 เป็น header)"""
    ws = get_cal_worksheet()
    values = ws.get_all_values()
    if len(values) < 2:
        return pd.DataFrame(columns=values[0] if values else [])
    return pd.DataFrame(values[1:], columns=values[0])


def write_itec_tab(ws, df: pd.DataFrame) -> None:
    """เขียนข้อมูลลงแท็บ ITec ทับของเดิมทั้งหมด (แท็บนี้ไม่มี header อยู่ก่อนแล้ว) แล้วตั้ง
    format คอลัมน์ Comment เป็น custom number "0" ตาม Flow"""
    clear_data_rows(ws) if ws.row_count > 1 else None
    headers = ["Invoice NO", "Comment"]
    values = [headers] + df[headers].astype(object).where(pd.notnull(df), "").values.tolist()
    ws.update(values, "A1", value_input_option="USER_ENTERED")

    if len(df) > 0:
        comment_range = f"B2:B{len(df) + 1}"
        ws.format(comment_range, {"numberFormat": {"type": "NUMBER", "pattern": "0"}})
    print(f"[write_itec_tab] เขียนข้อมูลสำเร็จ {len(df)} แถว ลงแท็บ ITec", flush=True)


def read_worksheet_dataframe(ws) -> pd.DataFrame:
    """อ่านข้อมูลทั้งหมดในชีทใดๆ คืนเป็น DataFrame (ใช้แถว 1 เป็น header)"""
    values = ws.get_all_values()
    if len(values) < 2:
        return pd.DataFrame(columns=values[0] if values else [])
    return pd.DataFrame(values[1:], columns=values[0])


def get_match_file_worksheet(tab_name: str):
    client = get_client()
    sh = client.open_by_key(MATCH_FILE_ID)
    return sh.worksheet(tab_name)


def get_bill_ufund_worksheet(tab_name: str):
    client = get_client()
    sh = client.open_by_key(BILL_UFUND_CORRECT_FILE_ID)
    return sh.worksheet(tab_name)


def get_worksheet_by_gid(file_id: str, gid: int):
    client = get_client()
    sh = client.open_by_key(file_id)
    return sh.get_worksheet_by_id(gid)


def read_range_values(ws, start_row: int, start_col: int, num_cols: int) -> list[list[str]]:
    """อ่านค่าดิบเฉพาะช่วงคอลัมน์ [start_col, start_col+num_cols-1] ตั้งแต่ start_row ถึง
    ท้ายชีท (เร็วกว่าอ่านทั้งชีทถ้าชีทกว้างมากแต่ต้องการแค่บางคอลัมน์) มี retry กัน 503"""
    end_col = start_col + num_cols - 1
    start_a1 = gspread.utils.rowcol_to_a1(start_row, start_col)
    end_a1 = gspread.utils.rowcol_to_a1(max(ws.row_count, start_row), end_col)
    return with_retry(lambda: ws.get(f"{start_a1}:{end_a1}"))


def clear_and_paste_range(ws, df: pd.DataFrame, start_row: int, start_col: int) -> None:
    """ลบข้อมูลเก่าในช่วงคอลัมน์ [start_col, start_col+len(df.columns)-1] ตั้งแต่ start_row
    ถึงท้ายชีท แล้ววางข้อมูลใหม่ทับที่ตำแหน่งเดิม (ไม่แตะคอลัมน์อื่นข้างๆ ที่อาจมีสูตรผูกอยู่)"""
    needed_rows = start_row + len(df) - 1
    if ws.row_count < needed_rows:
        print(f"[clear_and_paste_range] ขยายชีทจาก {ws.row_count} เป็น {needed_rows} แถว "
              f"(ข้อมูลเกิน grid เดิม) ...", flush=True)
        with_retry(lambda: ws.resize(rows=needed_rows))

    end_col = start_col + len(df.columns) - 1
    start_a1 = gspread.utils.rowcol_to_a1(start_row, start_col)
    end_a1 = gspread.utils.rowcol_to_a1(max(ws.row_count, start_row), end_col)
    with_retry(lambda: ws.batch_clear([f"{start_a1}:{end_a1}"]))
    print(f"[clear_and_paste_range] ลบข้อมูลเก่าช่วง {start_a1}:{end_a1} เสร็จแล้ว", flush=True)

    ordered = df.astype(object).where(pd.notnull(df), "")

    def _to_json_safe(v):
        if isinstance(v, (pd.Timestamp, datetime.date, datetime.datetime)):
            has_time = isinstance(v, (pd.Timestamp, datetime.datetime)) and v.time() != datetime.time(0, 0)
            return v.strftime("%d/%m/%Y %H:%M:%S") if has_time else v.strftime("%d/%m/%Y")
        return v

    values = ordered.map(_to_json_safe).values.tolist()
    if not values:
        print("[clear_and_paste_range] ไม่มีข้อมูลให้วาง (0 แถว)", flush=True)
        return

    # เขียนทีเดียวทั้งก้อนเสี่ยง timeout/เกิน payload limit ของ Sheets API ถ้าข้อมูลเยอะ
    # (หลักหมื่นแถว) แบ่งเขียนเป็นก้อนละ 5,000 แถว พร้อม print ความคืบหน้า กันดูเหมือนค้าง
    chunk_size = 5000
    total = len(values)
    for offset in range(0, total, chunk_size):
        chunk = values[offset : offset + chunk_size]
        chunk_start_row = start_row + offset
        chunk_start_a1 = gspread.utils.rowcol_to_a1(chunk_start_row, start_col)
        with_retry(lambda: ws.update(chunk, chunk_start_a1, value_input_option="USER_ENTERED"))
        print(f"[clear_and_paste_range] วางแล้ว {min(offset + chunk_size, total)}/{total} แถว ...", flush=True)

    print(f"[clear_and_paste_range] วางข้อมูลใหม่ {total} แถว เริ่มที่ {start_a1} เสร็จแล้ว", flush=True)
    print("[clear_and_paste_range] หมายเหตุ: สูตร Match Approve ในชีทอาจต้องรอ Google Sheets "
          "คำนวณเองสักครู่ถึงจะเห็นผลครบทุกแถว (อยู่นอกเหนือการควบคุมของสคริปต์)", flush=True)


def get_headers(ws) -> list[str]:
    return ws.row_values(1)


def clear_data_rows(ws) -> None:
    """ลบข้อมูลทุกแถวยกเว้น header (แถว 1) — ใช้ batch_clear ล้างแค่ค่าในเซลล์
    (ไม่ลบแถวจริง) เร็วกว่าและไม่กระทบ formatting/ขนาดชีท"""
    if ws.row_count <= 1:
        return
    last_col = gspread.utils.rowcol_to_a1(1, ws.col_count).rstrip("1")
    ws.batch_clear([f"A2:{last_col}{ws.row_count}"])
    print(f"[clear_data_rows] ลบข้อมูลแถว 2-{ws.row_count} เสร็จแล้ว", flush=True)


def append_dataframe(ws, df: pd.DataFrame):
    """เติมแถวต่อท้ายข้อมูลที่มีอยู่แล้วในชีท ตามลำดับคอลัมน์ header ปัจจุบันของชีท"""
    headers = get_headers(ws)
    # เรียงคอลัมน์ของ df ให้ตรงกับลำดับ header ในชีท เติมค่าว่างถ้าคอลัมน์ไหนไม่มีใน df
    ordered = df.reindex(columns=headers, fill_value="")
    ordered = ordered.astype(object).where(pd.notnull(ordered), "")

    def _to_json_safe(v):
        # pandas.Timestamp / datetime.date ไม่ใช่ JSON serializable ตรงๆ ต้องแปลงเป็น
        # string ก่อนส่งให้ gspread (คอลัมน์วันที่เช่น PO DATE, Contract Start, TAX DATE)
        # ถ้ามีเวลาติดมาด้วย (เช่น Doc date/UTime ของ iTEC Mis) ให้ใส่เวลาต่อท้ายด้วย
        if isinstance(v, (pd.Timestamp, datetime.date, datetime.datetime)):
            has_time = isinstance(v, (pd.Timestamp, datetime.datetime)) and v.time() != datetime.time(0, 0)
            return v.strftime("%d/%m/%Y %H:%M:%S") if has_time else v.strftime("%d/%m/%Y")
        return v

    values = ordered.map(_to_json_safe).values.tolist()
    if not values:
        print("[append_dataframe] ไม่มีข้อมูลให้เติม (0 แถว)", flush=True)
        return
    # table_range="A1" บังคับให้ Sheets API เริ่มหาตารางจากคอลัมน์ A เสมอ — ถ้าไม่ระบุ
    # (ปล่อยให้เดาเอง) แล้วหัวตารางมีคอลัมน์ว่างคั่นกลาง (เช่น header ตำแหน่ง 26 เป็นค่าว่าง)
    # API จะมองว่าตารางขาดเป็น 2 ท่อน แล้วสุ่มไปต่อท้ายท่อนหลัง ทำให้ข้อมูลเข้าไปผิดคอลัมน์
    # (เจอจริง: ข้อมูลทั้งหมดไปโผล่ตั้งแต่คอลัมน์ AA แทนที่จะเป็น A)
    ws.append_rows(values, value_input_option="USER_ENTERED", table_range="A1")
    print(f"[append_dataframe] เติมข้อมูลสำเร็จ {len(values)} แถว", flush=True)
