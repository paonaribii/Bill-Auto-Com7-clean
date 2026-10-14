"""cal.py — จำลองสูตรที่ใช้ในชีท "Match" (ไฟล์ Match, MATCH_FILE_ID) ด้วย Pandas แทนการพึ่ง
Google Sheets คำนวณเอง

ชีท "Match" มีสูตรหนักมาก โดยเฉพาะส่วนจับคู่กับ 'ITEC MIS' (XLOOKUP/VLOOKUP สแกนซ้ำหลายสิบครั้ง
ต่อแถว คูณ 30,000+ แถว) ทำให้ Google Sheets คำนวณช้า/ค้าง — ไฟล์นี้แปลสูตรแต่ละคอลัมน์เป็นโค้ด
Python ตรงตามสูตรเป๊ะ (ไม่ลัด/ปรับ semantics) แยกเป็นฟังก์ชันตามคอลัมน์ ให้เทียบกับสูตรต้นฉบับ
ได้ง่าย ก่อนใช้งานจริงต้องเทียบผลกับข้อมูลจริงในชีทให้ตรงกันก่อนเสมอ

โครงสร้างไฟล์: แบ่งเป็นโซนตามกลุ่มคอลัมน์ในชีท Match
  โซน 1: A, B            — แกะ Phy/ID จาก Phy ID ใบกำกับภาษีอย่างย่อ
  โซน 2: AI ถึง AW        — จับคู่หลักกับ ITEC MIS (ผ่าน XLOOKUP)
  โซน 3: AZ ถึง BN        — จับคู่สำรอง (fallback) กับ ITEC MIS (ผ่าน VLOOKUP string ต่อกัน)
  โซน 4: BU               — เช็คว่าเป็นข้อมูลจาก K2 หรือ ITOS
  โซน 5: ชีท ITEC MIS เอง — คอลัมน์ A,B,C คำนวณเอง, D-AJ ก็อปจากชีท "ITec Mis" ตรงๆ
  โซน 6: ชีท "Match Approve" — กรอง Match (Application Status="Approve") + จัดเรียงคอลัมน์ใหม่
"""
import re

import pandas as pd

from clean import ITEC_MIS_MEMBER_NAMES_VALID


def _col_letter(n: int) -> str:
    """เลขคอลัมน์ (1-based) -> ตัวอักษรคอลัมน์สไตล์ Google Sheets เช่น 1->A, 27->AA"""
    letters = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def build_itec_mis_lookup_frame(raw_values: list[list[str]], num_cols: int = 39) -> pd.DataFrame:
    """แปลงข้อมูลดิบจากชีท 'ITEC MIS' (ไม่มี header หรืออ่านแบบไม่สนใจ header) ให้เป็น
    DataFrame ที่ตั้งชื่อคอลัมน์เป็นตัวอักษร A, B, C, ... ตามตำแหน่งจริงในชีท — ให้ตรงกับที่
    สูตรต้นฉบับอ้างอิงคอลัมน์ด้วยตัวอักษร (เช่น 'ITEC MIS'!C:C, 'ITEC MIS'!AD:AD)
    num_cols=39 ครอบคลุมถึงคอลัมน์ AM ตามที่สูตรใช้ (VLOOKUP('ITEC MIS'!$A:$AM,...))"""
    columns = [_col_letter(i) for i in range(1, num_cols + 1)]
    normalized = [row + [""] * (num_cols - len(row)) for row in raw_values]
    return pd.DataFrame(normalized, columns=columns)


# ============================================================
# โซน 1: คอลัมน์ A (Phy) และ B (ID)
# ============================================================


def compute_phy(po_number: str, phy_id_short: str) -> str:
    """คอลัมน์ A (Phy)
    สูตรเดิม: =IFERROR(IF($D6="","",LEFT($I6,SUM(FIND("-",$I6,1)-1))),"ระบุ Phy ผิด")
    เอาส่วนก่อน "-" ใน Phy ID ใบกำกับภาษีอย่างย่อ (เช่น "16266-708" -> "16266")"""
    po_number = "" if po_number is None else str(po_number).strip()
    phy_id_short = "" if phy_id_short is None else str(phy_id_short).strip()
    if po_number == "":
        return ""
    try:
        idx = phy_id_short.index("-")
        return phy_id_short[:idx]
    except ValueError:
        return "ระบุ Phy ผิด"


def compute_id(po_number: str, branch_id, phy_id_short: str, application_number: str) -> str:
    """คอลัมน์ B (ID)
    สูตรเดิม: =IF(LEFT($D6,2)="PO",$E6,IFERROR(IF($A6="","",IF(RIGHT(I6,4)="1470",1470,
      IF(LEN($AA6)-LEN(SUBSTITUTE($AA6,"-",""))=1,MID($I6,FIND("-",$I6)+1,100)+0,
      IFERROR(IFERROR(IF(IF($D6="","",LEFT($AA6,SUM(FIND(2026,$AA6,1)-1)))+0=0,"",
      IF($D6="","",LEFT($AA6,SUM(FIND(2026,$AA6,1)-1)))+0),
      LEFT($AA6,SUM(FIND(2025,$AA6,1)-1)))+0,"ตรวจสอบเลขสัญญา")))),"-"))

    แกะเลข "ID" ตามลำดับความสำคัญ:
    1. PO NUMBER ขึ้นต้นด้วย "PO" -> คืนค่า Branch ID ตรงๆ (เคสพิเศษ)
    2. ไม่มี Phy (คอลัมน์ A ว่าง) -> ""
    3. Phy ID ลงท้ายด้วย "1470" -> คืน 1470 (เคสพิเศษของสาขา/ระบบเก่า)
    4. APPLICATION NUMBER มีขีด "-" อยู่พอดี 1 ตัว -> เอาส่วนหลัง "-" ใน Phy ID (เช่น "708")
    5. ไม่งั้น แกะตัวเลขก่อนคำว่า "2026" ใน APPLICATION NUMBER (หรือ "2025" ถ้าไม่เจอ 2026)
    6. แกะไม่ได้เลย -> "ตรวจสอบเลขสัญญา" / error อื่นๆ -> "-"
    """
    po_number_str = "" if po_number is None else str(po_number).strip()
    phy_id_short = "" if phy_id_short is None else str(phy_id_short).strip()
    application_number = "" if application_number is None else str(application_number).strip()

    try:
        if po_number_str[:2] == "PO":
            return branch_id

        phy = compute_phy(po_number, phy_id_short)
        if phy == "":
            return ""

        if phy_id_short[-4:] == "1470":
            return 1470

        if application_number.count("-") == 1:
            dash_idx = phy_id_short.index("-")
            suffix = phy_id_short[dash_idx + 1:][:100]
            return int(suffix)

        for year in ("2026", "2025"):
            pos = application_number.find(year)
            if pos != -1:
                prefix = application_number[:pos]
                if prefix == "":
                    continue
                try:
                    value = int(prefix)
                except ValueError:
                    continue
                if value == 0:
                    continue
                return value

        return "ตรวจสอบเลขสัญญา"
    except Exception:
        return "-"


