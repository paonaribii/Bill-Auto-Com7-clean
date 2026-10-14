"""
Automation ฝั่ง iTEC "Sale Inv View" (Flow Clean ขั้น E1-E7 -> วางลงแท็บ Cal)

iTEC ไม่ใช่เว็บ แต่เป็นโปรแกรม desktop (ITECStock2007.exe) ควบคุมผ่าน pywinauto (UI
Automation) — pattern login/เปิดรายงาน/reset filter ทั้งหมดเอามาจาก
C:\\Users\\Comseven\\Desktop\\CRM\\qa_automation\\itec_desktop.py ที่ทดสอบแล้วว่าใช้งานได้จริง
(เฉพาะส่วน Sale Inv View — ไม่ใช้ Sell Bill View)

ยืนยันแล้วจากการทดสอบจริง: auto_id "tbCustomerName" ถูกต้อง, ช่องวันที่ dtStartDocdate/
dtEndDocDate ต้องคลิกแล้วกด Up/Down ปรับทีละวัน (ไม่ใช่พิมพ์ทับ) — ตำแหน่งคลิกที่แน่นอน
ไม่คงที่ (ดู docstring ของ _adjust_date_pane_day) เลยตรวจสอบผลจริงทุกครั้งแทนเชื่อ offset
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # ให้ import module ที่ root ได้ (config/clean/sheets_client/date_utils)

import queue
import re
import subprocess
import threading
import time
from datetime import date
from io import StringIO

import pandas as pd
import win32clipboard
from pywinauto import Application

import config
from date_utils import po_date_range

_EXE_PATH = r"C:\Program Files (x86)\Softbox\ITEC2007_Search\ITECStock2007.exe"

# ยืนยันจากผู้ใช้ (2026-09-09): เจอจริง _login_instance() ค้างอยู่ใน UI Automation call
# เดียว (หา "Get Password") นานผิดปกติ (210+ วิ จากปกติ 0.1-4 วิ) — โปรแกรม iTEC ค้างแบบไม่
# ตอบสนอง ค้างแบบนี้ pywinauto ไม่มี timeout ในตัวให้ ต้องคุมเวลาเองจากข้างนอกด้วย thread +
# kill โปรเซสทิ้งแล้ว login ใหม่ (เหมือน pattern retry ของ ITOS)
LOGIN_TIMEOUT_SECONDS = 90
LOGIN_MAX_ATTEMPTS = 3


def _kill_stale_itec_processes() -> None:
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "ITECStock2007.exe"],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass


def _login_instance(username: str, password: str) -> Application | None:
    """เปิด ITECStock2007.exe + login คืน Application (ที่หน้า Main Form) หรือ None

    ⚠️ การค้นหาหน้าต่างด้วย backend="uia" (app.window(title=...)) แต่ละครั้งช้ามาก (สแกน UI
    tree ทั้งเดสก์ท็อป วัดจริง ~30 วินาทีต่อครั้ง!) เพราะ app.window(...) คืน WindowSpecification
    แบบ "lazy" ที่ค้นหาใหม่ทุกครั้งที่แตะ attribute (.exists(), .set_focus(), ...) — เดิมเรียก
    .exists() แล้วเรียก .set_focus() ต่อทันที กลายเป็นค้นหาซ้ำสองรอบ (รวม ~60 วิ) ระหว่างนั้น
    หน้าต่างอาจเปลี่ยนสถานะไปแล้ว ทำให้ .set_focus() เจอ ElementNotFoundError ทั้งที่เพิ่ง
    .exists()==True ไปหมาดๆ — แก้โดย resolve เป็น wrapper_object() ที่เป็น handle จริงครั้ง
    เดียว ใช้ซ้ำได้เลยไม่ต้องค้นหาใหม่ทุกครั้ง"""
    print("[iTEC] กำลังเปิดโปรแกรม ITECStock2007.exe ...", flush=True)
    t0 = time.time()
    app = Application(backend="uia").start(_EXE_PATH)
    print(f"[iTEC]   เปิดโปรแกรมสำเร็จ ({time.time() - t0:.1f} วิ) กำลังหาหน้าต่าง Get Password ...",
          flush=True)

    get_password = None
    for i in range(20):
        t1 = time.time()
        try:
            # visible_only=True ตัดการสแกน element ที่ซ่อน/ไม่ visible ทิ้ง (ค่า default ของ
            # pywinauto คือ False = สแกนทั้งเดสก์ท็อปแบบไม่กรอง ซึ่งช้ามาก วัดจริงถึง 30-65
            # วินาทีต่อครั้ง!) — ใส่ visible_only=True ให้ชัดเจนเพื่อลดเวลาค้นหา
            spec = app.window(title="Get Password", visible_only=True)
            if spec.exists():
                get_password = spec
                print(f"[iTEC]   เจอหน้าต่าง Get Password แล้ว (รอบที่ {i + 1}, "
                      f"ใช้เวลาค้นหา {time.time() - t1:.1f} วิ)", flush=True)
                break
        except Exception:
            pass
        print(f"[iTEC]   ยังไม่เจอ Get Password (รอบที่ {i + 1}/20, ค้นหา {time.time() - t1:.1f} วิ) ...",
              flush=True)
    if get_password is not None:
        # ลอง clipboard paste ไปแล้วเจอ pywintypes.error "handle is invalid" ซ้ำๆ (ไม่ใช่
        # ปัญหาชั่วคราว retry ก็ไม่หาย) — กลับไปใช้ child_window(auto_id=...).set_edit_text()
        # แบบเดิม (ตรงกับ itec_desktop.py ต้นฉบับที่ยืนยันว่าใช้งานได้จริง) ตอนนี้การค้นหา
        # "Get Password" เองเร็วขึ้นมากแล้ว (0.1-4 วิ จาก 30+ วิ หลัง kill โปรเซสค้างเก่าทิ้ง)
        # เลยคาดว่า child_window ที่ scope แคบกว่า (แค่ในไดอะล็อกนี้ ไม่ใช่ทั้งเดสก์ท็อป) จะ
        # เร็วตามไปด้วย ไม่ใช่ตัวการหลักที่ทำให้ 96 วิ เหมือนที่กังวลไปก่อนหน้า
        print("[iTEC]   กำลังกรอก username/password ...", flush=True)
        t3 = time.time()
        get_password.set_focus()
        get_password.child_window(auto_id="tbUserName", control_type="Edit").set_edit_text(username)
        pf = get_password.child_window(auto_id="tbPassword", control_type="Edit")
        pf.set_edit_text(password)
        time.sleep(0.5)
        pf.type_keys("{ENTER}")
        print(f"[iTEC]   กรอก + กด Enter แล้ว ({time.time() - t3:.1f} วิ) กำลังรอหน้า Main Form ...",
              flush=True)
    else:
        print("[iTEC]   !!! หาไม่เจอหน้าต่าง Get Password เลยภายใน 20 รอบ !!!", flush=True)

    for i in range(20):
        t2 = time.time()
        try:
            mf = app.window(title="ITECStock 2007 Main Form", visible_only=True)
            if mf.exists():
                print(f"[iTEC]   เจอหน้า Main Form แล้ว (รอบที่ {i + 1}, login สำเร็จ)", flush=True)
                return app
        except Exception:
            pass
        print(f"[iTEC]   ยังไม่เจอ Main Form (รอบที่ {i + 1}/20, ค้นหา {time.time() - t2:.1f} วิ) ...",
              flush=True)
    print("[iTEC]   !!! หาไม่เจอหน้า Main Form เลยภายใน 20 รอบ — login ไม่สำเร็จ !!!", flush=True)
    return None


def _open_sale_inv_view(app: Application):
    """คลิกแท็บ Sell -> ปุ่ม 'Sale Inv View' แล้วรอหน้าต่างรายงานเปิด"""
    main_form = app.window(title="ITECStock 2007 Main Form")
    main_form.wait("ready", timeout=15)
    main_form.set_focus()

    for attempt in range(3):
        try:
            main_form.child_window(title="Sell", control_type="TabItem").click_input()
            time.sleep(1.5)
            main_form.child_window(title="Sale Inv View", control_type="Button").click_input()
            time.sleep(2)
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)

    for _ in range(10):
        for w in app.windows():
            if "Full Sale Invoice View" in w.window_text():
                # อ้างหน้าต่างด้วย process แทนชื่อ title เป๊ะๆ — title อาจมีไอคอน/ข้อความ
                # เปลี่ยนแปลงได้ระหว่างใช้งาน (เจอจริง: ElementNotFoundError กลางทางทั้งที่
                # หน้าต่างเปิดอยู่จริง) app.top_window() หาแค่หน้าต่างบนสุดของ process นี้
                # ไม่สนใจ title เลย ทนกว่ามาก
                return app.top_window()
        time.sleep(1)
    return None


def _set_branch_zero(win) -> None:
    """เคลียร์ Branch เป็น 0 (= ไม่ระบุสาขา) — ค่า default เป็นสาขาของ user ที่ login"""
    win.set_focus()
    branch_field = win.child_window(auto_id="tbBranch", control_type="Edit")
    branch_field.set_edit_text("0")
    win.type_keys("{TAB}")
    time.sleep(0.3)


def _set_customer_name(win, name: str) -> None:
    # ช่อง Customer Name อยู่แท็บ "เงื่อนไขเบื้องต้น" — ต้องสลับกลับมาแท็บนี้ก่อนเสมอ เพราะ
    # รอบค้นหาก่อนหน้าอาจค้างอยู่แท็บ "เงื่อนไขเพิ่มเติม" จาก _set_comment() (เจอจริง:
    # ElementNotFoundError หา tbCustomerName ไม่เจอตอนเริ่มรอบค้นหาถัดไป)
    try:
        win.child_window(title="เงื่อนไขเบื้องต้น", control_type="TabItem").click_input()
        time.sleep(0.5)
    except Exception:
        pass
    field = win.child_window(auto_id="tbCustomerName", control_type="Edit")
    field.set_edit_text(name)
    win.type_keys("{TAB}")
    time.sleep(0.3)


_PANE_DAY_RE = re.compile(r"^(\d{1,2})\s")


def _read_pane_day(win, pane_id: str) -> int | None:
    """เจอจริง: บางครั้ง UIA/COM โยน COMError ('An event was unable to invoke any of the
    subscribers') ชั่วคราวตอน resolve Pane นี้ — ไม่เกี่ยวกับ login เลย เป็นความไม่เสถียร
    ของ COM เอง retry สั้นๆ กันพัง"""
    last_err = None
    for _ in range(3):
        try:
            pane = win.child_window(auto_id=pane_id, control_type="Pane")
            m = _PANE_DAY_RE.match(pane.window_text().strip())
            return int(m.group(1)) if m else None
        except Exception as exc:
            last_err = exc
            time.sleep(1)
    raise last_err


def _adjust_date_pane_day(win, pane_id: str, target: date, x_offset: int) -> None:
    """ช่องวันที่เป็น custom Pane เดียว (WinForms DateTimePicker ตัวเดียว ไม่มี sub-control
    แยกวัน/เดือน/ปีให้ set_edit_text ตรงๆ) คลิกที่ตำแหน่งเลขวันให้ segment นั้น highlight/
    focus ก่อน แล้วพิมพ์วัน/เดือน/ปีทับได้เลย (ยืนยันจากภาพจริง — segment ที่ focus จะ
    highlight เป็นแถบสีฟ้า พิมพ์ตัวเลขทับได้ทันที และ DateTimePicker ของ WinForms จะเลื่อน
    โฟกัสไป segment ถัดไปเอง (เดือน -> ปี) ทันทีที่พิมพ์ครบ 2 หลักของ segment ปัจจุบัน)

    ⚠️ เจอจริง 2026-09-01: เดิมพิมพ์แค่ "เลขวัน" ทับเฉยๆ ไม่เคยแตะเดือน/ปีเลย ใช้ได้มาตลอด
    เพราะ Start/End เดือนเดียวกับวันนี้เสมอ (ปฏิทินเปิดมา default เป็นเดือนปัจจุบันอยู่แล้ว)
    พอต้องข้ามเดือน (ดึงเดือนที่แล้วเต็มเดือนตอนรันวันที่ 1) พิมพ์วันที่ 31 ทับเดือนกันยายน
    (มีแค่ 30 วัน) เลยพัง — ตอนนี้พิมพ์ครบทั้งวัน/เดือน/ปี (พ.ศ.) ทุกครั้งกันเดือนไม่ตรง

    x_offset ต่างกันระหว่าง Start/End เพราะ Start (DocDate) มี checkbox ('☑') ติดอยู่หน้ากล่อง
    ดันตำแหน่งเลขวันเยื้องขวาไปจาก End (DocDate) ที่ไม่มี checkbox — x=15 เดิมไปโดน checkbox
    ของ Start แทน (ยืนยันจากภาพจริง: กดแล้วติ๊ก/เอาติ๊กออก ไม่ได้แก้เลขวันเลย)"""
    win_rect = win.rectangle()
    pane = win.child_window(auto_id=pane_id, control_type="Pane")
    r = pane.rectangle()
    x = (r.left - win_rect.left) + x_offset
    y = (r.top - win_rect.top) + r.height() // 2
    win.click_input(coords=(x, y))
    time.sleep(0.3)
    # ลองพิมพ์วัน->เดือน->ปีรัวๆ ต่อกันไปก่อนแล้วเจอว่า segment สับสน (อ่านค่ากลับมาผิดเพี้ยน
    # ไม่ตรงกับที่พิมพ์เลย) — เปลี่ยนมาใช้ปุ่มลูกศร {RIGHT} เลื่อน segment แบบชัดเจนแทนการหวัง
    # ให้ auto-advance เอง และตั้ง "เดือน+ปี" ก่อน "วัน" เสมอ กัน day เกินขอบเขตของเดือนเดิม
    # ที่ค้างอยู่ (เช่น พิมพ์วัน 31 ทับตอนเดือนยังเป็นกันยายนซึ่งมีแค่ 30 วัน)
    win.type_keys("{RIGHT}")  # day -> month
    time.sleep(0.15)
    win.type_keys(f"{target.month:02d}")
    time.sleep(0.2)
    win.type_keys("{RIGHT}")  # month -> year
    time.sleep(0.15)
    win.type_keys(f"{target.year + 543:04d}")  # ปี พ.ศ. (ปฏิทินของ iTEC แสดงเป็น พ.ศ.)
    time.sleep(0.2)
    win.type_keys("{LEFT}{LEFT}")  # year -> month -> day
    time.sleep(0.15)
    win.type_keys(f"{target.day:02d}")
    time.sleep(0.3)


def _set_doc_date_range(win, start: date, end: date) -> None:
    """ตั้งวันที่ Start(DocDate) = วันที่ 1 ของเดือนนี้, End(DocDate) = เมื่อวาน"""
    _adjust_date_pane_day(win, "dtStartDocdate", start, x_offset=35)
    _adjust_date_pane_day(win, "dtEndDocDate", end, x_offset=15)

    actual_start = _read_pane_day(win, "dtStartDocdate")
    actual_end = _read_pane_day(win, "dtEndDocDate")
    if actual_start != start.day or actual_end != end.day:
        raise RuntimeError(
            f"ตั้งวันที่ไม่สำเร็จ: Start ได้ {actual_start} (ต้องการ {start.day}), "
            f"End ได้ {actual_end} (ต้องการ {end.day})"
        )


def _set_comment(win, comment: str) -> None:
    """เคลียร์/ตั้งค่าช่อง Comment — อยู่แท็บ 'เงื่อนไขเพิ่มเติม' ของ Sale Inv View"""
    try:
        win.child_window(title="เงื่อนไขเพิ่มเติม", control_type="TabItem").click_input()
        time.sleep(0.5)
    except Exception:
        pass
    field = win.child_window(auto_id="tbComment", control_type="Edit")
    field.set_edit_text(comment or "")
    time.sleep(0.3)


def _wait_for_search_results(win, timeout: int = 180, poll_interval: int = 3) -> None:
    """เช็คจำนวนแถวผลลัพธ์ที่แสดงจริง (label auto_id='lItem' มุมขวาบน) แทนรอนิ่งๆ ตายตัว —
    พอตัวเลขไม่เปลี่ยนแล้ว 2 รอบติดกัน (และไม่ใช่ '0') ถือว่าโหลดเสร็จ อ่านแค่ label เล็กๆ
    ตัวเดียว ไม่ใช่เดินทั้ง tree เหมือนตอน Select All Rows เลยไม่น่าจะไปแย่ง CPU จนช้าลง"""
    last_value = None
    stable_count = 0
    elapsed = 0
    while elapsed < timeout:
        try:
            value = win.child_window(auto_id="lItem", control_type="Text").window_text().strip()
        except Exception:
            value = None

        if value and value != "0":
            if value == last_value:
                stable_count += 1
                if stable_count >= 2:
                    print(f"[iTEC] ผลลัพธ์นิ่งแล้ว: {value} แถว")
                    return
            else:
                stable_count = 0
            last_value = value

        time.sleep(poll_interval)
        elapsed += poll_interval

    print("[iTEC] รอผลลัพธ์เกินเวลาที่กำหนด ไปต่อเลย (เผื่อ label หาไม่เจอ/ชื่อไม่ตรง)")


def _read_clipboard_text() -> str:
    win32clipboard.OpenClipboard()
    try:
        return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    except TypeError:
        # "Specified clipboard format is not available" — clipboard ยังไม่มีข้อความเลย
        # (การ copy ยังไม่เสร็จ/ยังไม่เริ่ม) ไม่ใช่ error จริง คืนค่าว่างให้ loop ข้างนอก retry ต่อ
        return ""
    finally:
        win32clipboard.CloseClipboard()


def _set_clipboard_text(text: str) -> None:
    """เจอจริง: OpenClipboard/SetClipboardData บางครั้ง error 'The handle is invalid'
    เพราะแอปอื่น (เช่น ITECStock2007.exe เอง ระหว่างเปลี่ยนสถานะหน้าต่าง) ถือ clipboard
    ค้างชั่วคราว — retry สั้นๆ กันปัญหานี้"""
    last_err = None
    for _ in range(5):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            return
        except Exception as exc:
            last_err = exc
            time.sleep(0.3)
    raise last_err


def _copy_all_rows_via_clipboard(win, grid_point: tuple[int, int] = (150, 450)) -> pd.DataFrame:
    """ตารางผลลัพธ์เป็น DataGridView แบบ virtualized — ถ้าอ่านผ่าน UI Automation
    descendants() ตรงๆ จะได้แค่แถวที่ render บนจอ (ไม่กี่สิบแถว) ไม่ใช่ทั้งหมด (เจอจริง:
    ผลลัพธ์มี 28,581 แถว) จึงต้องใช้ฟีเจอร์ 'Select All Rows' ของโปรแกรมเอง + Ctrl+C
    (ตาม Flow ที่ผู้ใช้ระบุ) แล้วอ่านจาก clipboard แทน ซึ่งได้ข้อมูลทั้งหมดจริงไม่ติด
    virtualization

    ตารางนี้หาไม่เจอผ่าน win.child_window(auto_id="dtG01", ...) เลย (เจอจริง: ค้นหา/
    print_control_identifiers() ค้างนานผิดปกติ ไม่เจอ Table element ในผล dump เลยด้วยซ้ำ)
    เลยคลิกขวาที่พิกัดตรงๆ ในพื้นที่ตารางแทน (แถวแรกของผลลัพธ์เสมอ ไม่ว่าจะมีกี่หมื่นแถว)

    เมนูคลิกขวาจริง (ยืนยันจากภาพ) มี 2 รายการแยกกัน: 'Select All Rows' กับ
    'Copy to Clipboard' — ต้องคลิกขวา 2 รอบ (เลือกก่อน แล้วคลิกขวาอีกทีเพื่อ copy) ตรงกับ
    Flow เดิม ไม่ใช่ Ctrl+C เฉยๆ หลัง Select All Rows

    ก่อนหน้านี้ใช้ retry loop เช็คซ้ำๆ ระหว่างรอ ปรากฏว่าช้ากว่าคนคลิกเองเยอะ — เดาว่าการเช็ค
    ถี่ๆ ผ่าน UI Automation (แต่ละครั้งต้องคุยกับ Windows) ไปแย่ง CPU/ทรัพยากรกับที่แอปกำลัง
    ใช้ render การเลือกแถวอยู่พอดี ยิ่งเช็คถี่ยิ่งช้าลง (วนแย่งกันเอง) เปลี่ยนมาคลิกทีเดียว
    แบบเดียวกับคน แล้วรอนิ่งๆ ยาวๆ ครั้งเดียวโดยไม่ไปแตะ/เช็คอะไรเลยระหว่างรอ"""
    # เมนูมี 2 รายการเรียงบนลงล่าง: 'Copy to Clipboard' (item 1), 'Select All Rows' (item 2)
    # เดาพิกัดคลิกแม่นยากเกินไป (ลองมาหลายรอบแล้วไม่ตรงเป๊ะสักที) เปลี่ยนมาใช้ปุ่มลูกศร
    # เลือกเมนูแทน: Down ครั้งแรกไฮไลต์ item 1, Down อีกครั้งไฮไลต์ item 2, Enter เพื่อกด
    try:
        _set_clipboard_text("")  # เคลียร์ก่อน กันอ่านค่าเก่าค้างจากรอบก่อนแล้วเข้าใจผิดว่าเป็นผลค้นหารอบนี้
    except Exception:
        pass
    win.right_click_input(coords=grid_point)
    time.sleep(0.5)
    win.type_keys("{DOWN}{DOWN}")  # ไฮไลต์ Select All Rows (item 2)
    time.sleep(0.3)
    win.type_keys("{ENTER}")  # กดเลือกจริง — แยกจาก Down กัน Enter ไม่ทำงานเวลาส่งรวดเดียว
    print("[iTEC] กด Select All Rows แล้ว ...")

    for attempt in range(5):
        win.right_click_input(coords=grid_point)
        time.sleep(0.5)
        win.type_keys("{DOWN}")  # ไฮไลต์ Copy to Clipboard (item 1)
        time.sleep(0.3)
        win.type_keys("{ENTER}")
        time.sleep(2.0)

        text = _read_clipboard_text()
        # แถวเดียว (แค่ header) หรือว่างเปล่า แปลว่า selection ยังไม่เสร็จจริง
        if text.count("\n") > 1:
            break
        print(f"[iTEC] ข้อมูลที่คัดลอกยังดูน้อยผิดปกติ รออีกนิดแล้วลองใหม่ (ครั้งที่ {attempt + 1}/5) ...")
        time.sleep(3)

    if not text.strip():
        # ⚠️ เจอจริง 2026-10-07: ค้นหาแล้วไม่มีผลลัพธ์เลย (เช่นรอบชื่อ "ธันเดอร์" ที่ไม่มีบิลในช่วงวันที่นี้)
        # คลิปบอร์ดว่างเปล่า -> pd.read_csv พังด้วย EmptyDataError ทั้งไปป์ไลน์ — คืน DataFrame ว่างแทน
        # (ผู้เรียกจัดการ df.empty ได้อยู่แล้ว) พร้อมเตือนชัดๆ ไม่ให้เงียบ
        print("[iTEC] !!! คัดลอกแล้วคลิปบอร์ดว่าง = ผลค้นหารอบนี้ไม่มีแถวเลย (คืนตารางว่าง) !!!", flush=True)
        return pd.DataFrame()
    return pd.read_csv(StringIO(text), sep="\t", dtype=str)


def _copy_two_columns_via_clipboard(
    win, grid_point: tuple[int, int] = (150, 450)
) -> pd.DataFrame:
    """ทดลอง: เลือกแค่ 2 คอลัมน์ (Invoice NO, Comment) แทนทั้งแถว เผื่อเร็วกว่า Select All
    Rows ที่เลือกทุกคอลัมน์ — ยังไม่เคยทดสอบจริง มีความเสี่ยงพังได้ (คอลัมน์ Comment อยู่
    ท้ายสุดของตาราง ต้อง scroll ขวาสุดก่อนถึงจะคลิก header ได้ ใช้ปุ่ม End บนคีย์บอร์ด
    เลื่อนแทน scrollbar เพราะ auto_id ของ scrollbar เป็นเลขรันไทม์ ไม่คงที่ระหว่าง session)"""
    win.click_input(coords=grid_point)
    time.sleep(0.3)

    print("[iTEC] กำลังคลิกเลือกคอลัมน์ Invoice NO ...")
    win.child_window(title="Invoice NO", control_type="Header").click_input()
    time.sleep(0.5)

    print("[iTEC] กำลังเลื่อนไปขวาสุดเพื่อหาคอลัมน์ Comment ...")
    win.click_input(coords=grid_point)
    win.type_keys("{END}")
    time.sleep(1.0)

    print("[iTEC] กำลัง Ctrl+คลิกเลือกคอลัมน์ Comment เพิ่ม ...")
    win.child_window(title="Comment", control_type="Header").click_input(pressed="control")
    time.sleep(0.5)

    print("[iTEC] กด Ctrl+C เพื่อคัดลอก 2 คอลัมน์ที่เลือกไว้ ...")
    win.type_keys("^c")
    time.sleep(2.0)

    text = _read_clipboard_text()
    return pd.read_csv(StringIO(text), sep="\t", dtype=str)


def _login_worker(result_q: "queue.Queue") -> None:
    """รันใน daemon thread แยก — ใส่ผลลัพธ์ (หรือ exception) ลง queue เมื่อเสร็จ ถ้าฝั่งหลัก
    timeout ไปก่อนแล้ว thread นี้จะยังค้างต่อไปในเบื้องหลังได้ (pywinauto ไม่มีทาง cancel
    การเรียกที่ค้างอยู่กลางคันจริงๆ) แต่เพราะเป็น daemon=True โปรเซสหลักจะปิดตัวได้ปกติทันทีที่
    main thread จบงาน ไม่ต้องรอ thread นี้ (แก้บั๊ก 2026-09-09: ตัวเก่าใช้ ThreadPoolExecutor ที่
    thread ไม่ใช่ daemon ทำให้โปรเซส Python ค้างไม่ยอมจบแม้ raise error ไปแล้ว กลายเป็นโปรเซส
    ซอมบี้กินแรมสะสมไปเรื่อยๆ)"""
    try:
        app = _login_instance(config.ITEC_USER, config.ITEC_PASS)
        result_q.put(("ok", app))
    except Exception as exc:
        result_q.put(("error", exc))


def _login_with_timeout_retry():
    """เรียก _login_instance() แต่คุมเวลาไม่ให้ค้างเกิน LOGIN_TIMEOUT_SECONDS ต่อรอบ (ยืนยัน
    จากผู้ใช้ 2026-09-09 — เจอค้างจริงในหน้าต่าง Get Password) ถ้าค้าง/ล้มเหลว จะ kill
    โปรเซส iTEC ทิ้งแล้วเปิดใหม่ ลองสูงสุด LOGIN_MAX_ATTEMPTS รอบ

    ใช้ daemon thread (ไม่ใช่ ThreadPoolExecutor) เพื่อกันโปรเซสซอมบี้ค้างไม่ยอมจบ ดู
    _login_worker() docstring"""
    last_error = None
    for attempt in range(1, LOGIN_MAX_ATTEMPTS + 1):
        print(f"[iTEC] กำลัง login (รอบที่ {attempt}/{LOGIN_MAX_ATTEMPTS}) ...", flush=True)
        _kill_stale_itec_processes()
        time.sleep(1)

        result_q: "queue.Queue" = queue.Queue(maxsize=1)
        t = threading.Thread(target=_login_worker, args=(result_q,), daemon=True)
        t.start()
        try:
            status, payload = result_q.get(timeout=LOGIN_TIMEOUT_SECONDS)
        except queue.Empty:
            print(f"[iTEC] !!! login ค้างเกิน {LOGIN_TIMEOUT_SECONDS} วิ (รอบที่ {attempt}/"
                  f"{LOGIN_MAX_ATTEMPTS}) — kill โปรเซสแล้วลองใหม่ (thread เดิมปล่อยทิ้งไว้เบื้อง"
                  f"หลังแบบ daemon ไม่กันโปรเซสหลักปิด) ...", flush=True)
            last_error = TimeoutError(f"iTEC login ค้างเกิน {LOGIN_TIMEOUT_SECONDS} วิ")
            _kill_stale_itec_processes()
            continue

        if status == "error":
            print(f"[iTEC] !!! login รอบที่ {attempt}/{LOGIN_MAX_ATTEMPTS} error: {payload!r} "
                  f"— ลองใหม่ ...", flush=True)
            last_error = payload
            _kill_stale_itec_processes()
            continue

        app = payload
        if app is not None:
            return app
        last_error = RuntimeError("Login iTEC ไม่สำเร็จ (หาไม่เจอ Get Password/Main Form)")
        print(f"[iTEC] !!! login รอบที่ {attempt}/{LOGIN_MAX_ATTEMPTS} ไม่สำเร็จ — ลองใหม่ ...",
              flush=True)

    raise RuntimeError(
        f"Login iTEC ล้มเหลวหลังลอง {LOGIN_MAX_ATTEMPTS} รอบ (kill + เปิดโปรแกรมใหม่ทุกรอบแล้ว) "
        f"— เช็ค ITEC_USER/ITEC_PASS ใน .env ด้วยถ้ายังไม่ผ่าน"
    ) from last_error


def login_and_open_sale_inv_view():
    """Login + เปิด Sale Inv View + เคลียร์ Branch=0 ให้เสร็จ (จุดที่ผู้ใช้บอกให้ 'ลอกจนถึง
    ขั้นตอนใส่ Branch 0') คืน (app, win)"""
    app = _login_with_timeout_retry()

    print("[iTEC] กำลังเปิด Sale Inv View ...")
    win = _open_sale_inv_view(app)
    if win is None:
        raise RuntimeError("เปิดหน้าต่าง Sale Inv View ไม่สำเร็จ")

    _set_branch_zero(win)
    print("[iTEC] ตั้ง Branch = 0 เสร็จแล้ว")
    # วันที่ไม่ได้ตั้งตรงนี้ — เรียก set_doc_date_range(win, start, end) แยกทีหลังได้ หลายรอบ
    # ในหน้าต่างเดียวกัน (เช่น วนทีละ 10 วัน) เพราะ _adjust_date_pane_day พิมพ์ทับเลขวัน
    # ตรงๆ ไม่ต้องรู้ค่าปัจจุบันก่อน
    return app, win


def set_doc_date_range(win, start: date, end: date) -> None:
    """ตั้งช่วงวันที่ Start/End (DocDate) — เรียกซ้ำได้หลายรอบในหน้าต่างเดียวกัน (เช่น
    วนทีละ 10 วัน) ไม่จำกัดแค่ครั้งเดียวตอนเปิดหน้าต่าง"""
    _set_doc_date_range(win, start, end)
    print(f"[iTEC] ตั้ง Start/End (DocDate) = {start:%Y-%m-%d} / {end:%Y-%m-%d} เสร็จแล้ว")


def search_sale_inv_view(
    win, customer_name: str = "", comment: str = "", two_columns_only: bool = False
) -> pd.DataFrame:
    """ค้นหา 1 รอบตามเงื่อนไขที่ระบุ (ช่วงวันที่ตั้งไว้ครั้งเดียวตอนเปิดหน้าต่างแล้ว)
    คืน DataFrame ของผลลัพธ์ทั้งหมด — two_columns_only=True ทดลองเลือกแค่ Invoice NO/
    Comment แทน Select All Rows (ยังไม่เคยทดสอบจริง)"""
    _set_customer_name(win, customer_name)
    _set_comment(win, comment)

    win.child_window(title="Search", control_type="Button").click_input()
    # เคยลองเช็คตัวเลขจำนวนแถวเป็นระยะแทนรอนิ่งๆ (_wait_for_search_results) แต่ยิ่งแย่ลง —
    # การคุยกับ UI Automation ระหว่างแอป busy อยู่ (ไม่ว่าจะเบาแค่ไหน) ไปแย่งทรัพยากรกับที่
    # แอปกำลัง render อยู่พอดี ทำให้ค้างนานขึ้น/Not Responding กลับมาอีก เลยกลับไปรอนิ่งๆ
    # ตายตัวแบบไม่แตะอะไรเลยระหว่างรอ ปลอดภัยที่สุดเท่าที่ลองมา
    print("[iTEC] กำลังค้นหา รอนิ่งๆ 90 วิ (ไม่แตะอะไรเลยระหว่างนี้) ...")
    time.sleep(90)

    if two_columns_only:
        return _copy_two_columns_via_clipboard(win)
    return _copy_all_rows_via_clipboard(win)


if __name__ == "__main__":
    app, win = login_and_open_sale_inv_view()
    try:
        df = search_sale_inv_view(win, customer_name="ธันเดอร์", two_columns_only=True)
        print(f"[iTEC] เจอ {len(df)} แถว (Customer Name=ธันเดอร์)")
        print(df.head())
    finally:
        app.kill()
