"""Apply the post-feedback changes (issues #26-#35) on top of the deck from Claude Design.

    python3 apps/slides/apply_feedback.py

port_design.py rebuilds the deck from the Claude Design draft and would drop these changes, so run
this script again after it. It is idempotent: it edits slides by id, re-inserts the slides it adds,
and writes slides.json, the first line of deck.js and speaker-notes.md the same way port_design.py
does. Numbers come from the files in experiments/ named next to each slide.
"""
import csv
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SANS = "font-family:'IBM Plex Sans Thai', Tahoma, sans-serif"
MONO = "font-family:'Geist Mono', 'Courier New', monospace"
GEIST = 'font-family:Geist, Arial, sans-serif'
CARD = 'background:#ffffff; border-radius:12px; box-shadow:0 0 0 1px #00000014, 0 2px 2px #0000000a'
H2 = f'{SANS}; font-size:60px; font-weight:600; line-height:1.25; letter-spacing:-0.5px; color:#171717'
BLUE, RED, INK, GREY, MUTED = '#0a72ef', '#d92d20', '#171717', '#4d4d4d', '#666666'


def p(text, size=26, color=GREY, extra=''):
    return f'<p style="{SANS}; font-size:{size}px; line-height:1.5; color:{color}{"; " + extra if extra else ""}">{text}</p>'


def replace_once(html, old, new):
    """Replace old by new exactly once; a no-op when the edit is already applied (keeps the script idempotent)."""
    if old not in html and new in html:
        return html
    if html.count(old) != 1:
        raise SystemExit(f'expected exactly one match for: {old[:80]!r}')
    return html.replace(old, new)