def add_phy_id_columns(df: pd.DataFrame) -> pd.DataFrame:
    """เติมคอลัมน์ Phy/ID ให้ DataFrame ที่มีคอลัมน์ PO NUMBER, Branch ID,
    'Phy ID (ใบกำกับภาษีอย่างย่อ)', APPLICATION NUMBER อยู่แล้ว"""
    df = df.copy()
    df["Phy"] = df.apply(
        lambda r: compute_phy(r["PO NUMBER"], r["Phy ID (ใบกำกับภาษีอย่างย่อ)"]), axis=1
    )
    df["ID"] = df.apply(
        lambda r: compute_id(
            r["PO NUMBER"], r["Branch ID"], r["Phy ID (ใบกำกับภาษีอย่างย่อ)"], r["APPLICATION NUMBER"]
        ),
        axis=1,
    )
    return df


# ============================================================
# โซน 2: คอลัมน์ AI ถึง AW — จับคู่หลักกับ ITEC MIS (ผ่าน XLOOKUP)
# ============================================================
# XLOOKUP หา "ไม่เจอ" จะได้ "xxx" เสมอ (ใส่ไว้เป็น default ในสูตรทุกตัว) — ใช้ค่านี้แทน
NOT_FOUND = "xxx"


def _price_to_float(v) -> float:
    """แปลงราคาเป็นตัวเลขแบบทนรูปแบบข้อความ — ตัด "฿", คอมมา, ช่องว่างออกก่อน (เจอจริง 2026-10-05:
    float("฿24,100")/float("28,990.00") โยน ValueError แล้วตกไปเป็น "แก้ไข" ทั้งที่ราคาเท่ากัน)"""
    if isinstance(v, (int, float)):
        return float(v)
    return float(re.sub(r"[^\d.\-]", "", str(v)))


