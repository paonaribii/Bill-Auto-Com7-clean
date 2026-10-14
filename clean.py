"""Logic คลีนข้อมูล K-2 + ITOS ตาม Flow Clean ขั้น A6-A7, C1-C3"""
import pandas as pd

EXCLUDED_BRANDS = {"Apple (SPVI)", "Apple (UFicon)"}

ITOS_DEALER_NAME = "บริษัท คอมเซเว่น จำกัด (มหาชน)"

ITEC_MIS_BRANCH_ALLOWED = {"สำนักงานใหญ่", "00000"}
ITEC_MIS_LEASING_NAME = "UFUND"

# ยืนยันจากผู้ใช้ (2026-09-16): บริษัทเปลี่ยนชื่อจาก "บริษัท ธันเดอร์ ฟินฟิน" เป็น
# "บริษัท ยูฟัน แคปปิตอล จำกัด" มีผลตั้งแต่ 15/9/2026 เป็นต้นไป — แถวที่ Doc date ก่อน 15/9
# ยังเติมชื่อเก่า ส่วนแถวที่ Doc date ตั้งแต่ 15/9 เป็นต้นไปเติมชื่อใหม่ (ดู clean_itec_mis())
ITEC_MIS_MEMBER_NAME_OLD = "บริษัท ธันเดอร์ ฟินฟิน"
ITEC_MIS_MEMBER_NAME_NEW = "บริษัท ยูฟัน แคปปิตอล จำกัด"
ITEC_MIS_MEMBER_NAME_CUTOFF = pd.Timestamp("2026-09-15")  # ก่อนวันนี้ = ชื่อเก่า, ตั้งแต่วันนี้ = ชื่อใหม่
ITEC_MIS_MEMBER_NAMES_VALID = {ITEC_MIS_MEMBER_NAME_OLD, ITEC_MIS_MEMBER_NAME_NEW}

# ไฟล์ ITOS ใช้ชื่อคอลัมน์คนละแบบกับ K-2/หัวตารางใน Google Sheet (เช่น 'PO Date' vs
# 'PO DATE') ต้อง rename ให้ตรงกันก่อน ไม่งั้น merge_matching_columns จะตัดข้อมูล ITOS
# ทิ้งเกือบหมดเพราะชื่อคอลัมน์ไม่ตรงเป๊ะ — คอลัมน์ที่ชื่อตรงกันอยู่แล้ว (Contract Start,
# Contract Number, Amount, PO Status, Application Status, Contract Status, Branch ID)
# ไม่ต้อง map เพิ่ม ส่วน BUNDLE Price / Payment Status / Dealer Name ไม่มีคอลัมน์คู่ในชีท
# เลยปล่อยให้ merge_matching_columns ตัดทิ้งไปเองตามปกติ
ITOS_COLUMN_RENAME = {
    "PO Date": "PO DATE",
    "PO Number": "PO NUMBER",
    "Product Brand": "PRODUCT BRAND",
    "Product Category": "PRODUCT CATEGORY",
    "Product Series": "PRODUCT SERIES",
    "Phy ID": "Phy ID (ใบกำกับภาษีอย่างย่อ)",
    "Series Number": "Serial Number",
    "Sum Amount": "SUM AMOUNT \n(ราคาเครื่อง)",
    "ACS Price": "ACSPRICE \n(ราคาอุปกรณ์เสริม)",
    "Sum Price": "SUMPRICE",
    "Amount": "AMOUNT",
    "Vat AMT": "VAT AMOUNT",
    "Down AMT": "เงินดาวน์ก่อน VAT",
    "Down AMT Vat": "เงินดาวน์ VAT",
    "Down AMT Total": "ยอดรวมเงินดาวน์",
    "Trade in exvat": "Trade in ก่อน VAT",
    "Trade in vat": "Trade in\nVAT",
    "Trade in total": "ยอดรวม Trade in",
    "Loan AMT Exvat": "ยอดรวมหักเงินดาวน์ก่อน VAT",
    "Loan AMT Vat": "ยอดรวมหักเงินดาวน์ VAT",
    "Loan ANT Total": "ยอดรวม\nหักเงินดาวน์",
    "Application Number": "APPLICATION NUMBER",
    "App ID": "APP ID",
    "INV PN Number": "INV PN NUMBER (ใบกำกับภาษีเต็มรูปแบบ)",
    "TAX Date": "TAX DATE",
}