# --- #27: what we decide ----------------------------------------------------
def approach_slide():
    def card(tag, title, body):
        return (f'<div style="display:flex; flex-direction:column; gap:12px; flex:1; padding:36px; {CARD}">'
                f'<p style="{MONO}; font-size:24px; color:{BLUE}">{tag}</p>'
                f'<h3 style="{SANS}; font-size:36px; font-weight:600; line-height:1.3; color:{INK}">{title}</h3>'
                f'{p(body)}</div>')
    arrow = f'<p style="{GEIST}; font-size:64px; color:{BLUE}; align-self:center">→</p>'
    html = (
        f'<h2 style="position:absolute; top:112px; left:128px; width:1664px; {H2}">เราตัดสินใจสองชั้น: เวลาคงที่ทั้งเทอม ห้องเปลี่ยนรายสัปดาห์</h2>\n'
        '<div style="position:absolute; top:290px; left:128px; width:1664px; display:flex; flex-direction:row; gap:28px">'
        + card('01 เวลา', 'หนึ่งชุด ใช้ทั้ง 15 สัปดาห์',
               'แต่ละคลาสเลือกวันและเวลาจากตัวเลือกที่ต้นฉบับอนุญาต ทุกสัปดาห์เรียนเวลาเดิม')
        + arrow
        + card('02 ห้อง', 'เลือกใหม่ได้ทุกสัปดาห์',
               'สัปดาห์ที่ต้องใช้ Lab อยู่ Lab สัปดาห์อื่นอยู่ห้องบรรยายที่ว่าง แลกกับการย้ายห้อง')
        + '</div>\n'
        f'<div style="position:absolute; top:590px; left:128px; width:1664px; display:flex; flex-direction:column; gap:10px; padding:28px 36px; border-left:6px solid {BLUE}; background:#f5f9ff">'
        + p('<b style="color:#171717">เวลามีผลกับ Lab โดยตรง</b> ถ้าหลายคลาสที่ต้องใช้ Lab สัปดาห์เดียวกันเลือกเวลาเดียวกัน Lab 4 ห้องจะไม่พอในช่วงนั้น '
            'และ Lab ไม่จำเป็นที่ยังเหลือ <b style="color:#171717">ทุกชั่วโมง</b> เกิดตอนห้องบรรยายเต็มเพราะคลาสอื่นเลือกเวลาเดียวกัน', 28)
        + '</div>\n'
        f'<p style="position:absolute; top:800px; left:128px; width:1664px; {SANS}; font-size:32px; font-weight:600; line-height:1.45; color:{INK}">'
        'ระบบเลือกเวลาให้แต่ละคลาสหนึ่งชุดใช้ทั้งเทอม และเลือกห้องให้แต่ละคาบเป็นรายสัปดาห์ เพื่อให้จัดได้ครบทุกคาบ '
        'และ Lab ไม่ถูกจองไว้เปล่า ๆ โดยแลกกับการย้ายห้องให้น้อยที่สุด</p>\n'
        f'<p style="position:absolute; bottom:64px; left:128px; width:1664px; {SANS}; font-size:24px; color:{MUTED}">'
        'GA / HC / SA ค้นหา "ลำดับคลาส + เวลาที่ลองก่อน" ส่วนห้องถูกเลือกโดย decoder (ไม่มี move ที่ย้ายห้องโดยตรง) · '
        'ที่มา / experiments/lab-hours-breakdown</p>')
    note = ('งานนี้ตัดสินใจสองอย่าง อย่างแรกคือเวลา แต่ละคลาสเลือกวันและเวลาจากตัวเลือกที่ต้นฉบับอนุญาตหนึ่งชุด แล้วใช้ทั้ง 15 สัปดาห์ '
            'อย่างที่สองคือห้อง ซึ่งเลือกใหม่ได้ทุกสัปดาห์ สัปดาห์ที่ต้องใช้ Lab อยู่ Lab สัปดาห์อื่นอยู่ห้องบรรยาย '
            'สองเรื่องนี้เกี่ยวกันตรงที่เวลากำหนดว่าห้องจะพอไหม ถ้าคลาสที่ต้องใช้ Lab สัปดาห์เดียวกันเลือกเวลาเดียวกัน Lab สี่ห้องก็ไม่พอ '
            'เราตรวจตารางคำตอบทุกรันแล้วพบว่า Lab ไม่จำเป็นที่ยังเหลือเกิดตอนที่ห้องบรรยายที่คลาสใช้ได้เต็มหมด เพราะคลาสอื่นเลือกเวลาเดียวกันทุกครั้ง '
            'ไม่มีครั้งไหนที่นั่ง Lab ทั้งที่มีห้องบรรยายว่าง การเลือกเวลาที่ดีจึงคือการกระจายความต้องการห้อง '
            'ในทางเทคนิค GA HC และ SA ค้นหาลำดับคลาสกับเวลาที่อยากลองก่อน แล้ว decoder เป็นคนจัดเวลาและเลือกห้องรายสัปดาห์ '
            'ข้อจำกัดคือการค้นหาไม่มี move ที่ย้ายห้องโดยตรง')
    return {'id': 'approach', 'title': 'เราตัดสินใจสองชั้น: เวลาคงที่ทั้งเทอม ห้องเปลี่ยนรายสัปดาห์',
            'style': 'background:#ffffff', 'html': html, 'note': note}


