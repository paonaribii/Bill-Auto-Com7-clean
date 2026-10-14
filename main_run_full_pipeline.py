"""จุดรันเดียวของ Flow ทั้งหมด ตั้งแต่ดึงข้อมูลดิบ จนถึงเช็คสถานะ K2/ITOS

ลำดับ (แต่ละสเตจ = 1 ไฟล์ .py ที่มีอยู่แล้ว เรียก main() ตรงๆ ไม่มีการคำนวณซ้ำ):

  สเตจ 0: ดึงข้อมูลดิบ (browser/desktop automation, ต้อง login) -> ไฟล์ "Bill Auto Data"
    0.1 clean_flow/main_clean.py      : K2 + ITOS      -> แท็บ K2+ITOS
    0.2 clean_flow/main_itec.py       : iTEC Sale Inv   -> แท็บ Cal
    0.3 clean_flow/main_itec_tab.py   : Cal             -> แท็บ ITec
    0.4 clean_flow/main_itec_mis.py   : iTEC MIS export -> แท็บ ITec Mis

  สเตจ 1: คำนวณ Match/ITEC-MIS/ITEC MANNUAL (Python/Pandas, ไม่พึ่ง Google Sheets คำนวณ)
    -> ไฟล์ "Bill Auto"
    1.1 process_flow/main_build_all_bill_auto.py (รวม ITec->ITEC MANNUAL, ITec Mis->ITEC-MIS,
        K2+ITOS->Match ไว้ในตัวแล้ว)
    1.15 process_flow/main_fix_match_company_name_anomalies.py — เขียนทับ Match!AU/AY = "แก้ไข"
        ตรงๆ ให้บิล anomaly เปลี่ยนชื่อบริษัท (ธันเดอร์/ยูฟัน) จากสเตจ 0.2 เพื่อให้ "หน้าร้านแก้ไข"
        (สูตร FILTER Match!AY="แก้ไข") ดึงไปแสดงเองอัตโนมัติ — ต้องรันหลัง 1.1 ทุกครั้งเพราะ 1.1
        คำนวณ Match ใหม่ทับของเก่าหมด (ยืนยันจากผู้ใช้ 2026-09-16)

  สเตจ 2: แยก Match -> Match Approve / Match Rework / ถูกทั้งหมด รอ Confirm (ไฟล์ "Bill Auto")
    2.1 process_flow/main_build_match_approve_bill_auto.py
    2.2 process_flow/main_build_match_rework_bill_auto.py
    2.3 process_flow/main_build_confirm_bill_auto.py

  สเตจ 3: Match Approve/Rework -> สถานะ Approve/Rework (ไฟล์ "Bill Auto Cal")
    3.1 process_flow/main_build_status_approve_bill_auto.py
    3.2 process_flow/main_build_status_rework_bill_auto.py

  สเตจ 4: กระจายข้อมูลต่อไปยังชีทปลายทางอื่นๆ (ไฟล์ "Bill Auto Cal" / ไฟล์สาขา)
    4.1 process_flow/main_build_bil_tuktong_bill_auto.py   : ถูกทั้งหมด รอ Confirm -> บิลถูกต้อง
    4.2 process_flow/main_build_bill_k2_kill.py             : Match -> Bill K2 Kill
    4.21 process_flow/main_fill_billkill_raw_status.py      : เติม Application Status (ก่อนคลีน)
         เข้า Bill K2 Kill คอลัมน์ AI (ยืนยันจากผู้ใช้ 2026-09-17) — join จาก K2+ITOS ด้วย Phy ID
    4.215 process_flow/main_fill_billkill_branch_id_from_phy.py : เติม Branch ID (คอลัมน์ AK)
         ทุกแถว (D ถ้ามี ไม่งั้นดึงจากท้าย Phy-ID คอลัมน์ H เช่น "16386-708" -> "708")
         (ยืนยันจากผู้ใช้ 2026-09-18)
    4.216 process_flow/main_fill_billkill_customer_name.py : เติมชื่อ-นามสกุลลูกค้า (คอลัมน์ AJ)
         แยกจาก Comment ของแท็บ ITec (ไฟล์ Bill Auto Data) ผ่าน text parsing แล้ว join ด้วย
         Phy-ID (ไม่ต้องเปิดเบราว์เซอร์ค้นทีละใบ) — ยืนยันจากผู้ใช้ 2026-09-18
    4.22 process_flow/main_copy_billkill_to_external.py     : Bill K2 Kill -> แท็บ "Data" ของ
         สเปรดชีทภายนอก "สถานะ PO ที่ Approve แล้วยังไม่เกิดสัญญา" (ยืนยันจากผู้ใช้ 2026-09-18)
         คอลัมน์ A:AK ตรงกันเป๊ะ ไม่ต้อง mapping
    4.23 process_flow/main_append_data_to_dataall.py : คัดลอกแถวจากแท็บ Data ไปวางต่อท้ายแท็บ DataAll
         (สเปรดชีทภายนอกเดียวกัน, A:AK, ไม่เอา App No ซ้ำ, ห้ามลบของเดิม — ยืนยันจากผู้ใช้ 2026-10-05
         ต้องรันหลัง 4.22)
    4.25 process_flow/archive_sakha_to_yesterday.py         : Archive สาขาเปิดบิลใน ITec ผิด วันนี้ -> เมื่อวาน
    4.3 process_flow/main_build_sakha_phy_id.py             : หน้าร้านแก้ไข -> สาขาเปิดบิลใน ITec ผิด (Phy/ID)
    4.4 process_flow/main_build_sakha_details.py            : หน้าร้านแก้ไข -> สาขาเปิดบิลใน ITec ผิด (รายละเอียด)
    4.45 process_flow/main_flag_company_name_anomalies.py   : anomaly เปลี่ยนชื่อบริษัท (ธันเดอร์/ยูฟัน)
         จากสเตจ 0.2 -> เพิ่มเข้า สาขาเปิดบิลใน ITec ผิด ด้วย (append-only ห้ามลบของเก่า)
    4.46 process_flow/main_copy_new_bill_gaeikai_to_mdm.py  : สาขาเปิดบิลใน ITec ผิด (แถวใหม่วันนี้)
         -> บันทึกความผิดของ MDM แท็บ Sep (ถอดสูตร, append-only ห้ามลบของเก่า)
    4.47 process_flow/main_build_itec_only_wrong_bill.py    : ย้าย (ไม่ใช่ก็อป) แถวที่ผิด "จุดเดียว
         จริงๆ" (นับจากคอลัมน์ผลตรวจสอบ Comment/ราคา/Customer(Code)/Member Code/Customer(Name)/
         สำนักงานใหญ่/สถานะรับเงิน — ต้องมีแค่ 1 ใน 7 คอลัมน์นี้ที่ไม่ใช่ "ถูกต้อง") ออกจาก
         สาขาเปิดบิลใน ITec ผิด ไปชีท "ผลที่ผิด iTec" (ไฟล์ Sakha เดียวกัน) — ยืนยันจากผู้ใช้
         2026-09-29 ต้องรัน **หลัง 4.46 เสมอ** (ไม่ใช่ก่อน) เพราะ 4.46 ต้อง diff เจอแถวใหม่วันนี้
         ก่อนที่จะถูกย้ายออก ไม่งั้นบิลกลุ่มนี้จะหลุดจากการบันทึกลง MDM ไปเลย
    4.48 process_flow/main_fill_sakha_multi_wrong_detail.py : เติมคอลัมน์ S (Ufund Update) และ T
         (รายละเอียด) ของแถวที่เหลือในสาขาเปิดบิลใน ITec ผิด (ผิดมากกว่า 1 จุด/ผิดแค่ราคา) —
         ต้องรัน **หลัง 4.47 เสมอ** (ยืนยันจากผู้ใช้ 2026-10-05)
    4.5 process_flow/main_build_confirm_application_number.py : Etax -> Confirm เลข Application

  สเตจ 6 (สุดท้าย): process_flow/main_append_sakha_to_external.py : เอาแถวจาก สาขาเปิดบิลใน ITec ผิด
    (gid=0) ไปวางต่อท้ายชีทเดียวกันของสเปรดชีทภายนอก 18TygVBL... (A:BG, ไม่เอา App No ซ้ำ,
    ห้ามลบของเดิม + เติมชื่อลูกค้าคอลัมน์ BH ให้แถวใหม่ — ยืนยันจากผู้ใช้ 2026-10-05)

  สเตจ 5: เช็คสถานะจริงผ่าน K2/ITOS (เปิดเบราว์เซอร์ Playwright)
    5.1 process_flow/main_check_bill_approve_all.py

หมายเหตุ:
  - สเตจ 0 ต้อง login เว็บ/โปรแกรมจริง อาจมีหน้าต่างเบราว์เซอร์เด้งขึ้นมา ถ้าข้อมูลดิบของวันนี้
    ถูกดึงไปแล้ว ข้ามสเตจนี้ได้ด้วย --skip-fetch
  - สเตจ 5 เปิดเบราว์เซอร์ (headless=False) ใช้เวลานานถ้ามีรายการเยอะ ข้ามได้ด้วย --skip-check
  - ถ้าสเตจไหนพัง สคริปต์จะหยุดทันที (ไม่รันสเตจถัดไปทับข้อมูลที่อาจยังไม่พร้อม)
"""
import argparse
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "clean_flow"))
sys.path.insert(0, str(ROOT / "process_flow"))