# ยืนยันจากผู้ใช้ (2026-09-03): กลับ logic เป็น whitelist — ค่าที่อยู่ในเซ็ตนี้เท่านั้นที่คง
# ค่าเดิมไว้ ค่า Application Status อื่นๆ ที่ไม่ตรงกับค่าในเซ็ตนี้เลย ให้แทนเป็น "Approve" หมด
# (ตรงข้ามกับ blacklist STATUS_TO_APPROVE เดิมที่แปลงแค่ 5 ค่าที่ระบุไว้)
#
# ยืนยันจากผู้ใช้ (2026-09-07 รอบเช้า): ลองขยายเป็น 7 ค่า (เพิ่ม MDM/ลูกค้ารีวิวสัญญา/
# Asset Deliver/Reject ให้คงค่าเดิมไว้) — **แต่ภายหลังยกเลิก** ยืนยันให้กลับมาใช้ 3 ค่าเดิม
# เหมือนก่อน 2026-09-07 (ทุกอย่างนอกจาก 3 ค่านี้แปลงเป็น Approve หมดรวมถึง Reject ด้วย) —
# ส่วนตัวเลขสรุปว่าก่อนแปลงเป็นอะไรบ้าง ให้ไปดูที่ชีท "สรุป" แทน (เขียนด้วย
# count_status_before_approve() ก่อนเรียก apply_application_status_approve() ใน main_clean.py)
STATUS_KEEP_AS_IS = {
    "ลูกหนี้ปกติ",
    "ยกเลิกการขอสินเชื่อ",
    "Approve",
}

# สถานะที่จะแสดงในตารางสรุป "ก่อนแปลงเป็น Approve" ในชีท สรุป — ยืนยันจากผู้ใช้ (2026-09-07)
# ไม่รวม "Reject" ไว้ในตารางนี้ (Reject แยกไปมีบรรทัดของตัวเองต่างหาก — ดู REJECT_STATUS ด้านล่าง)
STATUS_BEFORE_APPROVE_DISPLAY_ORDER = [
    "รอดำเนินการ MDM",
    "Asset Deliver",
    "ลูกค้ารีวิวสัญญา",
    "รอลงทะเบียนสินค้า",
    "ลูกค้ารีวิวสัญญาแนบท้าย",
]

# ยืนยันจากผู้ใช้ (2026-09-07 รอบบ่าย): "Reject" ไม่แปลงเป็น Approve อีกต่อไป และไม่เก็บไว้ใน
# Match เลยด้วย — **ลบแถวทิ้งไปเลย** เก็บไว้แค่ "จำนวน" ไปกรอกในชีท สรุป เป็นบรรทัดแยกต่างหาก
REJECT_STATUS = "Reject"

# ยืนยันจากผู้ใช้ (2026-09-11): "In active" ให้ทำเหมือน Reject ทุกอย่าง — ไม่แปลงเป็น Approve,
# ลบแถวทิ้งจาก Match, และนับรวมกับ Reject ในบรรทัดเดียวกันของตารางสรุป (เจอจริง: มี 1 บิล
# "In active" ที่ไม่เคย track ทำให้ยอด Approve เกินจากที่ตารางสรุปแจกแถวได้ 1 บิล — pattern
# เดียวกับที่ "ลูกค้ารีวิวสัญญาแนบท้าย" ถูกรวมเข้ากับ "ลูกค้ารีวิวสัญญา")
IN_ACTIVE_STATUS = "In active"
DELETE_LIKE_REJECT_STATUSES = {REJECT_STATUS, IN_ACTIVE_STATUS}