# --- #29 + #31: objective and constraints ------------------------------------
def objective_slide():
    li = lambda n, title, body: (
        f'<div style="display:flex; flex-direction:row; gap:20px; align-items:flex-start">'
        f'<p style="{GEIST}; font-size:40px; font-weight:600; line-height:1.1; color:{BLUE}; width:36px">{n}</p>'
        f'<div style="display:flex; flex-direction:column; gap:4px">'
        f'<p style="{SANS}; font-size:30px; font-weight:600; line-height:1.35; color:{INK}">{title}</p>{p(body, 24)}</div></div>')
    rules = ['คลาสหนึ่งใช้เวลาชุดเดียวทั้งเทอม จากตัวเลือกที่ต้นฉบับอนุญาต',
             'ห้องจุนักศึกษาได้ และอยู่ในรายการห้องที่คลาสนั้นใช้ได้',
             'สัปดาห์ที่ต้องใช้ Lab ต้องอยู่ใน Computer Lab',
             'ห้อง ผู้สอน และกลุ่มนักศึกษาเดียวกัน ห้ามชนเวลากัน',
             'ห้ามชนกับคลาสพื้นหลัง 810 คลาสที่ล็อกไว้แล้ว',
             'กฎจากต้นฉบับ DIFF_TIME, SAME_TIME, SAME_STUDENTS',
             'โหมดห้องคงที่: ห้ามเปลี่ยนห้อง และคาบที่มีสัปดาห์ Lab อยู่ Lab ทั้งเทอม']
    rule_html = ''.join(f'<p style="{SANS}; font-size:24px; line-height:1.45; color:{GREY}; padding-left:24px; '
                        f'text-indent:-24px">· {r}</p>' for r in rules)
    html = (
        f'<h2 style="position:absolute; top:112px; left:128px; width:1664px; {H2}">เป้าหมายและข้อห้ามของปัญหา</h2>\n'
        '<div style="position:absolute; top:240px; left:128px; width:1664px; display:grid; grid-template-columns:1fr 1fr; column-gap:48px">'
        f'<div style="display:flex; flex-direction:column; gap:22px">'
        f'<p style="{SANS}; font-size:24px; color:{MUTED}">เป้าหมาย: ยิ่งน้อยยิ่งดี เทียบตามลำดับ</p>'
        + li('1', 'คาบที่ยังจัดไม่ได้', 'ทุกคาบรายสัปดาห์ที่ไม่ได้เวลาหรือไม่ได้ห้อง')
        + li('2', 'ชั่วโมง Lab ไม่จำเป็น', 'ชั่วโมงที่คาบนั่งอยู่ใน Lab ในสัปดาห์ที่คาบนั้นไม่ได้ต้องใช้ Lab')
        + li('3', 'จำนวนครั้งที่เปลี่ยนห้อง', 'นับทุกครั้งที่ห้องต่างจากสัปดาห์ก่อนหน้าของคาบเดียวกัน')
        + p('ตารางที่จัดครบกว่าชนะเสมอ ถ้าเท่ากันจึงดูข้อ 2 แล้วจึงดูข้อ 3', 24, INK)
        + f'<div style="display:flex; flex-direction:column; gap:6px; padding:24px 28px; {CARD}">'
        + f'<p style="{SANS}; font-size:24px; font-weight:600; color:{INK}">ตัวอย่าง Lab ไม่จำเป็น: คาบละ 1.5 ชม. ต้องใช้ Lab สัปดาห์ 3, 6, 9, 12</p>'
        + p(f'ห้องคงที่ อยู่ Lab ทั้ง 15 สัปดาห์ → 11 × 1.5 = <b style="color:{RED}">16.5 ชม.</b> · '
            f'ห้องรายสัปดาห์ อยู่ Lab แค่ 4 สัปดาห์นั้น → <b style="color:{BLUE}">0 ชม.</b>', 24)
        + p('ไม่นับคาบที่จัดไม่ได้ จึงต้องดูคู่กับข้อ 1 เสมอ', 22, MUTED)
        + '</div></div>'
        f'<div style="display:flex; flex-direction:column; gap:12px">'
        f'<p style="{SANS}; font-size:24px; color:{MUTED}">ข้อห้าม: ห้ามละเมิดเลย ถ้าจัดไม่ได้ให้เว้นเป็นคาบตกค้าง</p>'
        + rule_html
        + p('ไม่ได้คิด: เวลาเดินระหว่างห้อง และความชอบ (soft preference) ของต้นฉบับ', 22, MUTED, 'margin-top:12px')
        + '</div></div>\n'
        f'<p style="position:absolute; bottom:64px; left:128px; width:1664px; {SANS}; font-size:24px; color:{MUTED}">'
        'ที่มา / data/FORMAT.txt, engine/solution_validator.py</p>')
    note = ('ก่อนเข้าวิธี ขอสรุปเป้าหมายและข้อห้ามไว้ในหน้าเดียว เป้าหมายมีสามข้อ ยิ่งน้อยยิ่งดี และเทียบตามลำดับ '
            'ข้อแรกสำคัญที่สุดคือคาบที่ยังจัดไม่ได้ ข้อสองคือชั่วโมง Lab ที่ไม่จำเป็น ข้อสามคือจำนวนครั้งที่เปลี่ยนห้อง '
            'ตารางที่จัดครบกว่าชนะเสมอ ถ้าเท่ากันจึงดู Lab ไม่จำเป็น แล้วจึงดูการเปลี่ยนห้อง '
            'ชั่วโมง Lab ไม่จำเป็นคือชั่วโมงที่คาบนั่งอยู่ใน Lab ในสัปดาห์ที่ไม่ได้ต้องใช้ Lab ตัวอย่างเช่นวิชาคาบละชั่วโมงครึ่ง ใช้ Lab สี่สัปดาห์ '
            'ถ้าล็อกห้องไว้ใน Lab ทั้งเทอม สิบเอ็ดสัปดาห์ที่เหลือคือสิบหกชั่วโมงครึ่งที่ไม่จำเป็น ถ้าห้องเปลี่ยนรายสัปดาห์จะเป็นศูนย์ '
            'ตัวเลขนี้ไม่นับคาบที่จัดไม่ได้ จึงต้องดูคู่กับข้อแรกเสมอ '
            'ข้อห้ามทั้งหมดเป็น hard constraint ถ้าจัดไม่ได้จะเว้นเป็นคาบตกค้าง ไม่ยอมละเมิด '
            'ส่วนที่เราไม่ได้คิดคือเวลาเดินระหว่างห้อง และความชอบที่ไม่บังคับของต้นฉบับ')
    return {'id': 'objective', 'title': 'เป้าหมายและข้อห้ามของปัญหา', 'style': 'background:#ffffff', 'html': html, 'note': note}


