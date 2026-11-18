"""Build the simple hand-drawn version of the final deck. Standard library only.

    python3 apps/slides/simple/build.py

Writes slides.json, deck.js and speaker-notes.md next to this file. The slide
order, ids and speaker notes come from the main deck (../slides.json); a few
notes are reworded below where they point at a chart this version draws
differently. The slide controller is the one in ../deck.js.

Look: white page, Mali handwriting, black ink doodles, one yellow accent, and a
monitor mascot. Every slide is a title plus a short list, a small table or a
few big numbers. All numbers are the ones on the main deck (see ../README.md
for the experiment file behind each).
"""
import gzip
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent
INK, YELLOW, GREY = '#222222', '#FFD13F', '#555555'
SRIRACHA = "font-family:'Sriracha','Mali',cursive"
PAD = 'padding:64px 140px 130px;gap:36px'


# --- doodles -------------------------------------------------------------------
def mascot(mood='happy', wave=False, hat=False):
    """The monitor mascot on a 300x330 box. mood: happy, sad or wow."""
    mouth = {'happy': '<path d="M128 150C138 164 162 164 172 150" fill="none"/>',
             'sad': '<path d="M128 160C138 148 162 148 172 160" fill="none"/>',
             'wow': '<ellipse cx="150" cy="156" rx="10" ry="12" fill="#FFFFFF"/>'}[mood]
    arm = ('<path d="M246 150C266 140 276 116 280 92" fill="none"/><circle cx="281" cy="84" r="9" fill="#FFFFFF"/>'
           '<path d="M296 66L306 58M300 86L312 84M294 104L304 110" fill="none" stroke-width="3"/>'
           if wave else '<path d="M246 160C262 170 270 186 272 204" fill="none"/><circle cx="273" cy="212" r="9" fill="#FFFFFF"/>')
    sweat = ('<path d="M258 44C264 56 268 62 262 68C256 72 250 66 254 58Z" fill="#FFFFFF" stroke-width="3"/>'
             if mood == 'sad' else '')
    helmet = ('<path d="M92 52C92 8 208 8 208 52Z" fill="%s"/><path d="M78 50H222C226 58 222 64 216 64H84C78 64 74 58 78 50Z" '
              'fill="%s"/><path d="M150 18V50" fill="none" stroke-width="3.5"/>' % (YELLOW, YELLOW)) if hat else ''
    return (f'<g stroke="{INK}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M120 224L112 284L92 290M180 224L188 284L208 290" fill="none"/>'
            '<path d="M54 160C38 170 30 186 28 204" fill="none"/><circle cx="27" cy="212" r="9" fill="#FFFFFF"/>'
            f'{arm}'
            '<path d="M56 62C56 52 62 48 72 48L230 44C240 44 246 50 246 60L248 204C248 214 242 220 232 220L72 224'
            'C62 224 56 218 56 208Z" fill="#FFFFFF"/>'
            '<path d="M56 62C56 52 62 48 72 48L230 44C240 44 246 50 246 60L248 204C248 214 242 220 232 220L72 224'
            'C62 224 56 218 56 208Z" fill="none" stroke-width="1.5" transform="translate(4 -4)"/>'
            '<path d="M74 70L228 66L230 198L76 202Z" fill="#FFFFFF" stroke-width="3"/>'
            '<ellipse cx="122" cy="116" rx="20" ry="24" fill="#FFFFFF"/><ellipse cx="180" cy="116" rx="19" ry="23" fill="#FFFFFF"/>'
            f'<circle cx="127" cy="120" r="11" fill="{INK}" stroke="none"/><circle cx="184" cy="120" r="10" fill="{INK}" stroke="none"/>'
            f'{mouth}{sweat}{helmet}'
            '<path d="M96 246L108 240M100 258L112 254" fill="none" stroke-width="3"/>'
            '</g><g fill="#FFFFFF"><circle cx="123" cy="115" r="4"/><circle cx="180" cy="115" r="3.5"/></g>')


def sparkle(x, y, s=1.0):
    return (f'<path transform="translate({x} {y}) scale({s})" d="M30 0Q34 26 60 30Q34 34 30 60Q26 34 0 30Q26 26 30 0Z" '
            f'fill="{YELLOW}" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>')


def bubble(text, left, top, width, size=40):
    """Speech bubble: an ink outline with the words on top (words are real text so they stay editable)."""
    lines = text.count('<br>') + 1
    height = int(lines * size * 1.25 + 44)
    return (f'<svg aria-label="กรอบคำพูด" width="{width}" height="{height + 30}" viewBox="0 0 {width} {height + 30}" '
            f'style="position:absolute;left:{left}px;top:{top}px;width:{width}px;height:{height + 30}px">'
            f'<path d="M26 6H{width - 26}C{width - 10} 6 {width - 6} 18 {width - 6} 28V{height - 28}C{width - 6} {height - 12} '
            f'{width - 16} {height - 6} {width - 28} {height - 6}H{width * 0.42:.0f}L{width * 0.3:.0f} {height + 24}'
            f'L{width * 0.3:.0f} {height - 6}H26C12 {height - 6} 6 {height - 14} 6 {height - 28}V28C6 14 12 6 26 6Z" '
            f'fill="#FFFFFF" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/></svg>'
            f'<p style="position:absolute;left:{left}px;top:{top + 20}px;width:{width}px;{SRIRACHA};font-size:{size}px;'
            f'line-height:1.25;color:{INK};text-align:center">{text}</p>')


def buddy(say, mood='happy', wave=False, hat=False, scale=1.0, stars=True, size=40):
    """Right-hand column: the mascot with a speech bubble."""
    scale, size = scale * 1.3, round(size * 1.1)
    mw, mh = int(300 * scale), int(330 * scale)
    w, h = 500, mh + 200
    art = (f'<svg aria-label="น้องจอคอมพิวเตอร์ ตัวการ์ตูนประจำสไลด์" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           f'style="width:{w}px;height:{h}px">'
           f'<g transform="translate({(w - mw) // 2 + 20} {h - mh - 6}) scale({scale})">{mascot(mood, wave, hat)}</g>'
           f'{sparkle(4, h - 150, 0.9) + sparkle(436, h - 250, 0.6) if stars else ""}</svg>')
    return (f'<div style="position:relative;width:{w}px;height:{h}px;flex:none">{art}'
            f'{bubble(say, 10, 0, 340, size)}</div>')


