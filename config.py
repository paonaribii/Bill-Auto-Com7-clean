import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

K2_USER = os.getenv("K2_USER")
K2_PASS = os.getenv("K2_PASS")
K2_LOGIN_URL = os.getenv("K2_LOGIN_URL")  # เข้า dashboard ทั่วไป (ใช้โดย k2_scraper.py/record_k2.py)
# หน้า Management & Report (AEE) โดยตรง — ใช้เฉพาะ check_k2_status.py (คนละหน้ากับ K2_LOGIN_URL
# ด้านบน แยกตัวแปรกันเพราะเคยใช้ตัวแปรเดียวกันแล้วทำให้ k2_scraper.py เข้าผิดหน้าไปด้วย)
K2_AEE_REPORT_URL = os.getenv("K2_AEE_REPORT_URL")

ITOS_USER = os.getenv("ITOS_USER")
ITOS_PASS = os.getenv("ITOS_PASS")
ITOS_LOGIN_URL = os.getenv("ITOS_LOGIN_URL")

GOOGLE_SERVICE_ACCOUNT_JSON = BASE_DIR / os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json")
BILL_AUTO_SPREADSHEET_ID = os.getenv("BILL_AUTO_SPREADSHEET_ID")

# ไฟล์ใหม่ "Bill Auto Data" — ย้ายเฉพาะส่วน Flow Clean (K2+ITOS, ITec Mis, ITec, Cal) มาไว้ที่นี่
# แทน เพราะไฟล์ BILL_AUTO_SPREADSHEET_ID เดิมจะเต็ม — ส่วนที่คำนวณต่อ (Match, ITEC-MIS ฯลฯ)
# ยังอยู่ไฟล์เดิม แค่ไปอ่านข้อมูลดิบจากไฟล์นี้แทน
BILL_AUTO_DATA_SPREADSHEET_ID = os.getenv("BILL_AUTO_DATA_SPREADSHEET_ID")

# ไฟล์ "Bill Auto Cal" — แยกอีก 3 แท็บ (สถานะ Approve, สถานะ Rework, Check Bill Approve)
# ออกมาจากไฟล์ Bill Auto เดิมด้วยเหตุผลเดียวกัน (ไฟล์เดิมเต็ม)
BILL_AUTO_CAL_SPREADSHEET_ID = os.getenv("BILL_AUTO_CAL_SPREADSHEET_ID")

# ไฟล์ "สาขาเปิดบิลใน ITec ผิด" — รายชื่อ Phy/ID ที่หน้าร้านต้องแก้ไข (คัดลอกมาจากแท็บ
# "หน้าร้านแก้ไข" ในไฟล์ Bill Auto)
BILL_AUTO_SAKHA_SPREADSHEET_ID = os.getenv("BILL_AUTO_SAKHA_SPREADSHEET_ID")

ITEC_MIS_BASE_URL = os.getenv("ITEC_MIS_BASE_URL")
ITEC_MIS_API_KEY = os.getenv("ITEC_MIS_API_KEY")

ITEC_USER = os.getenv("ITEC_USER")
ITEC_PASS = os.getenv("ITEC_PASS")

APPS_SCRIPT_STEP4_URL = os.getenv("APPS_SCRIPT_STEP4_URL")
APPS_SCRIPT_STEP4_TOKEN = os.getenv("APPS_SCRIPT_STEP4_TOKEN")

# หน้าเลือกบริษัทของ ITOS (ต่อจาก ITOS_LOGIN_URL)
ITOS_SELECT_COMPANY_URL = os.getenv("ITOS_SELECT_COMPANY_URL")
# รายงาน PO ของ K2 (SSRS ReportViewer) — ใส่ URL เต็มที่มี {start:%Y-%m-%d} / {end:%Y-%m-%d}
K2_PO_REPORT_URL = os.getenv("K2_PO_REPORT_URL")

# สเปรดชีทอื่นๆ ที่ pipeline อ่าน/เขียน
CAL_SHEET_URL = os.getenv("CAL_SHEET_URL", "")
MATCH_FILE_ID = os.getenv("MATCH_FILE_ID")
BILL_UFUND_CORRECT_FILE_ID = os.getenv("BILL_UFUND_CORRECT_FILE_ID")
PO_APPROVED_SPREADSHEET_ID = os.getenv("PO_APPROVED_SPREADSHEET_ID")  # "สถานะ PO ที่ Approve แล้วยังไม่เกิดสัญญา"
SAKHA_EXTERNAL_SPREADSHEET_ID = os.getenv("SAKHA_EXTERNAL_SPREADSHEET_ID")
MDM_ERROR_LOG_SPREADSHEET_ID = os.getenv("MDM_ERROR_LOG_SPREADSHEET_ID")  # "บันทึกความผิดของ MDM"
FLAGGED_SPREADSHEET_ID = os.getenv("FLAGGED_SPREADSHEET_ID")