# --- #34: the one-Lab example from a real run -----------------------------------
def perweek_slide():
    # SIM-LAB-04, Tuesday 11:30-13:30, GA seed 1001 weekly (experiments/final); checked by check_perweek().
    real = ['A', 'B', 'B', 'C', 'D', 'D', 'B', 'B', 'A', 'A', 'C', 'C', None, 'C', 'D']
    a_lab = {1, 4, 9, 10}

    def cell(text, bg, fg='#ffffff', thai=False):
        font = f'{SANS}; font-size:24px; line-height:1.5' if thai else f'{GEIST}; font-size:30px; font-weight:600'
        return (f'<p class="cell" style="width:86px; padding:12px 0; {font}; text-align:center; color:{fg}; '
                f'background:{bg}; border-radius:8px">{text}</p>')

    def row(label, cells, sub=''):
        lab = (f'<div style="width:248px; display:flex; flex-direction:column">'
               f'<p style="{SANS}; font-size:28px; font-weight:600; line-height:1.3; color:{INK}">{label}</p>'
               + (f'<p style="{SANS}; font-size:20px; color:{MUTED}">{sub}</p>' if sub else '') + '</div>')
        return f'<div style="display:flex; flex-direction:row; gap:8px; align-items:center">{lab}{"".join(cells)}</div>'

    head = row('', [f'<p style="width:86px; {MONO}; font-size:24px; text-align:center; color:{MUTED}">{w}</p>' for w in range(1, 16)])
    head = head.replace(f'<p style="{SANS}; font-size:28px; font-weight:600; line-height:1.3; color:{INK}"></p>',
                        f'<p style="{SANS}; font-size:24px; color:{MUTED}">สัปดาห์</p>')
    fixed = row('ถ้าล็อกห้อง', [cell('A', BLUE if w in a_lab else RED) for w in range(1, 16)], 'สมมติ')
    weekly = row('รายสัปดาห์', [cell(x, BLUE) if x else cell('ว่าง', '#f2f2f2', MUTED, True) for x in real], 'ผลจริง GA seed 1001')
    legend = [('A', 'C1434', '1, 4, 9, 10 (สัปดาห์ 4 ใช้ LAB-03)'), ('B', 'C1564', '2, 3, 7, 8'),
              ('C', 'C1579', '4, 11, 12, 14'), ('D', 'C1488', '5, 6, 14, 15 (สัปดาห์ 14 ใช้ LAB-02)')]
    legend_html = ''.join(
        f'<p style="{SANS}; font-size:24px; line-height:1.45; color:{GREY}"><b style="{GEIST}; color:{INK}">{k}</b> = คลาส {c} · ต้องใช้ Lab สัปดาห์ {w}</p>'
        for k, c, w in legend)
    html = (
        f'<h2 style="position:absolute; top:112px; left:128px; width:1664px; {H2}">Lab ห้องเดียว: ล็อกทั้งเทอมได้ 1 คลาส แบ่งรายสัปดาห์ได้ 4 คลาส</h2>\n'
        f'<p style="position:absolute; top:250px; left:128px; width:1664px; {SANS}; font-size:26px; color:{MUTED}">'
        'SIM-LAB-04 · วันอังคาร 11:30–13:30 · สีน้ำเงิน = สัปดาห์ที่คลาสนั้นต้องใช้ Lab จริง · สีแดง = นั่ง Lab โดยไม่จำเป็น</p>\n'
        '<div style="position:absolute; top:360px; left:128px; width:1664px; display:flex; flex-direction:column; gap:12px">'
        + head + fixed + weekly + '</div>\n'
        '<div style="position:absolute; top:640px; left:128px; width:1664px; display:grid; grid-template-columns:1fr 1fr; column-gap:48px">'
        f'<div style="display:flex; flex-direction:column; gap:4px">{legend_html}'
        + p('สัปดาห์ที่เหลือทั้ง 4 คลาสเรียนในห้องบรรยาย', 22, MUTED) + '</div>'
        f'<div style="display:flex; flex-direction:column; gap:10px; padding:24px 28px; border-left:6px solid {BLUE}; background:#f5f9ff">'
        + p('<b style="color:#171717">ต้นเหตุไม่ได้อยู่ที่ Lab น้อย แต่อยู่ที่การล็อก Lab ไว้ทั้งเทอม</b>', 26)
        + p(f'ถ้าล็อก: A นั่ง Lab โดยไม่จำเป็น 11 สัปดาห์ (<span style="color:{RED}">Lab ไม่จำเป็น</span>) '
            'และ B, C, D ต้องหา Lab อื่นทั้งเทอม (ถ้าไม่มี = <span style="color:#171717">คาบที่จัดไม่ได้</span>)', 24)
        + p('รายสัปดาห์: ใช้ 14 จาก 15 สัปดาห์ ไม่มีช่องแดงเลย แลกกับการย้ายห้องไปกลับระหว่าง Lab กับห้องบรรยาย', 24)
        + '</div></div>')
    note = ('หน้านี้เป็นตัวอย่างจริงจากผลรัน GA seed 1001 โหมดรายสัปดาห์ ดู Lab ห้องเดียวคือ SIM-LAB-04 ช่วงวันอังคาร 11:30 ถึง 13:30 '
            'ช่วงนี้มีสี่คลาสผลัดกันใช้ คือ C1434 C1564 C1579 และ C1488 แทนด้วย A B C D ทุกช่องสีน้ำเงินคือสัปดาห์ที่คลาสนั้นต้องใช้ Lab จริง '
            'รวมกันใช้ 14 จาก 15 สัปดาห์ ไม่มีสัปดาห์ไหนที่นั่ง Lab โดยไม่จำเป็น สัปดาห์อื่นทั้งสี่คลาสเรียนในห้องบรรยาย '
            'มีสองสัปดาห์ที่ชนกัน คือสัปดาห์ 4 ที่ A กับ C ต้องใช้ Lab พร้อมกัน A จึงไปใช้ SIM-LAB-03 และสัปดาห์ 14 ที่ C กับ D ชนกัน D จึงไปใช้ SIM-LAB-02 '
            'แถวบนเป็นภาพสมมติว่าถ้าล็อกห้อง Lab ช่วงนี้จะให้ได้คลาสเดียวทั้งเทอม สมมติ A ได้ไป A ใช้จริงสี่สัปดาห์ อีกสิบเอ็ดสัปดาห์นั่ง Lab โดยไม่จำเป็น '
            'ส่วน B C D ต้องหา Lab อื่นช่วงเดียวกันให้ได้ทั้งเทอม ถ้าไม่มีก็จัดไม่ได้ ภาพนี้จึงเป็นภาพย่อของเป้าหมายทั้งสามข้อ '
            'ช่องแดงคือ Lab ไม่จำเป็น คลาสที่ไม่ได้ห้องคือคาบที่จัดไม่ได้ และการสลับไปมาระหว่าง Lab กับห้องบรรยายคือการเปลี่ยนห้อง '
            'ต้นเหตุจึงไม่ได้อยู่ที่ Lab น้อย แต่อยู่ที่การล็อก Lab ไว้ทั้งเทอม '
            'ในข้อมูลทั้งชุด วิชาที่ต้องใช้ Lab ใช้จริงรวม 804 ชั่วโมง ถ้าล็อกห้องคงที่ต้องถือ Lab เพิ่มอีก 2,211 ชั่วโมงในสัปดาห์ที่ไม่ได้ใช้')
    return html, note


