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
    s['note'] = s['note'].replace( 'คำถามที่ตอบในวันนี้มีสองข้อ คือแนวคิดนี้ลด Lab ที่ไม่จำเป็นได้จริงไหม และในสี่วิธีค้นหา วิธีไหนดีที่สุดเมื่อได้งบเท่ากัน',
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
    s['note'] = s['note'].replace( 'ส่วน Greedy ยังขาด 20 คาบทุก seed เพราะ Greedy ไม่สุ่มและประเมินครั้งเดียว',
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


# --- #30: Lab data is synthetic ------------------------------------------------
def edit_data(by):
    s = by['data']
    s['html'] = replace_once(s['html'],
        'Computer Lab จำลอง 4 ห้อง</h3>\n      <p style="font-family:\'IBM Plex Sans Thai\', Tahoma, sans-serif; font-size:26px; line-height:1.5; color:#4d4d4d">134 คาบประจำใช้ Lab คนละ 4 สัปดาห์&nbsp;</p>',
        'Lab และสัปดาห์ Lab สร้างขึ้นเอง</h3>\n      '
        + p('ต้นฉบับไม่มี Lab · เพิ่ม Lab จำลอง 4 ห้อง (61/36/30/26 ที่นั่ง) · สุ่ม 60% ของคาบประจำ (134 คาบ) ให้ใช้ Lab 4 จาก 15 สัปดาห์ · seed 20261027', 24))
    s['html'] = replace_once(s['html'], 'top:495px; left:128px; width:1664px; height:252px;', 'top:495px; left:128px; width:1664px; height:290px;')
    s['html'] = s['html'].split('\n<p data-extra="patterns"')[0] + (
        f'\n<p data-extra="patterns" style="position:absolute; top:830px; left:128px; width:1664px; {SANS}; font-size:26px; line-height:1.5; color:{GREY}">'
        '60% และ 4 สัปดาห์เป็นค่าที่ตั้งเอง ไม่ใช่ข้อมูลสำรวจ · ลองสัปดาห์ Lab แบบ<b style="color:#171717">ติดกัน</b>และ<b style="color:#171717">เว้นสัปดาห์</b>แล้ว '
        'ข้อสรุปและลำดับวิธีไม่เปลี่ยน เปลี่ยนแค่จำนวนครั้งที่ย้ายห้อง<br>'
        f'<span style="font-size:22px; color:{MUTED}">ที่มา / data/assumptions.json (A10), dataset_tools/config.json, experiments/lab-week-patterns</span></p>')
    s['note'] = s['note'].split(' ขอย้ำว่าข้อมูล Lab')[0] + (
        ' ขอย้ำว่าข้อมูล Lab ไม่ได้มาจากต้นฉบับ เราสร้างขึ้นเอง ต้นฉบับไม่มี Computer Lab และไม่มีความต้องการ Lab รายสัปดาห์ '
        'เราสุ่ม 60 เปอร์เซ็นต์ของคาบประจำให้ต้องใช้ Lab และแต่ละคาบสุ่มสี่สัปดาห์จากสิบห้า ด้วย seed 20261027 ซึ่งแยกจาก seed ของอัลกอริทึม '
        'ตัวเลข 60 เปอร์เซ็นต์และสี่สัปดาห์เป็นค่าที่ตั้งเอง ไม่ได้มาจากการสำรวจวิชาจริง '
        'เพราะวิชาจริงมักมีรูปแบบ เราจึงลองอีกสองแบบ คือ Lab สี่สัปดาห์ติดกัน และเว้นสัปดาห์ ข้อสรุปหลักและลำดับวิธีไม่เปลี่ยน '
        'สิ่งที่เปลี่ยนคือจำนวนครั้งที่ต้องย้ายห้อง แบบติดกันย้ายราว 270 ครั้ง แบบสุ่มราว 830 ครั้ง และแบบเว้นสัปดาห์ราว 1,080 ครั้ง')


def edit_result_titles(by):
    for sid, old, new in (('main', 'GA ใช้ Lab โดยไม่จำเป็นน้อยที่สุด', 'งบ 500: GA ใช้ Lab โดยไม่จำเป็นน้อยที่สุด'),
                          ('stats', 'GA ดีที่สุด', 'งบ 500: GA ดีที่สุด แต่ยังแยกจาก HC ไม่ได้')):
        s = by[sid]
        s['html'] = replace_once(s['html'], f'>{old}</h2>', f'>{new}</h2>')
        s['title'] = new
    s = by['stats']
    s['note'] = s['note'].split(' ข้อสรุปนี้เป็นของงบ 500')[0] + (
        ' ข้อสรุปนี้เป็นของงบ 500 ซึ่งเป็นงบหลักตาม protocol ในหน้าเรื่องงบเราจะเห็นว่าถ้าให้งบมากขึ้น ผู้ชนะเปลี่ยน')


# --- #33: run until the results settle -----------------------------------------
def edit_budget(by):
    summary = json.loads((ROOT / 'experiments/convergence/summary.json').read_text(encoding='utf-8'))
    levels = summary['levels']
    mean = {m: {int(k): v for k, v in summary['methods'][m]['mean_lab_hours'].items()} for m in ('hc', 'sa', 'ga')}
    x0, x1, w, h, y_max = 60, 1180, 1240, 380, 150
    lx = lambda b: x0 + (math.log10(b) - math.log10(levels[0])) / (math.log10(levels[-1]) - math.log10(levels[0])) * (x1 - x0)
    sy = lambda v: 360 - v / y_max * 340
    style = {'hc': ('#4d4d4d', 4, ''), 'sa': ('#8f8f8f', 4, ' stroke-dasharray="12 8"'), 'ga': (BLUE, 6, '')}
    lines = [f'<line x1="0" y1="{sy(v):.1f}" x2="{w}" y2="{sy(v):.1f}" stroke="{"#d4d4d4" if v == 0 else "#efefef"}" stroke-width="2"/>'
             for v in (0, 50, 100, 150)]
    lines.append(f'<line x1="{lx(500):.1f}" y1="10" x2="{lx(500):.1f}" y2="360" stroke="#d4d4d4" stroke-width="2" stroke-dasharray="6 6"/>')
    for m in ('hc', 'sa', 'ga'):
        color, width, dash = style[m]
        pts = ' '.join(f'{lx(b):.1f},{sy(mean[m][b]):.1f}' for b in levels)
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/>')
        lines.append(''.join(f'<circle cx="{lx(b):.1f}" cy="{sy(mean[m][b]):.1f}" r="{8 if m == "ga" else 6}" fill="{color}"/>' for b in levels))
    svg = (f'<svg class="reveal-x" xmlns="http://www.w3.org/2000/svg" aria-label="กราฟเส้น Lab ไม่จำเป็นเฉลี่ยของ HC SA GA ตามงบ 50 ถึง 50,000 '
           f'แกนนอนแบบ log ที่งบ 500 GA ต่ำสุด ตั้งแต่งบ 2,000 SA ต่ำสุด" viewBox="0 0 {w} 380" '
           f'style="position:absolute; top:50px; left:100px; width:{w}px; height:380px">\n' + '\n'.join(lines) + '\n</svg>')
    ticks = ''.join(f'<p style="position:absolute; top:{sy(v) + 32:.0f}px; left:0; width:80px; {MONO}; font-size:24px; text-align:right; color:{MUTED}">{v}</p>'
                    for v in (0, 50, 100, 150))
    xt = ''.join(f'<p style="position:absolute; top:442px; left:{100 + lx(b) - 60:.0f}px; width:120px; {MONO}; font-size:22px; text-align:center; '
                 f'color:{INK if b == 500 else MUTED}{"; font-weight:600" if b == 500 else ""}">{b:,}</p>' for b in levels)
    end = {'sa': (f'SA {mean["sa"][50000]:.1f} ชม.', '#8f8f8f', ''), 'ga': (f'GA {mean["ga"][50000]:.1f} ชม.', BLUE, '; font-weight:600'),
           'hc': (f'HC {mean["hc"][50000]:.1f} ชม.', '#4d4d4d', '')}
    labels = ''.join(f'<p style="position:absolute; top:{top}px; left:1360px; width:220px; {SANS}; font-size:24px; color:{c}{x}">{t}</p>'
                     for top, (t, c, x) in zip((330, 366, 402), (end['hc'], end['ga'], end['sa'])))
    tests = {(t['a'], t['b']): t for t in summary['tests_at_50000']}
    near = near_optimal()
    html = (
        f'<h2 style="position:absolute; top:112px; left:128px; width:1664px; {H2}">ผู้ชนะขึ้นกับงบ: งบ 500 GA ดีสุด ตั้งแต่ 2,000 SA ดีสุด</h2>\n'
        '<div style="position:absolute; top:250px; left:128px; width:1664px; height:560px">'
        f'<p style="position:absolute; top:0; left:0; width:600px; {SANS}; font-size:26px; color:{GREY}">Lab ไม่จำเป็นเฉลี่ย (ชม.) · seed 1001–1010</p>'
        + svg + ticks + xt
        + f'<p style="position:absolute; top:486px; left:100px; width:{w}px; {SANS}; font-size:24px; text-align:center; color:{GREY}">'
          'งบการค้นหาต่อรัน (จำนวนครั้งที่ประเมินคำตอบ, แกน log) · เส้นประ = งบ 500 ของการทดลองหลัก</p>'
        + labels + '</div>\n'
        f'<p style="position:absolute; top:800px; left:128px; width:1664px; {SANS}; font-size:26px; line-height:1.5; color:{GREY}">'
        f'<b style="color:#171717">เกือบดีที่สุดแล้ว:</b> ที่งบ 50,000 SA จัดครบและไม่มี Lab ไม่จำเป็นเลยใน {near["runs"]} จาก 10 seed '
        f'ย้ายห้อง {near["lo"]}–{near["hi"]} ครั้ง เทียบค่าต่ำสุดที่พิสูจน์ได้ {near["bound"]} (ห่าง ≤ {near["gap"]:.1f}%)<br>'
        f'SA ดีกว่า GA และ HC อย่างมีนัยสำคัญ (p ปรับ Holm {tests[("ga", "sa")]["p_holm"]:.3f} และ {tests[("hc", "sa")]["p_holm"]:.3f}) '
        'GA กับ HC ยังแยกกันไม่ได้ · ยังไม่นิ่งสนิท แต่ดีขึ้นช้ามาก<br>'
        f'<span style="font-size:22px; color:{MUTED}">รันละราว 3 นาทีด้วย C# · พารามิเตอร์จูนที่งบ 500 · ที่มา / experiments/convergence, experiments/budget</span></p>')
    by['budget'].update({'title': 'ผู้ชนะขึ้นกับงบ: งบ 500 GA ดีสุด ตั้งแต่ 2,000 SA ดีสุด', 'html': html, 'note': (
        'อาจารย์แนะนำให้รันจนผลนิ่ง ไม่ใช่หยุดที่งบตายตัว เราจึงรันต่อจนถึง 50,000 evaluations บน seed 1001 ถึง 1010 ด้วย engine C# รันละราวสามนาที '
        'เพราะไม่มีวิธีไหนใช้งบในการวางแผนการค้นหา รันยาวรันเดียวจึงบอกผลของทุกงบที่เล็กกว่าได้ และเราตรวจแล้วว่าตรงกับรันงบ 500 และ 1000 ที่เก็บไว้ทุกคู่ '
        'ผลคือผู้ชนะขึ้นกับงบ ที่งบ 500 ถึง 1000 GA ดีที่สุดเหมือนผลหลัก แต่ตั้งแต่งบ 2,000 SA ดีที่สุด '
        f'ที่งบ 50,000 SA เหลือ Lab ไม่จำเป็นเฉลี่ย {mean["sa"][50000]:.1f} ชั่วโมง เป็นศูนย์ใน 8 จาก 10 seed GA {mean["ga"][50000]:.1f} และ HC {mean["hc"][50000]:.1f} '
        'SA ดีกว่าทั้งสองอย่างมีนัยสำคัญ ส่วน GA กับ HC ยังแยกกันไม่ได้ทุกงบ และ SA เปลี่ยนห้องแค่ 786 ครั้ง ใกล้ค่าต่ำสุด 783 '
        'คำอธิบายที่เป็นไปได้คือ SA ที่จูนไว้ลดอุณหภูมิเร็ว หลังจากนั้นยอมรับคำตอบที่เท่าเดิมได้ จึงเดินบนที่ราบไปเรื่อย ๆ ส่วน HC เริ่มใหม่แบบสุ่มเมื่อติด '
        'เรื่องนิ่งหรือยัง เกณฑ์ไม่ดีขึ้นเลยในหนึ่งหมื่นครั้งใช้ไม่ได้ เพราะหลายรันหยุดนิ่งนานแล้วกลับดีขึ้นอีก '
        'จาก 20,000 ไป 50,000 ยังลดได้อีกสามถึงหกชั่วโมง จึงยังไม่นิ่งสนิท แต่ดีขึ้นช้ามากแล้ว '
        'ข้อควรระวังคือพารามิเตอร์ทุกวิธีจูนที่งบ 500 ถ้าจะใช้งบใหญ่จริงควรจูนใหม่')})


def edit_limits(by, slides):
    s = by['limits']
    n = next(i for i, x in enumerate(slides, 1) if x['id'] == 'limits')
    def card(title, body):
        return (f'<div style="display:flex; flex-direction:column; gap:10px; padding:32px 36px; {CARD}">'
                f'<h3 style="{SANS}; font-size:34px; font-weight:600; line-height:1.3; color:{INK}">{title}</h3>{p(body)}</div>')
    s['html'] = (
        '<div style="display:flex; flex-direction:column; gap:12px">\n'
        f'    <div style="display:flex; flex-direction:row; gap:16px; align-items:center"><p style="{MONO}; font-size:24px; color:{BLUE}">{n}</p>'
        f'<p style="{SANS}; font-size:24px; color:{MUTED}">ข้อจำกัด</p></div>\n'
        f'    <h2 style="{H2}">ข้อจำกัดของการศึกษา</h2>\n  </div>\n'
        '  <div style="display:grid; gap:28px; grid-template-columns:1fr 1fr">'
        + card('ข้อมูลดัดแปลงชุดเดียว', 'Lab และสัปดาห์ Lab สร้างขึ้นเอง ลองแบบติดกันและเว้นสัปดาห์แล้วข้อสรุปเดิม แต่ยังไม่มีข้อมูลวิชาจริง และไม่มีตารางที่คนจัดจริงมาเทียบ')
        + card('พารามิเตอร์จูนที่งบ 500', 'จูน SA เพิ่มหลังเห็นผลแล้ว ผลที่งบ 500 ไม่เปลี่ยน แต่ลำดับวิธีขึ้นกับงบ ถ้าใช้งบใหญ่ควรจูนใหม่ที่งบนั้น')
        + card('ยังไม่นิ่งสนิทที่งบ 50,000', 'ดีขึ้นช้ามากแล้ว และ SA เข้าใกล้ 0 · การศึกษางบใหญ่ใช้ 10 seed')
        + card('Search space และผลด้านคน', 'ไม่มี move ที่ย้ายห้องโดยตรง · ยังไม่ได้วัดผลของการย้ายห้องต่อนักศึกษา เช่น เดินไกลหรือสับสน')
        + '</div>\n'
        f'  <p style="position:absolute; bottom:64px; left:128px; width:1664px; {SANS}; font-size:24px; color:{MUTED}">'
        'ที่มา / README ของ experiments/lab-week-patterns, sa-extended-tuning, convergence และ lab-scarcity</p>')
    s['note'] = ('ข้อจำกัดสำคัญมีสี่ข้อ ข้อแรก ผลทั้งหมดมาจากข้อมูลดัดแปลงชุดเดียว และข้อมูล Lab เราสร้างขึ้นเอง '
                 'เราลองรูปแบบสัปดาห์ Lab แบบติดกันและเว้นสัปดาห์แล้วข้อสรุปไม่เปลี่ยน แต่ยังไม่มีข้อมูลวิชาจริง และไม่มีตารางที่คนจัดจริงมาเทียบ '
                 'ข้อสอง พารามิเตอร์ทุกวิธีจูนที่งบ 500 เราจูน SA เพิ่มแล้วผลที่งบ 500 ไม่เปลี่ยน แต่เมื่อให้งบมากขึ้นลำดับวิธีเปลี่ยน จึงควรจูนใหม่ถ้าจะใช้งบใหญ่ '
                 'ข้อสาม ที่งบ 50,000 ยังไม่นิ่งสนิท แต่ดีขึ้นช้ามากแล้ว และการศึกษางบใหญ่ใช้แค่ 10 seed '
                 'ข้อสี่ การค้นหาไม่มี move ที่ย้ายห้องโดยตรง และเรายังไม่ได้วัดผลของการย้ายห้องต่อนักศึกษา')


def edit_conclude(by):
    s = by['conclude']
    def card(n, title, body):
        return (f'<div style="display:flex; flex-direction:column; gap:12px; flex:1; padding:36px; {CARD}">'
                f'<p style="{GEIST}; font-size:40px; font-weight:600; color:{BLUE}">{n}</p>'
                f'<h3 style="{SANS}; font-size:32px; font-weight:600; line-height:1.3; color:{INK}">{title}</h3>{p(body, 24)}</div>')
    s['html'] = (
        f'<h2 style="position:absolute; top:112px; left:128px; width:1664px; {H2}">สรุปผลการศึกษา</h2>\n'
        '<div style="position:absolute; top:260px; left:128px; width:1664px; display:flex; flex-direction:row; gap:28px">'
        + card('1', 'ห้องรายสัปดาห์ประหยัด Lab ได้หนึ่งห้อง',
               'จัดครบทุกคาบ ห้องคงที่ใช้ Lab ไม่จำเป็นเพิ่ม 1,801–1,949 ชม. ต่อเทอมและยังจัดไม่ครบ เหลือ Lab 3 ห้องก็ยังจัดครบ ข้อสรุปเดิมแม้สัปดาห์ Lab ติดกันหรือเว้นสัปดาห์')
        + card('2', 'วิธีที่ดีที่สุดขึ้นกับงบ',
               'งบ 500: GA ≈ HC ดีกว่า SA และ Greedy · ตั้งแต่งบ 2,000: SA ดีที่สุด ที่งบ 50,000 ได้ 0 ชม. ใน 8/10 seed และห่างจากค่าดีที่สุดไม่เกิน 0.4%')
        + card('3', 'ราคาคือการย้ายห้อง',
               'ราว 1.06 เท่าของค่าต่ำสุดที่ข้อมูลบังคับ (831 เทียบ 783 ครั้ง) ที่งบ 50,000 SA ย้าย 786 ครั้ง ราคาขึ้นกับรูปแบบสัปดาห์ Lab ของวิชาจริง')
        + '</div>\n'
        f'<p style="position:absolute; top:800px; left:128px; width:1664px; {SANS}; font-size:26px; line-height:1.5; color:{GREY}">'
        '<b style="color:#171717">งานต่อยอด</b> ทดลองกับข้อมูลวิชาจริง · จูนพารามิเตอร์ที่งบใหญ่ · เพิ่ม move ที่ย้ายห้องโดยตรง · วัดผลของการย้ายห้องต่อนักศึกษา</p>')
    s['note'] = ('สรุปสามข้อ หนึ่ง ห้องรายสัปดาห์ลด Lab ที่ไม่จำเป็นได้ชัดเจน ห้องคงที่ใช้ Lab ไม่จำเป็นเพิ่มขึ้นเฉลี่ย 1,801 ถึง 1,949 ชั่วโมงต่อเทอมและยังจัดไม่ครบ '
                 'ขณะที่ห้องรายสัปดาห์จัดครบแม้เหลือ Lab 3 ห้อง คือประหยัด Lab ได้หนึ่งห้องเต็ม และข้อสรุปนี้ไม่เปลี่ยนเมื่อสัปดาห์ Lab ติดกันหรือเว้นสัปดาห์ '
                 'สอง วิธีที่ดีที่สุดขึ้นกับงบ ที่งบ 500 GA ดีที่สุดโดยรวม ดีกว่า SA อย่างมีนัยสำคัญ แต่ยังแยกจาก HC ไม่ได้ '
                 'เมื่อให้งบตั้งแต่ 2,000 ขึ้นไป SA ดีที่สุด และที่งบ 50,000 แทบไม่เหลือ Lab ที่ไม่จำเป็น '
                 'สาม สิ่งที่แลกมาคือการเปลี่ยนห้อง ซึ่งอยู่ที่ราว 1.06 เท่าของค่าต่ำสุดที่ข้อมูลบังคับ และขึ้นกับรูปแบบสัปดาห์ Lab ของวิชาจริง '
                 'งานต่อยอดคือทดลองกับข้อมูลวิชาจริง จูนพารามิเตอร์ที่งบใหญ่ เพิ่ม move ที่ย้ายห้องโดยตรง และวัดผลของการย้ายห้องต่อนักศึกษา ขอบคุณครับ')


# --- #35: recent references -----------------------------------------------------
RECENT_REFS = [
    ('https://doi.org/10.5772/intechopen.1017804', 'Cavalcante et al. (2026)',
     'A Mathematical Model for Class Scheduling: A Case Study with the Federal University of Maranhão. IntechOpen.',
     'คนจัดเอง 23 ห้อง · Greedy 20 · ILP 13 · ใช้ Lab จำลองเหมือนเรา'),
    ('https://doi.org/10.1016/j.cor.2026.107659', 'Raviv (2026)',
     'The lecture-hall quadratic assignment problem. Computers &amp; Operations Research, 196, 107659.',
     'ย้ายห้องระหว่างเทอมต้นทุนต่ำ แต่ย้ายเวลากระทบนักศึกษา'),
    ('https://doi.org/10.3390/a18030158', 'Han &amp; Wang (2025)',
     'Gradual Optimization of University Course Scheduling Problem Using Genetic Algorithm and Dynamic Programming. Algorithms, 18(3), 158.',
     'จัดห้องรายสัปดาห์ แต่ประเภทห้องผูกกับวิชา ไม่เปลี่ยนตามสัปดาห์'),
    ('https://www.sciencedirect.com/journal/procedia-computer-science/vol/278', 'Antunes-Batista et al. (2026)',
     'Multiobjective Optimization Approaches for Room Allocation in University Course Timetabling. Procedia Computer Science, 278, 663–670.',
     'นับการเปลี่ยนห้องของวิชาเดียวกันเป็นเป้าหมาย คล้าย room changes'),
    ('https://doi.org/10.1007/s10287-025-00529-2', 'Ozkan et al. (2025)',
     'University course timetabling with multi-section courses, room stability and lecturer preferences. Computational Management Science, 22(1), 3.',
     'room stability ตรงกับโหมดห้องคงที่'),
    ('https://doi.org/10.1007/s10951-023-00801-w', 'Müller, Rudová &amp; Müllerová (2025)',
     'Real-world university course timetabling at the International Timetabling Competition 2019. Journal of Scheduling, 28(2), 247–267.',
     'ข้อมูล UniTime สายเดียวกับ pu-fal07-cs'),
]


def recent_refs_slide():
    cards = []
    for url, who, ref, why in RECENT_REFS:
        cards.append(
            '    <div style="display:flex; flex-direction:column; gap:6px; padding:18px 0 0; border-top:1px solid #eaeaea">\n'
            f'      <p style="{GEIST}; font-size:28px; font-weight:600; color:#171717"><a href="{url}">{who}</a></p>\n'
            f'      <p style="{SANS}; font-size:22px; line-height:1.4; color:#4d4d4d">{ref}</p>\n'
            f'      <p style="{SANS}; font-size:22px; line-height:1.4; color:{BLUE}">{why}</p>\n'
            '    </div>')
    html = (f'<h2 style="position:absolute; top:112px; left:128px; width:1664px; {H2}">เอกสารอ้างอิง: งานใหม่ 2025–2026</h2>\n'
            '  <div style="position:absolute; top:232px; left:128px; width:1664px; display:grid; '
            'grid-template-columns:1fr 1fr; column-gap:56px; row-gap:32px">\n' + '\n'.join(cards) + '\n  </div>')
    note = ('หน้านี้เป็นงานใหม่ปี 2025 ถึง 2026 ที่เพิ่มตามข้อเสนอแนะว่าเอกสารอ้างอิงเก่า '
            'งานที่ใกล้เราที่สุดคือ Cavalcante และคณะ ที่มหาวิทยาลัย Maranhão ประเทศบราซิล ซึ่งเทียบแผนที่คนจัดเองกับ Greedy และ ILP บนข้อมูลชุดเดียวกัน '
            'คนจัดเองใช้ 23 ห้อง Greedy ใช้ 20 ห้อง ILP ใช้ 13 ห้อง และเขาก็เพิ่ม Lab จำลองเข้าไปเหมือนเรา พบว่าจำนวน Lab ที่ใช้พร้อมกันคือข้อจำกัดหลัก '
            'งานของ Raviv ปี 2026 ให้เหตุผลที่ตรงกับการออกแบบของเรา คือการย้ายห้องระหว่างเทอมมีต้นทุนต่ำ แต่การย้ายเวลาเรียนกระทบนักศึกษา '
            'เราจึงล็อกเวลาไว้ทั้งเทอม และให้เปลี่ยนได้แค่ห้อง '
            'Han และ Wang ปี 2025 จัดห้องเป็นรายสัปดาห์เหมือนกัน แต่ประเภทห้องที่ต้องใช้ผูกกับวิชา ไม่เปลี่ยนตามสัปดาห์ '
            'ส่วน Antunes-Batista และ Ozkan มองการเปลี่ยนห้องเป็นต้นทุนที่ต้องลด ตรงกับเมตริกการเปลี่ยนห้องของเรา '
            'สิ่งที่เรายังไม่เจอในงานเหล่านี้คือการให้คาบเดียวกันต้องใช้ห้องต่างประเภทในแต่ละสัปดาห์ แต่เราค้นยังไม่ครบทุกแหล่ง')
    return {'id': 'refs-recent', 'title': 'เอกสารอ้างอิง: งานใหม่ 2025–2026', 'style': 'background:#ffffff', 'html': html, 'note': note}

def near_optimal(method='sa', budget=50000):
    """Runs that reach 0 unassigned and 0 unnecessary Lab hours, and their gap to the room-change lower bound.

    The bound (783) holds for every schedule with all sessions placed and no unnecessary Lab hours
    (experiments/final/analysis/stats.json), so such a run is optimal on the first two objectives and
    at most (room_changes - bound) changes from the lexicographic optimum.
    """
    bound = json.loads((ROOT / 'experiments/final/analysis/stats.json').read_text(encoding='utf-8'))['room_changes']['dataset_lower_bound']
    rows = list(csv.DictReader(open(ROOT / 'experiments/convergence/convergence.csv', encoding='utf-8')))
    changes = [int(r[f'room_changes_{budget}']) for r in rows if r['algorithm'] == method
               and int(r[f'unassigned_{budget}']) == 0 and float(r[f'lab_hours_{budget}']) == 0]
    return {'runs': len(changes), 'lo': min(changes), 'hi': max(changes), 'bound': bound,
            'gap': (max(changes) - bound) / bound * 100}



# --- spoken script (review item 2: fit 20 slides into about 15 minutes) ----------
# The slide functions above keep their longer notes as background; NOTES is what is spoken and is
# written last. The original 17-slide deck used about 8,260 characters for 12-15 minutes, so the
# script must stay under NOTES_LIMIT characters.
NOTES_LIMIT = 8300
NOTES = {
    'cover': 'วันนี้นำเสนอผลขั้นสุดท้ายของโครงงานจัดตารางเรียนที่เลือกห้องตามความต้องการ Lab ในแต่ละสัปดาห์ เราเทียบ 4 อัลกอริทึม จูนพารามิเตอร์ ทดลองบน 30 seed และหลังได้ feedback ได้ทดลองเพิ่มอีก 4 ชุด ตัวเลขทุกตัวในสไลด์มาจากไฟล์ใน experiments',
    'problem': 'ตัวอย่างนี้เป็นสถานการณ์สมมติ ถ้าใช้ห้องคงที่ วิชาที่ต้องใช้ Lab บางสัปดาห์ต้องจอง Lab ไว้ทั้งเทอม สัปดาห์ที่เป็นบรรยายจึงนั่งอยู่ใน Lab โดยไม่ได้ใช้ ช่องสีแดงคือชั่วโมงแบบนี้ ซึ่งเราเรียกว่าชั่วโมง Lab ที่ไม่จำเป็น และคลาสอื่นที่สัปดาห์นั้นต้องใช้ Lab จริงก็จองไม่ได้ แนวคิดของเราคือคงเวลาเรียนเดิม แต่ให้ห้องเปลี่ยนได้รายสัปดาห์ แนวคิดนี้ฟังดูตรงไปตรงมา คำถามจึงไม่ใช่ว่าลดได้ไหม แต่คือลดได้เท่าไรภายใต้ข้อห้ามจริงทั้งหมด แลกกับการย้ายห้องกี่ครั้ง และประหยัด Lab ได้กี่ห้อง คำถามที่สองคือในสี่วิธีค้นหา วิธีไหนให้ตารางดีที่สุดเมื่อได้งบเท่ากัน',
    'approach': 'งานนี้ตัดสินใจสองชั้น ชั้นแรกคือเวลา แต่ละคลาสเลือกวันและเวลาจากตัวเลือกที่ต้นฉบับอนุญาตหนึ่งชุด แล้วใช้ทั้ง 15 สัปดาห์ ชั้นที่สองคือห้อง ซึ่งเลือกใหม่ได้ทุกสัปดาห์ สัปดาห์ที่ต้องใช้ Lab อยู่ Lab สัปดาห์อื่นอยู่ห้องบรรยาย สองเรื่องนี้เกี่ยวกันเพราะเวลากำหนดว่าห้องจะพอไหม ถ้าคลาสที่ต้องใช้ Lab สัปดาห์เดียวกันเลือกเวลาเดียวกัน Lab สี่ห้องก็ไม่พอ เราตรวจตารางคำตอบทุกรันแล้ว ไม่มีครั้งไหนที่คาบนั่ง Lab ทั้งที่มีห้องบรรยายว่าง ทุกครั้งห้องบรรยายเต็มเพราะคลาสอื่นเลือกเวลาเดียวกัน Lab ไม่จำเป็นที่เหลือจึงมาจากการเลือกเวลา อัลกอริทึมค้นหาลำดับคลาสกับเวลาที่อยากลองก่อน ส่วนห้องนั้น decoder เป็นคนเลือก',
    'since': 'จาก feedback ครั้งก่อน เราเทียบ 4 วิธีบนตัวแทนคำตอบเดียวกัน ทดลองทั้งห้องคงที่และห้องรายสัปดาห์รวม 240 รัน และเขียน engine ใหม่เป็น C# ที่ให้ผลตรงกับ Python ทุกรันแต่เร็วกว่าราว 75 เท่า',
    'data': 'ข้อมูลตั้งต้นคือ Purdue Fall 2007 CS จาก UniTime มี 174 คลาส รวม 3,345 คาบรายสัปดาห์ ต้นฉบับไม่มีห้อง Lab และไม่มีความต้องการ Lab รายสัปดาห์ ข้อมูล Lab จึงสร้างขึ้นเองทั้งหมด เราเพิ่ม Lab จำลอง 4 ห้อง และสุ่ม 60 เปอร์เซ็นต์ของคาบให้ใช้ Lab 4 จาก 15 สัปดาห์ รวม 804 ชั่วโมงที่ต้องใช้ Lab จริง ตัวเลข 60 เปอร์เซ็นต์และสี่สัปดาห์ตั้งเอง ไม่ได้มาจากการสำรวจวิชาจริง เราจึงลองสัปดาห์ Lab แบบติดกันและแบบเว้นสัปดาห์ด้วย ข้อสรุปและลำดับวิธีไม่เปลี่ยน ที่เปลี่ยนคือจำนวนครั้งที่ต้องย้ายห้อง ตั้งแต่ราว 270 ถึง 1,080 ครั้งต่อเทอม',
    'objective': 'เป้าหมายมีสามข้อ เทียบตามลำดับ หนึ่ง คาบที่ยังจัดไม่ได้ สอง ชั่วโมง Lab ไม่จำเป็น สาม จำนวนครั้งเปลี่ยนห้อง ตารางที่จัดครบกว่าชนะเสมอ Lab ไม่จำเป็นคือชั่วโมงที่นั่ง Lab ในสัปดาห์ที่ไม่ต้องใช้ เช่นวิชาคาบละชั่วโมงครึ่ง ใช้ Lab สี่สัปดาห์ ถ้าล็อกห้องทั้งเทอมจะเสียไป 16.5 ชั่วโมง ถ้าเปลี่ยนรายสัปดาห์จะเป็นศูนย์ ข้อห้ามทางขวาเป็น hard constraint ทั้งหมด จัดไม่ได้ก็เว้นไว้ ไม่ยอมละเมิด',
    'method': 'ทั้งสี่วิธีค้นหาบนตัวแทนเดียวกัน คือลำดับคลาสกับเวลาที่อยากลองก่อน แล้วใช้ decoder ตัวเดียวกันแปลงเป็นตาราง และตัวตรวจอิสระนับคะแนนใหม่ Greedy ประเมินครั้งเดียว HC รับเฉพาะคำตอบที่ดีขึ้นและเริ่มใหม่เมื่อติด SA ยอมรับคำตอบแย่ลงได้บางครั้ง GA ใช้ประชากรและผสมคำตอบ',
    'protocol': 'กติกาเขียนไว้ก่อนเริ่มจูน จูนบน seed 1 ถึง 10 ทดสอบบน seed 1001 ถึง 1030 ทุกวิธีได้งบ 500 การประเมินเท่ากัน สถิติใช้ Friedman แล้ว Wilcoxon จับคู่ ปรับ Holm ทั้ง 240 รันผ่านตัวตรวจอิสระ',
    'tuning': 'จูนบน seed 1 ถึง 10 เท่านั้น ลองทั้งหมด 47 ชุดค่า รวม 470 รัน GA ได้ประโยชน์มากที่สุด จาก 76.2 เหลือ 55.1 ชั่วโมง หลังนำเสนอ อาจารย์สังเกตว่าค่าของ SA อยู่มุม grid และ GA อาจชนะเพราะจูน SA ไม่พอ เราจึงจูน SA เพิ่มอีก 20 ชุด ค่าใหม่ดีขึ้นบน seed จูน แต่บน seed ทดสอบสามสิบตัวไม่ดีขึ้น จาก 76.2 เป็น 77.5 ชั่วโมง ชนะสิบห้าแพ้สิบห้า และ GA ยังดีกว่า SA อย่างมีนัยสำคัญ ผลหลักจึงใช้ค่าเดิม เรารายงานส่วนนี้แยกไว้ เพราะเป็นการจูนหลังเห็นผล',
    'main': 'เทียบบน seed ทดสอบ 30 ตัวที่งบ 500 HC SA และ GA จัดครบทุกคาบทั้ง 30 seed ส่วน Greedy ยังขาด 20 คาบทุก seed Greedy คือการจัดตามกฎง่าย ๆ ทีละขั้น จัดคลาสที่มีตัวเลือกน้อยก่อนแล้วจบในรอบเดียว แต่เราไม่มีตารางที่คนจัดจริงมาเทียบ จึงพูดได้แค่ว่าเป็นตัวแทนการจัดแบบกฎง่าย เมื่อจัดครบเท่ากัน ตัวตัดสินถัดไปคือ Lab ไม่จำเป็น แต่ละจุดคือหนึ่ง seed GA เฉลี่ย 57.7 ชั่วโมง HC 64.9 SA 76.2 และ Greedy 124 จุดของ GA กับ HC ซ้อนกันมาก ซึ่งตรงกับสถิติในหน้าถัดไป',
    'stats': 'Friedman test บอกว่าสี่วิธีต่างกันอย่างมีนัยสำคัญ p น้อยกว่า 0.001 อันดับเฉลี่ย GA ดีที่สุด ตามด้วย HC SA และ Greedy เมื่อเทียบรายคู่และปรับ Holm GA ดีกว่า SA ใน 26 จาก 30 seed อย่างมีนัยสำคัญ แต่ GA กับ HC ยังแยกกันไม่ได้ p 0.188 พูดง่าย ๆ คือที่งบ 500 GA ดีที่สุดโดยรวม แต่ยังไม่มีหลักฐานพอว่าดีกว่า HC และในหน้าเรื่องงบเราจะเห็นว่าถ้าให้งบมากขึ้นผู้ชนะเปลี่ยน',
    'perweek': 'นี่คือผลจริงจาก GA seed 1001 ดู Lab ห้องเดียว SIM-LAB-04 วันอังคาร 11:30 สี่คลาสผลัดกันใช้ ทุกช่องสีน้ำเงินคือสัปดาห์ที่ต้องใช้ Lab จริง รวม 14 จาก 15 สัปดาห์ ไม่มีช่องแดงเลย แถวบนเป็นภาพสมมติว่าถ้าล็อกห้อง Lab ช่วงนี้จะให้ได้คลาสเดียว นั่งเปล่า 11 สัปดาห์ และอีกสามคลาสต้องหา Lab อื่นทั้งเทอม ภาพนี้คือเป้าหมายทั้งสามข้อในหน้าเดียว ต้นเหตุจึงไม่ได้อยู่ที่ Lab น้อย แต่อยู่ที่การล็อก Lab ไว้ทั้งเทอม',
    'changes': 'ราคาของห้องรายสัปดาห์คือการเปลี่ยนห้อง ราว 830 ครั้งดูเยอะ แต่ข้อมูลบังคับให้เปลี่ยนอย่างน้อย 783 ครั้ง ถ้าจะจัดครบและไม่ใช้ Lab เกินจำเป็น เราอยู่ที่ 1.06 เท่าของค่าต่ำสุด ถ้าใช้ห้องคงที่ไม่ต้องเปลี่ยนห้องเลย แต่ Lab ที่ถูกครองเปล่าเพิ่มจากราว 66 เป็นเกือบ 2,000 ชั่วโมง',
    'scarcity': 'ถ้าตัด Lab ที่เล็กที่สุดออก ห้องรายสัปดาห์ยังจัดครบเมื่อเหลือ 3 ห้อง ส่วนห้องคงที่จัดไม่ครบตั้งแต่ 4 ห้อง ขาด 159 คาบ คือห้องรายสัปดาห์ประหยัด Lab ได้หนึ่งห้องเต็ม',
    'budget': 'อาจารย์แนะนำให้รันจนผลนิ่ง ไม่ใช่หยุดที่งบตายตัว เราจึงรันถึง 50,000 การประเมินบน seed 1001 ถึง 1010 ด้วย engine C# รันละราวสามนาที ผลคือผู้ชนะขึ้นกับงบ ที่งบ 500 ถึง 1,000 GA ดีที่สุดเหมือนผลหลัก แต่ตั้งแต่ 2,000 SA ดีที่สุด และที่ 50,000 SA ดีกว่า GA และ HC อย่างมีนัยสำคัญ ที่สำคัญคือ SA ได้ตารางที่จัดครบและไม่มี Lab ไม่จำเป็นเลยใน 8 จาก 10 seed และย้ายห้องห่างจากค่าต่ำสุดที่พิสูจน์ได้ไม่เกิน 3 ครั้ง ไม่ถึงครึ่งเปอร์เซ็นต์ จึงเกือบดีที่สุดแล้วโดยไม่ต้องใช้ ILP ผลยังไม่นิ่งสนิทแต่ดีขึ้นช้ามาก ข้อควรระวังคือพารามิเตอร์ทุกวิธีจูนที่งบ 500',
    'csharp': 'การทดลองหลักด้วย Python ใช้ราว 30 นาที เราจึงเขียน engine เป็น C# เหลือราว 20 วินาที ตัวสุ่มและลำดับการตัดสินเหมือน Python ทุกขั้น ผล 240 รันจึงตรงกันทุกตัว และ CI ตรวจซ้ำทั้งบน Ubuntu และ Windows ทำให้การทดลองงบ 50,000 ทำได้จริง',
    'limits': 'ข้อจำกัดมีสี่ข้อ ข้อมูลดัดแปลงชุดเดียวและข้อมูล Lab สร้างเอง ไม่มีตารางที่คนจัดจริงมาเทียบ พารามิเตอร์จูนที่งบ 500 การศึกษางบใหญ่ใช้ 10 seed และยังไม่ได้วัดผลของการย้ายห้องต่อนักศึกษา',
    'conclude': 'สรุปสามข้อ หนึ่ง ห้องรายสัปดาห์ลด Lab ที่ไม่จำเป็นได้ราว 1,800 ถึง 1,950 ชั่วโมงต่อเทอม และจัดครบแม้เหลือ Lab 3 ห้อง คือประหยัด Lab ได้หนึ่งห้องเต็ม ข้อสรุปนี้ไม่เปลี่ยนเมื่อสัปดาห์ Lab ติดกันหรือเว้นสัปดาห์ สอง วิธีที่ดีที่สุดขึ้นกับงบ ที่งบ 500 GA ดีที่สุดแต่ยังแยกจาก HC ไม่ได้ เมื่อให้งบมาก SA ดีที่สุดและเกือบถึงค่าที่ดีที่สุด สาม ราคาคือการย้ายห้อง ราว 1.06 เท่าของค่าต่ำสุดที่ข้อมูลบังคับ และขึ้นกับรูปแบบสัปดาห์ Lab ของวิชาจริง งานต่อยอดคือข้อมูลวิชาจริง จูนที่งบใหญ่ และวัดผลของการย้ายห้องต่อนักศึกษา ขอบคุณครับ',
    'refs': 'รายการอ้างอิงกดเปิดลิงก์ได้',
    'refs-recent': 'งานใหม่ที่ใกล้เราที่สุดคือ Cavalcante 2026 ซึ่งพบว่ากฎแบบ Greedy ดีกว่าคนจัดเอง แต่แพ้วิธีที่ค้นหาจริงจัง และเพิ่ม Lab จำลองแบบเดียวกับเรา Raviv 2026 ให้เหตุผลว่าการย้ายห้องระหว่างเทอมมีต้นทุนต่ำกว่าการย้ายเวลา งานอื่นมองการเปลี่ยนห้องเป็นต้นทุนที่ต้องลด ยังไม่พบงานที่ให้คาบเดียวกันใช้ห้องต่างประเภทตามสัปดาห์',
}


def spoken_minutes(slides):
    chars = sum(len(s['note']) for s in slides)
    return f'{chars / (8260 / 12):.0f}–{chars / (8260 / 15):.0f}'


def apply_notes(slides):
    missing = [s['id'] for s in slides if s['id'] not in NOTES]
    if missing:
        raise SystemExit(f'no spoken note for: {missing}')
    for s in slides:
        s['note'] = NOTES[s['id']]
    total = sum(len(s['note']) for s in slides)
    if total > NOTES_LIMIT:
        raise SystemExit(f'spoken script is {total} characters, over the {NOTES_LIMIT} limit for about 15 minutes')
    return total


# --- write ---------------------------------------------------------------------
def write(slides):
    payload = json.dumps(slides, ensure_ascii=False)
    (HERE / 'slides.json').write_text(json.dumps(slides, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    deck_js = (HERE / 'deck.js').read_text(encoding='utf-8').split('\n', 1)[1]
    (HERE / 'deck.js').write_text(f'const slides = {payload};\n' + deck_js, encoding='utf-8')
    notes = ['# บทพูดประกอบสไลด์ · Final Presentation', '',
             f'สไลด์ {len(slides)} หน้า บทพูด {sum(len(s["note"]) for s in slides):,} ตัวอักษร ราว {spoken_minutes(slides)} นาที '
             '(คิดจากเด็คเดิมที่ใช้ 8,260 ตัวอักษรสำหรับ 12–15 นาที) เผื่อเวลาเปลี่ยนหน้าและตอบคำถามจนไม่เกิน 15 นาที '
             'เนื้อหาเดียวกับฟิลด์ `note` ใน `slides.json` และ `deck.js` '
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
    insert_after(slides, 'refs', recent_refs_slide())
    by = {s['id']: s for s in slides}
    for extra in EXTRA_EDITS:
        extra(by)
    edit_limits(by, slides)
    chars = apply_notes(slides)
    write(slides)
    print(len(slides), 'slides,', chars, 'characters of speaker notes')


EXTRA_EDITS = [edit_problem, edit_main, edit_tuning, edit_data, edit_result_titles, edit_budget, edit_conclude]

if __name__ == '__main__':
    main()