def bars(items, width=640, height=420, unit=''):
    height = round(height * 1.25)
    """Hand-drawn bar chart. items: (label, value, text, highlighted)."""
    top, base, left = 60, height - 110, 30
    peak = max(v for _, v, _, _ in items)
    step = (width - left - 20) / len(items)
    bw = min(110, step * 0.62)
    out, labels = [], []
    for i, (label, value, text, hot) in enumerate(items):
        x = left + step * i + (step - bw) / 2
        y = base - (base - top) * value / peak
        hatch = ''.join(f'M{x:.0f} {yy:.0f}H{x + bw:.0f}' for yy in range(int(y) + 14, base, 14))
        out.append(f'<path class="grow-y" d="M{x:.0f} {base}V{y:.0f}H{x + bw:.0f}V{base}" fill="{YELLOW if hot else "#FFFFFF"}"/>'
                   + ('' if hot else f'<path class="grow-y" d="{hatch}" fill="none" stroke-width="2.2"/>'))
        labels.append(f'<p style="position:absolute;left:{x - 40:.0f}px;top:{y - 46:.0f}px;width:{bw + 80:.0f}px;font-size:30px;'
                      f'font-weight:700;line-height:1.2;text-align:center">{text}</p>'
                      f'<p style="position:absolute;left:{x - 40:.0f}px;top:{base + 12}px;width:{bw + 80:.0f}px;font-size:28px;'
                      f'line-height:1.2;text-align:center">{label}</p>')
    alt = ' · '.join(f'{label} {text}' for label, _, text, _ in items)
    return (f'<div style="position:relative;width:{width}px;height:{height}px;flex:none">'
            f'<svg aria-label="กราฟแท่ง {alt}" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'style="width:{width}px;height:{height}px"><g stroke="{INK}" stroke-width="4" stroke-linecap="round" '
            f'stroke-linejoin="round">{"".join(out)}<path d="M{left - 14} {base}H{width - 6}" fill="none"/></g></svg>'
            f'{"".join(labels)}'
            + (f'<p style="position:absolute;left:0;top:{base + 62}px;width:{width}px;font-size:24px;color:{GREY};text-align:center">{unit}</p>'
               if unit else '') + '</div>')


def strip(rows, legend=''):
    """Week strip: rows = (name, cells); a cell is (text, kind) with kind in lab, waste, room, empty."""
    look = {'lab': f'background:{YELLOW}', 'waste': 'background:repeating-linear-gradient(45deg,#FFFFFF 0 10px,#9A9A9A 10px 13px)',
            'room': 'background:#FFFFFF', 'empty': 'background:#FFFFFF;border-style:dashed'}
    n = len(rows[0][1])
    size = 86 if n > 8 else 150
    head = ''.join(f'<p style="width:{size}px;font-size:24px;color:{GREY};text-align:center">{i + 1}</p>' for i in range(n))
    body = [f'<div style="flex-direction:row;gap:8px;align-items:center"><p style="width:230px;font-size:26px;color:{GREY}">'
            f'สัปดาห์</p>{head}</div>']
    for name, cells in rows:
        boxes = ''.join(
            f'<div class="cell" style="width:{size}px;height:{84 if n > 8 else 110}px;border:4px solid {INK};border-radius:14px;'
            f'{look[kind]};align-items:center;justify-content:center"><p style="font-size:{32 if n > 8 else 30}px;font-weight:700;'
            f'line-height:1.1;text-align:center;{"background:#FFFFFF;border-radius:8px;padding:0 8px" if kind == "waste" else ""}">'
            f'{text}</p></div>' for text, kind in cells)
        body.append(f'<div style="flex-direction:row;gap:8px;align-items:center"><p style="width:230px;font-size:28px;'
                    f'font-weight:700;line-height:1.2">{name}</p>{boxes}</div>')
    if legend:
        body.append(f'<p style="font-size:24px;color:{GREY};line-height:1.4">{legend}</p>')
    return f'<div style="gap:14px">{"".join(body)}</div>'


# --- layouts ---------------------------------------------------------------------
def h2(text):
    """Big word for what the slide is about, with the full topic as a smaller line under it."""
    head, _, detail = text.partition('|')
    line = f'<p style="font-size:34px;line-height:1.35;color:{GREY}">{detail}</p>' if detail else ''
    return (f'<div style="gap:2px"><h2 style="font-size:64px;font-weight:700;line-height:1.2;color:{INK}">{head}</h2>'
            f'{line}</div>')


def ul(items, size=32, tag='ul'):
    size = round(size * 1.2)
    return f'<{tag} style="font-size:{size}px;line-height:1.65">{"".join(f"<li>{x}</li>" for x in items)}</{tag}>'


def two(left, right, gap=48):
    return (f'<div style="flex-direction:row;gap:{gap}px;align-items:flex-start">'
            f'<div style="flex:1;gap:24px">{left}</div>{right}</div>')


def table(head, rows, size=30, widths=None):
    widths = widths or [None] * len(head)
    size = round(size * 1.15)
    th = ''.join(f'<th{f" style=\"width:{w}\"" if w else ""}>{c}</th>' for c, w in zip(head, widths))
    tr = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows)
    return f'<table style="font-size:{size}px;color:{INK};width:100%"><tr>{th}</tr>{tr}</table>'


def big(number, label):
    return (f'<div style="flex:1;gap:6px"><p style="font-size:96px;font-weight:700;line-height:1.1">{number}</p>'
            f'<p style="font-size:30px;line-height:1.4;color:{GREY}">{label}</p></div>')


def small(text):
    return f'<p style="font-size:24px;line-height:1.5;color:{GREY}">{text}</p>'


def box(title, text, hot=False):
    return (f'<div style="flex:1;border:5px solid {INK};border-radius:28px;padding:28px 32px;gap:10px;'
            f'background:{YELLOW if hot else "#FFFFFF"}"><h3 style="font-size:40px;font-weight:700;line-height:1.25">{title}</h3>'
            f'<p style="font-size:32px;line-height:1.5">{text}</p></div>')


ARROW = f'<p style="font-size:72px;font-weight:700;line-height:1;align-self:center;{SRIRACHA}">→</p>'


def ref(who, what, why=''):
    return (f'<div style="flex-direction:row;gap:28px;align-items:baseline"><p style="width:400px;flex:none;font-size:26px;'
            f'font-weight:700;line-height:1.4">{who}</p><div style="flex:1;gap:2px"><p style="font-size:24px;line-height:1.4">{what}</p>'
            + (f'<p style="font-size:24px;line-height:1.4;color:{GREY}">→ {why}</p>' if why else '') + '</div></div>')


# --- slides ----------------------------------------------------------------------
LAB, WASTE, ROOM, MISS = ('ใช้ Lab', 'lab'), ('นั่งเปล่า', 'waste'), ('ห้องปกติ', 'room'), ('ไม่มี Lab', 'empty')
def panel(title, items, hot=False, size=30):
    """A box with a heading and a short list; the yellow one marks what this project made up."""
    return (f'<div style="flex:1;border:5px solid {INK};border-radius:28px;padding:26px 32px;gap:8px;'
            f'background:{YELLOW if hot else "#FFFFFF"}"><h3 style="font-size:40px;font-weight:700;line-height:1.25">{title}</h3>'
            f'{ul(items, size)}</div>')


def lab_need(path):
    """Read a dataset. Per course (largest first) and week: 0 = no Lab, 1 = some sessions, 2 = every session needs a Lab."""
    data = json.loads(gzip.decompress((MAIN.parents[1] / path).read_bytes()))
    course = {c['id']: c['course_id'] for c in data['classes']}
    weeks = sorted(data['calendar']['week_ids'])
    total, need, minutes = {}, {}, dict.fromkeys(weeks, 0)
    for s in data['recurring_sessions']:
        c = course[s['class_id']]
        total[c] = total.get(c, 0) + 1
        for w in s['lab_weeks']:
            need.setdefault(c, dict.fromkeys(weeks, 0))[w] += 1
            minutes[w] += s['duration_minutes']
    order = sorted(total, key=lambda c: (-total[c], c))
    rows = [[0 if not need.get(c, {}).get(w) else 2 if need[c][w] == total[c] else 1 for w in weeks] for c in order]
    return rows, len(need), len(order), round(min(minutes.values()) / 60), round(max(minutes.values()) / 60)