def check_perweek():
    """The example on the perweek slide must match the stored GA seed 1001 weekly schedule."""
    import gzip
    payload = json.loads(gzip.decompress((ROOT / 'experiments/final/experiment.json.gz').read_bytes()))
    data = json.loads(payload['dataset_text'])
    run = next(r for r in payload['batch']['results'] if r['algorithm'] == 'ga' and r['room_mode'] == 'weekly' and r['seed'] == 1001)
    classes = {c['id']: c for c in data['classes']}
    meeting = {}
    for cid, oid in run['solution']['class_time_options'].items():
        for m in next(o for o in classes[cid]['time_options'] if o['id'] == oid)['meetings']:
            meeting[m['session_id']] = m
    names = {'C1434-M1': 'A', 'C1564-M1': 'B', 'C1579-M1': 'C', 'C1488-M1': 'D'}
    got = [None] * 15
    for a in run['solution']['weekly_room_assignments']:
        m = meeting[a['session_id']]
        if a['room_id'] == 'SIM-LAB-04' and (m['day'], m['start_minute'], m['duration_minutes']) == (1, 690, 120):
            got[a['week'] - 1] = names[a['session_id']]
    want = ['A', 'B', 'B', 'C', 'D', 'D', 'B', 'B', 'A', 'A', 'C', 'C', None, 'C', 'D']
    assert got == want, got
    lab_weeks = {s['id']: s['lab_weeks'] for s in data['recurring_sessions']}
    assert lab_weeks['C1434-M1'] == [1, 4, 9, 10] and lab_weeks['C1564-M1'] == [2, 3, 7, 8]
    assert lab_weeks['C1579-M1'] == [4, 11, 12, 14] and lab_weeks['C1488-M1'] == [5, 6, 14, 15]