def add_itec_mis_primary_match_columns(df: pd.DataFrame, itec_mis: pd.DataFrame) -> pd.DataFrame:
    """เติมคอลัมน์ AI-AW (จับคู่หลักกับ ITEC MIS) ให้ DataFrame ของ Match
    df ต้องมีคอลัมน์: APPLICATION NUMBER(AA), SUMPRICE(O)
    itec_mis ต้องมีคอลัมน์ตามชื่อจริงในชีท 'ITEC MIS': AD, C, X, J, K, L, M, AG
    (คอลัมน์ชื่อในชีทนั้นเป็นตัวอักษร A1-notation ไม่ใช่ชื่อ field — ต้องอ่านด้วย header=None
    แล้ว rename ตามตำแหน่งคอลัมน์ ดู build_itec_mis_lookup_frame())
    """
    df = df.copy()
    aa = df["APPLICATION NUMBER"].astype(str)

    # AI: นับว่า AA6 (APPLICATION NUMBER) ตรงกับ ITEC MIS!AD:AD กี่แถว
    # ใช้ dtype=object (ไม่ใช่ int) เพราะต้องใส่ค่าว่าง "" ได้ด้วยตามสูตร IF(AA6="","",...)
    ad_counts = itec_mis["AD"].astype(str).value_counts()
    ai_counts = aa.map(ad_counts).fillna(0).astype(int)
    df["AI"] = ai_counts.astype(object)
    df.loc[df["APPLICATION NUMBER"].astype(str) == "", "AI"] = ""

    # AJ: ถ้า AI==1 -> XLOOKUP(AA6, ITEC MIS!AD:AD, ITEC MIS!C:C, "xxx") ไม่งั้น "xxx"
    # (เอาตัวแรกที่เจอ กรณี AD ซ้ำ — แต่ตรงนี้ใช้เฉพาะตอน AI==1 อยู่แล้วเลยไม่ซ้ำจริง)
    ad_to_c = (
        itec_mis.drop_duplicates(subset="AD", keep="first")
        .assign(AD=lambda d: d["AD"].astype(str))
        .set_index("AD")["C"]
    )
    aj_lookup = aa.map(ad_to_c)
    df["AJ"] = df.apply(
        lambda r: (aj_lookup.get(r.name, NOT_FOUND) if r["AI"] == 1 else NOT_FOUND)
        if r["APPLICATION NUMBER"] not in ("", None)
        else "",
        axis=1,
    )

    # AK-AP: XLOOKUP(AJ6, ITEC MIS!C:C, <คอลัมน์เป้าหมาย>, "xxx") — เอาตัวแรกที่เจอ
    def _lookup_from_c(target_col: str, empty_becomes: str | None = None) -> pd.Series:
        c_to_target = (
            itec_mis.drop_duplicates(subset="C", keep="first").set_index("C")[target_col]
        )
        result = df["AJ"].map(c_to_target)
        result = result.where(df["AJ"] != NOT_FOUND, NOT_FOUND)
        result = result.where(df["APPLICATION NUMBER"].astype(str) != "", "")
        if empty_becomes is not None:
            result = result.mask(result == "", empty_becomes)
        return result.fillna(NOT_FOUND)

    df["AK"] = _lookup_from_c("X")   # ราคา
    df["AL"] = _lookup_from_c("J")   # Customer(Code)
    df["AM"] = _lookup_from_c("K")   # Member Code
    df["AN"] = _lookup_from_c("L")   # Customer(Name)
    df["AO"] = _lookup_from_c("M", empty_becomes="ไม่กรอกข้อมูล")  # สำนักงานใหญ่/สาขา
    df["AP"] = _lookup_from_c("AG")  # สถานะรับเงิน (Finish)
    # ⚠️ เพิ่มเข้ามา 2026-09-16: Customer(Name) จริงจากหน้า iTEC (ผ่าน ITEC-MIS!AK ที่ threading
    # มาจาก Cal->ITec->ITEC MANNUAL) — ใช้ตรวจ anomaly เปลี่ยนชื่อบริษัท (ดู _customer_name_check())
    # คนละตัวกับ AN (ซึ่งเป็นค่าที่เราสังเคราะห์เองจากวันที่ ไม่ใช่ข้อมูลจริงจาก iTEC)
    df["REAL_CN"] = _lookup_from_c("AK") if "AK" in itec_mis.columns else ""

    # AQ-AW: เทียบค่าที่ดึงมากับค่าที่ควรจะเป็น
    df["AQ"] = df["AJ"].map(lambda v: "" if v == "" else ("Match ไม่เจอ" if v == NOT_FOUND else "ถูกต้อง"))

    def _price_check(ak, sumprice) -> str:
        if ak == "":
            return ""
        if ak == NOT_FOUND:
            return "Match ไม่เจอ"
        try:
            return "ถูกต้อง" if _price_to_float(ak) - _price_to_float(sumprice) == 0 else "แก้ไข"
        except (TypeError, ValueError):
            return "แก้ไข"

    df["AR"] = df.apply(lambda r: _price_check(r["AK"], r["SUMPRICE"]), axis=1)

    def _customer_code_check(al) -> str:
        if al == "":
            return ""
        if al == NOT_FOUND:
            return "Match ไม่เจอ"
        return "ถูกต้อง" if al in ("UFUND STUDENT", "UFUND PERSONAL", "UFUND UNIDAYS") else "แก้ไข"

    df["AS"] = df["AL"].map(_customer_code_check)

    def _fixed_value_check(source_empty_check, target, expected) -> str:
        """expected: ค่าเดียว หรือ set ของค่าที่ยอมรับได้หลายค่า (เช่น ชื่อบริษัทเก่า/ใหม่
        ช่วงเปลี่ยนผ่าน — ยืนยันจากผู้ใช้ 2026-09-16 ดู ITEC_MIS_MEMBER_NAMES_VALID)"""
        if source_empty_check == "":
            return ""
        if target == NOT_FOUND:
            return "Match ไม่เจอ"
        if target == "***":
            return "แก้ไข"
        if isinstance(expected, (set, frozenset, tuple, list)):
            return "ถูกต้อง" if target in expected else "แก้ไข"
        return "ถูกต้อง" if target == expected else "แก้ไข"

    # หมายเหตุ: AT/AU เช็คค่าว่างจากคอลัมน์ D (PO NUMBER) ไม่ใช่ AM/AN เอง (ตามสูตรต้นฉบับ)
    df["AT"] = df.apply(
        lambda r: _fixed_value_check(r["PO NUMBER"], r["AM"], "AEE0201777774"), axis=1
    )

    def _customer_name_check(po_number, expected_name, real_name) -> str:
        """⚠️ แก้ตามผู้ใช้ (2026-09-16): เดิม AU เช็คแค่ว่า AN (ชื่อที่เราสังเคราะห์เองจากวันที่)
        อยู่ในชุด {ธันเดอร์, ยูฟัน} ไหม — ซึ่ง "ถูกต้อง" เสมอโดยธรรมชาติ (เราเป็นคนเติมเอง) จับ
        anomaly จริงไม่ได้เลย เปลี่ยนมาเทียบกับ REAL_CN (ชื่อจริงจาก iTEC ที่ threading มาใหม่)
        แทน — ถ้าไม่มีข้อมูลจริง (Invoice นี้ไม่เคยถูกดึงจาก iTEC Sale Inv เลย) fallback เป็น
        "ถูกต้อง" (พฤติกรรมเดิมก่อนแก้ ไม่ทำให้เกิด false positive กับแถวที่ไม่มีข้อมูลให้เทียบ)
        เทียบแบบ substring คำสั้นๆ (ไม่ใช่ทั้งชื่อ) เพราะชื่อจริงจาก iTEC ถูก mask ตัดที่ความยาว
        คงที่ (เช่น "ธันเดอร์" ถูกตัดเหลือ "ธันเดอร" ไม่มี ์ ท้าย — เจอจริงตอนทดสอบ)"""
        if po_number == "":
            return ""
        if expected_name == NOT_FOUND:
            return "Match ไม่เจอ"
        if expected_name == "***":
            return "แก้ไข"
        if not real_name:
            return "ถูกต้อง"
        key = "ยูฟัน" if "ยูฟัน" in str(expected_name) else "ธันเดอร"
        return "ถูกต้อง" if key in str(real_name) else "แก้ไข"

    df["AU"] = df.apply(
        lambda r: _customer_name_check(r["PO NUMBER"], r["AN"], r["REAL_CN"]), axis=1
    )

    def _headquarter_check(ao) -> str:
        if ao == "":
            return ""
        if ao == NOT_FOUND:
            return "Match ไม่เจอ"
        return "ถูกต้อง" if ao == "สำนักงานใหญ่" else "แก้ไข"

    df["AV"] = df["AO"].map(_headquarter_check)

    def _payment_status_check(ap) -> str:
        if ap == "":
            return ""
        if ap == NOT_FOUND:
            return "Match ไม่เจอ"
        return "ถูกต้อง" if ap == "ยังรับเงินไม่ครบ" else "แก้ไข"

    df["AW"] = df["AP"].map(_payment_status_check)

    return df


def compute_ax(ai, aq_to_aw_row: dict) -> str:
    """คอลัมน์ AX: สรุปผลจากโซน 2 (จับคู่หลัก)
    สูตรเดิม: =IF(AI6="","",IF(AI6>1,"เลขสัญญาเดียวกันมีมากกว่า 1 บิล",
      IF(COUNTIFS(AQ6:AW6,"แก้ไข")>0,"แก้ไข",IF(AQ6="Match ไม่เจอ","Match ไม่เจอ",
      IF(AQ6="","","ถูกต้องทั้งหมด")))))
    aq_to_aw_row: dict ของค่าคอลัมน์ AQ ถึง AW ของแถวเดียวกัน (7 ค่า)"""
    if ai == "":
        return ""
    if isinstance(ai, (int, float)) and ai > 1:
        return "เลขสัญญาเดียวกันมีมากกว่า 1 บิล"
    values = list(aq_to_aw_row.values())
    if values.count("แก้ไข") > 0:
        return "แก้ไข"
    if aq_to_aw_row["AQ"] == "Match ไม่เจอ":
        return "Match ไม่เจอ"
    if aq_to_aw_row["AQ"] == "":
        return ""
    return "ถูกต้องทั้งหมด"