NEED_FILL = {0: '#EEEEEE', 1: YELLOW, 2: INK}


def need_chart(title, path):
    """One row per course, one cell per week, drawn from the dataset file itself."""
    rows, used, courses, low, high = lab_need(path)
    cells = ''.join(f'<rect x="{x * 37}" y="{y * 11}" width="34" height="9" rx="2" fill="{NEED_FILL[v]}"/>'
                    for y, row in enumerate(rows) for x, v in enumerate(row))
    return (f'<div style="gap:6px;width:560px"><p style="font-size:36px;font-weight:700;line-height:1.3">{title}</p>'
            f'<p style="font-size:27px;line-height:1.4;color:{GREY}"><b>{used} จาก {courses} วิชา</b> ใช้ Lab / {low} ถึง {high} ชม. ต่อสัปดาห์</p>'
            f'<svg viewBox="0 0 555 {len(rows) * 11}" width="555" height="{len(rows) * 11}" style="margin-top:8px">{cells}</svg>'
            f'<p style="font-size:22px;line-height:1.4;color:{GREY}">สัปดาห์ 1 → 15</p></div>')


def key(value, text):
    return (f'<div style="flex-direction:row;gap:14px;align-items:center"><span style="flex:none;width:44px;height:22px;'
            f'border-radius:5px;background:{NEED_FILL[value]}"></span><p style="font-size:27px;line-height:1.35">{text}</p></div>')