# --- #28: research questions and what Greedy stands for -------------------------
def edit_problem(by):
    s = by['problem']
    s['html'] = replace_once(s['html'], '>วิธีค้นหาใดให้ตารางดีที่สุดเมื่อได้งบเท่ากัน</p>',
        '>คำถาม: ห้องรายสัปดาห์ลด Lab ไม่จำเป็นได้เท่าไร แลกกับย้ายห้องกี่ครั้ง และประหยัด Lab ได้กี่ห้อง<br>'
        'และวิธีค้นหาแบบไหนให้ตารางดีที่สุดเมื่อได้งบเท่ากัน</p>')
    s['html'] = replace_once(s['html'], 'top:841.35px; left:50%; width:1584px', 'top:810px; left:50%; width:1664px')
    s['note'] = replace_once(s['note'], 'คำถามที่ตอบในวันนี้มีสองข้อ คือแนวคิดนี้ลด Lab ที่ไม่จำเป็นได้จริงไหม และในสี่วิธีค้นหา วิธีไหนดีที่สุดเมื่อได้งบเท่ากัน',
        'แนวคิดนี้ฟังดูตรงไปตรงมา คำถามจึงไม่ใช่ว่าลดได้ไหม แต่คือลดได้เท่าไรภายใต้ข้อห้ามจริงทั้งหมด '
        'ต้องแลกด้วยการย้ายห้องกี่ครั้ง และประหยัด Lab ได้กี่ห้อง คำถามที่สองคือในสี่วิธีค้นหา วิธีไหนให้ตารางดีที่สุดเมื่อได้งบเท่ากัน')