def compute_ay(ax: str, bn: str) -> str:
    """คอลัมน์ AY: รวมผลโซน 2 (AX) กับโซน 3 (BN — จับคู่สำรอง)
    สูตรเดิม: =IF($AX6="","",IF($AX6="เลขสัญญาเดียวกันมีมากกว่า 1 บิล",BN6,
      IF($AX6="Match ไม่เจอ",BN6,IF($BN6="ถูกต้องทั้งหมด",BN6,IF($BN6="แก้ไข",BN6,$AX6)))))
    ต้องมีค่า BN (โซน 3) มาก่อนถึงจะคำนวณ AY ได้ครบ"""
    if ax == "":
        return ""
    if ax == "เลขสัญญาเดียวกันมีมากกว่า 1 บิล":
        return bn
    if ax == "Match ไม่เจอ":
        return bn
    if bn == "ถูกต้องทั้งหมด":
        return bn
    if bn == "แก้ไข":
        return bn
    return ax


# ============================================================
# โซน 3: คอลัมน์ AZ ถึง BN — จับคู่สำรอง (fallback) กับ ITEC MIS (VLOOKUP string ต่อกัน)
# ============================================================
# ใช้เมื่อโซน 2 หา match ไม่ได้ (AI<>1 หรือ AJ="xxx") — key เป็น wildcard VLOOKUP:
#   "*" & AA6(APPLICATION NUMBER) & "*" & O6(SUMPRICE) & "UFUND STUDENT"/"UNIDAYS"/"PERSONAL"
#   & "AEE0201777774" & "บริษัท ธันเดอร์ ฟินฟิน" & "สำนักงานใหญ่" & "ยังรับเงินไม่ครบ"
# ค้นใน 'ITEC MIS'!A:AM คอลัมน์ A (ลองทีละ 3 แบบ STUDENT/UNIDAYS/PERSONAL ตามลำดับ)
#
# ตั้งแต่ BA เป็นต้นไป (ต่างจาก AZ): key ไม่มี wildcard "*" แล้ว ใช้ AZ6 (ผลลัพธ์ที่ AZ หาเจอ)
# ต่อกับ O6 ตรงๆ แบบ exact match แทน — ถ้า AZ หาไม่เจอ (AZ6="แก้ไข") key นี้ก็จะหาไม่เจอต่อเนื่องกัน
# ไปเองโดยธรรมชาติ (ไม่ต้อง special-case)

CUSTOMER_TYPES = ("UFUND STUDENT", "UFUND UNIDAYS", "UFUND PERSONAL")
FIXED_SUFFIX = "AEE0201777774บริษัท ธันเดอร์ ฟินฟินสำนักงานใหญ่ยังรับเงินไม่ครบ"


FALLBACK_RESULT_COLS = {
    "BA": 24, "BB": 10, "BC": 11, "BD": 12, "BE": 13, "BF": 33,
    "BO": 21, "BP": 23, "BQ": 8, "BR": 9, "BS": 14, "BT": 2,
}


def _build_fallback_indices(itec_mis: pd.DataFrame) -> dict:
    """เตรียม index ล่วงหน้าสำหรับจับคู่สำรอง แบ่งตาม (ประเภทลูกค้า, ราคา) แทนการสแกน itec_mis
    ทั้งตารางซ้ำทุกแถวของ Match (แบบ wildcard string เดิม) — เร็วขึ้นมากตอนข้อมูลเป็นหมื่นแถว
    สมมูลกับสูตรต้นฉบับเพราะ K,L,M,AG (รหัสสมาชิก/ชื่อบริษัท/สาขา/สถานะ) เป็นค่าคงที่เดียวกัน
    ทุกครั้งอยู่แล้วในสูตร VLOOKUP เดิม (ไม่ได้เปลี่ยนไปตามแถว) เลยกรองแยกไว้ล่วงหน้าได้ปลอดภัย"""
    fixed_mask = (
        (itec_mis["K"].astype(str) == "AEE0201777774")
        & (itec_mis["L"].astype(str).isin(ITEC_MIS_MEMBER_NAMES_VALID))
        & (itec_mis["M"].astype(str) == "สำนักงานใหญ่")
        & (itec_mis["AG"].astype(str) == "ยังรับเงินไม่ครบ")
    )
    fixed_candidates = itec_mis[fixed_mask]

    indices = {}
    for customer_type in CUSTOMER_TYPES:
        subset = fixed_candidates[fixed_candidates["J"].astype(str) == customer_type]
        indices[customer_type] = {
            price: group for price, group in subset.groupby(subset["X"].astype(str))
        }
    return indices


def _find_fallback_row(application_number, sumprice, indices: dict):
    """หาแถว ITEC MIS ที่ตรงกัน (ราคา+ประเภทลูกค้าตรง จาก index ที่เตรียมไว้แล้ว จากนั้นดูว่า
    C มี application_number อยู่ในนั้นไหม) ลองทีละประเภทลูกค้า คืนแถวแรกที่เจอ หรือ None"""
    application_number_str = str(application_number)
    sumprice_str = str(sumprice)
    for customer_type in CUSTOMER_TYPES:
        group = indices[customer_type].get(sumprice_str)
        if group is None or group.empty:
            continue
        mask = group["C"].astype(str).str.contains(application_number_str, regex=False)
        matched = group[mask]
        if not matched.empty:
            return matched.iloc[0]
    return None