SLIDES = {
    'cover': ('ระบบจัดตารางเรียนและจัดสรรห้องเรียน ภายใต้ความต้องการใช้ Lab รายสัปดาห์',
              f'<div style="flex-direction:row;align-items:center;gap:40px;flex:1">'
              f'<div style="flex:1;gap:28px">'
              f'<h1 style="font-size:68px;font-weight:700;line-height:1.3;color:{INK}">ระบบจัดตารางเรียน<br>และจัดสรรห้องเรียน</h1>'
              f'<p style="font-size:40px;line-height:1.4">ภายใต้ความต้องการใช้ Lab รายสัปดาห์</p>'
              f'<p style="font-size:30px;line-height:1.5;color:{GREY}">CS373 · นำเสนอผลงานขั้นสุดท้าย<br>'
              f'github.com/Micosz/CS373_CourseTimetablingLab</p></div>'
              f'{buddy("สวัสดี!", wave=True, scale=1.25, size=56)}</div>'),
    'problem': ('ที่มา|จากงานวิจัยเรื่องการใช้ห้องเรียน สู่โจทย์ของเรา',
                strip([('ห้องคงที่', [WASTE, WASTE, WASTE, LAB, WASTE, WASTE, WASTE, LAB]),
                       ('รายสัปดาห์', [ROOM, ROOM, ROOM, LAB, ROOM, ROOM, ROOM, LAB])],
                      'ตัวอย่างสมมติ: วิชาที่ต้องใช้ Lab แค่สัปดาห์ 4 และ 8 / ช่องขีดเส้น = นั่งใน Lab โดยไม่ได้ใช้')
                + two(ul(['<b>งานวิจัยพบ</b> ห้องเรียนมหาวิทยาลัยถูกใช้จริงต่ำได้ถึง 20–40% และข้อจำกัดของการจัดตารางเป็นสาเหตุหนึ่ง (Beyrouthy et al., 2009)',
                          '<b>กรณีที่เราเลือกศึกษา</b> วิชาที่ใช้ Lab แค่บางสัปดาห์ แต่จองห้องเดียวทั้งเทอม',
                          '<b>โจทย์ที่ได้</b> ถ้าให้ห้องเปลี่ยนได้รายสัปดาห์ จะจัดได้ครบไหม ด้วยวิธีไหน และถึงขอบเขตไหน'], 28),
                      buddy('จองทิ้งไว้<br>ทำไมอะ', 'sad', scale=0.42, stars=False, size=32))),
    'approach': ('โจทย์|เลือกเวลาครั้งเดียว ให้ทุกคาบมีห้องทั้ง 15 สัปดาห์ และใช้ Lab เท่าที่จำเป็น',
                 '<div style="flex-direction:row;gap:28px;align-items:stretch">'
                 + panel('รู้ก่อนเปิดเทอม', ['คลาสทั้งหมด และเวลาที่แต่ละคลาสเลือกได้', 'ห้องบรรยาย ห้อง Lab และความจุ',
                                           'คลาสไหนต้องใช้ Lab สัปดาห์ไหน'], size=27)
                 + panel('ต้องตัดสินใจ', ['<b>เวลา</b> ของแต่ละคลาส หนึ่งชุด ใช้ทั้ง 15 สัปดาห์',
                                         '<b>ห้อง</b> ของแต่ละคาบ เลือกใหม่ได้ทุกสัปดาห์'], hot=True, size=27)
                 + panel('ต้องได้ (เรียงตามความสำคัญ)', ['ทุกคาบมีห้องทุกสัปดาห์', 'ไม่นั่ง Lab ในสัปดาห์ที่ไม่ต้องใช้', 'ย้ายห้องน้อยที่สุด'], size=27)
                 + '</div>'
                 + small('เวลากำหนดว่าห้องจะพอไหม / อัลกอริทึมค้นหาลำดับคลาสกับเวลา ส่วนห้อง decoder เป็นคนเลือก')),
    'since': ('ข้อเสนอแนะ|สิ่งที่ปรับปรุงตามข้อเสนอแนะของอาจารย์',
              f'<div style="flex-direction:row;gap:48px">{big("4 วิธี", "Greedy, Hill Climbing, Simulated Annealing, Genetic Algorithm")}'
              f'{big("240 รัน", "ทดลองครบทั้งห้องคงที่และห้องรายสัปดาห์")}'
              f'{big("~75 เท่า", "เขียน engine ใหม่เป็น C# ผลตรงกับ Python ทุกรัน")}</div>'
              + two('', buddy('ทำการบ้าน<br>มาแล้ว!', wave=True, scale=0.72, size=36))),
    'data': ('ข้อมูล|อะไรเป็นข้อมูลจริง อะไรที่เราสมมติ',
             '<div style="flex-direction:row;gap:40px;align-items:stretch">'
             + panel('ข้อมูลจริง จาก Purdue Fall 2007 CS',
                     ['44 วิชา 174 คลาส 223 คาบต่อสัปดาห์', 'เวลาเรียนที่แต่ละคลาสเลือกได้', 'ห้องบรรยาย 13 ห้อง ความจุ และห้องที่แต่ละคลาสใช้ได้',
                      'กลุ่มนักศึกษาที่ห้ามเรียนชนกัน', 'คลาสนอกภาค 810 คลาสที่ล็อกห้องและเวลาไว้'])
             + panel('ที่เราสมมติ',
                     ['Lab 4 ห้อง จุ 61, 36, 30 และ 26 ที่นั่ง', 'วิชาไหนใช้ Lab และใช้สัปดาห์ไหน', 'เทอม 15 สัปดาห์ที่เหมือนกันทุกสัปดาห์',
                      'ผู้สอนของ 143 คลาสที่ต้นฉบับไม่ระบุ', '<b>อาจารย์บอกสัปดาห์ Lab ได้ก่อนเปิดเทอม</b>'], hot=True)
             + '</div>'
             + small('รวม 3,345 คาบรายสัปดาห์ที่ต้องจัด (223 คาบ * 15 สัปดาห์) / จำนวนนักศึกษาใช้ค่าจำกัดที่นั่งของคลาส')),
    'objective': ('เป้าหมาย|ฟังก์ชันเป้าหมายและข้อจำกัดของปัญหา',
                  two(ul(['<b>คาบที่ยังจัดไม่ได้</b> ต้องน้อยที่สุดก่อน', '<b>ชั่วโมง Lab ไม่จำเป็น</b> นั่ง Lab ในสัปดาห์ที่ไม่ได้ใช้',
                          '<b>จำนวนครั้งที่เปลี่ยนห้อง</b> ห้องต่างจากสัปดาห์ก่อน'], 32, 'ol')
                      + f'<p style="font-size:30px;line-height:1.5">ตัวอย่าง: คาบ 1.5 ชม. ใช้ Lab 4 สัปดาห์ → ห้องคงที่เสีย '
                        f'<b>16.5 ชม.</b> ห้องรายสัปดาห์เสีย <b>0 ชม.</b></p>'
                      + ul(['ห้อง ผู้สอน กลุ่มนักศึกษา ห้ามชนเวลากัน', 'ห้องต้องจุพอ และสัปดาห์ Lab ต้องอยู่ใน Lab',
                            'ห้ามชนกับคลาสพื้นหลัง 810 คลาส', 'จัดไม่ได้ก็เว้นไว้ ไม่ยอมละเมิด'], 28),
                      buddy('ห้ามชนกัน<br>เด็ดขาด', hat=True, scale=0.8, size=36))),
    'method': ('วิธีการ|การแทนคำตอบและอัลกอริทึมที่เปรียบเทียบ',
               f'<div style="flex-direction:row;gap:20px;align-items:stretch">'
               f'{box("ตัวแทนคำตอบ", "ลำดับคลาส และเวลาที่ลองก่อน")}{ARROW}'
               f'{box("ตัวจัดตาราง", "คงเวลาทั้งเทอม เลือกห้องรายสัปดาห์", True)}{ARROW}'
               f'{box("ตัวตรวจอิสระ", "ตรวจข้อห้ามและนับผลใหม่ทุกรัน")}</div>'
               + table(['วิธี', 'ค้นหายังไง'],
                       [['Greedy', 'จัดคลาสที่มีตัวเลือกน้อยก่อน ประเมินครั้งเดียว'],
                        ['Hill Climbing', 'รับเมื่อดีขึ้น เริ่มใหม่แบบสุ่มเมื่อติด'],
                        ['Simulated Annealing', 'ยอมรับคำตอบแย่ลงได้ตามอุณหภูมิ'],
                        ['Genetic Algorithm', 'มีประชากร ผสมคำตอบ เก็บตัวดีที่สุด']], 30, ['30%', None])),
    'protocol': ('การทดลอง|ระเบียบวิธีการทดลอง',
                 two(ul(['จูนบน seed 1–10 ทดสอบจริงบน seed 1001–1030', 'ทุกวิธีได้งบเท่ากัน 500 ครั้งต่อรัน',
                         'กำหนดสถิติก่อนรัน: Friedman แล้ว Wilcoxon จับคู่ ปรับ Holm', 'ระดับนัยสำคัญ α = 0.05'], 32)
                     + f'<div style="flex-direction:row;gap:48px">{big("240/240", "รันผ่านตัวตรวจอิสระ (4 วิธี × 30 seed × 2 โหมดห้อง)")}</div>',
                     buddy('ตั้งกติกา<br>ก่อนเล่น', scale=0.8, size=36))),
    'tuning': ('พารามิเตอร์|ผลการปรับค่าพารามิเตอร์ของแต่ละวิธี',
               table(['วิธี', 'ค่าที่เลือก', 'Lab ไม่จำเป็นเฉลี่ย (ชม.)'],
                     [['Hill Climbing', 'restart patience 50', '72.7 → 71.1'],
                      ['Simulated Annealing', 'acceptance 0.2 / cooling 0.9', '68.9 → 58.4'],
                      ['Genetic Algorithm', 'ประชากร 35 / mutation 0.66 / crossover 0.64', '76.2 → 55.1']], 30, ['28%', None, '30%'])
               + two(ul(['ค่าของ SA อยู่มุม grid จึงจูนเพิ่มอีก 20 ชุดหลังเห็นผล',
                         'ดีขึ้นบน seed จูน (58.4 → 54.9) แต่ไม่ดีขึ้นบน seed ทดสอบ (76.2 → 77.5)',
                         'GA ยังดีกว่า SA (p = 0.003) ผลหลักจึงใช้ค่าเดิม'], 30),
                     buddy('จูนเพิ่มแล้ว<br>ผลเหมือนเดิม', scale=0.4, stars=False, size=30))),
    'main': ('ผลการทดลอง|ชั่วโมง Lab ที่ไม่จำเป็น ที่งบ 500',
             two(ul(['งบ 500: GA ใช้ Lab โดยไม่จำเป็นน้อยที่สุด', 'HC, SA, GA จัดครบทุกคาบทั้ง 30 seed', 'Greedy ยังขาด 20 คาบทุก seed',
                     'Greedy คือการจัดตามกฎง่าย ๆ รอบเดียว ไม่ใช่ตัวแทนคนจัดจริง', 'GA กับ HC ใกล้กันมาก'], 30),
                 bars([('GA', 57.7, '57.7', True), ('HC', 64.9, '64.9', False), ('SA', 76.2, '76.2', False),
                       ('Greedy', 124.0, '124.0', False)], 700, 520, 'Lab ไม่จำเป็นเฉลี่ย (ชม.) · 30 seed · ยิ่งเตี้ยยิ่งดี'), 40)),
    'stats': ('สถิติ|การทดสอบทางสถิติของผลการทดลองหลัก',
              two(table(['วิธี', 'อันดับเฉลี่ย (น้อย = ดี)'], [['GA', '1.53'], ['HC', '1.93'], ['SA', '2.53'], ['Greedy', '4.00']], 32)
                  + ul(['Friedman χ² = 63.12, p &lt; 0.001: สี่วิธีต่างกันจริง', 'GA ดีกว่า SA ใน 26/30 seed (p &lt; 0.001)',
                        'GA กับ HC ยังแยกไม่ได้: GA ชนะ 18/30 seed (p = 0.188)'], 30),
                  buddy('ชนะ แต่ยัง<br>ไม่ขาด', 'wow', scale=0.8, size=36))),
    'perweek': ('ตัวอย่าง|การใช้ห้อง Lab ร่วมกันรายสัปดาห์',
                strip([('ถ้าล็อกห้อง<br>(สมมติ)', [('A', 'lab' if w in (1, 4, 9, 10) else 'waste') for w in range(1, 16)]),
                       ('รายสัปดาห์<br>(ผลจริง)', [(c, 'lab' if c != 'ว่าง' else 'empty') for c in
                                                   ['A', 'B', 'B', 'C', 'D', 'D', 'B', 'B', 'A', 'A', 'C', 'C', 'ว่าง', 'C', 'D']])],
                      'SIM-LAB-04 วันอังคาร 11:30–13:30 · ผลจริงจาก GA seed 1001 · สีเหลือง = ใช้ Lab จริง · ขีดเส้น = นั่งเปล่า')
                + two(ul(['ล็อกห้อง: A นั่งเปล่า 11 สัปดาห์ ส่วน B, C, D ต้องหา Lab อื่นทั้งเทอม',
                          'รายสัปดาห์: ใช้ 14 จาก 15 สัปดาห์ ไม่มีช่องนั่งเปล่าเลย',
                          'ต้นเหตุไม่ใช่ Lab น้อย แต่คือการล็อก Lab ไว้ทั้งเทอม'], 30),
                      buddy('ผลัดกัน<br>ใช้สิ', wave=True, scale=0.55, stars=False, size=32))),
    'changes': ('การเปลี่ยนห้อง|ย้ายห้องเท่าที่การใช้ Lab กำหนด',
                two(ul(['ย้ายห้องเมื่อถึงสัปดาห์ที่ต้องใช้ Lab แล้วกลับห้องบรรยาย', 'ข้อมูลกำหนดให้ย้ายอย่างน้อย 783 ครั้งต่อเทอม',
                        'ระบบย้ายราว 830 ครั้ง คือ 1.06 เท่าของค่าที่จำเป็น', 'ห้องคงที่ไม่ย้ายเลย แต่ Lab ถูกครองเปล่าเกือบ 2,000 ชม.'], 30),
                    bars([('ต่ำสุด', 783, '783', True), ('GA', 831, '831', False), ('HC', 831, '831', False), ('SA', 835, '835', False)],
                         700, 520, 'จำนวนครั้งที่เปลี่ยนห้องต่อเทอม (เฉลี่ย 30 seed)'), 40)),
    'scarcity': ('จำนวนห้อง Lab|ผลเมื่อจำนวนห้อง Lab ลดลง',
                 two(table(['จำนวน Lab', 'ห้องรายสัปดาห์', 'ห้องคงที่'],
                           [['4 ห้อง (กรณีหลัก)', '<b>0</b>', '159'], ['3 ห้อง', '<b>0</b>', '482'], ['2 ห้อง', '17.7', '896']], 34)
                     + small('ตัวเลข = คาบที่ไม่มีห้องเรียน (เฉลี่ย 10 seed, GA) ยิ่งน้อยยิ่งดี')
                     + ul(['ห้องคงที่จัดไม่ครบตั้งแต่มี Lab 4 ห้อง', 'ห้องรายสัปดาห์ประหยัด Lab ได้หนึ่งห้องเต็ม'], 32),
                     buddy('ประหยัดได้<br>1 ห้อง!', wave=True, scale=0.8, size=38))),
    'budget': ('งบการค้นหา|ผลของงบประมาณการค้นหาต่อคุณภาพคำตอบ',
               two(table(['งบต่อรัน', 'HC', 'SA', 'GA'],
                         [['500', '60.0', '76.1', '<b>56.7</b>'], ['2,000', '35.0', '<b>26.5</b>', '30.1'],
                          ['50,000', '9.8', '<b>2.0</b>', '8.7']], 34)
                   + small('Lab ไม่จำเป็นเฉลี่ย (ชม.) · seed 1001–1010 · ตัวหนา = ดีที่สุดของงบนั้น')
                   + ul(['งบ 500 GA ดีสุด ตั้งแต่งบ 2,000 SA ดีสุด',
                         'งบ 50,000: SA ไม่มี Lab ไม่จำเป็นเลยใน 8/10 seed',
                         'ย้ายห้อง 785–786 ครั้ง เทียบค่าต่ำสุด 783 (ห่าง ≤ 0.4%)'], 30),
                   buddy('ให้เวลาหน่อย<br>SA แซงเลย', 'wow', scale=0.8, size=34))),
    'csharp': ('ประสิทธิภาพ|engine ภาษา C# เทียบกับ Python',
               two(ul(['240 รัน: Python ราว 30 นาที → C# ราว 20 วินาที', 'ผลตรงกับ Python ทั้ง 240/240 รัน',
                       'ใช้ตัวสุ่ม MT19937 และลำดับการตัดสินเดียวกัน', 'CI ตรวจซ้ำทั้ง Ubuntu และ Windows'], 30),
                   bars([('Python', 1812, '30 นาที', False), ('C#', 60, '20 วินาที', True)], 520, 520,
                        'เวลาของการทดลองหลัก 240 รัน'), 40)),
    'limits': ('ข้อจำกัด|ข้อจำกัดของการศึกษา',
               two(ul(['<b>ข้อมูลดัดแปลงชุดเดียว</b> Lab สร้างขึ้นเอง และไม่มีตารางที่คนจัดจริงมาเทียบ',
                       '<b>พารามิเตอร์จูนที่งบ 500</b> ถ้าใช้งบใหญ่ควรจูนใหม่',
                       '<b>ยังไม่นิ่งสนิทที่งบ 50,000</b> และการศึกษางบใหญ่ใช้ 10 seed',
                       '<b>ยังไม่ได้วัดผลด้านคน</b> เช่น เดินไกลหรือสับสนจากการย้ายห้อง',
                       '<b>ขอบเขต 6 ถึง 8 สัปดาห์เป็นของงบ 500</b> และสุ่มเลือกวิชาที่ใช้ Lab ครั้งเดียว'], 29),
                   buddy('ยังไม่เพอร์เฟกต์<br>นะ', 'sad', scale=0.8, size=34))),
    'conclude': ('สรุป|สรุปผลการศึกษา',
                 two(ul(['<b>บนข้อมูลจำลองนี้ จัดได้ครบ</b> วิธีค้นหาจัดครบทุกคาบ ใช้ Lab เกินจำเป็นน้อย และยังจัดครบเมื่อเหลือ Lab 3 ห้อง',
                         '<b>วิธีที่ดีที่สุดขึ้นกับงบ</b> งบ 500 GA ≈ HC ตั้งแต่งบ 2,000 SA ดีที่สุด',
                         '<b>ย้ายห้องเท่าที่จำเป็น</b> 831 ครั้ง ใกล้ค่าที่ข้อมูลกำหนด 783 ครั้ง (1.06 เท่า)',
                         '<b>แนวคิดนี้มีขอบเขต</b> จัดครบเมื่อวิชาใช้ Lab ถึง 4 สัปดาห์ เริ่มไม่ครบที่ 6 ถึง 8 และยิ่ง Lab ตึงการค้นหายิ่งจำเป็น'], 28, 'ol')
                     + small('ทั้งหมดเป็นผลบนโจทย์ที่ตั้งขึ้นและข้อมูล Lab จำลอง / งานต่อยอด: ข้อมูลวิชาจริง, จูนที่งบใหญ่, เทียบกับการจอง Lab เมื่อจะใช้, วัดผลของการย้ายห้องต่อนักศึกษา'),
                     buddy('ขอบคุณครับ!', wave=True, scale=0.9, size=44))),
    'whyhard': ('ทำไมยาก|เวลาเลือกได้ครั้งเดียว แต่ความต้องการห้องเปลี่ยนทุกสัปดาห์',
                strip([('A / จันทร์ 9:00', [ROOM, LAB, ROOM, ROOM, LAB, ROOM, ROOM, ROOM]),
                       ('B / จันทร์ 9:00', [ROOM, MISS, ROOM, ROOM, MISS, ROOM, ROOM, ROOM])],
                      'ตัวอย่างสมมติ: A และ B มีนักศึกษาวิชาละ 50 คน ใช้ได้แค่ Lab ใหญ่ห้องเดียว และต้องใช้ Lab สัปดาห์ 2 กับ 5 ทั้งคู่')
                + two(ul(['<b>B ไม่มี Lab ทั้งสองสัปดาห์</b> และย้ายเวลากลางเทอมไม่ได้',
                          '<b>ถ้าตอนต้นเทอมให้ B เรียนเวลาอื่น</b> ทั้งคู่ได้ Lab ครบ',
                          '<b>ต้องเลือกเวลาของทุกคลาสพร้อมกัน</b> โดยรู้ว่าใครใช้ Lab สัปดาห์ไหน'], 32),
                      buddy('ชนกันแล้ว<br>แก้ไม่ได้', 'wow', scale=0.42, stars=False, size=32))),
    'questions': ('คำถาม|สิ่งที่งานนี้ตอบ และสิ่งที่ไม่ได้ตอบ',
                  '<div style="flex-direction:row;gap:40px;align-items:stretch">'
                  + panel('งานนี้ตอบ', ['จัดได้ครบไหม และเหลือ Lab ที่ใช้โดยไม่จำเป็นเท่าไร', 'วิธีค้นหาแบบไหนดีที่สุดเมื่อได้งบเท่ากัน',
                                       'ใช้ได้ถึงขอบเขตไหนเมื่อวิชาใช้ Lab มากขึ้น'], hot=True)
                  + panel('งานนี้ไม่ได้ตอบ', ['มหาวิทยาลัยมีสถานการณ์นี้มากแค่ไหน', 'ดีกว่าคนจัดตารางจริงหรือไม่',
                                             'ดีกว่าการจอง Lab เมื่อจะใช้หรือไม่', 'การย้ายห้องกระทบนักศึกษาแค่ไหน'])
                  + '</div>'
                  + small('ผลทั้งหมดจึงเป็นผลบนโจทย์ที่เราตั้งขึ้นและข้อมูล Lab จำลอง')),
    'coursedata': ('ข้อมูลชุดที่สอง|กำหนดความต้องการ Lab เป็นรายวิชา',
                   '<div style="flex-direction:row;gap:56px;align-items:flex-start">'
                   + need_chart('ชุดหลัก: สุ่มทีละคาบ', 'data/fall-cs.json.gz')
                   + need_chart('ชุดที่สอง: สุ่มทีละวิชา', 'data/variants/fall-cs-course-labs-w04.json.gz')
                   + '<div style="flex:1;gap:16px">' + key(2, 'ทุกคาบของวิชาใช้ Lab สัปดาห์นั้น') + key(1, 'ใช้ Lab แค่บางคาบของวิชา')
                   + key(0, 'ไม่ใช้ Lab')
                   + small('แต่ละแถวคือหนึ่งวิชา แต่ละช่องคือหนึ่งสัปดาห์ / ภาพนี้ทั้งสองชุดใช้ Lab 4 จาก 15 สัปดาห์ '
                           '/ ชุดที่สองยังทดลองตั้งแต่ 1 ถึง 15 สัปดาห์')
                   + buddy('วิชาเดียวกัน<br>เข้า Lab พร้อมกัน', scale=0.5, stars=False, size=30) + '</div></div>'),
    'labweeks': ('ขอบเขต|เมื่อวิชาใช้ Lab มากขึ้นจาก 1 ถึง 15 สัปดาห์',
                 two(table(['สัปดาห์ Lab ต่อวิชา', 'Greedy', 'วิธีค้นหา', 'รันที่จัดครบ'],
                           [['1 ถึง 2', '0', '<b>0</b>', '10 จาก 10'], ['4', '3', '<b>0</b>', '10 จาก 10'], ['6', '13', '<b>0.1</b>', '8 ถึง 9'],
                            ['8', '71', '<b>2.1</b>', '1 ถึง 2'], ['12', '197', '<b>39.8</b>', '0'], ['15', '420', '<b>87</b>', '0']], 30)
                     + small('ตัวเลข = คาบที่ไม่มีห้องเรียน เฉลี่ย 10 seed งบ 500 / วิธีค้นหา = ค่าดีที่สุดในสามวิธี (HC, SA, GA)')
                     + ul(['จัดครบทุกรันถึง 4 สัปดาห์ เริ่มไม่ครบที่ 6 ถึง 8 สัปดาห์', 'ยิ่ง Lab ตึง ช่องว่างกับ Greedy ยิ่งกว้าง'], 30),
                     buddy('ยิ่งยาก<br>ยิ่งต้องค้นหา', 'wow', scale=0.8, size=34))),
    'refs': ('เอกสารอ้างอิง',
             '<div style="gap:20px">'
             + ref('Lemos et al. (2019)', 'Room usage optimization in timetabling: A case study at Universidade de Lisboa. Operations Research Perspectives, 6, 100092.')
             + ref('Bellio et al. (2016)', 'Feature-based tuning of simulated annealing applied to the curriculum-based course timetabling problem. Computers &amp; Operations Research, 65, 83–92.')
             + ref('Müller (2009)', 'ITC2007 solver description: A hybrid approach. Annals of Operations Research, 172(1), 429–446.')
             + ref('Xiao (2021)', 'The Course Scheduling Problem with Room Considerations. Doctoral dissertation, Wright State University.')
             + ref('ITC2007', 'Curriculum-based Course Timetabling: The Problem Model. Queen’s University Belfast.')
             + ref('Beyrouthy et al. (2009)', 'Towards improving the utilization of university teaching space. Journal of the Operational Research Society, 60, 130–143.')
             + ref('UniTime', 'University course timetabling datasets, Purdue Fall 2007 CS (pu-fal07-cs).') + '</div>'),
    'refs-recent': ('เอกสารอ้างอิง|งานใหม่ 2025–2026',
                    '<div style="gap:14px">'
                    + ref('Cavalcante et al. (2026)', 'A Mathematical Model for Class Scheduling: A Case Study with the Federal University of Maranhão. IntechOpen.', 'คนจัดเอง 23 ห้อง · Greedy 20 · ILP 13 · ใช้ Lab จำลองเหมือนเรา')
                    + ref('Raviv (2026)', 'The lecture-hall quadratic assignment problem. Computers &amp; Operations Research, 196, 107659.', 'ย้ายห้องระหว่างเทอมต้นทุนต่ำ แต่ย้ายเวลากระทบนักศึกษา')
                    + ref('Han &amp; Wang (2025)', 'Gradual Optimization of University Course Scheduling Problem Using Genetic Algorithm and Dynamic Programming. Algorithms, 18(3), 158.', 'จัดห้องรายสัปดาห์ แต่ประเภทห้องผูกกับวิชา')
                    + ref('Antunes-Batista et al. (2026)', 'Multiobjective Optimization Approaches for Room Allocation in University Course Timetabling. Procedia Computer Science, 278, 663–670.', 'นับการเปลี่ยนห้องของวิชาเดียวกันเป็นเป้าหมาย')
                    + ref('Ozkan et al. (2025)', 'University course timetabling with multi-section courses, room stability and lecturer preferences. Computational Management Science, 22(1), 3.', 'room stability ตรงกับโหมดห้องคงที่')
                    + ref('Müller, Rudová &amp; Müllerová (2025)', 'Real-world university course timetabling at the International Timetabling Competition 2019. Journal of Scheduling, 28(2), 247–267.', 'ข้อมูล UniTime สายเดียวกับ pu-fal07-cs')
                    + '</div>'),
}