def edit_main(by):
    s = by['main']
    s['html'] = replace_once(s['html'],
        'left:128px; width:905.41px; font-family:\'Geist Mono\', \'Courier New\', monospace; font-size:30px; transform:translateY(-50%)">'
        'Greedy ยังขาด 20 คาบ ( seed * จุดหนึ่งจุด = หนึ่ง seed )</p>',
        f'left:128px; width:1664px; {SANS}; font-size:26px; line-height:1.45; color:{GREY}; transform:translateY(-50%)">'
        '<b style="color:#171717">Greedy</b> = จัดตามกฎง่าย ๆ ทีละขั้น (คลาสที่มีตัวเลือกน้อยก่อน รอบเดียว) ยังขาด 20 คาบทุก seed '
        'เป็นตัวแทนการจัดแบบกฎง่าย ไม่ใช่ตัวแทนคนจัดจริง<br><span style="font-size:22px; color:#666666">จุดหนึ่งจุด = หนึ่ง seed · เส้นดำ = ค่าเฉลี่ย</span></p>')
    s['note'] = replace_once(s['note'], 'ส่วน Greedy ยังขาด 20 คาบทุก seed เพราะ Greedy ไม่สุ่มและประเมินครั้งเดียว',
        'ส่วน Greedy ยังขาด 20 คาบทุก seed Greedy คือการจัดตามกฎง่าย ๆ ทีละขั้น จัดคลาสที่มีตัวเลือกน้อยก่อนแล้วจบในรอบเดียว '
        'ใกล้กับวิธีที่คนจัดตารางด้วยกฎ แต่เราไม่มีตารางที่คนจัดจริงมาเทียบ จึงพูดได้แค่ว่าเป็นตัวแทนการจัดแบบกฎง่าย '
        'งานของ Cavalcante และคณะปี 2026 ก็พบว่ากฎง่ายแบบ Greedy ดีกว่าแผนที่คนจัดเองแล้ว แต่ยังแพ้วิธีที่ค้นหาจริงจัง')