def compute_az(application_number: str, po_number: str, sumprice, itec_mis: pd.DataFrame) -> str:
    """คอลัมน์ AZ (โซน 3 ตัวแรก) — VLOOKUP คอลัมน์ที่ 3 (C) ของ 'ITEC MIS'!A:AM
    สูตรเดิม: ดู docstring โซน 3 ด้านบน (IFERROR ซ้อน 3 ชั้น ลอง STUDENT/UNIDAYS/PERSONAL)
    หมายเหตุ: ไว้ใช้เดี่ยวๆ/เทส — ถ้าจะใช้กับหลายแถว ใช้ add_itec_mis_fallback_match_columns()
    แทน (build index ครั้งเดียวใช้ร่วมกันทุกแถว เร็วกว่ามาก)"""
    po_number_str = "" if po_number is None else str(po_number).strip()
    if po_number_str == "":
        return ""
    indices = _build_fallback_indices(itec_mis)
    row = _find_fallback_row(application_number, sumprice, indices)
    return row.iloc[2] if row is not None else "แก้ไข"  # คอลัมน์ C = 0-based index 2


def add_itec_mis_fallback_match_columns(df: pd.DataFrame, itec_mis: pd.DataFrame) -> pd.DataFrame:
    """เติมคอลัมน์ AZ-BT (โซน 3 ทั้งหมด) ให้ DataFrame ของ Match
    df ต้องมีคอลัมน์: APPLICATION NUMBER(AA), PO NUMBER(D), SUMPRICE(O)
    itec_mis ต้องมีคอลัมน์ A (key รวม) และคอลัมน์ตามตำแหน่ง B ถึง AM (สำหรับ VLOOKUP index)
    ดู build_itec_mis_lookup_frame() สำหรับวิธีเตรียม itec_mis ให้ตรงรูปแบบนี้

    หมายเหตุประสิทธิภาพ: build index (_build_fallback_indices) แค่ครั้งเดียวก่อนวนแถว แล้วหา
    แถวที่ตรงกันแค่ "ครั้งเดียวต่อแถว" (ไม่ใช่สแกนทั้งตารางซ้ำทีละคอลัมน์แบบที่เคยเขียนไว้ตอนแรก
    ซึ่งช้ามากตอนข้อมูลเป็นหมื่นแถว) แล้วดึงทุกคอลัมน์ผลลัพธ์จากแถวเดียวกันนั้นทีเดียว"""
    df = df.copy()
    indices = _build_fallback_indices(itec_mis)

    az_values: list[str] = []
    matched_rows: list = []
    for _, r in df.iterrows():
        po_number_str = "" if r["PO NUMBER"] is None else str(r["PO NUMBER"]).strip()
        if po_number_str == "":
            az_values.append("")
            matched_rows.append(None)
            continue
        row = _find_fallback_row(r["APPLICATION NUMBER"], r["SUMPRICE"], indices)
        az_values.append(row.iloc[2] if row is not None else "แก้ไข")
        matched_rows.append(row)

    df["AZ"] = az_values

    for col_letter, col_index in FALLBACK_RESULT_COLS.items():
        df[col_letter] = [
            row.iloc[col_index - 1] if row is not None else "แก้ไข" for row in matched_rows
        ]
    # แถวที่ PO NUMBER ว่าง (ไม่มี AZ ให้คำนวณเลย) ต้องเป็นค่าว่าง ไม่ใช่ "แก้ไข"
    empty_mask = df["AZ"] == ""
    for col_letter in FALLBACK_RESULT_COLS:
        df.loc[empty_mask, col_letter] = ""

    df["BG"] = df["AZ"].map(lambda v: "" if v == "" else ("แก้ไข" if v == "แก้ไข" else "ถูกต้อง"))

    def _price_check_fallback(ba, sumprice) -> str:
        if ba == "":
            return ""
        if ba == "แก้ไข":
            return "แก้ไข"
        try:
            return "ถูกต้อง" if _price_to_float(ba) - _price_to_float(sumprice) == 0 else "แก้ไข"
        except (TypeError, ValueError):
            return "แก้ไข"

    df["BH"] = df.apply(lambda r: _price_check_fallback(r["BA"], r["SUMPRICE"]), axis=1)

    def _customer_code_check_fallback(bb) -> str:
        if bb == "":
            return ""
        if bb == "แก้ไข":
            return "แก้ไข"
        return "ถูกต้อง" if bb in ("UFUND STUDENT", "UFUND PERSONAL", "UFUND UNIDAYS") else "แก้ไข"

    df["BI"] = df["BB"].map(_customer_code_check_fallback)

    def _fixed_value_check_fallback(value, expected) -> str:
        """expected: ค่าเดียว หรือ set ของค่าที่ยอมรับได้หลายค่า (ดู _fixed_value_check ด้านบน)"""
        if value == "":
            return ""
        if value == "แก้ไข":
            return "แก้ไข"
        if isinstance(expected, (set, frozenset, tuple, list)):
            return "ถูกต้อง" if value in expected else "แก้ไข"
        return "ถูกต้อง" if value == expected else "แก้ไข"

    df["BJ"] = df["BC"].map(lambda v: _fixed_value_check_fallback(v, "AEE0201777774"))
    df["BK"] = df["BD"].map(lambda v: _fixed_value_check_fallback(v, ITEC_MIS_MEMBER_NAMES_VALID))
    df["BL"] = df["BE"].map(lambda v: _fixed_value_check_fallback(v, "สำนักงานใหญ่"))
    df["BM"] = df["BF"].map(lambda v: _fixed_value_check_fallback(v, "ยังรับเงินไม่ครบ"))

    def _compute_bn(row) -> str:
        if str(row["APPLICATION NUMBER"]).strip() == "":
            return ""
        checks = [row["BG"], row["BH"], row["BI"], row["BJ"], row["BK"], row["BL"], row["BM"]]
        return "แก้ไข" if checks.count("แก้ไข") > 0 else "ถูกต้องทั้งหมด"

    df["BN"] = df.apply(_compute_bn, axis=1)

    return df


# ============================================================
# โซน 4: คอลัมน์ BU — เช็คว่าเป็นข้อมูลจาก K2 หรือ ITOS
# ============================================================


def compute_source_system(contract_number: str) -> str:
    """คอลัมน์ BU (K2 / ITOS)
    สูตรเดิม: =IF(L:L="","",IF(LEFT(L:L,3)="TFF","ITOS","K2"))
    L = Contract Number — ถ้าขึ้นต้นด้วย "TFF" แปลว่าเป็น ITOS ไม่งั้นเป็น K2"""
    contract_number = "" if contract_number is None else str(contract_number).strip()
    if contract_number == "":
        return ""
    return "ITOS" if contract_number[:3] == "TFF" else "K2"