# Notes that point at a drawing this version shows differently (the rest are the main deck's notes, unchanged).
NOTE_EDITS = {
    'objective': [('ข้อห้ามทางขวาเป็น hard constraint ทั้งหมด', 'ข้อห้ามด้านล่างเป็น hard constraint ทั้งหมด')],
    'main': [('แต่ละจุดคือหนึ่ง seed GA เฉลี่ย', 'แต่ละแท่งคือค่าเฉลี่ยของ 30 seed GA เฉลี่ย'),
             ('จุดของ GA กับ HC ซ้อนกันมาก', 'GA กับ HC ใกล้กันมาก')],
    'changes': [('ราคาของห้องรายสัปดาห์คือการเปลี่ยนห้อง', 'ห้องรายสัปดาห์ต้องมีการเปลี่ยนห้องเมื่อถึงสัปดาห์ Lab')],
    'conclude': [('หนึ่ง ห้องรายสัปดาห์ลด Lab ที่ไม่จำเป็นได้ราว 1,800 ถึง 1,950 ชั่วโมงต่อเทอม และจัดครบแม้เหลือ Lab 3 ห้อง คือประหยัด Lab ได้หนึ่งห้องเต็ม',
                  'หนึ่ง บนโจทย์ที่เราตั้งและข้อมูล Lab จำลอง วิธีค้นหาจัดได้ครบทุกคาบ ใช้ Lab เกินจำเป็นน้อย และยังจัดครบเมื่อเหลือ Lab 3 ห้อง'),
                 ('สาม ราคาคือการย้ายห้อง ราว', 'สาม การย้ายห้องเกิดเท่าที่จำเป็น ราว'), ('สรุปสามข้อ', 'สรุปสี่ข้อ'),
                 (' งานต่อยอดคือ', ' สี่ แนวคิดนี้มีขอบเขต วิธีค้นหาจัดครบเมื่อวิชาใช้ Lab ไม่เกินราว 4 ถึง 6 สัปดาห์ '
                                   'และยิ่ง Lab ตึง การค้นหายิ่งจำเป็นกว่าการจัดตามกฎ งานต่อยอดคือ')],
    'limits': [('ข้อจำกัดมีสี่ข้อ', 'ข้อจำกัดมีห้าข้อ'),
               ('และยังไม่ได้วัดผลของการย้ายห้องต่อนักศึกษา', 'ยังไม่ได้วัดผลของการย้ายห้องต่อนักศึกษา '
                                                         'และขอบเขต 6 ถึง 8 สัปดาห์เป็นของงบ 500 กับการสุ่มเลือกวิชาครั้งเดียว')],
    'perweek': [('ทุกช่องสีน้ำเงินคือสัปดาห์ที่ต้องใช้ Lab จริง', 'ทุกช่องสีเหลืองคือสัปดาห์ที่ต้องใช้ Lab จริง'),
                ('ไม่มีช่องแดงเลย', 'ไม่มีช่องนั่งเปล่าเลย')],
}