# --- #32: SA tuned again after seeing the results -------------------------------
def edit_tuning(by):
    s = by['tuning']
    s['html'] = replace_once(s['html'],
        'top:689.64px; left:50%; width:1269px; font-family:\'IBM Plex Sans Thai\', Tahoma, sans-serif; font-size:28px; line-height:1.5; color:#4d4d4d; transform:translateX(-50%)">'
        '&nbsp;ค่าที่เลือกของ SA อยู่ที่มุมของช่วงที่ลอง (acceptance ต่ำสุด 0.2, cooling เร็วสุด 0.9) ค่าที่ดีกว่าอาจอยู่นอกช่วง</p>',
        f'top:680px; left:128px; width:1664px; {SANS}; font-size:28px; line-height:1.5; color:{GREY}; padding:24px 32px; '
        f'border-left:6px solid {BLUE}; background:#f5f9ff">'
        '<b style="color:#171717">SA อยู่มุมของ grid จึงจูนเพิ่มหลังเห็นผล</b> อีก 20 ชุด (acceptance 0.001–0.2 × cooling 0.7–0.9) '
        'ได้ 0.01 / 0.8 ดีขึ้นบน seed จูน (58.4 → 54.9 ชม.) แต่บน seed ทดสอบไม่ดีขึ้น (76.2 → 77.5 ชม.) '
        'และ GA ยังดีกว่า SA อย่างมีนัยสำคัญ (p = 0.003) ผลหลักจึงใช้ค่าเดิม<br>'
        f'<span style="font-size:22px; color:{MUTED}">ที่มา / experiments/sa-extended-tuning</span></p>')
    s['note'] = s['note'].split(' หลังนำเสนอ อาจารย์สังเกต')[0] + (
        ' หลังนำเสนอ อาจารย์สังเกตว่าค่าของ SA อยู่ที่มุมของช่วงที่ลอง GA อาจชนะเพราะจูน SA ไม่พอ '
        'เราจึงจูนเพิ่มอีก 20 ชุดบน seed จูนชุดเดิม ซึ่งเป็นการจูนหลังเห็นผล จึงรายงานแยกจากผลหลัก '
        'ค่าที่ดีที่สุดคือ acceptance 0.01 cooling 0.8 ดีขึ้นจาก 58.4 เป็น 54.9 ชั่วโมงบน seed จูน '
        'แต่เมื่อรันบน seed ทดสอบสามสิบตัว กลับได้ 77.5 ชั่วโมง เทียบกับ 76.2 ของค่าเดิม ชนะสิบห้าแพ้สิบห้า '
        'GA ยังดีกว่า SA อย่างมีนัยสำคัญที่ p เท่ากับ 0.003 ข้อสรุปจึงไม่เปลี่ยน '
        'ที่ SA ดีสุดเมื่อแทบไม่ยอมรับคำตอบที่แย่ลง แปลว่าที่งบนี้ SA ทำงานใกล้กับ hill climbing')

# --- write ---------------------------------------------------------------------
def write(slides):
    payload = json.dumps(slides, ensure_ascii=False)
    (HERE / 'slides.json').write_text(json.dumps(slides, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    deck_js = (HERE / 'deck.js').read_text(encoding='utf-8').split('\n', 1)[1]
    (HERE / 'deck.js').write_text(f'const slides = {payload};\n' + deck_js, encoding='utf-8')
    notes = ['# บทพูดประกอบสไลด์ · Final Presentation', '',
             f'สไลด์ {len(slides)} หน้า ประมาณ 12–15 นาที เนื้อหาเดียวกับฟิลด์ `note` ใน `slides.json` และ `deck.js` '
             'ตัวเลขผลทดลองทุกตัวมาจากไฟล์ใน `experiments/`', '']
    for i, s in enumerate(slides, 1):
        notes += [f'## {i}. {s["title"]}', '', s['note'] or '(ไม่มีบทพูด)', '']
    (HERE / 'speaker-notes.md').write_text('\n'.join(notes), encoding='utf-8')


def insert_after(slides, after_id, slide):
    slides[:] = [s for s in slides if s['id'] != slide['id']]
    i = next(i for i, s in enumerate(slides) if s['id'] == after_id)
    slides.insert(i + 1, slide)


def main():
    slides = json.loads((HERE / 'slides.json').read_text(encoding='utf-8'))
    by = {s['id']: s for s in slides}
    insert_after(slides, 'problem', approach_slide())
    insert_after(slides, 'data', objective_slide())
    check_perweek()
    by['perweek']['html'], by['perweek']['note'] = perweek_slide()
    by['perweek']['title'] = 'Lab ห้องเดียว: ล็อกทั้งเทอมได้ 1 คลาส แบ่งรายสัปดาห์ได้ 4 คลาส'
    for extra in EXTRA_EDITS:
        extra(by)
    write(slides)
    print(len(slides), 'slides')


EXTRA_EDITS = [edit_problem, edit_main, edit_tuning]

if __name__ == '__main__':
    main()