def _run_stage(label: str, module_name: str):
    print(f"\n{'=' * 60}\n[pipeline] เริ่ม: {label} ({module_name}.py)\n{'=' * 60}", flush=True)
    start = time.time()
    module = __import__(module_name)
    module.main()
    elapsed = time.time() - start
    print(f"[pipeline] จบ: {label} (ใช้เวลา {elapsed:.0f} วินาที)", flush=True)


def main():
    parser = argparse.ArgumentParser(description="รัน Flow ทั้งหมดตั้งแต่ดึงข้อมูลดิบถึงเช็คสถานะ")
    parser.add_argument("--skip-fetch", action="store_true",
                         help="ข้ามสเตจ 0 (ดึงข้อมูลดิบ K2/ITOS/iTEC) ถ้าดึงไปแล้ววันนี้")
    parser.add_argument("--skip-check", action="store_true",
                         help="ข้ามสเตจ 5 (เช็คสถานะ K2/ITOS ผ่านเบราว์เซอร์)")
    args = parser.parse_args()

    stages = []

    if not args.skip_fetch:
        stages += [
            ("0.1 ดึง K2 + ITOS", "main_clean"),
            ("0.2 ดึง iTEC Sale Inv -> Cal", "main_itec"),
            ("0.3 Cal -> ITec", "main_itec_tab"),
            ("0.4 ดึง iTEC MIS export", "main_itec_mis"),
        ]

    stages += [
        ("1.1 คำนวณ ITEC MANNUAL / ITEC-MIS / Match", "main_build_all_bill_auto"),
        ("1.15 anomaly เปลี่ยนชื่อบริษัท -> เขียนทับ Match!AU/AY", "main_fix_match_company_name_anomalies"),
        ("2.1 Match -> Match Approve", "main_build_match_approve_bill_auto"),
        ("2.2 Match -> Match Rework", "main_build_match_rework_bill_auto"),
        ("2.3 Match -> ถูกทั้งหมด รอ Confirm", "main_build_confirm_bill_auto"),
        # ⚠️ ก่อนเขียนทับ "สถานะ Approve" (ซึ่งจะไปกระทบข้อมูลที่ Check Bill Approve คำนวณสด
        # จาก 3.1 ด้านล่าง) ต้อง archive C:E "วันนี้" ของ Check Bill Approve ไปเก็บที่ H:J
        # "ของเมื่อวาน" ก่อนเสมอ (Check Bill Approve เป็นข้อยกเว้นเดียวที่ไม่ clear ข้อมูลเก่า
        # ทิ้ง แต่ย้ายไปเก็บอีกคอลัมน์แทน — ยืนยันจากผู้ใช้)
        ("2.9 Archive Check Bill Approve วันนี้ -> เมื่อวาน", "archive_check_bill_approve"),
        ("3.1 Match Approve -> สถานะ Approve", "main_build_status_approve_bill_auto"),
        ("3.2 Match Rework -> สถานะ Rework", "main_build_status_rework_bill_auto"),
        ("4.1 ถูกทั้งหมด รอ Confirm -> บิลถูกต้อง", "main_build_bil_tuktong_bill_auto"),
        ("4.2 Match -> Bill K2 Kill", "main_build_bill_k2_kill"),
        ("4.21 เติม Application Status (ก่อนคลีน) เข้า Bill K2 Kill", "main_fill_billkill_raw_status"),
        ("4.215 เติม Branch ID จากท้าย Phy-ID เข้า Bill K2 Kill", "main_fill_billkill_branch_id_from_phy"),
        ("4.216 เติมชื่อ-นามสกุลลูกค้าเข้า Bill K2 Kill", "main_fill_billkill_customer_name"),
        ("4.22 Bill K2 Kill -> Data (สเปรดชีทภายนอก)", "main_copy_billkill_to_external"),
        ("4.23 Data -> วางต่อท้าย DataAll (ไม่เอา App No ซ้ำ)", "main_append_data_to_dataall"),
        # ⚠️ ก่อนเขียนทับ "สาขาเปิดบิลใน ITec ผิด" (สเตจ 4.3 ด้านล่าง) ต้อง archive A:BU
        # "วันนี้" ไปเก็บที่ "ของเมื่อวาน" ก่อนเสมอ (ข้อยกเว้นเหมือน Check Bill Approve —
        # ยืนยันจากผู้ใช้ 2026-09-03)
        ("4.25 Archive สาขาเปิดบิลใน ITec ผิด วันนี้ -> เมื่อวาน", "archive_sakha_to_yesterday"),
        ("4.3 หน้าร้านแก้ไข -> สาขา (Phy/ID)", "main_build_sakha_phy_id"),
        ("4.4 หน้าร้านแก้ไข -> สาขา (รายละเอียด)", "main_build_sakha_details"),
        # ⚠️ ยืนยันจากผู้ใช้ (2026-09-16): บิลที่ Customer Name จริงในระบบ iTEC ยังไม่ตรงกับ
        # ชื่อบริษัทที่ควรเป็นตามวันที่ (ธันเดอร์/ยูฟัน — เช็คไว้ตั้งแต่สเตจ 0.2 บันทึกลงไฟล์
        # anomaly CSV) ก็ควรนับเป็น "บิลแก้ไข" ด้วย — เพิ่มเข้า สาขาเปิดบิลใน ITec ผิด ตรงนี้
        # (หลัง 4.3/4.4 เขียนทับข้อมูลวันนี้เสร็จแล้ว แต่ก่อน 4.46 diff กับเมื่อวาน เพื่อให้
        # anomaly พวกนี้ถูกนับเป็น "แถวใหม่วันนี้" ไปเข้า MDM ด้วยในตัว)
        ("4.45 anomaly เปลี่ยนชื่อบริษัท -> สาขาเปิดบิลใน ITec ผิด", "main_flag_company_name_anomalies"),
        # ⚠️ ยืนยันจากผู้ใช้ (2026-09-09): หลังจากสาขาเปิดบิลใน ITec ผิด (gid=0) ถูกเขียนทับด้วย
        # ข้อมูลวันนี้เสร็จแล้ว (4.3/4.4/4.45 ด้านบน) ให้เทียบกับ "ของเมื่อวาน" (archive ไว้ตอน
        # 4.25 ก่อนถูกทับ) หาแถว "บิลแก้ไข" ที่เพิ่งเพิ่มเข้ามาใหม่วันนี้ แล้ว copy เป็นค่านิ่ง
        # (ถอดสูตร) ไปวางต่อท้ายชีท Sep ของไฟล์ "บันทึกความผิดของ MDM" — ห้ามลบของเก่าเด็ดขาด
        ("4.46 สาขา (แถวใหม่วันนี้) -> บันทึกความผิดของ MDM (Sep)", "main_copy_new_bill_gaeikai_to_mdm"),
        ("4.47 ย้ายบิลผิดจุดเดียว -> ผลที่ผิด iTec", "main_build_itec_only_wrong_bill"),
        ("4.48 เติม S/T (Ufund Update/รายละเอียด) แถวที่เหลือในสาขาเปิดบิลใน ITec ผิด",
         "main_fill_sakha_multi_wrong_detail"),
        ("4.5 Etax -> Confirm เลข Application", "main_build_confirm_application_number"),
    ]

    if not args.skip_check:
        stages.append(("5.1 เช็คสถานะ K2/ITOS", "main_check_bill_approve_all"))

    stages.append(("6.1 สาขาเปิดบิลใน ITec ผิด -> วางต่อท้ายสเปรดชีทภายนอก (ไม่เอา App No ซ้ำ)",
                   "main_append_sakha_to_external"))

    overall_start = time.time()
    for label, module_name in stages:
        try:
            _run_stage(label, module_name)
        except Exception:
            print(f"\n[pipeline] !!! สเตจ '{label}' พัง หยุดทั้งไปป์ไลน์ !!!", flush=True)
            traceback.print_exc()
            sys.exit(1)

    total = time.time() - overall_start
    print(f"\n{'=' * 60}\n[pipeline] เสร็จสิ้นทุกสเตจ (รวม {total / 60:.1f} นาที)\n{'=' * 60}", flush=True)


if __name__ == "__main__":
    main()