# Slides only this version has: {id: (id of the main-deck slide it follows, speaker note)}.
# Numbers come from experiments/course-level-labs/README.md.
EXTRA = {
    'whyhard': ('problem', 'ทำไมโจทย์นี้ถึงยาก ดูตัวอย่างสมมตินี้ วิชา A กับ B มีนักศึกษาวิชาละ 50 คน จึงใช้ได้แค่ Lab ใหญ่ห้องเดียว '
                           'ทั้งสองวิชาเรียนวันจันทร์เก้าโมงเหมือนกัน และต้องใช้ Lab ในสัปดาห์ 2 กับ 5 เหมือนกัน A ได้ Lab ส่วน B ไม่มี Lab ทั้งสองสัปดาห์ '
                           'และแก้ไม่ได้แล้วเพราะเวลาเรียนย้ายกลางเทอมไม่ได้ ถ้าตอนต้นเทอมเราให้ B เรียนเวลาอื่น ทั้งคู่จะได้ Lab ครบ '
                           'ความยากจึงอยู่ที่การเลือกเวลาครั้งเดียวตอนต้นเทอม ให้ใช้ได้กับความต้องการห้องที่ต่างกันทั้ง 15 สัปดาห์ และต้องทำกับทุกคลาสพร้อมกัน'),
    'questions': ('approach', 'งานนี้ตอบสามคำถาม หนึ่ง จัดได้ครบไหมและเหลือ Lab ที่ใช้โดยไม่จำเป็นเท่าไร สอง วิธีค้นหาแบบไหนดีที่สุดเมื่อได้งบเท่ากัน '
                              'สาม ใช้ได้ถึงขอบเขตไหนเมื่อวิชาใช้ Lab มากขึ้น และมีสี่เรื่องที่งานนี้ไม่ได้ตอบ มหาวิทยาลัยมีสถานการณ์นี้มากแค่ไหน '
                              'ดีกว่าคนจัดตารางจริงหรือไม่ ดีกว่าการจอง Lab เมื่อจะใช้หรือไม่ และการย้ายห้องกระทบนักศึกษาแค่ไหน '
                              'ผลทั้งหมดจึงเป็นผลบนโจทย์ที่เราตั้งและข้อมูล Lab จำลอง'),
    'coursedata': ('data', 'ภาพนี้เทียบข้อมูลตั้งต้นสองชุด แต่ละแถวคือหนึ่งวิชา แต่ละช่องคือหนึ่งสัปดาห์ ภาพซ้ายคือชุดหลักที่สุ่มความต้องการ Lab ทีละคาบ '
                           'ช่องสีเหลืองคือวิชาที่ใช้ Lab แค่บางคาบ จะเห็นว่ากระจายเต็มตาราง 42 จาก 44 วิชาใช้ Lab '
                           'และความต้องการ Lab เกือบเท่ากันทุกสัปดาห์ Lab 4 ห้องจึงเหลือเฟือ ภาพขวาคือชุดที่สองที่กำหนด Lab เป็นรายวิชา '
                           'ช่องสีเข้มคือทุกคลาสของวิชาเข้า Lab สัปดาห์เดียวกัน เหลือ 30 จาก 44 วิชาที่ใช้ Lab และมีสัปดาห์ที่ Lab แน่นกับสัปดาห์ที่ Lab โล่ง '
                           'นอกจากนี้เราไม่ใช้ค่า 4 สัปดาห์ค่าเดียว แต่ทดลองตั้งแต่ 1 ถึง 15 สัปดาห์ อย่างอื่นเหมือนชุดหลักทุกอย่าง'),
    'labweeks': ('scarcity', 'นี่คือผลบนชุดที่สอง 640 รัน ผ่านตัวตรวจทุกรัน เมื่อวิชาใช้ Lab ไม่เกิน 4 สัปดาห์ วิธีค้นหาทั้งสามจัดครบทุกรัน '
                             'ที่ 6 สัปดาห์ยังจัดครบ 8 ถึง 9 จาก 10 รัน ที่ 8 สัปดาห์เหลือ 1 ถึง 2 รัน และตั้งแต่ 10 สัปดาห์ไม่มีรันไหนจัดครบ '
                             'ขอบเขตของแนวคิดนี้ที่งบ 500 จึงอยู่ราว 6 ถึง 8 สัปดาห์ สิ่งที่น่าสนใจคือช่องว่างกับ Greedy ที่ 12 สัปดาห์ '
                             'Greedy ขาด 197 คาบ ส่วนวิธีค้นหาขาดราว 40 คาบ ยิ่ง Lab ตึง การค้นหายิ่งจำเป็น '
                             'และที่ 15 สัปดาห์ ห้องรายสัปดาห์กับห้องคงที่ให้ผลเท่ากันทุกรัน ซึ่งยืนยันว่าระบบทำงานถูกต้อง'),
}