def count_status_before_approve(df: pd.DataFrame) -> dict[str, int]:
    """นับ Application Status ดิบก่อนถูกแปลงเป็น Approve (เฉพาะที่จะถูกแปลงจริง คือไม่อยู่ใน
    STATUS_KEEP_AS_IS และไม่ใช่ Reject) แยกตามค่าดั้งเดิม คืนค่าเป็น dict {สถานะ: จำนวน}
    ตามลำดับ STATUS_BEFORE_APPROVE_DISPLAY_ORDER"""
    if "Application Status" not in df.columns:
        return {k: 0 for k in STATUS_BEFORE_APPROVE_DISPLAY_ORDER}
    to_be_converted = df[
        ~df["Application Status"].isin(STATUS_KEEP_AS_IS)
        & (df["Application Status"] != REJECT_STATUS)
    ]
    counts = to_be_converted["Application Status"].value_counts()
    return {k: int(counts.get(k, 0)) for k in STATUS_BEFORE_APPROVE_DISPLAY_ORDER}


def count_reject(df: pd.DataFrame) -> int:
    """นับจำนวนแถว Application Status = Reject (ก่อนถูกลบทิ้ง) — เอาไปกรอกในชีท สรุป"""
    if "Application Status" not in df.columns:
        return 0
    return int((df["Application Status"] == REJECT_STATUS).sum())


def count_normal_debtor(df: pd.DataFrame) -> int:
    """นับจำนวนแถว Application Status = ลูกหนี้ปกติ — ยืนยันจากผู้ใช้ (2026-09-07) ให้ใส่
    ไว้ในตารางสรุป "สถานะก่อนแปลงเป็น Approve" ด้วย (ค่านี้ไม่ถูกแปลง/ลบ คงเดิมทั้งก่อน-หลัง)"""
    if "Application Status" not in df.columns:
        return 0
    return int((df["Application Status"] == "ลูกหนี้ปกติ").sum())


# ยืนยันจากผู้ใช้ (2026-09-08): เจอตาราง "สถานะ PO ที่ Approve แล้วยังไม่เกิดสัญญา" ที่มีอยู่แล้ว
# ในชีท "Summary" (ไฟล์ Bill Auto Cal, แถว 17-24) เคยกรอกมือ — ให้เขียนอัตโนมัติแทนที่ตรงนี้เลย
# ลำดับแถวต้องตรงเป๊ะ: 17 ยกเลิกการขอสินเชื่อ, 18 รอดำเนินการ MDM, 19 ลูกค้ารีวิวสัญญา, 20
# ลูกค้ารีวิวสัญญาแนบท้าย (แยกเป็นแถวของตัวเองแล้ว — ยืนยันจากผู้ใช้ 2026-09-17, เดิมรวมกับ
# ลูกค้ารีวิวสัญญา เพราะตารางมีแค่แถวเดียว ตอนนี้แทรกแถวใหม่ในชีทจริงแล้ว), 21 ลูกหนี้ปกติ, 22
# Approve (ค่าดิบก่อนแปลง), 23 Asset Deliver, 24 Reject, 25 รอลงทะเบียนสินค้า (เพิ่มเข้ามาทีหลัง
# 2026-09-09 — ก่อนหน้านี้ไม่ได้ track แถวนี้ ทำให้ยอดรวม Approve ไม่ตรงกับบล็อกบน ขาดไปพอดี
# เท่ากับจำนวนนี้)
SUMMARY_TABLE_ROW_ORDER = [
    "ยกเลิกการขอสินเชื่อ",
    "รอดำเนินการ MDM",
    "ลูกค้ารีวิวสัญญา",
    "ลูกค้ารีวิวสัญญาแนบท้าย",
    "ลูกหนี้ปกติ",
    "Approve",
    "Asset Deliver",
    "Reject",
    "รอลงทะเบียนสินค้า",
]


def count_summary_table_rows(df: pd.DataFrame) -> dict[str, int]:
    """นับ Application Status ดิบ (ก่อนแปลง/ก่อนลบใดๆ) ตามลำดับ SUMMARY_TABLE_ROW_ORDER สำหรับ
    เขียนลงตาราง "สถานะ PO ที่ Approve แล้วยังไม่เกิดสัญญา" ในชีท Summary แถว 17-25 โดยตรง —
    "ลูกค้ารีวิวสัญญา" และ "ลูกค้ารีวิวสัญญาแนบท้าย" แยกเป็นคนละแถวแล้ว (ยืนยันจากผู้ใช้
    2026-09-17) — "Reject" ยังรวม "In active" เข้าด้วยกันเหมือนเดิม (ยืนยันจากผู้ใช้ 2026-09-11:
    ให้ In active ทำเหมือน Reject ทุกอย่าง)"""
    if "Application Status" not in df.columns:
        return {k: 0 for k in SUMMARY_TABLE_ROW_ORDER}
    counts = df["Application Status"].value_counts()
    result = {k: int(counts.get(k, 0)) for k in SUMMARY_TABLE_ROW_ORDER}
    result["Reject"] += int(counts.get(IN_ACTIVE_STATUS, 0))
    return result