# ============================================================
# โซน 5: ชีท ITEC MIS เอง — คอลัมน์ A, B, C คำนวณเอง, D-AJ ก็อปจากชีท "ITec Mis" ตรงๆ
# ============================================================
# หมายเหตุ: ตัวอักษรคอลัมน์ในโซนนี้คือตำแหน่งในชีท "ITEC MIS" เอง (คนละชีทกับ Match) —
# C,X,J,K,L,M,AG ในสูตร A2 หมายถึงคอลัมน์ของ ITEC MIS เอง ไม่ใช่ของ Match


def compute_itec_mis_key_a(c, x, j, k, l, m, ag) -> str:
    """คอลัมน์ A ของชีท ITEC MIS — key รวมสำหรับให้ Match ค้นหาแบบ exact VLOOKUP กลับมา
    สูตรเดิม: =IF(E2="","",C2&X2&J2&K2&L2&M2&AG2)
    หมายเหตุ: เช็คค่าว่างจากคอลัมน์ E (ไม่ใช่ C) ตามสูตรต้นฉบับ — ฟังก์ชันนี้รับ e แยกต่างหาก"""

    def _s(v) -> str:
        return "" if v is None else str(v)

    return f"{_s(c)}{_s(x)}{_s(j)}{_s(k)}{_s(l)}{_s(m)}{_s(ag)}"


def compute_itec_mis_b(d, e) -> str:
    """คอลัมน์ B ของชีท ITEC MIS
    สูตรเดิม: =IF(D2="","",D2&"-"&E2)"""
    d_str = "" if d is None else str(d).strip()
    e_str = "" if e is None else str(e)
    if d_str == "":
        return ""
    return f"{d_str}-{e_str}"


def build_itec_manual_lookup(itec_manual: pd.DataFrame) -> pd.Series:
    """เตรียม dict สำหรับ XLOOKUP(H2, 'ITEC MANUAL'!A:A, 'ITEC MANUAL'!B:B)
    itec_manual ต้องมีคอลัมน์ 'A' และ 'B' (ตั้งชื่อตามตัวอักษรคอลัมน์ เหมือน ITEC MIS)
    เอาตัวแรกที่เจอถ้า A ซ้ำ (พฤติกรรมเดียวกับ XLOOKUP ค่าเริ่มต้น)"""
    return itec_manual.drop_duplicates(subset="A", keep="first").set_index("A")["B"]


def build_itec_manual_customer_lookup(itec_manual: pd.DataFrame) -> pd.Series:
    """เตรียม dict สำหรับ XLOOKUP(H2, 'ITEC MANUAL'!A:A, 'ITEC MANUAL'!C:C) — คอลัมน์ C ของ
    ITEC MANUAL คือ Customer(Name) จริงจากหน้า iTEC (เพิ่มเข้ามา 2026-09-16 เพื่อตรวจ anomaly
    เปลี่ยนชื่อบริษัทธันเดอร์/ยูฟัน — ดู _customer_name_check() ด้านล่าง)"""
    if "C" not in itec_manual.columns:
        return pd.Series(dtype=object)
    return itec_manual.drop_duplicates(subset="A", keep="first").set_index("A")["C"]


def add_itec_mis_derived_columns(
    df: pd.DataFrame, itec_manual_lookup: pd.Series, itec_manual_customer_lookup: pd.Series | None = None
) -> pd.DataFrame:
    """เติมคอลัมน์ A, B, C, AK ให้ DataFrame ที่มีคอลัมน์ดิบจากชีท "ITec Mis" อยู่แล้ว (ตั้งชื่อ
    คอลัมน์ตามตัวอักษร C,D,E,H,J,K,L,M,X,AG ตามตำแหน่งจริงในชีท ITEC MIS) — AK = Customer(Name)
    จริงจาก iTEC (ผ่าน Invoice NO เดียวกับที่ C ใช้หา Comment) ไม่บังคับใส่ (ถ้าไม่ส่ง
    itec_manual_customer_lookup มา AK จะว่างทั้งคอลัมน์ ไม่ error — backward compatible)"""
    df = df.copy()

    # ต้องคำนวณ C ก่อน A เสมอ (A ใช้ค่า C เป็น input — ตามลำดับ dependency ของสูตรต้นฉบับ)
    df["C"] = df["H"].map(
        lambda h: "" if str(h).strip() == "" else itec_manual_lookup.get(h, "")
    )
    if itec_manual_customer_lookup is not None and len(itec_manual_customer_lookup) > 0:
        df["AK"] = df["H"].map(
            lambda h: "" if str(h).strip() == "" else itec_manual_customer_lookup.get(h, "")
        )
    else:
        df["AK"] = ""
    df["A"] = df.apply(
        lambda r: (
            ""
            if str(r.get("E", "")).strip() == ""
            else compute_itec_mis_key_a(r["C"], r["X"], r["J"], r["K"], r["L"], r["M"], r["AG"])
        ),
        axis=1,
    )
    df["B"] = df.apply(lambda r: compute_itec_mis_b(r["D"], r["E"]), axis=1)
    return df


# ============================================================
# โซน 6: ชีท "Match Approve" / "Match Rework" — กรอง Match ตามสถานะ + จัดเรียงคอลัมน์ใหม่
# ============================================================
# ไม่มีการคำนวณหนักเพิ่มเติมเลย (Match คำนวณ AI-BU มาแล้วตั้งแต่โซน 1-4) เป็นแค่ filter +
# คัดลอก/จัดเรียงคอลัมน์ใหม่ ทำได้เร็วมากด้วย Pandas — df ที่รับเข้ามาต้องเป็นชีท "Match" ที่
# ผ่าน add_phy_id_columns / add_itec_mis_primary_match_columns / add_itec_mis_fallback_match_columns
# / compute_source_system มาแล้วครบ (คอลัมน์ตั้งชื่อตามตัวอักษร AI ถึง BU ตรงๆ อยู่แล้ว)
#
# "Match Rework" ใช้สูตรแบบเดียวกันเป๊ะ แค่เปลี่ยนเงื่อนไข FILTER จาก Application Status=
# "Approve" เป็น "Rework" — ใช้ฟังก์ชันเดียวกันนี้ผ่านพารามิเตอร์ status ได้เลย