# Notes replaced whole because this version's slide says something the main deck's slide does not.
NOTE_OVERRIDE = {
    'problem': 'งานวิจัยของ Beyrouthy และคณะ ปี 2009 รายงานว่าห้องเรียนของมหาวิทยาลัยไม่ได้ขาดแคลนอย่างที่คนเข้าใจ แต่ถูกใช้ไม่เต็ม '
               'อัตราการใช้จริงต่ำได้ถึง 20 ถึง 40 เปอร์เซ็นต์ และข้อจำกัดของการจัดตารางเป็นสาเหตุหนึ่ง เราจึงเลือกศึกษากรณีหนึ่ง '
               'คือวิชาที่ต้องใช้ Lab แค่บางสัปดาห์ ดูตัวอย่างสมมตินี้ วิชาหนึ่งต้องใช้ Lab แค่สัปดาห์ 4 และ 8 ถ้าจองห้องเดียวทั้งเทอม '
               'สัปดาห์ที่เป็นบรรยายจะนั่งอยู่ใน Lab โดยไม่ได้ใช้ ช่องที่ขีดเส้นคือชั่วโมงแบบนี้ ซึ่งเราเรียกว่าชั่วโมง Lab ที่ไม่จำเป็น '
               'ทางออกที่เห็นได้ทันทีคือให้ห้องเปลี่ยนได้รายสัปดาห์ โจทย์ของเราจึงเป็นว่า ถ้าทำแบบนั้นจะจัดได้ครบไหม ต้องใช้วิธีไหน และใช้ได้ถึงขอบเขตไหน',
    'approach': 'โจทย์ของเราเขียนได้เป็นสามส่วน ส่วนแรกคือสิ่งที่รู้ก่อนเปิดเทอม คือคลาสทั้งหมด เวลาที่แต่ละคลาสเลือกได้ ห้องและความจุ '
                'และคลาสไหนต้องใช้ Lab สัปดาห์ไหน ส่วนที่สองคือสิ่งที่ต้องตัดสินใจ มีสองอย่าง เวลาเรียนของแต่ละคลาสหนึ่งชุดใช้ทั้ง 15 สัปดาห์ '
                'และห้องของแต่ละคาบซึ่งเลือกใหม่ได้ทุกสัปดาห์ ส่วนที่สามคือสิ่งที่ต้องได้ เรียงตามความสำคัญ ทุกคาบมีห้อง '
                'ไม่นั่ง Lab ในสัปดาห์ที่ไม่ต้องใช้ และย้ายห้องน้อยที่สุด สองการตัดสินใจนี้เกี่ยวกันเพราะเวลากำหนดว่าห้องจะพอไหม '
                'อัลกอริทึมของเราค้นหาลำดับคลาสกับเวลา ส่วนห้องนั้น decoder เป็นคนเลือก',
}


