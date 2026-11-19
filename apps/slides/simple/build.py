"""Build the hand-drawn final deck. Standard library only.

    python apps/slides/simple/build.py

Writes slides.json, deck.js and speaker-notes.md next to this file. Everything
the deck says lives here: SLIDES holds the title and body of each slide, NOTES
holds the spoken script of each slide (shown in the deck's notes panel, key N)
and its key order is the slide order. deck.js is the slide list followed by
controller.js (the slide controller).

Rules this file keeps:
- No made-up examples. Every strip, chart and number is drawn from the real
  dataset (data/fall-cs.json.gz) or from committed runs (experiments/...), is
  labelled with the class, room and run it comes from, and is checked on every
  build: check() stops the build when the stored data stops matching a slide.
- One picture per slide; the script carries the explanation and points at
  what is drawn. No side-by-side text boxes.
- Text a viewer reads is at least 32px on the 1920x1080 canvas (only the slide
  number and the reference lists are smaller).
- Groups in a picture differ by solid fills far apart in lightness AND by a
  printed label, never by hue or hatching alone.
- A speech bubble exists only together with its mascot (duo()), with its tail
  ending at the mascot's head; on result slides the mascot stands in the data.

Look: white page, Mali handwriting, black ink doodles, one yellow accent, and a
monitor mascot.
"""
import gzip
import json
import math
import re
import sys
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
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


# Colour carries one meaning in the whole deck, and a printed label always says it again (the presenter is colour-blind):
#   BLUE = in a Lab in a week that needs it, the good value / RED = Lab ไม่จำเป็น, no room, the baseline (Greedy)
#   DGREY, LIGHT, white = ordinary lecture room, neutral. Solid dark fills with white text only: no tints, no hatching.
BLUE, RED, DGREY, LIGHT = '#1D4ED8', '#B91C1C', '#4B5563', '#E5E7EB'

# The monitor that is the mascot's head, inside its 300x330 box (left, top, right, bottom).
HEAD = (56, 44, 248, 224)
TAIL_GAP = 30  # a bubble's tail tip may be at most this far (px on the 1920x1080 canvas) from its mascot's head
Duo = namedtuple('Duo', 'html w h mx my mw mh')


def _bubble(text, left, top, width, size, flip=False):
    """Speech bubble outline with the words on top. Only duo() may call this, so no bubble exists without its mascot.
    The tail hangs under the left third (flip: the right third) and ends at y = top + height + 24."""
    lines = text.count('<br>') + 1
    height = int(lines * size * 1.25 + 44)
    return (f'<svg aria-label="กรอบคำพูด" width="{width}" height="{height + 30}" viewBox="0 0 {width} {height + 30}" '
            f'style="position:absolute;left:{left}px;top:{top}px;width:{width}px;height:{height + 30}px'
            f'{";transform:scaleX(-1)" if flip else ""}">'
            f'<path d="M26 6H{width - 26}C{width - 10} 6 {width - 6} 18 {width - 6} 28V{height - 28}C{width - 6} {height - 12} '
            f'{width - 16} {height - 6} {width - 28} {height - 6}H{width * 0.42:.0f}L{width * 0.3:.0f} {height + 24}'
            f'L{width * 0.3:.0f} {height - 6}H26C12 {height - 6} 6 {height - 14} 6 {height - 28}V28C6 14 12 6 26 6Z" '
            f'fill="#FFFFFF" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/></svg>'
            f'<p style="position:absolute;left:{left}px;top:{top + 20}px;width:{width}px;{SRIRACHA};font-size:{size}px;'
            f'line-height:1.25;color:{INK};text-align:center">{text}</p>')


def duo(say='', mood='happy', wave=False, hat=False, scale=1.0, size=34, width=None, mirror=False, stars=False, lean_left=False):
    """The mascot and its speech bubble as ONE group, so they cannot drift apart: the bubble sits above the head
    and its tail tip ends just above the monitor. Stops the build if the tip is further than TAIL_GAP from the head.
    Returns the group's html and size plus where the mascot sits inside it (mx, my, mw, mh), for place().
    mirror=True flips the mascot (raised arm on its left); lean_left=True hangs the bubble to the left of the head
    instead of the right."""
    mw, mh = round(300 * scale), round(330 * scale)
    pad = 56 if stars else 0
    if say:
        lines = say.split('<br>')
        width = width or max(230, round(max(len(re.sub(r'<[^>]+>', '', x)) for x in lines) * size * 0.56) + 64)
        bh = int(len(lines) * size * 1.25 + 44)
        tail = width * (0.7 if lean_left else 0.3)
        head_top = (8 if hat else HEAD[1]) * scale
        mx = pad + max(0, round(tail - 150 * scale))
        bx = round(mx + 150 * scale - tail)
        my = round(bh + 24 + 8 - head_top)
        tip = (bx + tail, bh + 24)
        box = (mx + HEAD[0] * scale, my + head_top, mx + HEAD[2] * scale, my + HEAD[3] * scale)
        gap = math.hypot(max(box[0] - tip[0], 0, tip[0] - box[2]), max(box[1] - tip[1], 0, tip[1] - box[3]))
        if gap > TAIL_GAP:
            raise SystemExit(f'bubble "{say}" floats {gap:.0f}px away from its mascot')
        talk = _bubble(say, bx, 0, width, size, flip=lean_left)
    else:
        mx, my, bx, width, talk = pad, 0, 0, 0, ''
    w, h = max(mx + mw + (round(16 * scale) if wave else 0), bx + width) + (40 if stars else 0), my + mh
    art = (f'<svg aria-label="น้องจอคอมพิวเตอร์ ตัวการ์ตูนประจำสไลด์" viewBox="0 0 300 330" width="{mw}" height="{mh}" '
           f'style="position:absolute;left:{mx}px;top:{my}px;width:{mw}px;height:{mh}px;overflow:visible'
           f'{";transform:scaleX(-1)" if mirror else ""}">{mascot(mood, wave, hat)}</svg>')
    if stars:
        art += (f'<svg aria-hidden="true" width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="position:absolute;left:0;top:0;'
                f'width:{w}px;height:{h}px">{sparkle(0, my + mh * 0.55, 0.9)}{sparkle(mx + mw - 6, my + mh * 0.22, 0.6)}</svg>')
    return Duo(art + talk, w, h, mx, my, mw, mh)


def place(d, left, top):
    """Put a duo() inside a position:relative parent so that the MASCOT's top-left corner is at (left, top)."""
    return (f'<div style="position:absolute;left:{round(left - d.mx)}px;top:{round(top - d.my)}px;width:{d.w}px;'
            f'height:{d.h}px">{d.html}</div>')


def buddy(say, mood='happy', wave=False, hat=False, scale=1.0, stars=True, size=40):
    """Right-hand column: the mascot with its speech bubble, as a normal flow element."""
    d = duo(say, mood, wave, hat, scale * 1.3, round(size * 0.9), stars=stars)
    return f'<div style="position:relative;width:{d.w}px;height:{d.h}px;flex:none">{d.html}</div>'


def pointer(say='', mood='happy', scale=0.4, edge=False):
    """The mascot standing just right of a table, level with the row whose LAST cell this is appended to
    (edge=True: on the line above that row), arm raised towards the row. Needs free space right of the table."""
    d = duo(say, mood, wave=True, scale=scale, size=32, mirror=True)
    return (f'<div style="position:absolute;left:100%;top:{"0" if edge else "50%"};width:{d.mw}px;height:{d.mh}px;'
            f'margin-left:22px;transform:translateY(-50%)">{place(d, 0, 0)}</div>')


def aside(html, room=330):
    """Keep `room` px free on the right of a table for a pointer()."""
    return f'<div style="padding-right:{room}px">{html}</div>'


# Bar fills (fill, colour of the value on it). Every bar also carries its name and its value as text.
BAR_FILL = {'blue': (BLUE, '#FFFFFF'), 'red': (RED, '#FFFFFF'), 'grey': (DGREY, '#FFFFFF')}


def bars(items, width=640, height=420, unit='', top=60, rider=None):
    """Bar chart. items: (label, value, text, kind) with kind in BAR_FILL. Every bar carries its value (inside, at
    the top) and its name (below). unit: caption lines separated by <br>.
    rider = (bar index, duo): the mascot stands on that bar; raise `top` to give it headroom."""
    height = round(height * 1.25)
    lines = unit.count('<br>') + 1 if unit else 0
    base, left = height - 70 - 46 * lines, 30
    peak = max(v for _, v, _, _ in items)
    step = (width - left - 20) / len(items)
    bw = min(130, step * 0.8)
    out, labels, tops = [], [], []
    for i, (label, value, text, kind) in enumerate(items):
        x = left + step * i + (step - bw) / 2
        y = base - (base - top) * value / peak
        fill, ink = BAR_FILL[kind]
        tops.append((x + bw / 2, y))
        out.append(f'<path class="grow-y" d="M{x:.0f} {base}V{y:.0f}H{x + bw:.0f}V{base}" fill="{fill}"/>')
        labels.append(f'<p style="position:absolute;left:{x:.0f}px;top:{y + 10:.0f}px;width:{bw:.0f}px;font-size:32px;'
                      f'font-weight:700;line-height:1.2;text-align:center;color:{ink}">{text}</p>'
                      f'<p style="position:absolute;left:{x - 30:.0f}px;top:{base + 8}px;width:{bw + 60:.0f}px;font-size:32px;'
                      f'line-height:1.2;text-align:center">{label}</p>')
    extra = ''
    if rider:
        i, d = rider
        cx, y = tops[i]
        extra = place(d, cx - d.mw / 2, y - d.mh * 292 / 330)
    alt = ', '.join(f'{label} {text}' for label, _, text, _ in items)
    return (f'<div style="position:relative;width:{width}px;height:{height}px;flex:none">'
            f'<svg aria-label="กราฟแท่ง {alt}" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'style="width:{width}px;height:{height}px"><g stroke="{INK}" stroke-width="4" stroke-linecap="round" '
            f'stroke-linejoin="round">{"".join(out)}<path d="M{left - 14} {base}H{width - 6}" fill="none"/></g></svg>'
            f'{"".join(labels)}{extra}'
            + (f'<p style="position:absolute;left:0;top:{base + 60}px;width:{width}px;font-size:32px;line-height:1.4;'
               f'color:{GREY};text-align:center">{unit}</p>' if unit else '') + '</div>')


# Week-strip cells: (fill, text colour, border). The text of a cell says the same thing as its colour: a plain Lab
# code (blue: Lab needed), a code in (brackets) (red: Lab not needed), a lecture room code (white), 'ไม่มี' (red
# dashed outline: no room) or 'ว่าง' (dark dashed outline: the room is free).
CELL = {'lab': (BLUE, '#FFFFFF', f'solid {INK}'), 'waste': (RED, '#FFFFFF', f'solid {INK}'),
        'room': ('#FFFFFF', INK, f'solid {INK}'), 'none': ('#FFFFFF', RED, f'dashed {RED}'),
        'empty': ('#FFFFFF', INK, f'dashed {INK}'), 'full': (DGREY, '#FFFFFF', f'solid {INK}')}


def legend(*keys):
    """A key, not a sentence: sample cells with one or two words each. keys = (kind in CELL, sample text, label)."""
    out = ''
    for kind, sample, label in keys:
        fill, ink, border = CELL[kind]
        out += (f'<div style="flex-direction:row;gap:10px;align-items:center;flex:none"><div style="width:86px;height:48px;'
                f'border:4px {border};border-radius:12px;background:{fill};align-items:center;justify-content:center">'
                f'<p style="font-size:32px;font-weight:700;line-height:1;color:{ink}">{sample}</p></div>'
                f'<p style="font-size:32px;line-height:1.2">{label}</p></div>')
    return out


def strip(rows, caption='', keys=(), tall=84):
    """15-week strip: rows = (name, cells); a cell is (text, kind) with kind in CELL. Cell i starts at 238 + 94 * i px.
    Under it: one short caption saying what the picture is, and the key as sample cells (see legend())."""
    n = len(WEEKS)
    head = ''.join(f'<p style="width:86px;font-size:32px;line-height:1.2;color:{GREY};text-align:center">{i + 1}</p>'
                   for i in range(n))
    body = [f'<div style="flex-direction:row;gap:8px;align-items:center"><p style="width:230px;font-size:32px;line-height:1.2;'
            f'color:{GREY}">สัปดาห์</p>{head}</div>']
    for title, cells in rows:
        if cells is None:   # a heading between rows: 'number|words'
            number, _, words = title.partition('|')
            body.append(f'<p style="font-size:36px;font-weight:700;line-height:1.2;margin-top:6px">'
                        f'<span style="font-size:50px;{SRIRACHA}">{number}</span>&nbsp; {words}</p>')
            continue
        boxes = ''
        for text, kind in cells:
            fill, ink, border = CELL[kind]
            boxes += (f'<div class="cell" style="width:86px;height:{tall}px;border:4px {border};border-radius:14px;'
                      f'background:{fill};align-items:center;justify-content:center"><p style="font-size:32px;font-weight:700;'
                      f'line-height:1.1;text-align:center;color:{ink}">{text}</p></div>')
        body.append(f'<div style="flex-direction:row;gap:8px;align-items:center"><p style="width:230px;font-size:32px;'
                    f'font-weight:700;line-height:1.15">{title}</p>{boxes}</div>')
    if caption or keys:
        body.append(f'<div style="flex-direction:row;gap:36px;align-items:center;margin-top:4px">'
                    f'<p style="flex:none;font-size:32px;color:{GREY};line-height:1.3">{caption}</p>{legend(*keys)}</div>')
    return f'<div style="gap:{14 if tall > 60 else 8}px">{"".join(body)}</div>'


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
    th = ''.join((f'<th style="width:{w}">' if w else '<th>') + f'{c}</th>' for c, w in zip(head, widths))
    tr = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows)
    return f'<table style="font-size:{size}px;color:{INK};width:100%"><tr>{th}</tr>{tr}</table>'


def big(number, label):
    return (f'<div style="flex:1;gap:6px"><p style="font-size:96px;font-weight:700;line-height:1.1">{number}</p>'
            f'<p style="font-size:32px;line-height:1.4;color:{GREY}">{label}</p></div>')


def small(text):
    return f'<p style="font-size:32px;line-height:1.4;color:{GREY}">{text}</p>'


def line(text, size=32):
    return f'<p style="font-size:{size}px;line-height:1.4">{text}</p>'


def box(title, text, hot=False):
    return (f'<div style="flex:1;border:5px solid {INK};border-radius:28px;padding:22px 30px;gap:8px;'
            f'background:{YELLOW if hot else "#FFFFFF"}"><h3 style="font-size:40px;font-weight:700;line-height:1.25">{title}</h3>'
            f'<p style="font-size:32px;line-height:1.4">{text}</p></div>')


ARROW = f'<p style="font-size:72px;font-weight:700;line-height:1;align-self:center;{SRIRACHA}">→</p>'


def ref(who, what, why=''):
    return (f'<div style="flex-direction:row;gap:28px;align-items:baseline"><p style="width:400px;flex:none;font-size:26px;'
            f'font-weight:700;line-height:1.4">{who}</p><div style="flex:1;gap:2px"><p style="font-size:24px;line-height:1.4">{what}</p>'
            + (f'<p style="font-size:24px;line-height:1.4;color:{GREY}">→ {why}</p>' if why else '') + '</div></div>')