def build_match_approve_from_match(match_df: pd.DataFrame, status: str = "Approve") -> pd.DataFrame:
    """สร้างข้อมูลเทียบเท่าชีท "Match Approve" (หรือ "Match Rework" ถ้าส่ง status="Rework")
    จากชีท "Match" — ตรวจสอบสูตรจริงจากไฟล์ต้นฉบับ (spreadsheet
    ไฟล์ Bill Auto, แท็บ "Match Approve"/"Match Rework")
    ยืนยันแล้วว่าเป็นบล็อกเดียวกันทั้งหมด (A:BM) กรองด้วยเงื่อนไขเดียว
    Match!AE6:AE (Application Status) == status เท่านั้น — ไม่มีเงื่อนไข AY/"ลูกหนี้ปกติ" เข้ามา
    เกี่ยวข้องเลย (อันนั้นเป็นของแท็บ "ถูกทั้งหมด รอ Confirm" คนละแท็บ ดู build_confirm_from_match)

    คืนค่า DataFrame ที่ตั้งชื่อคอลัมน์เป็นตัวอักษร A ถึง BM ตรงกับชีทจริง"""
    approved = match_df[match_df["Application Status"] == status].reset_index(drop=True)
    result = pd.DataFrame(index=approved.index)

    # A:D <- Match!A6:D (Phy, ID, PO DATE, PO NUMBER)
    for dest, src in zip("ABCD", ["Phy", "ID", "PO DATE", "PO NUMBER"]):
        result[dest] = approved[src]

    # E:G <- Match!F:H (PRODUCT BRAND, PRODUCT CATEGORY, PRODUCT SERIES)
    for dest, src in zip("EFG", ["PRODUCT BRAND", "PRODUCT CATEGORY", "PRODUCT SERIES"]):
        result[dest] = approved[src]

    # H <- ผลลัพธ์เอง: A&"-"&B (คำนวณจาก A,B ของผลลัพธ์นี้เอง ไม่ใช่ของ Match)
    result["H"] = result.apply(
        lambda r: "" if str(r["B"]).strip() == "" else f"{r['A']}-{r['B']}", axis=1
    )

    # I:Z (18 คอลัมน์) <- Match!J:AA
    source_j_to_aa = [
        "Serial Number", "Contract Start", "Contract Number", "SUM AMOUNT \n(ราคาเครื่อง)",
        "ACSPRICE \n(ราคาอุปกรณ์เสริม)", "SUMPRICE", "AMOUNT", "VAT AMOUNT", "เงินดาวน์ก่อน VAT",
        "เงินดาวน์ VAT\n", "ยอดรวมเงินดาวน์", "Trade in ก่อน VAT", "Trade in\nVAT", "ยอดรวม Trade in",
        "ยอดรวมหักเงินดาวน์ก่อน VAT", "ยอดรวมหักเงินดาวน์ VAT", "ยอดรวม\nหักเงินดาวน์",
        "APPLICATION NUMBER",
    ]
    for dest, src in zip((_col_letter(i) for i in range(9, 27)), source_j_to_aa):  # I(9)..Z(26)
        result[dest] = approved[src]

    # AA:AF (6 คอลัมน์) <- Match!AC:AH
    source_ac_to_ah = [
        "APP ID", "PO Status", "Application Status", "Contract Status",
        "INV PN NUMBER (ใบกำกับภาษีเต็มรูปแบบ)", "TAX DATE",
    ]
    for dest, src in zip((_col_letter(i) for i in range(27, 33)), source_ac_to_ah):  # AA(27)..AF(32)
        result[dest] = approved[src]

    # AQ:BK (21 คอลัมน์) <- Match!AZ:BT — ต้องทำก่อน AG,AH,AI,AJ,AL,AM,AN,AP,AO,BL ทุกตัว เพราะ
    # สูตรต้นฉบับของคอลัมน์เหล่านั้น (เช่น AG=AS6, AH=BH6) เป็น "self-reference" ภายในชีท
    # Match Approve เอง (อ้างถึงคอลัมน์ AS/BH/... ที่ FILTER มาจาก Match!AZ:BT ในบล็อกนี้ ซึ่งอยู่
    # แถวเดียวกัน) ไม่ใช่การอ้างอิงคอลัมน์ AS/BH/... ของชีท Match ตรงๆ
    for dest, src in (
        (_col_letter(i), _col_letter(i + 9)) for i in range(43, 64)
    ):  # dest AQ(43)..BK(63) <- src AZ(52)..BT(72), offset คงที่ +9 ทุกคอลัมน์
        result[dest] = approved[src]

    # AG,AH,AI,AJ,AL,AM,AN,AP: self-reference ไปที่คอลัมน์ AS,BH,BI,BK,BF,BG,AR,BJ "ของผลลัพธ์
    # Match Approve เอง" (เพิ่งเติมไว้จาก AQ:BK ด้านบน) ไม่ใช่ของ Match
    result["AG"] = result["AS"]
    result["AH"] = result["BH"]
    result["AI"] = result["BI"]
    result["AJ"] = result["BK"]
    result["AL"] = result["BF"]
    result["AM"] = result["BG"]
    result["AN"] = result["AR"]
    result["AP"] = result["BJ"]

    # AK: ข้อความคงที่ ถ้า AG มีค่า (ตามสูตรต้นฉบับ ข้อความมีวงเล็บเปิดไม่ปิดจริงๆ ในตัวสตริง)
    IMEI_NOTE = "ใน Itec เป็นเลข IMEI (ไม่สามารถระบุเป็น Serial Number ได้"
    result["AK"] = result["AG"].map(lambda v: "" if str(v).strip() == "" else IMEI_NOTE)

    # AO: ผลต่าง AN-AR ของผลลัพธ์นี้เอง (ไม่ใช่ของ Match) — ต้องคำนวณหลัง AQ:BK เติม AR แล้ว
    def _compute_ao(row) -> str:
        if str(row["AG"]).strip() == "":
            return ""
        try:
            return float(row["AN"]) - float(row["AR"])
        except (TypeError, ValueError):
            return "แก้ไข"

    result["AO"] = result.apply(_compute_ao, axis=1)

    # BL: เช็ค BF+BG == AR ของผลลัพธ์นี้เอง — ต้องคำนวณหลัง AQ:BK เติม AR,BF,BG แล้ว
    def _compute_bl(row) -> str:
        if str(row["AR"]).strip() == "":
            return ""
        try:
            return float(row["BF"]) + float(row["BG"]) == float(row["AR"])
        except (TypeError, ValueError):
            return "แก้ไข"

    result["BL"] = result.apply(_compute_bl, axis=1)

    # BM <- Match!AI (คอลัมน์เดียว)
    result["BM"] = approved["AI"]

    return result