def load_k2_excel(path) -> pd.DataFrame:
    # แถวแรกของไฟล์ที่ K-2 export คือหัวรายงาน (ชื่อรายงาน/โลโก้) ไม่ใช่หัวคอลัมน์
    # หัวคอลัมน์จริงอยู่แถวที่ 2 (index 1) เลยต้องข้าม 1 แถว
    df = pd.read_excel(path, header=1)
    df.columns = df.columns.str.strip()
    return df


def load_itos_excel(path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    return df


def clean_k2(df: pd.DataFrame) -> pd.DataFrame:
    """A6-A7: ตัดแถวที่ PRODUCT BRAND เป็น Apple (SPVI) หรือ Apple (UFicon)"""
    if "PRODUCT BRAND" not in df.columns:
        raise ValueError(
            "ไม่พบคอลัมน์ 'PRODUCT BRAND' ในไฟล์ K-2 — เช็คชื่อคอลัมน์จริงในไฟล์ที่ export มา"
        )
    return df[~df["PRODUCT BRAND"].isin(EXCLUDED_BRANDS)].copy()


def clean_itos(df: pd.DataFrame) -> pd.DataFrame:
    """B: คอลัมน์ Branch ID -> ค่าที่ขึ้นต้นด้วย 'COMS7' ให้ตัดคำว่า 'COMS7' ออก (เก็บเลข
    สาขาที่ต่อท้ายไว้ เช่น 'COMS7123' -> '123') แล้วแปลงคอลัมน์ทั้งหมดเป็นตัวเลข (Format
    Number) — ค่าที่ไม่ใช่ตัวเลขหลังตัดแล้วจะกลายเป็น NaN
    จากนั้นดึงเฉพาะแถวที่คอลัมน์ Dealer Name เป็น 'บริษัท คอมเซเว่น จำกัด (มหาชน)'"""
    if "Branch ID" not in df.columns:
        raise ValueError(
            "ไม่พบคอลัมน์ 'Branch ID' ในไฟล์ ITOS — เช็คชื่อคอลัมน์จริงในไฟล์ที่ export มา"
        )
    if "Dealer Name" not in df.columns:
        raise ValueError(
            "ไม่พบคอลัมน์ 'Dealer Name' ในไฟล์ ITOS — เช็คชื่อคอลัมน์จริงในไฟล์ที่ export มา"
        )
    df = df.copy()
    branch_id = df["Branch ID"].astype(str).str.replace(r"^COMS7", "", regex=True)
    df["Branch ID"] = pd.to_numeric(branch_id, errors="coerce")

    df = df[df["Dealer Name"].astype(str).str.strip() == ITOS_DEALER_NAME].copy()
    df = df.rename(columns=ITOS_COLUMN_RENAME)
    return df


def load_itec_mis_excel(path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    return df


def clean_itec_mis(df: pd.DataFrame) -> pd.DataFrame:
    """D: เติม Member Name ทุกแถวที่ Member Code มีค่า — ใช้ "บริษัท ธันเดอร์ ฟินฟิน" (ชื่อเก่า)
    สำหรับแถวที่ Doc date ก่อน 15/9/2026 และ "บริษัท ยูฟัน แคปปิตอล จำกัด" (ชื่อใหม่หลังเปลี่ยน
    ชื่อบริษัท — ยืนยันจากผู้ใช้ 2026-09-16) สำหรับแถวที่ Doc date ตั้งแต่ 15/9/2026 เป็นต้นไป
    ส่วนแถวที่ Member Code ว่าง เติม Member Name = '***' (Doc date/UTime อ่านมาเป็น datetime64
    อยู่แล้วจาก pandas ไม่ต้องแปลงเพิ่ม) — เติม Member Code ว่างด้วย '***' เช่นกัน (ยืนยันจาก
    ผู้ใช้ 2026-08-28)

    เงื่อนไขกรอง (แก้ตามผู้ใช้ 2026-08-28): ไม่กรองคอลัมน์ 'สำนักงานใหญ่/สาขา' อีกต่อไป
    (เก็บทุกค่าไว้หมด ไม่ใช่แค่ "สำนักงานใหญ่"/"00000") แต่แปลงค่า "00000" ในคอลัมน์นี้ให้
    เป็น "สำนักงานใหญ่" แทน (ค่าอื่นคงเดิม) — กรองแถวด้วยเงื่อนไขเดียวคือ Leasing Name = UFUND"""
    required = ["Member Code", "Member Name", "สำนักงานใหญ่/สาขา", "Leasing Name", "Doc date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"ไม่พบคอลัมน์ {missing} ในไฟล์ iTEC Mis — เช็คชื่อคอลัมน์จริงในไฟล์ที่ export มา"
        )
    df = df.copy()
    # คอลัมน์ Member Name ในไฟล์จริงว่างทั้งคอลัมน์ (dtype float64/NaN ล้วน) ต้อง cast เป็น
    # object ก่อน ไม่งั้นใส่ string ไม่ได้ (TypeError: Invalid value ... for dtype 'float64')
    df["Member Name"] = df["Member Name"].astype(object)
    has_member_code = df["Member Code"].notna()
    doc_date = pd.to_datetime(df["Doc date"], errors="coerce")
    is_new_company = doc_date >= ITEC_MIS_MEMBER_NAME_CUTOFF
    df.loc[has_member_code & is_new_company, "Member Name"] = ITEC_MIS_MEMBER_NAME_NEW
    df.loc[has_member_code & ~is_new_company, "Member Name"] = ITEC_MIS_MEMBER_NAME_OLD
    df.loc[~has_member_code, "Member Name"] = "***"

    # Member Code ว่าง -> เติม "***" (คอลัมน์นี้เองด้วย ไม่ใช่แค่ Member Name)
    df["Member Code"] = df["Member Code"].astype(object)
    df.loc[~has_member_code, "Member Code"] = "***"

    # "00000" ในคอลัมน์สำนักงานใหญ่/สาขา -> "สำนักงานใหญ่" (ค่าอื่นคงเดิมทั้งหมด ไม่กรองทิ้ง)
    df["สำนักงานใหญ่/สาขา"] = df["สำนักงานใหญ่/สาขา"].replace("00000", "สำนักงานใหญ่")

    df = df[df["Leasing Name"] == ITEC_MIS_LEASING_NAME].copy()
    return df


def build_itec_mis_dataframe(itec_mis_path, sheet_headers: list[str]) -> pd.DataFrame:
    df = clean_itec_mis(load_itec_mis_excel(itec_mis_path))
    return merge_matching_columns(df, sheet_headers)


CAL_COLUMNS_TO_KEEP = ["Invoice NO", "Comment", "Customer(Name)"]
# ⚠️ ยืนยันจากผู้ใช้ (2026-09-16): เพิ่ม "Customer(Name)" เข้ามาด้วย (เดิมมีแค่ Invoice NO,
# Comment) — เพื่อดึงชื่อลูกค้า/บริษัทจริงจากหน้า iTEC มาใช้ตรวจ anomaly เปลี่ยนชื่อบริษัท
# (ธันเดอร์/ยูฟัน) ให้ "หน้าร้านแก้ไข" (Match!AY) เห็น anomaly นี้ได้เองโดยไม่ต้องพึ่งสเตจแยก


def build_cal_dataframe(df: pd.DataFrame, sheet_headers: list[str]) -> pd.DataFrame:
    """เตรียม DataFrame ที่ copy มาจากตาราง Sale Inv View (iTEC) ให้พร้อม append เข้าแท็บ
    Cal — คัดลอกมาทั้งตาราง (Select All Rows) แต่วางลงชีทแค่ 3 คอลัมน์ (Invoice NO,
    Comment, Customer(Name)) ตามที่ยืนยันจากผู้ใช้ — คอลัมน์อื่นที่เหลือของแถวใหม่จะว่างไว้"""
    if df.empty:
        return pd.DataFrame(columns=[h for h in sheet_headers if h])
    keep = [c for c in CAL_COLUMNS_TO_KEEP if c in df.columns]
    return merge_matching_columns(df[keep], sheet_headers)


def _normalize_header(s: str) -> str:
    """รวม whitespace/newline ทุกแบบให้เหลือช่องว่างเดียวแล้ว strip — บางหัวคอลัมน์ใน
    Google Sheet มี \\n ฝังอยู่จริง (เช่น 'เงินดาวน์ VAT\\n') ซึ่งจะไม่ตรงกับชื่อคอลัมน์จาก
    ไฟล์ K-2/ITOS ที่ผ่าน .str.strip() ไปแล้วแบบเป๊ะๆ ถ้าเทียบตรงตัว"""
    return " ".join(str(s).split())


def merge_matching_columns(df: pd.DataFrame, sheet_headers: list[str]) -> pd.DataFrame:
    """C2: เอาเฉพาะคอลัมน์ที่ชื่อตรงกับคอลัมน์ที่มีอยู่แล้วใน Google Sheet (แท็บ K2+ITOS)
    เทียบแบบ normalize whitespace แล้ว rename กลับเป็นชื่อ header เป๊ะๆ ตามชีท เพื่อให้
    sheets_client.append_dataframe() เรียงคอลัมน์ถูกตอน reindex"""
    normalized_sheet = {_normalize_header(h): h for h in sheet_headers if h}
    rename_map = {}
    used_keys = set()
    for c in df.columns:
        key = _normalize_header(c)
        if key in normalized_sheet and key not in used_keys:
            rename_map[c] = normalized_sheet[key]
            used_keys.add(key)
    matched = df[list(rename_map.keys())].rename(columns=rename_map)
    missing_in_source = [h for h in sheet_headers if h and h not in matched.columns]
    if missing_in_source:
        print(f"[merge_matching_columns] คอลัมน์ในชีทที่ไม่พบในไฟล์ต้นทาง (จะเว้นว่าง): {missing_in_source}")
    return matched


def apply_application_status_approve(df: pd.DataFrame) -> pd.DataFrame:
    """C3: แทนค่าคอลัมน์ Application Status — เก็บเฉพาะ "ลูกหนี้ปกติ", "ยกเลิกการขอสินเชื่อ",
    "Approve" ไว้ตามเดิม (STATUS_KEEP_AS_IS) ค่าอื่นทั้งหมดที่ไม่ตรงกับ 3 ค่านี้ (ยกเว้น Reject/
    In active และยกเว้นค่าว่าง) ให้แทนเป็น "Approve" หมด — ส่วน **Reject และ In active ลบแถวทิ้ง
    ไปเลย ไม่เก็บไว้ใน Match** (ยืนยันจากผู้ใช้ 2026-09-07 รอบบ่าย เรื่อง Reject, และ 2026-09-11
    ให้ In active ทำเหมือน Reject ทุกอย่าง — จำนวนที่ลบไปเอาไปกรอกในชีท สรุป รวมกันบรรทัดเดียว
    กับ Reject แทน ดู count_summary_table_rows())

    ⚠️ ยืนยันจากผู้ใช้ (2026-09-10): **แถวที่ Application Status ว่าง/NaN ให้ปล่อยว่างไว้ ไม่แปลง
    เป็น Approve** (เดิมโดนแปลงเป็น Approve ทำให้ยอด Approve ในตาราง Summary เกินจากที่ตารางแจก
    แถวได้ 2 บิล — พวกนี้คือแถวเดียวกับที่เคยทำสเตจ 5.1 crash เรื่อง nan)"""
    if "Application Status" not in df.columns:
        return df
    df = df.copy()
    df = df[~df["Application Status"].isin(DELETE_LIKE_REJECT_STATUSES)].copy()
    status = df["Application Status"]
    is_blank = status.isna() | status.astype(str).str.strip().isin(["", "nan", "None", "<NA>", "NaT"])
    mask = ~status.isin(STATUS_KEEP_AS_IS) & ~is_blank
    df.loc[mask, "Application Status"] = "Approve"
    return df


# ยืนยันจากผู้ใช้ (2026-09-17): "Bill K2 Kill" อยากเห็นสถานะ Application Status **ก่อนคลีน**
# (ก่อนแปลงเป็น Approve) ด้วย — คอลัมน์ K2+ITOS เดิมมี "Application Status" ซ้ำท้ายสุด (คอลัมน์
# ว่าง ไม่เคยถูกใช้งานจริง — main_build_match_bill_auto.py ตัดทิ้งด้วย .duplicated() ทุกครั้ง)
# เอามา repurpose เป็นคอลัมน์เก็บค่าดิบก่อนคลีนแทน (เปลี่ยนชื่อหัวคอลัมน์ในชีทจริงแล้วเป็น
# "Application Status (ก่อนคลีน)") ไม่ต้องเพิ่มคอลัมน์ใหม่
RAW_STATUS_COLUMN = "Application Status (ก่อนคลีน)"


def build_k2_itos_dataframe(
    k2_path, itos_path, sheet_headers: list[str]
) -> tuple[pd.DataFrame, dict[str, int]]:
    """คืนค่าเป็น (combined_df, summary_table_counts) — นับสถานะดิบ **ก่อน**
    apply_application_status_approve() แปลงทับ/ลบ Reject ทิ้ง (ยืนยันจากผู้ใช้ 2026-09-07:
    บันทึกค่าก่อนค่อยแปลง/ลบ) เอาไปเขียนลงตาราง "สถานะ PO ที่ Approve แล้วยังไม่เกิดสัญญา"
    ในชีท Summary (ไฟล์ Bill Auto Cal) แถว 17-25 ต่อใน main_clean.py (ยืนยันจากผู้ใช้ 2026-09-08
    ว่าต้องเขียนทับตารางที่มีอยู่แล้วตรงนั้นเลย ไม่ใช่สร้างตารางใหม่แยก)

    ก่อนแปลง/ลบ Application Status คัดลอกค่าดิบไปเก็บไว้ที่คอลัมน์ RAW_STATUS_COLUMN ด้วย
    (ยืนยันจากผู้ใช้ 2026-09-17) — merge_matching_columns หาค่าให้คอลัมน์นี้ไม่ได้เอง เพราะไฟล์
    K2/ITOS ต้นทางไม่มีคอลัมน์ชื่อนี้ (มีแต่ "Application Status" เฉยๆ) เลยต้องก็อปข้อมูลเข้าไปเอง"""
    k2_df = clean_k2(load_k2_excel(k2_path))
    itos_df = clean_itos(load_itos_excel(itos_path))

    combined = pd.concat([k2_df, itos_df], ignore_index=True, sort=False)
    combined = merge_matching_columns(combined, sheet_headers)

    if RAW_STATUS_COLUMN in sheet_headers and "Application Status" in combined.columns:
        combined[RAW_STATUS_COLUMN] = combined["Application Status"]

    summary_counts = count_summary_table_rows(combined)
    combined = apply_application_status_approve(combined)
    return combined, summary_counts


def build_itec_tab_dataframe(cal_df: pd.DataFrame) -> pd.DataFrame:
    """F: จากข้อมูลในแท็บ Cal เอาแค่ 3 คอลัมน์ Invoice NO (unique) + Comment + Customer(Name)
    (แถวเดียวกับ Invoice NO ที่ตรงกัน) แล้วเคลียร์อักขระ '\"' ('ฟันหนู') ออกจาก Comment —
    Customer(Name) เพิ่มเข้ามา 2026-09-16 เพื่อตรวจ anomaly เปลี่ยนชื่อบริษัท"""
    cols = ["Invoice NO", "Comment"]
    if "Customer(Name)" in cal_df.columns:
        cols.append("Customer(Name)")
    df = cal_df[cols].copy()
    df = df[df["Invoice NO"].astype(str).str.strip() != ""]
    df = df.drop_duplicates(subset="Invoice NO", keep="first")
    df["Comment"] = df["Comment"].astype(str).str.replace('"', "", regex=False)
    return df.reset_index(drop=True)