def tag(text, made_up=False):
    """Word label that says where a number comes from: the word itself says which; filled marks our assumption."""
    look = f'background:{INK};color:#FFFFFF' if made_up else f'background:#FFFFFF;color:{INK}'
    return (f'<p style="flex:none;font-size:32px;font-weight:700;line-height:1.3;border:4px solid {INK};border-radius:12px;'
            f'padding:0 14px;{look}">{text}</p>')


def count(number, label, size=84):
    return (f'<div style="gap:0"><p style="font-size:{size}px;font-weight:700;line-height:1.1">{number}</p>'
            f'<p style="font-size:32px;line-height:1.3">{label}</p></div>')


def numbered(n, html, size=72, text=36):
    return (f'<div style="flex-direction:row;gap:20px;align-items:center"><p style="flex:none;font-size:{size}px;font-weight:700;'
            f'line-height:1;{SRIRACHA}">{n}</p><p style="font-size:{text}px;line-height:1.3">{html}</p></div>')


# --- the real data and the real runs every picture is drawn from -----------------------
def load(path):
    return json.loads(gzip.decompress((ROOT / path).read_bytes()))


def check(what, got, want):
    """Stop the build when the stored data no longer says what a slide or its script says."""
    if got != want:
        raise SystemExit(f'{what}: the data gives {got!r}, the slide says {want!r}')


def text_of(path):
    return (ROOT / path).read_text(encoding='utf-8')


FINAL = load('experiments/final/experiment.json.gz')   # 4 methods x 2 room modes x seeds 1001-1030, budget 500
DATA = json.loads(FINAL['dataset_text'])
check('experiments/final was run on data/fall-cs.json.gz', DATA == load('data/fall-cs.json.gz'), True)
RUNS = {(r['algorithm'], r['room_mode'], r['seed']): r for r in FINAL['batch']['results']}
CLASSES = {c['id']: c for c in DATA['classes']}
SESSIONS = {x['id']: x for x in DATA['recurring_sessions']}
ROOMS = {r['id']: r for r in DATA['rooms']}
WEEKS = sorted(DATA['calendar']['week_ids'])
DAYS = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์']
SEEDS = range(1001, 1031)
REPORT = text_of('experiments/final/analysis/report.md')
_schedules = {}


def schedule(algorithm, mode, seed=1001):
    """(meeting of each placed session, room of each (session, week)) in one stored run."""
    key = (algorithm, mode, seed)
    if key not in _schedules:
        run = RUNS[key]
        meet = {}
        for cid, oid in run['solution']['class_time_options'].items():
            for option in CLASSES[cid]['time_options']:
                if option['id'] == oid:
                    for m in option['meetings']:
                        meet[m['session_id']] = m
        room = {(a['session_id'], a['week']): a['room_id'] for a in run['solution']['weekly_room_assignments']}
        _schedules[key] = meet, room
    return _schedules[key]


def is_lab(room):
    return ROOMS[room]['kind'] == 'computer_lab'


def code(room):
    """Short room name for a cell: L4 for SIM-LAB-04, the source id (R95) for a lecture room."""
    return 'L' + room[-1] if is_lab(room) else room


def when(m):
    return f'{DAYS[m["day"]]} {m["start_minute"] // 60}:{m["start_minute"] % 60:02d}'


def overlap(a, b):
    return (a['day'] == b['day'] and a['start_minute'] < b['start_minute'] + b['duration_minutes']
            and b['start_minute'] < a['start_minute'] + a['duration_minutes'])


def week_cells(session, algorithm, mode, seed=1001):
    """One session in one stored run, week by week: its room code; (brackets) and a grey cell when it sits in a Lab
    in a week it does not need one; 'ไม่มี' when it has no room that week."""
    _, room = schedule(algorithm, mode, seed)
    cells = []
    for w in WEEKS:
        r = room.get((session, w))
        if r is None:
            cells.append(('ไม่มี', 'none'))
        elif is_lab(r):
            cells.append((code(r), 'lab') if w in SESSIONS[session]['lab_weeks'] else (f'({code(r)})', 'waste'))
        else:
            cells.append((code(r), 'room'))
    return cells


def kinds(cells):
    return tuple(sum(1 for _, k in cells if k in kind) for kind in (('lab',), ('waste',), ('room',), ('empty', 'none')))


def holder_cells(room_id, like, algorithm, mode, names, seed=1001):
    """Who holds one room at the time of meeting `like`, week by week, in one stored run. `names` maps session id to
    a letter and grows as new sessions appear. A letter in (brackets) = that session does not need a Lab that week."""
    meet, room = schedule(algorithm, mode, seed)
    cells = []
    for w in WEEKS:
        who = [x for (x, week), r in room.items() if week == w and r == room_id and overlap(meet[x], like)]
        if len(who) > 1:
            raise SystemExit(f'{room_id} week {w}: more than one session at {when(like)}')
        if not who:
            cells.append(('ว่าง', 'empty'))
            continue
        letter = names.setdefault(who[0], 'ABCDEFGH'[len(names)])
        cells.append((letter, 'lab') if w in SESSIONS[who[0]]['lab_weeks'] else (f'({letter})', 'waste'))
    return cells