def build_confirm_from_match(match_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """สร้างข้อมูลเทียบเท่าชีท "ถูกทั้งหมด รอ Confirm" (ไฟล์ Bill Auto) จากชีท "Match"

    ยืนยันจากสูตรจริง (ไฟล์ Bill Auto,
    แท็บ "ถูกทั้งหมด รอ Confirm", gid=1447034513) — เป็นคนละแท็บกับ "Match Approve"/"Match
    Rework" (ที่กรองด้วย Application Status==status) โดยสิ้นเชิง มี 2 บล็อกอิสระ ยาวไม่เท่ากัน:
      1. บล็อกหลัก (A:BL, 64 คอลัมน์) — กรอง Match!AY=="ถูกต้องทั้งหมด" AND
         Match!AE6:AE(Application Status)=="ลูกหนี้ปกติ" — แถวเดียวกันตลอดทั้งบล็อก (A:D<-A:D,
         E:Z<-F:AA, AA:AF<-AC:AH, AQ:BK<-AZ:BT, AG-AP/AK/AO/BL self-reference เหมือน Match
         Approve ทุกอย่าง)
      2. บล็อก BM (1 คอลัมน์) — กรอง Match!AY=="ถูกต้องทั้งหมด" เงื่อนไขเดียว (ไม่มี AE) ยาวไม่
         เท่าบล็อก 1

    คืนค่า dict {"main": df A:BL, "bm": df BM}"""
    verified = match_df[
        (match_df["AY"] == "ถูกต้องทั้งหมด") & (match_df["Application Status"] == "ลูกหนี้ปกติ")
    ].reset_index(drop=True)
    result = pd.DataFrame(index=verified.index)

    # A:D <- Match!A:D
    for dest, src in zip("ABCD", ["Phy", "ID", "PO DATE", "PO NUMBER"]):
        result[dest] = verified[src]

    # E:Z (22 คอลัมน์) <- Match!F:AA
    source_f_to_aa = [
        "PRODUCT BRAND", "PRODUCT CATEGORY", "PRODUCT SERIES", "Phy ID (ใบกำกับภาษีอย่างย่อ)",
        "Serial Number", "Contract Start", "Contract Number", "SUM AMOUNT \n(ราคาเครื่อง)",
        "ACSPRICE \n(ราคาอุปกรณ์เสริม)", "SUMPRICE", "AMOUNT", "VAT AMOUNT", "เงินดาวน์ก่อน VAT",
        "เงินดาวน์ VAT\n", "ยอดรวมเงินดาวน์", "Trade in ก่อน VAT", "Trade in\nVAT", "ยอดรวม Trade in",
        "ยอดรวมหักเงินดาวน์ก่อน VAT", "ยอดรวมหักเงินดาวน์ VAT", "ยอดรวม\nหักเงินดาวน์",
        "APPLICATION NUMBER",
    ]
    for dest, src in zip((_col_letter(i) for i in range(5, 27)), source_f_to_aa):  # E(5)..Z(26)
        result[dest] = verified[src]

    # AA:AF (6 คอลัมน์) <- Match!AC:AH
    source_ac_to_ah = [
        "APP ID", "PO Status", "Application Status", "Contract Status",
        "INV PN NUMBER (ใบกำกับภาษีเต็มรูปแบบ)", "TAX DATE",
    ]
    for dest, src in zip((_col_letter(i) for i in range(27, 33)), source_ac_to_ah):  # AA(27)..AF(32)
        result[dest] = verified[src]

    # AQ:BK (21 คอลัมน์) <- Match!AZ:BT — ทำก่อน self-reference ทุกตัว (เหตุผลเดียวกับ Match Approve)
    for dest, src in (
        (_col_letter(i), _col_letter(i + 9)) for i in range(43, 64)
    ):  # dest AQ(43)..BK(63) <- src AZ(52)..BT(72)
        result[dest] = verified[src]

    # AG,AH,AI,AJ,AL,AM,AN,AP: self-reference ของผลลัพธ์นี้เอง
    result["AG"] = result["AS"]
    result["AH"] = result["BH"]
    result["AI"] = result["BI"]
    result["AJ"] = result["BK"]
    result["AL"] = result["BF"]
    result["AM"] = result["BG"]
    result["AN"] = result["AR"]
    result["AP"] = result["BJ"]

    IMEI_NOTE = "ใน Itec เป็นเลข IMEI (ไม่สามารถระบุเป็น Serial Number ได้"
    result["AK"] = result["AG"].map(lambda v: "" if str(v).strip() == "" else IMEI_NOTE)

    def _compute_ao(row) -> str:
        if str(row["AG"]).strip() == "":
            return ""
        try:
            return float(row["AN"]) - float(row["AR"])
        except (TypeError, ValueError):
            return "แก้ไข"

    result["AO"] = result.apply(_compute_ao, axis=1)

    def _compute_bl(row) -> str:
        if str(row["AR"]).strip() == "":
            return ""
        try:
            return float(row["BF"]) + float(row["BG"]) == float(row["AR"])
        except (TypeError, ValueError):
            return "แก้ไข"

    result["BL"] = result.apply(_compute_bl, axis=1)

    # ---- บล็อก BM (1 คอลัมน์) — กรอง Match แยกอีกชุด ด้วย AY=="ถูกต้องทั้งหมด" เงื่อนไขเดียว
    # (ไม่มี AE) ยาวไม่เท่าบล็อกหลักด้านบนด้วยซ้ำ ----
    bm_source = match_df[match_df["AY"] == "ถูกต้องทั้งหมด"].reset_index(drop=True)
    bm_result = pd.DataFrame({"BM": bm_source["AI"]})

    return {"main": result, "bm": bm_result}