def main():
    source = json.loads((MAIN / 'slides.json').read_text(encoding='utf-8'))
    missing = [s['id'] for s in source if s['id'] not in SLIDES]
    if missing or len(source) + len(EXTRA) != len(SLIDES):
        raise SystemExit(f'Slide ids differ from the main deck: {missing}')
    source = [x for s in source for x in [s] + [{'id': k, 'note': note} for k, (after, note) in EXTRA.items() if after == s['id']]]
    if len(source) != len(SLIDES):
        raise SystemExit('An EXTRA slide follows an id the main deck does not have')
    slides = []
    for number, s in enumerate(source, 1):
        title, body = SLIDES[s['id']]
        note = NOTE_OVERRIDE.get(s['id'], s['note'])
        for old, new in NOTE_EDITS.get(s['id'], []):
            if old not in note:
                raise SystemExit(f'Note of {s["id"]} no longer contains: {old}')
            note = note.replace(old, new)
        cover = s['id'] == 'cover'
        html = (body if cover else h2(title) + body) + (
            '' if cover else f'<p style="position:absolute;right:140px;bottom:56px;width:120px;font-size:24px;'
                             f'color:#777777;text-align:right">{number}</p>')
        slides.append({'id': s['id'], 'title': title.replace('|', ': '), 'style': f'background:#FFFFFF;{PAD}', 'html': html, 'note': note})
    controller = (MAIN / 'deck.js').read_text(encoding='utf-8').split('\n', 1)[1]
    controller, swapped = re.subn(r'const ZOOMS = \[.*?\];', 'const ZOOMS = [];', controller, count=1)
    if swapped != 1:
        raise SystemExit('Could not find ZOOMS in ../deck.js')
    data = json.dumps(slides, ensure_ascii=False)
    (HERE / 'slides.json').write_text(json.dumps(slides, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (HERE / 'deck.js').write_text(f'const slides = {data};\n{controller}', encoding='utf-8')
    notes = ['# บทพูด (ชุดเรียบง่าย)', '']
    for number, s in enumerate(slides, 1):
        notes += [f'## {number}. {s["title"]}', '', s['note'], '']
    (HERE / 'speaker-notes.md').write_text('\n'.join(notes), encoding='utf-8')
    print(len(slides), 'slides ·', sum(len(s['note']) for s in slides), 'note characters')


if __name__ == '__main__':
    main()