# -- slide 2 and 9: one real section in the run with fixed rooms and in the weekly run of the same method and seed
ONE = 'C1422-M1'
ONE_FIXED, ONE_WEEKLY = week_cells(ONE, 'ga', 'fixed'), week_cells(ONE, 'ga', 'weekly')
check(f'{ONE} lab weeks, minutes', (SESSIONS[ONE]['lab_weeks'], SESSIONS[ONE]['duration_minutes']), ([1, 4, 13, 15], 120))
check(f'{ONE} in GA seed 1001 fixed: (Lab needed, Lab not needed, lecture room, no room) weeks', kinds(ONE_FIXED), (4, 11, 0, 0))
check(f'{ONE} in GA seed 1001 weekly', kinds(ONE_WEEKLY), (4, 0, 11, 0))
check(f'{ONE} rooms', ({t for t, _ in ONE_FIXED}, {t for t, _ in ONE_WEEKLY}), ({'L4', '(L4)'}, {'L4', 'R95'}))
check(f'{ONE} unnecessary Lab hours, fixed run', kinds(ONE_FIXED)[1] * SESSIONS[ONE]['duration_minutes'] // 60, 22)

# -- slide 3: one real section that Greedy leaves without a room in four weeks, and who holds the Labs it may use
STUCK = 'C1566-M3'


def busy(room_id, week, like, algorithm, mode, skip=None):
    """Is a room held at the time of meeting `like` in that week, by another session of the run or by a class of
    another department (those are fixed in the data)?"""
    meet, room = schedule(algorithm, mode)
    if any(x != skip and w == week and r == room_id and overlap(meet[x], like) for (x, w), r in room.items()):
        return True
    return any(room_id in e['room_ids'] and week in e['active_weeks'] and any(overlap(m, like) for m in e['meetings'])
               for e in DATA['external_classes'])


def stuck_rows():
    """Slide 3 as three steps of one real case: 1 the lecture rooms the class may use are full in every week,
    2 so it sits in a Lab it never needs, 3 and in the weeks both Labs it fits in are held by others it has no room."""
    meet, room = schedule('greedy', 'weekly')
    m, c = meet[STUCK], CLASSES[SESSIONS[STUCK]['class_id']]
    cells = week_cells(STUCK, 'greedy', 'weekly')
    check(f'{STUCK}: time, seats, lab weeks, Labs it may use, lecture rooms it may use',
          (when(m), c['student_count'], SESSIONS[STUCK]['lab_weeks'], c['lab_room_ids'], c['lecture_room_ids']),
          ('ศุกร์ 8:30', 36, [], ['SIM-LAB-01', 'SIM-LAB-02'], ['R57', 'R63', 'R64']))
    check(f'{STUCK} in Greedy weekly', (kinds(cells), [w for w in WEEKS if (STUCK, w) not in room]), ((0, 11, 0, 4), [3, 8, 9, 12]))
    check('seats of the two Labs', (ROOMS['SIM-LAB-02']['capacity'], ROOMS['SIM-LAB-01']['capacity']), (36, 61))
    held = [sum(busy(r, w, m, 'greedy', 'weekly', skip=STUCK) for r in c['lecture_room_ids']) for w in WEEKS]
    check(f'lecture rooms {c["lecture_room_ids"]} held by others at {when(m)}, per week', held, [3] * 15)
    names = {STUCK: 'A'}
    labs = [holder_cells(r, m, 'greedy', 'weekly', names) for r in ('SIM-LAB-02', 'SIM-LAB-01')]
    check('who holds the two Labs', names, {'C1566-M3': 'A', 'C1524-M1': 'B', 'C1458-M1': 'C', 'C1444-M1': 'D'})
    for w in (3, 8, 9, 12):               # in its four roomless weeks both Labs are held by another section
        check(f'week {w}: both Labs held by others', all(x[w - 1][0].strip('()') in 'BCD' for x in labs), True)

    def plain(lab_cells):
        """No letters to decode: นี้ = this section, อื่น = another section; (brackets) = it does not need the Lab that week."""
        out = []
        for text, kind in lab_cells:
            word = text if kind == 'empty' else 'นี้' if text.strip('()') == 'A' else 'อื่น'
            out.append((f'({word})' if kind == 'waste' else word, kind))
        return out

    return [('1|ห้องบรรยายที่ใช้ได้ เต็มทุกสัปดาห์', None), ('บรรยาย 3 ห้อง', [('เต็ม', 'full')] * 15),
            ('2|จึงต้องไปอยู่ห้อง Lab', None), ('กลุ่ม C1566', cells),
            ('3|สัปดาห์ที่ห้อง Lab มีกลุ่มอื่นใช้ ก็ไม่มีที่ไป', None),
            ('L2: 36 ที่นั่ง', plain(labs[0])), ('L1: 61 ที่นั่ง', plain(labs[1]))]


# -- slide 4: one real section in the weekly run: one time for the term, a room chosen again every week
MOVER = 'C1419-M1'
MOVER_CELLS = week_cells(MOVER, 'ga', 'weekly')
check(f'{MOVER} in GA seed 1001 weekly', (when(schedule('ga', 'weekly')[0][MOVER]), kinds(MOVER_CELLS), [t for t, _ in MOVER_CELLS]),
      ('พฤหัสบดี 11:30', (4, 0, 11, 0), ['L4', 'R96', 'R96', 'L2'] + ['R96'] * 8 + ['L3', 'R96', 'L4']))

# -- slide perweek: one Lab at one day and time in the fixed run and in the weekly run of GA seed 1001
SLOT = ('SIM-LAB-04', {'day': 3, 'start_minute': 690, 'duration_minutes': 120})


def slot_rows():
    names = {}
    weekly = holder_cells(SLOT[0], SLOT[1], 'ga', 'weekly', names)
    check('weekly holders of the slot', names, {'C1419-M1': 'A', 'C1568-M1': 'B', 'C1540-M1': 'C', 'C1487-M1': 'D', 'C1523-M1': 'E'})
    courses = {CLASSES[SESSIONS[x]['class_id']]['course_id'] for x in names}
    fixed = holder_cells(SLOT[0], SLOT[1], 'ga', 'fixed', names)
    check('fixed holder of the slot', names.get('C1522-M1'), 'F')
    check('slot: (Lab needed, not needed, -, free) weekly / fixed, courses sharing, free week',
          (kinds(weekly), kinds(fixed), len(courses), [w for w, c in zip(WEEKS, weekly) if c[1] == 'empty']),
          ((14, 0, 0, 1), (4, 11, 0, 0), 5, [5]))
    return fixed, weekly


# -- slide greedy: the weekly sessions Greedy leaves without a room
def greedy_rows():
    run = RUNS[('greedy', 'weekly', 1001)]
    _, room = schedule('greedy', 'weekly')
    missing = sorted({x for x in SESSIONS for w in SESSIONS[x]['active_weeks'] if (x, w) not in room})
    rows = [(x, week_cells(x, 'greedy', 'weekly')) for x in missing]
    check('Greedy weekly: sessions without a room, their Lab weeks, classes, slots without a room, metrics',
          (missing, {tuple(SESSIONS[x]['lab_weeks']) for x in missing}, len({SESSIONS[x]['class_id'] for x in missing}),
           sum(kinds(c)[3] for _, c in rows), run['metrics']['unassigned_weekly_sessions'], run['metrics']['unnecessary_lab_hours']),
          (['C1566-M2', 'C1566-M3', 'C1581-M2', 'C1581-M3', 'C1582-M2', 'C1582-M3', 'C1588-M2'], {()}, 4, 14, 14, 242))
    meet = schedule('greedy', 'weekly')[0]
    for x in missing:
        for w in SESSIONS[x]['active_weeks']:
            if (x, w) not in room:
                free = [r for r in CLASSES[SESSIONS[x]['class_id']]['lecture_room_ids'] if not busy(r, w, meet[x], 'greedy', 'weekly', skip=x)]
                check(f'{x} week {w}: lecture rooms it may use that are free', free, [])
    check('Greedy gives the same schedule for every seed',
          len({json.dumps(RUNS[('greedy', 'weekly', s)]['solution'], sort_keys=True) for s in SEEDS}), 1)
    return rows


# -- slides hc, sa, ga: best-so-far unnecessary Lab hours and complete runs against evaluations, from the stored traces
MARKS = (1, 50, 100, 200, 300, 500)
TICKS = (1, 100, 200, 300, 400, 500)


def progress(algorithm):
    """(mean unnecessary Lab hours of the best timetable so far, runs with every slot placed) at evaluation 1..500."""
    hours, done = [0.0] * 501, [0] * 501
    for seed in SEEDS:
        trace = RUNS[(algorithm, 'weekly', seed)]['trace']
        check(f'{algorithm} {seed}: trace starts at the Greedy timetable', (trace[0]['evaluations'], trace[0]['objectives'][:2]), (1, [14, 14520]))
        i = 0
        for e in range(1, 501):
            while i + 1 < len(trace) and trace[i + 1]['evaluations'] <= e:
                i += 1
            unassigned, minutes, _ = trace[i]['objectives']
            hours[e] += minutes / 60 / len(SEEDS)
            done[e] += unassigned == 0
    return hours, done


def report_row(name):
    """(complete %, mean unnecessary Lab hours, mean room changes) of one method, weekly mode, from the generated report."""
    row = re.search(rf'\| weekly \| {name} \| 30/30 \| (\d+)% \| \S+ ± [^|]*\| ([\d.]+) ± [^|]*\| ([\d.]+) ± ', REPORT)
    return int(row[1]), float(row[2]), float(row[3])


CURVES = {}
for _alg, _name, _marks, _ticks, _end in [
        ('hc', 'Hill Climbing', [242.0, 231.7, 220.5, 205.5, 190.8, 169.4], [0, 2, 12, 20, 22, 26], (87, 169.4, 624.4)),
        ('sa', 'Simulated Annealing', [242.0, 244.3, 242.1, 219.6, 195.1, 145.8], [0, 9, 20, 27, 29, 29], (97, 145.8, 619.7)),
        ('ga', 'Genetic Algorithm', [242.0, 246.8, 221.8, 191.5, 174.7, 146.9], [0, 17, 23, 28, 28, 28], (93, 146.9, 617.8))]:
    _hours, _done = progress(_alg)
    check(f'{_alg}: mean best-so-far Lab hours at evaluations {MARKS}', [round(_hours[e], 1) for e in MARKS], _marks)
    check(f'{_alg}: complete runs at evaluations {TICKS}', [_done[e] for e in TICKS], _ticks)
    check(f'{_alg}: report.md row', report_row(_name), _end)
    check(f'{_alg}: trace end equals the report', (round(_done[500] / 30 * 100), round(_hours[500], 1)), _end[:2])
    CURVES[_alg] = _hours, _done
check('Greedy: report.md row', report_row('Greedy'), (0, 242.0, 654.0))
for _snippet in ['χ² = 56.44', 'Greedy 4.00, Hill Climbing 2.30, Simulated Annealing 1.83, Genetic Algorithm 1.87',
                 '| Hill Climbing vs Simulated Annealing | 11 / 0 / 19 |', '| 0.102 |', '| 0.666 |',
                 'Lower bound ของข้อมูล = 596 ครั้ง', '| Greedy vs Genetic Algorithm | 0 / 0 / 30 |']:
    check(f'report.md contains {_snippet}', _snippet in REPORT, True)
_convergence = text_of('experiments/convergence/summary.csv')
for _row in ['hc,500,161.1,', 'sa,500,135.8,', 'ga,500,146.3,', 'hc,2000,72.0,', 'sa,2000,60.8,', 'ga,2000,77.7,',
             'hc,10000,41.3,', 'sa,10000,0.0,', 'ga,10000,48.6,', 'hc,50000,19.4,600.3,10', 'sa,50000,0.0,596.0,10',
             'ga,50000,40.9,596.9,10', 'hc,1000,109.4,611.1,10', 'sa,1000,89.4,609.6,10', 'ga,1000,112.8,608.8,10']:
    check(f'convergence/summary.csv contains {_row}', _row in _convergence, True)


def curve(algorithm, say, mood='happy'):
    """Line chart of one method: same axes for all three, so the slides can be compared by eye."""
    hours, done = CURVES[algorithm]
    W, H, L, T, pw, ph, top = 1080, 636, 215, 104, 770, 360, 260
    x = lambda e: L + (e - 1) / 499 * pw
    y = lambda v: T + ph * (1 - v / top)
    path = 'M' + 'L'.join(f'{x(e):.1f} {y(hours[e]):.1f}' for e in range(1, 501))
    grid = ''.join(f'<path d="M{L} {y(v):.0f}H{L + pw}" stroke="#CFCFCF" stroke-width="2" fill="none"/>' for v in (100, 200))
    labels = ''.join(f'<p style="position:absolute;left:0;top:{y(v) - 22:.0f}px;width:{L - 16}px;font-size:32px;line-height:1.3;'
                     f'text-align:right;color:{GREY}">{v} ชม.</p>' for v in (0, 100))
    for row, (name, values) in enumerate([('ครั้งที่ลอง', TICKS), ('รันที่จัดครบ', [done[e] for e in TICKS])]):
        ytop = T + ph + 26 + row * 48
        labels += (f'<p style="position:absolute;left:0;top:{ytop}px;width:{L - 16}px;font-size:32px;line-height:1.3;text-align:right;'
                   f'color:{GREY if row == 0 else INK};font-weight:{400 if row == 0 else 700}">{name}</p>')
        labels += ''.join(f'<p style="position:absolute;left:{x(e) - 50:.0f}px;top:{ytop}px;width:100px;font-size:32px;line-height:1.3;'
                          f'text-align:center;color:{GREY if row == 0 else INK};font-weight:{400 if row == 0 else 700}">{v:,}</p>'
                          for e, v in zip(TICKS, values))
    labels += (f'<p style="position:absolute;left:0;top:{y(hours[1]) - 22:.0f}px;width:{L - 16}px;font-size:32px;font-weight:700;'
               f'line-height:1.3;text-align:right">{hours[1]:.0f} ชม.</p>'
               f'<p style="position:absolute;left:{x(500) - 130:.0f}px;top:{y(hours[500]) + 10:.0f}px;width:120px;font-size:32px;'
               f'font-weight:700;line-height:1.2;text-align:right">{hours[500]:.1f}</p>'
               f'<p style="position:absolute;left:0;top:{T + ph + 126}px;width:{W}px;font-size:32px;line-height:1.3;color:{GREY};'
               f'text-align:center">Lab ไม่จำเป็นเฉลี่ย 30 seed (ชม.)</p>')
    d = duo(say, mood, wave=False, scale=0.42, size=32, lean_left=True)
    return (f'<div style="position:relative;width:{W}px;height:{H}px;flex:none">'
            f'<svg aria-label="กราฟเส้น Lab ไม่จำเป็นเฉลี่ยเทียบกับจำนวนครั้งที่ลอง" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'style="width:{W}px;height:{H}px">{grid}<g fill="none" stroke="{INK}" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M{L} {T - 10}V{T + ph}H{L + pw + 10}" stroke-width="4"/><path d="{path}" stroke="{BLUE}" stroke-width="8"/></g>'
            f'<circle cx="{x(1):.0f}" cy="{y(hours[1]):.0f}" r="10" fill="{INK}"/>'
            f'<circle cx="{x(500):.0f}" cy="{y(hours[500]):.0f}" r="12" fill="{BLUE}"/></svg>'
            f'{labels}{place(d, x(500) - d.mw / 2, y(hours[500]) - d.mh * 292 / 330 - 12)}</div>')


def method_slide(algorithm, how, say, mood, complete):
    hours, done = CURVES[algorithm]
    check(f'{algorithm} complete runs', done[500], complete)
    return two(curve(algorithm, say, mood),
               '<div style="width:500px;flex:none;gap:22px">'
               + count(f'{hours[500]:.1f}', 'ชม. Lab ไม่จำเป็น เมื่อลองครบ 500 ครั้ง', 96)
               + count(f'{complete}/30', 'รันที่ทุกช่องมีห้อง', 96)
               + line(f'<b>วิธีค้นหา:</b> {how}', 34) + '</div>', 40)


# -- slide source: where the unnecessary Lab hours of the weekly runs come from (experiments/lab-hours-breakdown)
def source_picture():
    summary = json.loads(text_of('experiments/lab-hours-breakdown/summary.json'))
    want = {'greedy': (226.0, 16.0), 'hc': (163.9, 5.5), 'sa': (140.6, 5.2), 'ga': (135.7, 11.2)}
    rows = ''
    for key, name in [('greedy', 'Greedy'), ('hc', 'HC'), ('sa', 'SA'), ('ga', 'GA')]:
        s = summary[key]
        check(f'breakdown {key}: (lecture-only hours, hours of sessions of Lab courses)',
              (round(s['type_lecture_only_hours'], 1), round(s['type_mixed_hours'], 1)), want[key])
        check(f'breakdown {key}: every hour happens when no lecture room it may use is free',
              (round(s['cause_no_free_lecture_room_hours'], 6), round(s['cause_no_eligible_lecture_room_hours'] + s['cause_free_lecture_room_existed_hours'], 6)),
              (round(s['unnecessary_lab_hours'], 6), 0))
        a, b = want[key]
        rows += (f'<div style="flex-direction:row;gap:16px;align-items:center"><p style="width:120px;flex:none;font-size:34px;font-weight:700">{name}</p>'
                 f'<div style="flex-direction:row;height:52px;flex:none"><span style="width:{a * 3.6:.0f}px;border:4px solid {INK};background:{RED}"></span>'
                 f'<span style="width:{max(b * 3.6, 8):.0f}px;border:4px solid {INK};border-left:0;background:{DGREY}"></span></div>'
                 f'<p style="font-size:32px;line-height:1.2">คาบบรรยาย <b>{a:g}</b> + คาบวิชา Lab <b>{b:g}</b> ชม.</p></div>')
    lecture_only = sum(1 for x in DATA['recurring_sessions'] if not x['lab_weeks'])
    lecture_rooms = sum(1 for r in DATA['rooms'] if r['kind'] == 'lecture' and r['schedulable'])
    check('sessions that never need a Lab, lecture rooms', (lecture_only, lecture_rooms), (117, 13))
    return ('<div style="flex-direction:row;gap:40px;align-items:center">'
            + count(f'<span style="color:{RED}">100%</span>', 'ของ Lab ไม่จำเป็น เกิดตอนที่ห้องบรรยายที่ใช้ได้เต็ม', 110)
            + '</div><div style="gap:14px">' + rows
            + '<div style="flex-direction:row;gap:36px;align-items:center">'
            + small('ชม. Lab ไม่จำเป็นเฉลี่ย 30 seed')
            + ''.join(f'<div style="flex-direction:row;gap:10px;align-items:center"><span style="flex:none;width:56px;height:32px;'
                      f'border:4px solid {INK};background:{c}"></span><p style="font-size:32px;line-height:1.2">{t}</p></div>'
                      for c, t in [(RED, 'คาบบรรยาย'), (DGREY, 'คาบวิชา Lab')]) + '</div>'
            + '</div>'
            + line('<b>การตีความ (ยังไม่ได้ทดสอบ):</b> คอขวดคือห้องบรรยาย ไม่ใช่ห้อง Lab: มี 13 ห้อง สำหรับ 117 คาบที่ไม่ใช้ Lab เลย'))


# -- slide data: the dataset as one picture
def dataset_picture():
    sessions = DATA['recurring_sessions']
    labs = sorted((r['capacity'] for r in DATA['rooms'] if r['kind'] == 'computer_lab'), reverse=True)
    lab_slots = sum(len(x['lab_weeks']) for x in sessions)
    slots = len(sessions) * len(WEEKS)
    check('data slide numbers',
          (len({c['course_id'] for c in DATA['classes']}), len(CLASSES), len(sessions), len(WEEKS), slots,
           sum(1 for x in sessions if x['lab_weeks']), lab_slots, slots - lab_slots,
           sum(1 for r in DATA['rooms'] if r['kind'] == 'lecture' and r['schedulable']), labs, len(DATA['external_classes']),
           len({CLASSES[x['class_id']]['course_id'] for x in sessions if x['lab_weeks']}),
           sum(x['duration_minutes'] * len(x['lab_weeks']) for x in sessions) // 60),
          (44, 174, 223, 15, 3345, 106, 424, 2921, 13, [61, 36, 30, 26], 810, 20, 800))
    example = [(c['id'], c['student_count'], [(SESSIONS[x]['duration_minutes'], SESSIONS[x]['lab_weeks']) for x in c['session_ids']])
               for c in DATA['classes'] if c['course_id'] == 'O756']
    check('course O756', example, [('C1493', 60, [(60, [])] * 3), ('C1494', 30, [(120, [2, 3, 8, 9])]), ('C1495', 30, [(120, [2, 3, 8, 9])])])
    chain = '<div style="flex-direction:row;gap:36px;align-items:center">' + ARROW.join(
        [count('44', 'วิชา'), count('174', 'กลุ่มเรียน'), count('223', 'คาบต่อสัปดาห์'),
         count('3,345', 'ช่อง (223 × 15 สัปดาห์)')]) + '</div>'
    split = (f'<div style="flex-direction:row;height:64px;border:5px solid {INK};border-radius:14px;overflow:hidden">'
             f'<div style="width:{lab_slots / slots * 100:.2f}%;background:{BLUE};align-items:center;justify-content:center">'
             f'<p style="font-size:32px;font-weight:700;color:#FFFFFF">424</p></div>'
             f'<div style="flex:1;background:#FFFFFF;align-items:center;justify-content:center">'
             f'<p style="font-size:32px;font-weight:700">2,921 ช่อง ใช้ห้องบรรยายได้</p></div></div>')
    need = (f'<div style="flex-direction:row;gap:20px;align-items:center">'
            f'<p style="flex:none;font-size:44px;font-weight:700;line-height:1.1"><span style="font-size:76px;color:{BLUE}">424</span> ช่อง ต้องอยู่ห้อง Lab</p>'
            f'{tag("เราสมมติ", True)}'
            f'<p style="font-size:32px;line-height:1.3">20 จาก 44 วิชา, เฉพาะคาบปฏิบัติ 106 คาบ, คาบละ 4 จาก 15 สัปดาห์</p></div>')

    def rooms(n, fill, label, word, made_up):
        squares = ''.join(f'<span style="flex:none;width:40px;height:40px;border:4px solid {INK};border-radius:8px;'
                          f'background:{fill}"></span>' for _ in range(n))
        return (f'<div style="gap:8px"><div style="flex-direction:row;gap:6px">{squares}</div>'
                f'<div style="flex-direction:row;gap:14px;align-items:center"><p style="font-size:34px;font-weight:700;'
                f'line-height:1.3">{label}</p>{tag(word, made_up)}</div></div>')

    return ('<div style="gap:14px">'
            f'<div style="flex-direction:row;gap:16px;align-items:center">{tag("ของจริง")}'
            f'<p style="font-size:32px;line-height:1.3">ของจริงจาก Purdue: งานที่ต้องจัด</p></div>'
            + chain
            + line('<b>ตัวอย่าง:</b> วิชา O756 = กลุ่มบรรยาย 1 กลุ่ม + กลุ่มปฏิบัติ 2 กลุ่ม')
            + split + need
            + '<div style="flex-direction:row;gap:72px;align-items:flex-end;margin-top:6px">'
            + rooms(13, '#FFFFFF', 'ห้องบรรยาย 13 ห้อง', 'ของจริง', False)
            + rooms(4, BLUE, 'ห้อง Lab 4 ห้อง: จุ 61, 36, 30, 26 คน', 'เราสมมติ', True) + '</div>'
            + line('อีก 810 คลาสของภาคอื่นจองห้องไว้แล้ว อัลกอริทึมต้องหลบ') + '</div>')


# -- slide coursedata: Lab hours needed each week, and the 20 Lab courses that add up to them
def demand_picture():
    hours = {w: 0 for w in WEEKS}
    need = {}
    for x in DATA['recurring_sessions']:
        for w in x['lab_weeks']:
            hours[w] += x['duration_minutes'] / 60
            need.setdefault(CLASSES[x['class_id']]['course_id'], set()).add(w)
    order = sorted(need)
    low, high = min(hours, key=hours.get), max(hours, key=hours.get)
    check('Lab demand: courses, all courses, (week, hours) lowest and highest, weeks of O756',
          (len(order), len({c['course_id'] for c in DATA['classes']}), (low, hours[low]), (high, hours[high]), sorted(need['O756'])),
          (20, 44, (7, 9.0), (8, 89.0), [2, 3, 8, 9]))
    L, cw, ch, bar_top, bar_h = 150, 58, 18, 44, 150
    grid_top = bar_top + bar_h + 52
    width, height = L + cw * 15, grid_top + ch * len(order)
    svg, text = '', ''
    for i, w in enumerate(WEEKS):
        h = bar_h * hours[w] / hours[high]
        svg += f'<rect x="{L + i * cw + 6}" y="{bar_top + bar_h - h:.0f}" width="{cw - 12}" height="{h:.0f}" fill="{BLUE}"/>'
        text += (f'<p style="position:absolute;left:{L + i * cw}px;top:{bar_top + bar_h + 4}px;width:{cw}px;font-size:32px;line-height:1.3;'
                 f'text-align:center;color:{GREY}">{w}</p>')
        if w in (low, high):
            text += (f'<p style="position:absolute;left:{L + i * cw - 20}px;top:{bar_top + bar_h - h - 44:.0f}px;width:{cw + 40}px;'
                     f'font-size:32px;font-weight:700;line-height:1.3;text-align:center">{hours[w]:.0f}</p>')
    for r, course in enumerate(order):
        for i, w in enumerate(WEEKS):
            svg += (f'<rect x="{L + i * cw + 2}" y="{grid_top + r * ch + 2}" width="{cw - 4}" height="{ch - 4}" rx="2" '
                    f'fill="{BLUE if w in need[course] else LIGHT}"/>')
    row = order.index('O756')
    row_y = grid_top + row * ch
    svg += f'<rect x="{L - 2}" y="{row_y - 1}" width="{cw * 15 + 4}" height="{ch + 2}" fill="none" stroke="{INK}" stroke-width="4"/>'
    text += (f'<p style="position:absolute;left:0;top:{row_y - 13}px;width:{L - 14}px;font-size:32px;font-weight:700;line-height:1.3;'
             f'text-align:right">O756</p>'
             f'<p style="position:absolute;left:0;top:{bar_top + bar_h - 100}px;width:{L - 14}px;font-size:32px;line-height:1.25;'
             f'text-align:right;color:{GREY}">ชม. Lab</p>'
             f'<p style="position:absolute;left:0;top:{bar_top + bar_h + 4}px;width:{L - 14}px;font-size:32px;line-height:1.3;'
             f'text-align:right;color:{GREY}">สัปดาห์</p>')
    d = duo('ทุกกลุ่มของวิชาเดียวกัน<br>ใช้ Lab สัปดาห์เดียวกัน', scale=0.42, size=32, wave=True, mirror=True)
    swatch = (f'<span style="flex:none;width:56px;height:28px;border:3px solid {INK};border-radius:6px;background:{BLUE}"></span>')
    notes = (f'<div style="position:absolute;left:{L}px;top:{height + 10}px;width:{1640 - L}px;flex-direction:row;gap:16px;align-items:center">'
             f'{swatch}<p style="font-size:32px;line-height:1.3;margin-right:40px">ต้องใช้ Lab</p>'
             f'<p style="font-size:32px;line-height:1.3;color:{GREY}">20 วิชาที่ใช้ Lab, อีก 24 วิชาไม่ใช้</p></div>')
    return (f'<div style="position:relative;width:1640px;height:{height + 60}px">'
            f'<svg aria-label="ชั่วโมง Lab ที่ต้องใช้ในแต่ละสัปดาห์ และสัปดาห์ Lab ของ 20 วิชา" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" style="position:absolute;left:0;top:0;width:{width}px;height:{height}px">{svg}</svg>'
            f'{text}{place(d, width + 96, row_y + ch / 2 - d.mh * 0.62)}{notes}</div>')


# --- slides ----------------------------------------------------------------------
# Words used the same way on every slide and in every script:
#   กลุ่มเรียน = one class (section) / คาบ = one meeting of it per week (223) / ช่อง = one คาบ in one week (3,345)
#   Lab ไม่จำเป็น = sitting in a Lab in a week that does not need the computers (the second objective)
SLOT_FIXED, SLOT_WEEKLY = slot_rows()


def pill(text, colour):
    """A table value on a solid colour with white text: blue = the good value, red = where it stops working."""
    return f'<span style="background:{colour};color:#FFFFFF;font-weight:700;border-radius:8px;padding:0 14px">{text}</span>'


# Solid red square in front of a row name; the caption under the table says what it means.
RED_ROW = f'<span style="display:inline-block;width:22px;height:22px;background:{RED};margin-right:12px"></span>'

SLIDES = {
    'cover': ('ระบบจัดตารางเรียนและจัดสรรห้องเรียน ภายใต้ความต้องการใช้ Lab รายสัปดาห์',
              f'<div style="flex-direction:row;align-items:center;gap:40px;flex:1">'
              f'<div style="flex:1;gap:28px">'
              f'<h1 style="font-size:68px;font-weight:700;line-height:1.3;color:{INK}">ระบบจัดตารางเรียน<br>และจัดสรรห้องเรียน</h1>'
              f'<p style="font-size:40px;line-height:1.4">ภายใต้ความต้องการใช้ Lab รายสัปดาห์</p>'
              f'<p style="font-size:32px;line-height:1.5;color:{GREY}">CS373 นำเสนอผลงานขั้นสุดท้าย<br>'
              f'github.com/Micosz/CS373_CourseTimetablingLab</p></div>'
              f'{buddy("สวัสดี!", wave=True, scale=1.25, size=56)}</div>'),
    'problem': ('ปัญหา|ใช้คอมแค่ 4 จาก 15 สัปดาห์ แต่จองห้อง Lab ไว้ทั้งเทอม',
                strip([('ห้องคงที่', ONE_FIXED), ('รายสัปดาห์', ONE_WEEKLY)], 'GA seed 1001, กลุ่ม C1422',
                      [('lab', 'L4', 'ใช้ Lab'), ('waste', '(L4)', 'Lab ไม่จำเป็น'), ('room', 'R95', 'ห้องบรรยาย')])
                + two(ul(['<b>ห้องคงที่</b> อยู่ห้อง Lab 15 สัปดาห์ ต้องใช้จริง 4',
                          'ระหว่างนั้น กลุ่มอื่นใช้ห้อง Lab นี้ไม่ได้',
                          '<b>โจทย์</b> ถ้าห้องเปลี่ยนได้รายสัปดาห์ จะจัดครบไหม'], 30),
                      buddy('อีก 11 สัปดาห์<br>ไม่ได้แตะคอมเลย', 'sad', scale=0.3, stars=False, size=36))),
    'whyhard': ('ทำไมยาก|ห้องบรรยายเต็ม คาบบรรยายจึงล้นไปห้อง Lab และสัปดาห์ที่ห้อง Lab มีกลุ่มอื่นใช้ ก็ไม่มีที่ไป',
                strip(stuck_rows(), 'Greedy, วันศุกร์ 8:30',
                      [('full', 'เต็ม', 'มีกลุ่มอื่นใช้'), ('waste', '(L2)', 'Lab ไม่จำเป็น'), ('none', 'ไม่มี', 'ไม่มีห้อง'),
                       ('lab', 'อื่น', 'กลุ่มอื่นใช้ Lab')], tall=58)
                + line('<b>เวลาเรียนเลือกครั้งเดียวทั้งเทอม จึงย้ายเวลาเฉพาะ 4 สัปดาห์นั้นไม่ได้</b>', 40)),
    'approach': ('โจทย์|เลือกเวลาครั้งเดียว ให้ทุกคาบมีห้องทั้ง 15 สัปดาห์ และใช้ Lab เท่าที่จำเป็น',
                 '<div style="gap:12px">'
                 + line('<b>เวลาเรียน: เลือกครั้งเดียว ใช้ทั้งเทอม</b> (กลุ่มเรียน C1419: วันพฤหัสบดี 11:30)', 40)
                 + strip([('ห้องของ<br>C1419', MOVER_CELLS)], 'GA seed 1001, ห้องรายสัปดาห์',
                         [('lab', 'L4', 'ใช้ Lab'), ('room', 'R96', 'ห้องบรรยาย')])
                 + line('<b>ห้อง: เลือกใหม่ได้ทุกสัปดาห์</b>', 40) + '</div>'
                 + '<div style="flex-direction:row;gap:64px;align-items:center">'
                 + numbered(1, 'ทุกคาบมีห้อง') + numbered(2, 'ไม่มี Lab ไม่จำเป็น') + numbered(3, 'ย้ายห้องน้อยที่สุด') + '</div>'
                 + f'<div style="flex-direction:row;gap:56px;align-items:baseline;border-left:10px solid {YELLOW};padding-left:20px">'
                   '<p style="font-size:34px;line-height:1.1"><b style="font-size:72px">174</b> กลุ่มเรียน</p>'
                   '<p style="font-size:34px;line-height:1.1"><b style="font-size:72px">3,345</b> ช่อง</p>'
                   '<p style="font-size:34px;line-height:1.1">ห้อง Lab <b style="font-size:72px">4</b> ห้อง</p></div>'),
    'questions': ('คำถาม|สิ่งที่งานนี้ตอบ และสิ่งที่ไม่ได้ตอบ',
                  two('<div style="gap:14px">'
                      + numbered(1, 'จัดได้ครบไหม และเหลือ Lab ไม่จำเป็นเท่าไร', 104, 44)
                      + numbered(2, 'วิธีค้นหาแบบไหนดีที่สุดเมื่อได้งบเท่ากัน', 104, 44)
                      + numbered(3, 'ใช้ได้ถึงขอบเขตไหนเมื่อวิชาใช้ Lab มากขึ้น', 104, 44) + '</div>'
                      + f'<p style="font-size:32px;line-height:1.45;border-top:5px solid {INK};padding-top:14px"><b>ไม่ได้ตอบ:</b> '
                        'มหาวิทยาลัยเจอสถานการณ์นี้มากแค่ไหน, ดีกว่าคนจัดตารางจริงไหม, ดีกว่าการจอง Lab เมื่อจะใช้ไหม, '
                        'การย้ายห้องกระทบนักศึกษาแค่ไหน</p>'
                      + small('เพิ่มจากโครงร่าง: เทียบ 4 อัลกอริทึม, ข้อมูลจริงของ Purdue, นับการย้ายห้อง'),
                      buddy('เดี๋ยวกลับมา<br>ตอบตอนท้าย', wave=True, scale=0.6, size=38))),
    'data': ('ข้อมูล|อะไรเป็นข้อมูลจริง อะไรที่เราสมมติ', dataset_picture()),
    'coursedata': ('ความต้องการ Lab|แต่ละสัปดาห์ต้องใช้ Lab ไม่เท่ากัน: น้อยสุด 9 ชั่วโมง มากสุด 89 ชั่วโมง', demand_picture()),
    'objective': ('เป้าหมาย|ฟังก์ชันเป้าหมายและข้อจำกัดของปัญหา',
                  two(ul(['<b>ช่องที่ไม่มีห้อง</b> ต้องน้อยที่สุดก่อน', '<b>Lab ไม่จำเป็น</b> อยู่ห้อง Lab ในสัปดาห์ที่ไม่ต้องใช้',
                          '<b>จำนวนครั้งที่เปลี่ยนห้อง</b> ห้องต่างจากสัปดาห์ก่อน'], 30, 'ol')
                      + line('<b>จากรันจริง</b> (กลุ่มเรียน C1422, คาบ 2 ชม., GA seed 1001): ห้องคงที่อยู่ห้อง Lab 15 สัปดาห์ ต้องใช้ 4 '
                             '→ Lab ไม่จำเป็น <b>22 ชม.</b> / ห้องรายสัปดาห์ <b>0 ชม.</b>')
                      + f'<p style="font-size:32px;line-height:1.4;border-left:10px solid {YELLOW};padding-left:20px"><b>ข้อห้าม</b> '
                        f'ห้อง ผู้สอน กลุ่มนักศึกษา ห้ามชนเวลากัน / ห้องต้องจุพอ / สัปดาห์ Lab ต้องอยู่ห้อง Lab / จัดไม่ได้ก็เว้นไว้</p>',
                      buddy('กฎคือกฎ', hat=True, scale=0.7, size=42))),
    'method': ('วิธีการ|การแทนคำตอบและอัลกอริทึมที่เปรียบเทียบ',
               f'<div style="flex-direction:row;gap:20px;align-items:stretch">'
               f'{box("อัลกอริทึมค้นหา", "ลำดับกลุ่มเรียน และเวลาที่ลองก่อน")}{ARROW}'
               f'{box("ห้อง: ไม่ได้ค้นหา", "กฎตายตัว: ห้องบรรยายก่อน, ห้องเดิมของสัปดาห์ก่อน, ห้องเล็กสุดที่จุพอ", True)}{ARROW}'
               f'{box("ตัวตรวจอิสระ", "ตรวจข้อห้ามและนับผลใหม่ทุกรัน")}</div>'
               + table(['วิธี', 'ค้นหายังไง'],
                       [['Greedy', 'จัดกลุ่มเรียนที่มีตัวเลือกน้อยก่อน รอบเดียวจบ'],
                        ['Hill Climbing (HC)', 'แก้ทีละนิด เก็บไว้เฉพาะที่ดีขึ้น'],
                        ['Simulated Annealing (SA)', 'ยอมรับตารางที่แย่ลงได้บ้างในช่วงแรก'],
                        ['Genetic Algorithm (GA)', 'เก็บตารางไว้หลายชุด แล้วเอามาผสมกัน']], 28, ['36%', None])),
    'protocol': ('การทดลอง|ระเบียบวิธีการทดลอง',
                 two(ul(['ปรับค่าบน seed 1–10 (51 ชุดค่า 510 รัน) ทดสอบบน seed 1001–1030',
                         'ทุกวิธีได้งบเท่ากัน: ลองได้ 500 ตารางต่อรัน',
                         'สถิติกำหนดก่อนรัน: Friedman, Wilcoxon, Holm',
                         'ตรวจซ้ำ 16 รันด้วยโปรแกรม Python ที่เขียนแยกกัน ผลตรงกัน'], 28)
                     + f'<div style="flex-direction:row;gap:48px">{big("240/240", "รันผ่านตัวตรวจอิสระ (4 วิธี × 30 seed × 2 โหมดห้อง)")}</div>',
                     buddy('ตั้งกติกา<br>ก่อนเล่น', scale=0.7, size=40))),
    'greedy': ('Greedy|ห้องบรรยายเต็ม คาบบรรยายจึงล้นไปห้อง Lab และเหลือ 14 ช่องที่ไม่มีห้อง',
               strip(greedy_rows(), 'Greedy: 7 คาบบรรยาย',
                     [('none', 'ไม่มี', 'ไม่มีห้อง'), ('waste', '(L2)', 'Lab ไม่จำเป็น'), ('room', 'R57', 'ห้องบรรยาย')], tall=48)
               + '<div style="flex-direction:row;gap:72px;align-items:baseline">'
                 f'<p style="font-size:36px;line-height:1.1"><b style="font-size:84px;color:{RED}">14</b> ช่องไม่มีห้อง (จาก 3,345)</p>'
                 f'<p style="font-size:36px;line-height:1.1"><b style="font-size:84px;color:{RED}">242</b> ชม. Lab ไม่จำเป็น</p></div>'),
    'hc': ('Hill Climbing|เส้นลดลงตั้งแต่ต้น และยังลดอยู่เมื่อลองครบ 500 ครั้ง',
           method_slide('hc', 'แก้ทีละนิด เก็บไว้เฉพาะที่ดีขึ้น เริ่มใหม่เมื่อติด', 'ลงเรื่อย ๆ', 'happy', 26)),
    'sa': ('Simulated Annealing|100 ครั้งแรกเส้นแทบไม่ขยับ แล้วจึงลดลงจนครบ 500 ครั้ง',
           method_slide('sa', 'ยอมรับตารางที่แย่ลงได้บ้างในช่วงแรก', 'ตอนแรกนิ่งเลย', 'wow', 29)),
    'ga': ('Genetic Algorithm|เส้นขึ้นในช่วงแรก แล้วลดลงต่อเนื่องจนครบ 500 ครั้ง',
           method_slide('ga', 'เก็บตารางไว้หลายชุด แล้วเอามาผสมกัน', 'ขึ้นก่อนแล้วลง', 'wow', 28)),
    'main': ('สรุปผลที่งบ 500|วิธีค้นหาทั้งสามดีกว่า Greedy ทุก seed แต่ยังแยกกันเองไม่ได้',
             two(ul(['วิธีค้นหาดีกว่า Greedy ครบ 30 จาก 30 seed (Friedman p &lt; 0.001)',
                     'จัดครบ 83 จาก 90 รัน (3 วิธี วิธีละ 30 รัน)',
                     'HC, SA, GA แยกไม่ได้: p = 0.102, 0.102, 0.666'], 28),
                 bars([('SA', 145.8, '145.8', 'blue'), ('GA', 146.9, '146.9', 'blue'), ('HC', 169.4, '169.4', 'blue'),
                       ('Greedy', 242.0, '242.0', 'red')], 700, 520,
                      'Lab ไม่จำเป็นเฉลี่ย 30 seed (ชม.)',
                      top=110, rider=(1, duo('โห สูงกว่าเราเยอะ', 'wow', wave=True, scale=0.5, size=32))), 40)),
    'source': ('ที่มาของ Lab ไม่จำเป็น|ห้องบรรยายเต็ม คาบบรรยายจึงล้นไปห้อง Lab', source_picture()),
    'budget': ('งบการค้นหา|ผลของงบประมาณการค้นหาต่อคุณภาพคำตอบ',
               aside(table(['งบต่อรัน', 'HC', 'GA', 'SA'],
                           [['500', '161.1', '146.3', '135.8'], ['2,000', '72.0', '77.7', '60.8'],
                            ['10,000', '41.3', '48.6', pill('0.0', BLUE)],
                            ['50,000', '19.4', '40.9',
                             pill('0.0', BLUE) + pointer('ศูนย์จริง ๆ<br>ไม่ได้พิมพ์ผิด', 'wow', 0.42, edge=True)]], 30), 560)
               + small('Lab ไม่จำเป็นเฉลี่ย 10 seed (ชม.)')
               + ul(['ตั้งแต่งบ 1,000 ทุกรันจัดครบทุกช่อง',
                     'งบ 50,000: SA ดีกว่า HC และ GA (p = 0.012)',
                     '<b>แต่</b> ทุกวิธีปรับค่าที่งบ 500 ไม่ได้ปรับใหม่ที่งบใหญ่ จึงอาจไม่แฟร์กับ HC และ GA'], 28)),
    'changes': ('การเปลี่ยนห้อง|ย้ายห้องเท่าที่การใช้ Lab กำหนด',
                two(ul(['ข้อมูลบังคับให้ย้ายอย่างน้อย 596 ครั้ง',
                        'ระบบย้ายราว 620 ครั้ง (1.04 ถึง 1.05 เท่า)',
                        'ห้องคงที่ไม่ย้าย แต่มี Lab ไม่จำเป็นราว 2,035 ชม.'], 30),
                    bars([('ต่ำสุด', 596, '596', 'grey'), ('GA', 617.8, '617.8', 'blue'), ('SA', 619.7, '619.7', 'blue'),
                          ('HC', 624.4, '624.4', 'blue')], 700, 520,
                         'ครั้งที่เปลี่ยนห้องต่อเทอม เฉลี่ย 30 seed',
                         top=170, rider=(0, duo('', 'happy', wave=True, scale=0.45))), 40)),
    'scarcity': ('จำนวนห้อง Lab|ผลเมื่อจำนวนห้อง Lab ลดลง',
                 aside(table(['จำนวน Lab', 'Greedy', 'HC', 'SA', 'GA', 'ห้องคงที่'],
                             [['4 ห้อง (หลัก)', '14', '<b>0</b>', '<b>0.1</b>', '<b>0</b>', 'ราว 180 ถึง 200'],
                              [RED_ROW + '3 ห้อง', '30', '<b>3.8</b>', '<b>1.5</b>', '<b>1.9</b>',
                               '505 ถึง 520' + pointer('เกือบครบ<br>แต่ไม่ครบ', 'sad', 0.45)],
                              [RED_ROW + '2 ห้อง', '126', '<b>40.1</b>', '<b>38.8</b>', '<b>32.2</b>', '858 ถึง 867']], 30,
                             ['21%', None, None, None, None, '25%']), 330)
                 + '<div style="flex-direction:row;gap:40px;align-items:center">'
                 + small('ช่องที่ไม่มีห้อง เฉลี่ย 10 seed งบ 500')
                 + f'<p style="font-size:32px;line-height:1.3">{RED_ROW}จัดไม่ครบทุกรัน</p></div>'
                 + ul(['Lab 3 ห้อง: จัดครบแค่ 1 ถึง 4 จาก 10 รัน',
                       'Lab 2 ห้อง: ไม่มีห้อง 32 ถึง 40 ช่อง',
                       'ห้องคงที่ไม่มีห้องมากกว่าทุกแถว'], 28)),
    'labweeks': ('ขอบเขต|เมื่อวิชาใช้ Lab มากขึ้นจาก 1 ถึง 15 สัปดาห์',
                 aside(table(['สัปดาห์ Lab', 'Greedy', 'HC', 'SA', 'GA', 'จัดครบ (จาก 10 รัน)'],
                             [['1 ถึง 2', '0', '<b>0</b>', '<b>0</b>', '<b>0</b>', '10'],
                              ['4 (กรณีหลัก)', '14', '<b>0</b>', '<b>0.1</b>', '<b>0</b>', '9 ถึง 10'],
                              ['6', '66', '<b>10.2</b>', '<b>9.2</b>', '<b>8.6</b>',
                               pill('0', RED) + pointer('เส้นแบ่ง<br>อยู่ตรงนี้', 'wow', 0.42, edge=True)],
                              ['8', '87', '<b>18.4</b>', '<b>16.7</b>', '<b>15.6</b>', pill('0', RED)],
                              ['12', '193', '<b>89.9</b>', '<b>86.1</b>', '<b>80.3</b>', pill('0', RED)],
                              ['15', '285', '<b>189.0</b>', '<b>190.5</b>', '<b>181.5</b>', pill('0', RED)]], 28,
                             ['22%', None, None, None, None, '27%']), 330)
                 + small('ช่องที่ไม่มีห้อง เฉลี่ย 10 seed งบ 500')
                 + ul(['ขอบเขตอยู่ระหว่าง 4 กับ 6 สัปดาห์',
                       'ที่ 15 สัปดาห์ สองโหมดห้องให้ผลเท่ากันทุกรัน'], 28)),
    'limits': ('ข้อจำกัด|ข้อจำกัดของการศึกษา',
               two(ul(['<b>ความต้องการ Lab เป็นเรื่องสมมติ</b> ส่วนปฏิบัติเดาจากรูปแบบคาบ',
                       '<b>ห้องคงที่คือห้องเดียวทั้งเทอม</b> ไม่ได้เทียบกับการจอง Lab เฉพาะสัปดาห์ที่ใช้',
                       '<b>ปรับค่าที่งบ 500 เท่านั้น</b> ผลที่งบใหญ่อาจไม่แฟร์กับ HC และ GA',
                       '<b>งบ 500 น้อย</b> หลายข้อสรุปขึ้นกับงบ'], 27)
                   + small('และ: สุ่มเลือกวิชาที่ใช้ Lab ครั้งเดียว, งบใหญ่ใช้ 10 seed, ยังไม่ได้วัดผลด้านคน'),
                   buddy('ยังไม่เพอร์เฟกต์<br>นะ', 'sad', scale=0.7, size=38))),
    'conclude': ('สรุป|สรุปผลการศึกษา บนโจทย์ที่เราตั้งขึ้น',
                 two(ul(['<b>จัดได้ครบไหม</b> วิธีค้นหาดีกว่า Greedy ทั้ง 30 seed จัดครบ 83 จาก 90 รัน',
                         '<b>วิธีไหนดีที่สุด</b> ขึ้นกับงบ: งบ 500 แยกไม่ได้ งบ 50,000 SA ดีที่สุด (ค่าที่ปรับที่งบ 500)',
                         '<b>ขอบเขต</b> ที่งบ 500 เริ่มไม่ครบเมื่อใช้ Lab 6 สัปดาห์ หรือเหลือห้อง Lab 3 ห้อง'], 30, 'ol')
                     + small('เป็นผลบนโจทย์ที่ตั้งขึ้น ไม่ใช่ข้อสรุปเรื่องมหาวิทยาลัยจริง'),
                     buddy('ขอบคุณครับ!', wave=True, scale=0.8, size=46))),
    'refs': ('เอกสารอ้างอิง',
             '<div style="gap:20px">'
             + ref('Lemos et al. (2019)', 'Room usage optimization in timetabling: A case study at Universidade de Lisboa. Operations Research Perspectives, 6, 100092.')
             + ref('Bellio et al. (2016)', 'Feature-based tuning of simulated annealing applied to the curriculum-based course timetabling problem. Computers &amp; Operations Research, 65, 83–92.')
             + ref('Müller (2009)', 'ITC2007 solver description: A hybrid approach. Annals of Operations Research, 172(1), 429–446.')
             + ref('Xiao (2021)', 'The Course Scheduling Problem with Room Considerations. Doctoral dissertation, Wright State University.')
             + ref('ITC2007', 'Curriculum-based Course Timetabling: The Problem Model. Queen’s University Belfast.')
             + ref('Even, Itai &amp; Shamir (1976)', 'On the complexity of timetable and multicommodity flow problems. SIAM Journal on Computing, 5(4), 691–703.')
             + ref('Beyrouthy et al. (2009)', 'Towards improving the utilization of university teaching space. Journal of the Operational Research Society, 60, 130–143.')
             + ref('Li, Zhao &amp; Xue (2026)', 'An Empirical Study on Assessing Classroom Space Utilization Efficiency in Higher Education Institutions. Buildings, 16(10), 1929.')
             + ref('UniTime', 'University course timetabling datasets, Purdue Fall 2007 CS (pu-fal07-cs).') + '</div>'),
    'refs-methods': ('เอกสารอ้างอิง|อัลกอริทึมและสถิติ',
                     '<div style="gap:20px">'
                     + ref('Davis (1985)', 'Applying adaptive algorithms to epistatic domains. Proceedings of IJCAI-85, 162–164.', 'order crossover ของ GA')
                     + ref('Goldberg &amp; Deb (1991)', 'A comparative analysis of selection schemes used in genetic algorithms. Foundations of Genetic Algorithms, 69–93.', 'tournament selection ของ GA')
                     + ref('Demšar (2006)', 'Statistical comparisons of classifiers over multiple data sets. Journal of Machine Learning Research, 7, 1–30.', 'Friedman แล้วเทียบรายคู่')
                     + ref('Holm (1979)', 'A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65–70.', 'ปรับค่า p เมื่อเทียบหลายคู่')
                     + '</div>'),
    'refs-recent': ('เอกสารอ้างอิง|งานใหม่ 2025–2026',
                    '<div style="gap:14px">'
                    + ref('Cavalcante et al. (2026)', 'A Mathematical Model for Class Scheduling: A Case Study with the Federal University of Maranhão. IntechOpen.', 'คนจัดเอง 23 ห้อง, Greedy 20, ILP 13, ใช้ Lab จำลองเหมือนเรา')
                    + ref('Raviv (2026)', 'The lecture-hall quadratic assignment problem. Computers &amp; Operations Research, 196, 107659.', 'ย้ายห้องระหว่างเทอมต้นทุนต่ำ แต่ย้ายเวลากระทบนักศึกษา')
                    + ref('Han &amp; Wang (2025)', 'Gradual Optimization of University Course Scheduling Problem Using Genetic Algorithm and Dynamic Programming. Algorithms, 18(3), 158.', 'จัดห้องรายสัปดาห์ แต่ประเภทห้องผูกกับวิชา')
                    + ref('Antunes-Batista et al. (2026)', 'Multiobjective Optimization Approaches for Room Allocation in University Course Timetabling. Procedia Computer Science, 278, 663–670.', 'นับการเปลี่ยนห้องของวิชาเดียวกันเป็นเป้าหมาย')
                    + ref('Ozkan et al. (2025)', 'University course timetabling with multi-section courses, room stability and lecturer preferences. Computational Management Science, 22(1), 3.', 'room stability ตรงกับโหมดห้องคงที่')
                    + ref('Müller, Rudová &amp; Müllerová (2025)', 'Real-world university course timetabling at the International Timetabling Competition 2019. Journal of Scheduling, 28(2), 247–267.', 'ข้อมูล UniTime สายเดียวกับ pu-fal07-cs')
                    + '</div>'),
}


# Spoken script per slide, casual polite Thai. The key order of NOTES is the slide order.
# Rules for the main script (the part before the Q&A block): at most two numbers, say which one thing to look at,
# "เรา" for the work, the takeaway only on the technical slides (the detail lives in the Q&A answers).
# [square brackets] are stage cues: each names a position or a printed label on that slide, never a colour.
# qa() appends answers kept ready for the lecturer's questions; they are not part of the timed script.
ASK = '——— ถ้าอาจารย์ถาม ———'
SCRIPT_LIMIT = 6800  # spoken characters of all main scripts together: the length that fitted 15 minutes


def qa(*pairs):
    return f'\n{ASK}' + ''.join(f'\nถาม: {q}\nตอบ: {a}' for q, a in pairs)


NOTES = {
    'cover': 'สวัสดีครับ [ชี้น้องจอคอมที่โบกมือ] วันนี้เราจะเล่างานจัดตารางเรียนครับ โจทย์คือวิชาที่ใช้ห้อง Lab แค่บางสัปดาห์ '
             'แต่จองห้อง Lab ไว้ทั้งเทอม เราเลยลองให้ห้องเปลี่ยนได้ทุกสัปดาห์ แล้วดูว่าจัดได้ครบไหม '
             '',
    'problem': 'เริ่มจากปัญหาครับ ดูกลุ่มเรียนหนึ่งกลุ่ม [ชี้แถวที่เขียนว่าห้องคงที่] กลุ่มนี้ต้องใช้คอมแค่ 4 จาก 15 สัปดาห์ '
               'แต่ถูกจองห้อง Lab ไว้ทั้งเทอม สัปดาห์ที่เหลือจึงนั่งอยู่ในห้อง Lab ในสัปดาห์ที่ไม่ต้องใช้คอม '
               'เราเรียกว่า Lab ไม่จำเป็นครับ คือช่องที่มีวงเล็บ และระหว่างนั้นกลุ่มอื่นก็ใช้ห้อง Lab นี้ไม่ได้ '
               'แถวล่าง [ชี้แถวที่เขียนว่ารายสัปดาห์] คือเมื่อให้ห้องเปลี่ยนได้ทุกสัปดาห์ คำถามคือ ทำแบบนี้กับทุกกลุ่มพร้อมกันได้ไหม'
               + qa(('มีหลักฐานไหมว่าเป็นปัญหาจริง',
                     'งานของ Li และคณะ ปี 2026 วัดจากตารางสอนจริง 2,943 วิชา พบว่าห้องเรียนถูกใช้จริงแค่ราว 20 ถึง 50 เปอร์เซ็นต์ครับ '
                     'และงานของ Beyrouthy และคณะ ปี 2009 '
                     'ชี้ว่าข้อจำกัดของการจัดตารางเป็นสาเหตุหนึ่ง'),
                    ('กลุ่มเรียนในภาพคือกลุ่มไหน',
                     'กลุ่ม C1422 ของวิชา O144 ครับ ต้องใช้ Lab สัปดาห์ 1, 4, 13 และ 15 แถวบนมาจากรัน GA seed 1001 แบบห้องคงที่ '
                     'ซึ่งกลุ่มนี้อยู่ห้อง SIM-LAB-04 ทั้ง 15 สัปดาห์ แถวล่างมาจากรัน GA seed 1001 แบบห้องรายสัปดาห์ '
                     'ในช่อง L4 คือห้อง SIM-LAB-04 และ R95 คือห้องบรรยาย')),
    'whyhard': 'ฟังดูง่าย แต่ดูกรณีนี้ครับ ไล่จากบนลงล่างสามขั้น ขั้นหนึ่ง [ชี้แถวใต้เลข 1] ห้องบรรยายที่กลุ่มนี้ใช้ได้เต็มทุกสัปดาห์ '
               'ขั้นสอง [ชี้แถวใต้เลข 2] กลุ่มนี้จึงล้นไปอยู่ห้อง Lab ทั้งที่ไม่ต้องใช้คอมเลย '
               'ขั้นสาม [ชี้ช่องที่เขียนว่าไม่มี] มี 4 สัปดาห์ที่ห้อง Lab ก็มีกลุ่มอื่นใช้ กลุ่มนี้จึงไม่มีห้องเรียน '
               'และ [ชี้บรรทัดล่างสุด] จะย้ายเวลาเฉพาะสัปดาห์นั้นก็ไม่ได้ครับ เพราะเวลาเรียนเลือกครั้งเดียวทั้งเทอม'
               + qa(('กรณีนี้มาจากรันไหน',
                     'จากตารางของ Greedy แบบห้องรายสัปดาห์ครับ กลุ่มนี้คือ C1566 คาบวันศุกร์ 8:30 มีนักศึกษา 36 คน '
                     'ไม่มีห้องในสัปดาห์ 3, 8, 9 และ 12 ห้องบรรยายที่ใช้ได้คือ R57, R63 และ R64 ส่วนห้อง Lab ที่จุพอมีสองห้อง '
                     'คือ L2 จุ 36 ที่นั่ง และ L1 จุ 61 ที่นั่ง ในสองแถวล่าง คำว่านี้คือกลุ่มนี้เอง คำว่าอื่นคือกลุ่มเรียนอื่น'),
                    ('ทำไมกลุ่มอื่นถึงได้ห้อง Lab ในสัปดาห์นั้น',
                     'ข้อมูลบอกได้แค่ว่าใครอยู่ห้องไหนครับ ในสี่สัปดาห์นั้นห้อง L2 เป็นของ C1524 ซึ่งเป็นสัปดาห์ที่กลุ่มนั้นต้องใช้ Lab '
                     'ส่วนห้อง L1 เป็นของ C1458 หรือ C1444 เราไม่ได้วิเคราะห์ลำดับการตัดสินใจของ Greedy ไปมากกว่านี้')),
    'approach': 'โจทย์ของเราดูจากกลุ่มเรียนกลุ่มนี้ครับ สิ่งที่ต้องตัดสินใจมีสองอย่าง อย่างแรก [ชี้บรรทัดเวลาเรียนเหนือแถบ] '
                'เวลาเรียน เลือกครั้งเดียวใช้ทั้งเทอม อย่างที่สอง [ชี้แถบ 15 ช่อง] ห้อง เลือกใหม่ได้ทุกสัปดาห์ '
                'สิ่งที่ต้องได้เรียงตามความสำคัญ [ชี้เลข 1 2 3] ทุกคาบมีห้อง ไม่มี Lab ไม่จำเป็น และย้ายห้องน้อยที่สุด '
                'ตัวเลขเดียวที่อยากให้จำ [ชี้ตัวเลข 4 ท้ายแถวล่างสุด] เรามีห้อง Lab แค่ 4 ห้องครับ'
                + qa(('ก่อนเปิดเทอมรู้อะไรบ้าง',
                      'รู้กลุ่มเรียนทั้งหมด 174 กลุ่ม เวลาที่แต่ละกลุ่มเลือกได้ ห้องและความจุ และรู้ว่ากลุ่มไหนต้องใช้ Lab สัปดาห์ไหนครับ '
                      'ข้อสุดท้ายเป็นข้อสมมติของเราว่าอาจารย์บอกสัปดาห์ Lab ได้ก่อนเปิดเทอม'),
                     ('กลุ่มเรียนในภาพคือกลุ่มไหน',
                      'กลุ่ม C1419 จากรัน GA seed 1001 แบบห้องรายสัปดาห์ครับ เรียนวันพฤหัสบดี 11:30 ทั้งเทอม '
                      'อยู่ห้องบรรยาย R96 สิบเอ็ดสัปดาห์ และอยู่ห้อง Lab ในสัปดาห์ 1, 4, 13 และ 15 ซึ่งเป็นสัปดาห์ที่ต้องใช้')),
    'questions': 'งานนี้ตอบสามคำถามครับ [ชี้เลข 1] จัดได้ครบไหม [ชี้เลข 2] วิธีค้นหาแบบไหนดีที่สุดเมื่อได้งบเท่ากัน '
                 'งบคือจำนวนตารางที่ให้อัลกอริทึมลองได้ [ชี้เลข 3] และใช้ได้ถึงขอบเขตไหน เก็บสามข้อนี้ไว้นะครับ [ชี้กรอบคำพูด] '
                 'เดี๋ยวกลับมาตอบตอนท้าย ส่วนนี้ [ชี้บรรทัดที่ขึ้นต้นว่าไม่ได้ตอบ] คือสิ่งที่งานนี้ไม่ได้ตอบ '
                 'และเทียบกับโครงร่าง [ชี้บรรทัดล่างสุด] เราเพิ่มสามอย่าง คือเทียบ 4 อัลกอริทึมตามที่อาจารย์แนะนำ '
                 'ใช้ข้อมูลจริงของ Purdue และนับการย้ายห้องครับ',
    'data': 'ขอนิยามคำก่อนครับ ดูบรรทัดตัวอย่าง [ชี้บรรทัดที่ขึ้นต้นว่าตัวอย่าง] วิชาหนึ่งมีหลายกลุ่มเรียน มีกลุ่มบรรยายกับกลุ่มปฏิบัติ '
            'แต่ละกลุ่มมีคาบ คือเวลาเรียนในหนึ่งสัปดาห์ ส่วนปฏิบัติคือส่วนที่เราสมมติว่าต้องใช้คอม '
            'และคำว่าต้องใช้ Lab คือสัปดาห์นั้นคาบนั้นต้องอยู่ห้อง Lab สัปดาห์อื่นใช้ห้องธรรมดาได้ '
            'ทีนี้ดูแถบยาวตรงกลางครับ [ชี้ตัวเลข 424 ที่ปลายซ้ายของแถบ] จาก 3,345 ช่อง มี 424 ช่องที่ต้องอยู่ห้อง Lab '
            'ส่วนนี้เราสมมติเอง'
            + qa(('ทำไมความต้องการ Lab ต้องสมมติเอง',
                  'ข้อมูลต้นฉบับของ UniTime ไม่มีห้อง Lab และไม่มีความต้องการ Lab รายสัปดาห์ครับ เราจึงสร้างเป็นสถานการณ์จำลอง '
                  'รวม 800 ชั่วโมง Lab ต่อเทอม และบอกไว้ในข้อจำกัดว่าไม่ใช่ข้อมูลจริง ส่วนของจริงคือวิชา กลุ่มเรียน เวลาที่เลือกได้ '
                  'ห้องบรรยาย และกลุ่มนักศึกษาที่ห้ามเรียนชนกัน'),
                 ('ส่วนปฏิบัติของวิชาเลือกยังไง',
                  'ต้นฉบับบอกว่าวิชามีกี่ส่วน แต่ไม่บอกว่าส่วนไหนเป็นปฏิบัติครับ ถ้าวิชามีหลายส่วน เราเลือกส่วนที่คาบยาวที่สุด '
                  'ถ้าวิชามีส่วนเดียว จะนับเป็นปฏิบัติก็ต่อเมื่อเรียนสัปดาห์ละครั้ง ข้อนี้เป็นการอนุมานของเรา '
                  'เช่นวิชา O756 กลุ่มบรรยาย C1493 รับ 60 คน เรียนสัปดาห์ละ 3 คาบ ส่วนกลุ่มปฏิบัติ C1494 และ C1495 รับกลุ่มละ 30 คน '
                  'เรียนสัปดาห์ละ 1 คาบ คาบละ 2 ชั่วโมง'),
                 ('ข้อมูลรุ่นก่อนผิดตรงไหน',
                  'รุ่นก่อนสุ่มสัปดาห์ Lab ทีละคาบครับ กลุ่มเรียนของวิชาเดียวกันเลยได้สัปดาห์ Lab ไม่ตรงกัน และคาบบรรยายก็ถูกบังคับเข้า Lab ด้วย '
                  'เราจึงเปลี่ยนเป็นกำหนดรายวิชา แล้วรันทุกการทดลองใหม่ทั้งหมด')),
    'coursedata': 'ภาพนี้บอกเรื่องเดียวครับ ความต้องการ Lab แต่ละสัปดาห์ไม่เท่ากัน ดูแท่งด้านบน [ชี้แท่งที่เขียนว่า 89] '
                  'สัปดาห์ที่มากที่สุดต้องใช้ 89 ชั่วโมง [ชี้แท่งที่เขียนว่า 9] ที่น้อยที่สุดแค่ 9 ชั่วโมง '
                  'ตารางด้านล่างคือที่มา หนึ่งแถวคือหนึ่งวิชา ดูแถวที่น้องจอคอมชี้ครับ [ชี้แถวที่เขียนว่า O756] '
                  'ทุกกลุ่มของวิชาเดียวกัน ใช้ Lab สัปดาห์เดียวกัน แต่ยังเรียนคนละเวลาได้'
                  + qa(('ทำไมทุกกลุ่มของวิชาเดียวกันต้องใช้ Lab สัปดาห์เดียวกัน',
                        'เป็นกฎของข้อมูลจำลองของเราครับ ความต้องการ Lab กำหนดเป็นรายวิชา ทุกกลุ่มของส่วนปฏิบัติจึงได้สัปดาห์ Lab ชุดเดียวกัน เช่นวิชา O756 กลุ่มปฏิบัติ C1494 และ C1495 '
                        'ใช้ Lab สัปดาห์ 2, 3, 8 และ 9 ทั้งคู่'),
                       ('อีก 24 วิชาเป็นวิชาแบบไหน',
                        'เป็นวิชาที่ไม่มีส่วนปฏิบัติตามกฎของเรา หรือไม่ถูกสุ่มเลือกครับ จาก 44 วิชา มี 27 วิชาที่มีส่วนปฏิบัติ '
                        'และเราสุ่มเลือก 20 วิชาให้ใช้ Lab')),
    'objective': 'เป้าหมายมีสามข้อ เทียบตามลำดับครับ [ชี้รายการ 1 2 3] ช่องที่ไม่มีห้องมาก่อนเสมอ แล้วจึงดู Lab ไม่จำเป็น '
                 'แล้วจึงดูจำนวนครั้งที่ย้ายห้อง ดูตัวอย่างครับ [ชี้บรรทัดที่ขึ้นต้นว่าจากรันจริง] '
                 'ถ้าห้องคงที่ เกิด Lab ไม่จำเป็น 22 ชั่วโมง ถ้าห้องเปลี่ยนรายสัปดาห์เป็นศูนย์ '
                 'ส่วนบรรทัดล่างสุด [ชี้บรรทัดที่ขึ้นต้นว่าข้อห้าม] ละเมิดไม่ได้เลยครับ [ชี้กรอบคำพูด] กฎคือกฎ'
                 + qa(('22 ชั่วโมงคิดยังไง',
                       'คาบของกลุ่ม C1422 ยาว 2 ชั่วโมงครับ ในรันห้องคงที่ กลุ่มนี้อยู่ห้อง Lab 15 สัปดาห์ แต่ต้องใช้แค่ 4 '
                       'อีก 11 สัปดาห์ คูณ 2 ชั่วโมง ได้ 22 ชั่วโมง')),
    'method': 'เราเทียบสี่วิธีครับ [ชี้ตารางสี่แถว] แต่ละวิธีเดี๋ยวเล่าพร้อมผล จุดสำคัญอยู่แถวบน [ชี้กล่องซ้าย] '
              'สิ่งที่อัลกอริทึมค้นหามีแค่ลำดับกลุ่มเรียน กับเวลาที่ลองก่อน ส่วนห้อง [ชี้กล่องกลาง] ไม่ได้ค้นหาครับ '
              'ทุกวิธีใช้กฎตายตัวชุดเดียวกัน คือห้องบรรยายก่อน ห้องเดิมของสัปดาห์ก่อน แล้วจึงห้องเล็กสุดที่จุพอ'
              + qa(('อัลกอริทึมค้นหาอะไรกันแน่',
                    'ค้นหาลำดับของกลุ่มเรียน กับเวลาที่อยากลองก่อนของแต่ละกลุ่มครับ จากนั้นตัวจัดตารางตัวเดียวกันแปลงเป็นตารางจริง '
                    'ห้องไม่ได้ค้นหา ในแต่ละสัปดาห์ตัวจัดตารางเลือกห้องที่ว่างตามลำดับ คือไม่ใช่ห้อง Lab ถ้าสัปดาห์นั้นไม่ต้องใช้ '
                    'แล้วห้องเดียวกับสัปดาห์ก่อน แล้วห้องที่ความจุน้อยที่สุด ทั้งสี่วิธีจึงต่างกันแค่วิธีค้นหาลำดับกับเวลา '
                    'และมีตัวตรวจอิสระนับผลใหม่ทุกรัน'),
                   ('ทำไมไม่ใช้ solver แบบ exact',
                    'การจัดตารางเรียนเป็นปัญหา NP-hard ครับ เราจึงใช้วิธีค้นหา และตรวจคุณภาพด้วยค่าต่ำสุดที่พิสูจน์ได้ '
                    'เช่นจำนวนครั้งย้ายห้องอย่างน้อย 596 ครั้ง')),
    'protocol': 'ก่อนรัน เราตั้งกติกาไว้ก่อนครับ [ชี้กรอบคำพูด] seed คือการรันหนึ่งครั้งที่เริ่มสุ่มต่างกัน '
                'เราใช้ seed ชุดหนึ่งไว้ปรับค่า แล้วทดสอบบนอีกชุดหนึ่ง 30 seed ทุกวิธีได้งบ 500 '
                'คือให้ลองตารางได้ 500 แบบต่อรันเท่ากันครับ ตัวเลขใหญ่ [ชี้ 240/240] คือทุกรันผ่านตัวตรวจ '
                'และ [ชี้ข้อล่างสุด] เรารันซ้ำ 16 รันด้วยโปรแกรมอีกตัวที่เขียนแยกกัน ผลตรงกันทุกรัน'
                + qa(('ใช้สถิติอะไร',
                      'กำหนดไว้ก่อนรันครับ คือ Friedman แล้วเทียบรายคู่ด้วย Wilcoxon แบบจับคู่ ปรับค่า p ด้วย Holm ที่ระดับนัยสำคัญ 0.05'),
                     ('240 รันมาจากไหน',
                      '4 วิธี คูณ 30 seed คูณ 2 โหมดห้องครับ คือห้องคงที่กับห้องรายสัปดาห์'),
                     ('SA ได้ปรับค่าอย่างยุติธรรมไหม',
                    'SA ได้ลอง 20 ชุดค่าเท่ากับ GA ครับ คือ acceptance 5 ค่า คูณ cooling 4 ค่า ส่วน HC ลอง 7 ค่า '
                    'และเมื่อค่าที่ชนะของ SA คือ acceptance 0.8 ซึ่งอยู่ขอบบน เราก็ลอง 0.95 เพิ่มอีก 4 ชุดค่า ผลไม่ดีกว่า '
                    'ค่าที่เลือกจึงเป็นค่าเริ่มต้นเดิม รวมทั้งหมด 51 ชุดค่า 510 รัน ตัวเลขในตารางเป็นค่าเฉลี่ยบน seed 1 ถึง 10'),
                   ('กฎขอบคืออะไร ตั้งเมื่อไร',
                    'ค่าที่เลือกต้องไม่อยู่ขอบของช่วงที่ลองครับ ถ้าอยู่ ต้องขยายฝั่งนั้นออกไปหนึ่งขั้นตามลำดับที่กำหนดไว้ล่วงหน้าแล้วรันเพิ่ม '
                    'กฎนี้เขียนไว้ในระเบียบวิธีก่อนเริ่มปรับค่า และใช้กับทุกวิธี'),
                   ('ทำไม HC เลือกค่าที่ Lab ไม่จำเป็นสูงกว่า',
                    'เกณฑ์คือจัดครบก่อนครับ ค่าเริ่มต้นยังเหลือช่องที่ไม่มีห้องเฉลี่ย 0.30 ช่อง ส่วนค่า 200 จัดครบทุกรัน '
                    'แม้ Lab ไม่จำเป็นจะเป็น 174.6 เทียบกับ 150.2 ชั่วโมง ส่วน GA ดีขึ้นจาก 167.2 เหลือ 102.5 ชั่วโมง'),
                     ('รู้ได้ยังไงว่า engine C# ถูก',
                    'มีสามชั้นครับ ตัวตรวจอิสระนับคะแนนใหม่ทุกรัน การรันซ้ำ 16 รันด้วยโปรแกรม Python ให้ผลตรงกันทั้งตัวชี้วัด คำตอบ '
                    'และเส้นทางการค้นหา และที่ระดับ 15 สัปดาห์ Lab ห้องรายสัปดาห์กับห้องคงที่ให้ผลเท่ากันทุกรันตามที่ควรเป็น '
                    'นอกจากนี้ CI เล่นซ้ำรันที่เก็บไว้ทั้งบน Linux และ Windows'),
                   ('ทำไมตรวจแค่ 16 รัน และเร็วกว่ากันแค่ไหน',
                    '16 รันคือ 4 วิธี 2 โหมดห้อง seed 1001 และ 1002 ครอบคลุมทุกวิธีและทุกโหมดครับ รันที่เหลือไม่ได้รันซ้ำด้วย Python '
                    'ส่วนความเร็ว รอบนี้เราไม่ได้เทียบสอง engine จึงไม่มีตัวเลข'),
                   ('โปรแกรม Python ตัวนั้นอยู่ที่ไหน',
                    'เราตรวจ 16 รันนั้นเสร็จแล้ว จึงลบโปรแกรม Python ออกจาก repository ครับ ตอนนี้เหลืออยู่ในประวัติของ git '
                    'การตรวจซ้ำชุดนี้จึงรันซ้ำจากโค้ดปัจจุบันไม่ได้ ต้องย้อนไปที่ commit ก่อนลบ')),
    'greedy': 'เริ่มผลจาก Greedy ครับ จัดทีละกลุ่ม รอบเดียวจบ เรื่องเดิมเลยครับ ห้องบรรยายเต็ม คาบบรรยายจึงล้นไปห้อง Lab '
              '[ชี้ช่องที่มีวงเล็บ] และดูตัวเลขใหญ่ตัวแรก [ชี้ตัวเลข 14] มี 14 ช่องที่ไม่มีห้องเลย [ชี้ช่องที่เขียนว่าไม่มี] '
              'สามหน้าถัดไปคือวิธีค้นหาที่งบ 500 ครับ'
              + qa(('ทำไม Greedy ถึงเหลือ 14 ช่อง',
                    'ข้อมูลบอกได้ว่าทั้ง 14 ช่องเป็นของ 7 คาบบรรยายจาก 4 กลุ่มเรียน คือ C1566, C1581, C1582 และ C1588 ครับ '
                    'ไม่ใช่สัปดาห์ที่ต้องใช้ Lab และทุกช่องนั้นห้องบรรยายที่ใช้ได้มีกลุ่มอื่นใช้อยู่ '
                    'อยู่ในสัปดาห์ 3, 4, 8, 9, 12 และ 13 และในสัปดาห์อื่นคาบเหล่านี้หลายคาบอยู่ห้อง Lab ทั้งที่ไม่ต้องใช้ '
                    'ส่วนสาเหตุเชิงลำดับการตัดสินใจ เราไม่ได้วิเคราะห์ต่อ'),
                   ('Greedy แทนคนจัดตารางได้ไหม',
                    'ไม่ได้ครับ Greedy คือกฎง่าย ๆ และเราไม่มีตารางที่คนจัดจริงมาเทียบ ผลของ Greedy เหมือนกันทุก seed เพราะไม่มีการสุ่ม')),
    'hc': 'Hill Climbing ครับ แก้ตารางทีละนิด เก็บไว้เฉพาะที่ดีขึ้น ดูเส้นจากซ้ายไปขวา [ชี้จุดเริ่มที่เขียนว่า 242] '
          'ทุกรันเริ่มจากตารางของ Greedy แล้วเส้นลดลงตั้งแต่ต้น [ชี้ปลายเส้นที่น้องจอคอมยืนอยู่] จบที่ 169.4 ชั่วโมง '
          'และยังลดอยู่ตอนงบหมด แถวล่างสุดใต้กราฟ [ชี้แถวที่เขียนว่ารันที่จัดครบ] คือจำนวนรันที่ทุกช่องมีห้องครับ'
          + qa(('เส้นนี้คำนวณยังไง',
                'ทุกรันเก็บตารางที่ดีที่สุดที่พบไว้ทุกครั้งที่ลองครับ เส้นคือค่าเฉลี่ย Lab ไม่จำเป็นของตารางนั้นจาก 30 seed '
                'ที่ครั้งที่ 100 อยู่ที่ 220.5 ชั่วโมง ครั้งที่ 300 อยู่ที่ 190.8 และจบที่ 169.4 จัดครบ 26 จาก 30 รัน')),
    'sa': 'Simulated Annealing ครับ ช่วงแรกยอมรับตารางที่แย่ลงได้บ้าง ดูช่วงซ้ายของเส้น [ชี้เส้นช่วงครั้งที่ 1 ถึง 100] '
          'ร้อยครั้งแรกเส้นแทบไม่ขยับ จากนั้นจึงลดลง [ชี้ปลายเส้นที่น้องจอคอมยืนอยู่] จบที่ 145.8 ชั่วโมง '
          'และยังลดอยู่ตอนงบหมดเช่นกันครับ'
          + qa(('ทำไมร้อยครั้งแรกเส้นไม่ลง',
                'ที่เห็นจากข้อมูลคือ ที่ครั้งที่ 100 ค่าเฉลี่ยอยู่ที่ 242.1 ชั่วโมง เท่ากับจุดเริ่ม แต่จำนวนรันที่จัดครบเพิ่มจาก 0 เป็น 9 แล้วครับ '
                'คือช่วงนั้นช่องที่ไม่มีห้องลดลงก่อนตามลำดับเป้าหมาย ส่วนจะเกี่ยวกับการยอมรับตารางที่แย่ลงแค่ไหน เราไม่ได้ทดลองแยก')),
    'ga': 'Genetic Algorithm ครับ เก็บตารางไว้หลายชุดแล้วเอามาผสมกัน ดูช่วงแรกของเส้น [ชี้ยอดเส้นใกล้จุดเริ่ม] '
          'เส้นขึ้นก่อน ช่วงนั้นช่องที่ไม่มีห้องลดลงก่อนตามลำดับเป้าหมาย จากนั้นเส้นลดลงต่อเนื่อง '
          '[ชี้ปลายเส้นที่น้องจอคอมยืนอยู่] จบที่ 146.9 ชั่วโมง ใกล้ SA มากครับ'
          + qa(('ทำไมเส้นขึ้นได้ ทั้งที่เก็บตารางที่ดีที่สุด',
                'เพราะดีที่สุดวัดจากช่องที่ไม่มีห้องก่อนครับ ตารางที่มีช่องไม่มีห้องน้อยกว่าชนะเสมอ แม้ Lab ไม่จำเป็นจะมากกว่า '
                'ที่ครั้งที่ 50 ค่าเฉลี่ยขึ้นไปที่ 246.8 ชั่วโมง แต่มี 8 รันที่จัดครบแล้ว จากนั้นลดลงเหลือ 146.9 จัดครบ 28 จาก 30 รัน')),
    'main': 'เอาสี่วิธีมาวางข้างกันครับ ดูแท่งขวาสุดก่อน [ชี้แท่งที่เขียนว่า Greedy] สูงที่สุด ส่วนสามแท่งทางซ้าย '
            '[ชี้แท่งที่น้องจอคอมยืนอยู่] คือวิธีค้นหา ดีกว่า Greedy ทุก seed แต่ยังจัดไม่ครบทุกรันครับ '
            'สามวิธี วิธีละ 30 รัน รวม 90 รัน จัดครบ 83 รัน และสามแท่งนี้สูงพอ ๆ กัน [ชี้ข้อล่างสุด] '
            'สถิติยังบอกไม่ได้ว่าใครดีกว่ากัน ตัวเลขนี้เป็นของงบน้อยนะครับ'
            + qa(('ทำไมโหมดรายสัปดาห์ยังมีช่องที่ไม่มีห้อง',
                  'ที่งบ 500 มี 7 จาก 90 รันที่เหลือ 1 ถึง 2 ช่องครับ HC จัดครบ 26 รัน SA 29 รัน และ GA 28 รัน '
                  'และในการศึกษางบบน 10 seed เมื่อให้งบตั้งแต่ 1,000 ขึ้นไป ทุกรันของทุกวิธีจัดครบทุกช่อง'),
                 ('ตัวเลขบนแท่งคืออะไร',
                  'ค่าเฉลี่ย Lab ไม่จำเป็นของ 30 seed ครับ SA 145.8 ชั่วโมง GA 146.9 HC 169.4 และ Greedy 242'),
                     ('สถิติที่ใช้คืออะไร ผลเป็นเท่าไร',
                   'Friedman ได้ไคสแควร์ 56.44 ค่า p น้อยกว่า 0.001 ครับ อันดับเฉลี่ย SA 1.83 GA 1.87 HC 2.30 และ Greedy 4.00 '
                   'เทียบรายคู่ด้วย Wilcoxon ปรับ Holm ทั้งสามวิธีดีกว่า Greedy ใน 30 จาก 30 seed'),
                  ('ทำไมสามวิธีถึงไม่ต่างกัน',
                   'ที่งบ 500 ทั้งสามชนะกันไปมาครับ เช่น SA ดีกว่า GA 16 seed แพ้ 14 seed ค่า p ของสามคู่คือ 0.102, 0.102 และ 0.666 '
                   'ส่วนต่างของค่าเฉลี่ยเล็กกว่าความแกว่งระหว่าง seed'),
                  ('ทำไมใช้ Friedman กับ Wilcoxon',
                   'ทุกวิธีรันบน seed ชุดเดียวกัน ข้อมูลจึงจับคู่กันครับ และเราเทียบเป้าหมายแบบเรียงลำดับ จึงใช้สถิติแบบอันดับ '
                   'แล้วปรับ Holm เพราะเทียบ 6 คู่')),
    'source': 'แล้ว Lab ไม่จำเป็นที่เหลือมาจากไหน เราไล่ดูทุกรันครับ เรื่องเดิมอีกแล้ว ดูตัวเลขใหญ่ [ชี้ 100%] '
              'ทั้งหมดเกิดตอนที่ห้องบรรยายเต็ม และดูแถบนอน [ชี้แถบแถวที่เขียนว่า GA] '
              'เกือบทั้งหมดเป็นคาบบรรยายที่ล้นไปห้อง Lab เราจึงตีความว่า [ชี้บรรทัดที่ขึ้นต้นว่าการตีความ] '
              'คอขวดคือห้องบรรยาย ไม่ใช่ห้อง Lab ข้อนี้ยังไม่ได้ทดสอบครับ'
              + qa(('ตัวเลขแต่ละวิธีเป็นเท่าไร',
                    'คาบบรรยายคือคาบที่ไม่ต้องใช้ Lab เลย ส่วนคาบวิชา Lab คือคาบของวิชาที่ใช้ Lab ในสัปดาห์ที่ไม่ต้องใช้ครับ '
                    'GA เป็นคาบบรรยาย 135.7 ชั่วโมง กับคาบวิชา Lab 11.2 ชั่วโมง SA 140.6 กับ 5.2 HC 163.9 กับ 5.5 '
                    'และ Greedy 226 กับ 16'),
                   ('ทำไมห้องบรรยายถึงไม่พอ',
                    'ที่เรารู้คือ ทุกชั่วโมงของ Lab ไม่จำเป็นเกิดตอนที่ห้องบรรยายที่ใช้ได้มีกลุ่มเรียนอื่นใช้อยู่ครับ '
                    'เราตีความว่าคาบที่ไม่ต้องใช้ Lab เลย 117 คาบแย่งห้องบรรยาย 13 ห้องกัน ซึ่งข้อนี้ยังไม่ได้ทดสอบโดยตรง')),
    'budget': 'เราเลยให้งบเพิ่มเป็นร้อยเท่าครับ ดูตัวเลขตัวเดียว [ชี้ตัวเลข 0.0 ในคอลัมน์ SA] ตั้งแต่งบ 10,000 '
              'SA ไม่เหลือ Lab ไม่จำเป็นเลยทุกรัน [ชี้กรอบคำพูด] ศูนย์จริง ๆ ไม่ได้พิมพ์ผิด ส่วนอีกสองวิธียังเหลืออยู่ '
              'วิธีไหนดีที่สุดจึงขึ้นกับงบครับ แต่ [ชี้ข้อล่างสุด] ทุกวิธีปรับค่าที่งบ 500 แล้วใช้ค่าเดิมที่งบใหญ่ '
              'จึงอาจไม่แฟร์กับ HC และ GA'
              + qa(('ทำไมวิธีที่ดีที่สุดขึ้นกับงบ',
                    'ที่เราเห็นคือ ที่งบ 500 สามวิธียังแยกกันไม่ได้ ที่งบ 50,000 SA ดีกว่า HC ทั้ง 10 seed และดีกว่า GA 9 จาก 10 seed '
                    'ค่า p 0.012 ครับ ส่วน GA กับ HC ไม่ต่างกัน สาเหตุเชิงกลไกเราไม่ได้ทดลองแยก'),
                   ('ทำไมบอกว่าอาจไม่แฟร์กับ HC และ GA',
                    'ค่าพารามิเตอร์ของทั้งสามวิธีเลือกจากการปรับที่งบ 500 ครับ HC ได้ restart patience 200 GA ได้ชุดประชากร 12 '
                    'ส่วน SA ได้ค่าเริ่มต้นเดิม แล้วเราใช้ค่าชุดนี้กับทุกงบ ไม่ได้ปรับใหม่ที่งบ 50,000 '
                    'ผลจึงบอกได้ว่าลำดับของวิธีขึ้นกับงบ แต่ยังบอกไม่ได้ว่าวิธีไหนดีที่สุดเมื่อปรับค่าที่งบใหญ่แล้ว'),
                   ('ทำไมไม่รัน 50,000 ทุกการทดลอง',
                    'กติกาที่ตั้งไว้ก่อนคืองบ 500 เท่ากันทุกวิธีครับ การศึกษางบทำเพิ่มบน 10 seed คือ 1001 ถึง 1010 เพื่อดูว่าข้อสรุปเปลี่ยนไหม '
                    'และเราบอกไว้ในข้อจำกัดว่างบ 500 น้อย'),
                   ('ที่งบมาก จัดครบและย้ายห้องเป็นยังไง',
                    'ตั้งแต่งบ 1,000 ทุกรันของทุกวิธีจัดครบทุกช่องครับ และที่งบ 50,000 การย้ายห้องอยู่ที่ 596 ถึง 600 ครั้ง '
                    'เทียบกับค่าต่ำสุดที่ข้อมูลบังคับ 596 ครั้ง')),
    'changes': 'ห้องเปลี่ยนได้ แล้วต้องย้ายห้องบ่อยแค่ไหน ดูแท่งซ้ายสุดครับ [ชี้แท่งที่เขียนว่าต่ำสุด] '
               '596 ครั้งคือจำนวนที่ข้อมูลบังคับอยู่แล้ว เพราะคาบที่ใช้ Lab บางสัปดาห์ต้องสลับเข้าออกห้อง Lab '
               'ส่วนสามแท่งทางขวา [ชี้แท่ง GA SA HC] คือของเรา สูงกว่านิดเดียว ราว 620 ครั้งครับ'
               + qa(('ถ้าใช้ห้องคงที่ล่ะ',
                     'ไม่ต้องย้ายห้องเลยครับ แต่ Lab ไม่จำเป็นเพิ่มจากราว 154 เป็นราว 2,035 ชั่วโมงต่อเทอม '
                     'และยังมีช่องที่ไม่มีห้องเฉลี่ย 179 ถึง 199 ช่อง แท่งที่เขียนว่าต่ำสุดคือจำนวนที่ข้อมูลบังคับ'),
                    ('ตัวเลขแต่ละวิธีเป็นเท่าไร',
                     'GA เฉลี่ย 617.8 ครั้ง SA 619.7 และ HC 624.4 ครับ คือ 1.04 ถึง 1.05 เท่าของค่าต่ำสุด')),
    'scarcity': 'ขอเริ่มจากข่าวไม่ดีครับ เราลองลดห้อง Lab ลง ดูแถวเดียว [ชี้แถวที่เขียนว่า 3 ห้อง] พอเหลือ 3 ห้อง '
                'วิธีค้นหาจัดครบได้ไม่ถึงครึ่งของรัน [ชี้กรอบคำพูด] เกือบครบ แต่ไม่ครบ '
                'เราจึงพูดไม่ได้ว่าประหยัดห้อง Lab ได้หนึ่งห้องที่งบนี้ ส่วนคอลัมน์ขวาสุด [ชี้คอลัมน์ที่เขียนว่าห้องคงที่] '
                'ห้องคงที่ไม่มีห้องมากกว่าทุกแถวครับ'
                + qa(('ถ้าให้งบมากขึ้น Lab 3 ห้องจะจัดครบไหม',
                      'ที่งบ 500 เราเห็นว่าจัดครบ 1 ถึง 4 จาก 10 รัน และเหลือเฉลี่ย 1.5 ถึง 3.8 ช่องครับ '
                      'ส่วนงบที่มากกว่านี้กับ Lab 3 ห้อง ยังไม่ได้ทดลอง'),
                     ('ตัวเลขห้องคงที่ทำไมเป็นช่วง',
                      'เป็นค่าเฉลี่ยของ HC SA และ GA ครับ จากทั้งหมด 3,345 ช่อง เช่นที่ 3 ห้องคือ 520.5, 505.5 และ 507.0 ช่อง และที่ 2 ห้อง '
                      'ห้องรายสัปดาห์เหลือ 32 ถึง 40 ช่อง ส่วนห้องคงที่ 858 ถึง 867 ช่อง')),
    'labweeks': 'คำถามข้อสามครับ ใช้ได้ถึงไหน เราเพิ่มจำนวนสัปดาห์ที่วิชาใช้ Lab ดูคอลัมน์ขวาสุด [ชี้คอลัมน์ที่เขียนว่าจัดครบ] '
                'ถึง 4 สัปดาห์ยังจัดครบเกือบทุกรัน พอ 6 สัปดาห์ [ชี้เส้นเหนือแถวที่เขียนว่า 6] ไม่มีรันไหนจัดครบเลย '
                'ขอบเขตที่งบนี้จึงอยู่ระหว่าง 4 กับ 6 สัปดาห์ครับ'
                + qa(('ขอบเขต 4 ถึง 6 สัปดาห์เป็นของปัญหาหรือของงบ',
                      'ที่งบ 500 เราเห็นว่าระดับ 4 สัปดาห์จัดครบ 9 ถึง 10 จาก 10 รัน และระดับ 6 สัปดาห์ไม่มีรันไหนครบ เหลือราว 9 ถึง 10 ช่องครับ '
                      'ส่วนระดับ 6 สัปดาห์ที่งบมากกว่านี้ยังไม่ได้ทดลอง'),
                     ('แถว 15 สัปดาห์บอกอะไร',
                      'เป็นการตรวจระบบครับ เมื่อวิชาใช้ Lab ทุกสัปดาห์ ห้องรายสัปดาห์กับห้องคงที่ต้องให้ผลเท่ากัน ซึ่งก็เท่ากันทุกรัน '
                      'จากทั้งหมด 640 รัน'),
                     ('ทำไมไม่มีระดับ 5 สัปดาห์ และเทียบกับ Greedy เป็นยังไง',
                      'เราทดลอง 8 ระดับครับ คือ 1, 2, 4, 6, 8, 10, 12 และ 15 และยิ่ง Lab ตึง วิธีค้นหายิ่งห่างจาก Greedy '
                      'เช่นที่ 12 สัปดาห์ Greedy เหลือ 193 ช่อง วิธีค้นหาเหลือ 80 ถึง 90 ช่อง')),
    'limits': 'ข้อจำกัดครับ [ชี้กรอบคำพูด] ยังไม่เพอร์เฟกต์ ข้อแรก ความต้องการ Lab เป็นสิ่งที่เราสมมติ '
              'ข้อสอง [ชี้ข้อที่สอง] ห้องคงที่ของเราคือห้องเดียวทั้งเทอมแบบเคร่ง เราไม่ได้เทียบกับการจอง Lab เฉพาะสัปดาห์ที่ใช้ '
              'ตัวเทียบนี้จึงอาจแย่กว่าที่คนจัดจริงทำ ข้อสาม ค่าพารามิเตอร์ปรับที่งบ 500 เท่านั้น '
              'ข้อสี่ งบ 500 น้อย ข้อสรุปหลายข้อจึงขึ้นกับงบครับ'
              + qa(('ห้องคงที่ในงานนี้คืออะไร',
                    'คาบหนึ่งได้ห้องเดียวทั้ง 15 สัปดาห์ครับ กลุ่มที่ต้องใช้ Lab จึงต้องอยู่ห้อง Lab ทั้งเทอม '
                    'หรือไม่มีห้องในสัปดาห์ที่ห้องนั้นใช้ไม่ได้ เราไม่ได้ทดลองแบบที่อยู่ห้องบรรยายเป็นหลัก แล้วจอง Lab เฉพาะสัปดาห์ที่ใช้ '
                    'ซึ่งคนจัดจริงอาจทำ ผลต่างระหว่างสองโหมดจึงเป็นผลเทียบกับตัวเทียบที่เคร่ง'),
                   ('ในชีวิตจริง ห้องรายสัปดาห์ดีกว่าห้องคงที่ไหม',
                    'ที่เรารู้คือ บนโจทย์ที่เราตั้ง ห้องรายสัปดาห์มีช่องที่ไม่มีห้องและ Lab ไม่จำเป็นน้อยกว่าห้องคงที่มากครับ '
                    'ส่วนในมหาวิทยาลัยจริง งานนี้ตอบไม่ได้ เพราะความต้องการ Lab เป็นข้อมูลจำลอง ไม่มีตารางจริงมาเทียบ '
                    'และยังไม่ได้วัดต้นทุนของการย้ายห้องต่อนักศึกษา')),
    'conclude': 'สรุปครับ ทั้งหมดนี้เป็นผลบนโจทย์ที่เราตั้งขึ้น ไม่ใช่ข้อสรุปเรื่องมหาวิทยาลัยจริง กลับมาตอบสามคำถาม '
                'ข้อหนึ่ง [ชี้ข้อ 1] วิธีค้นหาจัดได้เกือบครบที่งบน้อย และครบทุกรันเมื่อให้งบมากขึ้น '
                'ข้อสอง [ชี้ข้อ 2] วิธีที่ดีที่สุดขึ้นกับงบ งบน้อยยังแยกไม่ได้ งบมาก SA ดีที่สุด '
                'ข้อสาม [ชี้ข้อ 3] เริ่มจัดไม่ครบเมื่อวิชาใช้ Lab 6 สัปดาห์ หรือเมื่อเหลือห้อง Lab 3 ห้อง ขอบคุณครับ '
                '[ชี้น้องจอคอมที่โบกมือ]'
                + qa(('แล้วควรเอาไปใช้จริงไหม',
                      'ที่เรารู้คือแนวคิดนี้จัดได้บนข้อมูลจำลองของเราครับ ส่วนการใช้จริงต้องมีข้อมูลความต้องการ Lab ของวิชาจริง '
                      'และต้องวัดผลของการย้ายห้องต่อนักศึกษาก่อน ซึ่งเป็นงานต่อยอด'),
                     ('ถ้าทำต่อจะทำอะไรก่อน',
                      'ใช้ข้อมูลวิชาจริงแทนข้อมูลจำลองครับ แล้วทดลองที่งบใหญ่ขึ้น เพราะข้อสรุปหลายข้อขึ้นกับงบ')),
    'refs': 'หน้านี้คือเอกสารอ้างอิงหลักครับ ชื่อผู้แต่งกับปีตรงกับบรรทัดที่มาใต้แต่ละหน้า',
    'refs-methods': 'หน้านี้คืออ้างอิงของอัลกอริทึมและสถิติที่ใช้ครับ',
    'refs-recent': 'หน้าสุดท้ายคืองานใหม่ที่ใกล้เราที่สุดครับ [ชี้รายการแรก] งานของ Cavalcante พบว่ากฎแบบ Greedy ดีกว่าคนจัดเอง '
                   'แต่แพ้วิธีที่ค้นหาจริงจังครับ',
}


# One line at the bottom of a slide: which claim on it comes from which work (full entries on the reference slides).
CITES = {
    'problem': 'ใช้ห้อง 20–50%: Li, Zhao &amp; Xue (2026) / สาเหตุจากการจัดตาราง: Beyrouthy et al. (2009)',
    'whyhard': 'ย้ายห้องง่ายกว่าย้ายเวลา: Raviv (2026)',
    'approach': 'สูตรตั้งต้น: ITC2007 / ห้องรายสัปดาห์: Han &amp; Wang (2025)',
    'data': 'ข้อมูล: UniTime pu-fal07-cs / Lab จำลองแบบเดียวกับ Cavalcante et al. (2026)',
    'objective': 'เป้าหมายแบบเรียงลำดับ: ITC2007, Lemos et al. (2019)',
    'method': 'Müller (2009) / Bellio et al. (2016) / Davis (1985) / Goldberg &amp; Deb (1991)',
    'protocol': 'งบเท่ากัน: Bellio et al. (2016) / Friedman: Demšar (2006) / ปรับค่า p: Holm (1979)',
    'main': 'Cavalcante et al. (2026) / สถิติ: Demšar (2006), Holm (1979)',
    'changes': 'นับการเปลี่ยนห้องเป็นต้นทุน: Ozkan et al. (2025), Antunes-Batista et al. (2026)',
    'scarcity': 'จำนวน Lab เป็นข้อจำกัดหลักเช่นกัน: Cavalcante et al. (2026)',
    'limits': 'ผลด้านคนวัดได้ เช่น ระยะเดิน: Raviv (2026)',
}


def footnote(text):
    return (f'<p style="position:absolute;left:140px;right:280px;bottom:44px;font-size:32px;line-height:1.4;'
            f'color:#777777">ที่มา: {text}</p>')


def main():
    unknown = set(CITES) - set(SLIDES)
    if unknown:
        raise SystemExit(f'CITES names slides that do not exist: {sorted(unknown)}')
    if set(NOTES) != set(SLIDES):
        raise SystemExit(f'SLIDES and NOTES name different slides: {sorted(set(NOTES) ^ set(SLIDES))}')
    slides = []
    for number, (sid, note) in enumerate(NOTES.items(), 1):
        title, body = SLIDES[sid]
        cover = sid == 'cover'
        html = (body if cover else h2(title) + body) + (
            '' if cover else f'<p style="position:absolute;right:140px;bottom:56px;width:120px;font-size:24px;'
                             f'color:#777777;text-align:right">{number}</p>') + (footnote(CITES[sid]) if sid in CITES else '')
        slides.append({'id': sid, 'title': title.replace('|', ': '), 'style': f'background:#FFFFFF;{PAD}', 'html': html, 'note': note})
    controller = (HERE / 'controller.js').read_text(encoding='utf-8')
    data = json.dumps(slides, ensure_ascii=False)
    (HERE / 'slides.json').write_text(json.dumps(slides, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (HERE / 'deck.js').write_text(f'const slides = {data};\n{controller}', encoding='utf-8')
    notes = ['# บทพูด', '']
    for number, s in enumerate(slides, 1):
        notes += [f'## หน้า {number} {s["title"]}', '', s['note'].replace('\n', '\n\n'), '']
    (HERE / 'speaker-notes.md').write_text('\n'.join(notes), encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')  # slide titles are Thai; a Windows console may default to cp1252
    # Spoken length: the script without the Q&A block and without the [stage cues].
    spoken = [len(re.sub(r' ?\[[^\]]*\]', '', s['note'].split(ASK)[0])) for s in slides]
    for number, (s, n) in enumerate(zip(slides, spoken), 1):
        print(f'{number:2d} {s["id"]:13s} {n:4d} {"Q&A " if ASK in s["note"] else "    "}{s["title"]}')
    for algorithm, (hours, done) in CURVES.items():
        print(f'curve {algorithm}: Lab hours at evaluations {MARKS} = {[round(hours[e], 1) for e in MARKS]}, '
              f'complete runs at {TICKS} = {[done[e] for e in TICKS]}')
    longest = sorted(zip(spoken, (s['id'] for s in slides)), reverse=True)[:3]
    print(f'{len(slides)} slides, {sum(spoken)} spoken script characters (limit about {SCRIPT_LIMIT}), longest: '
          + ', '.join(f'{sid} {n}' for n, sid in longest))
    if sum(spoken) > SCRIPT_LIMIT:
        print(f'WARNING: the main scripts are {sum(spoken) - SCRIPT_LIMIT} characters over the 15-minute length')


if __name__ == '__main__':
    main()
