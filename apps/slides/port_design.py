"""Port Claude Design deck (project/deck.json + slides/*.html) -> apps/slides.

Re-run after editing the draft in Claude Design (download its project/ files first).
Writes slides.json, the `slides` array line of deck.js, and speaker-notes.md so the
three stay identical. Usage: python apps/slides/port_design.py <draft project dir> <apps/slides dir>
"""
import json, re, sys, pathlib

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
deck = json.loads((src / 'deck.json').read_text(encoding='utf-8'))

ANIMATE_BARS_Y = {'changes', 'scarcity'}
ANIMATE_BARS_X = {'stats', 'csharp'}
ANIMATE_DOTS = {'main'}
ANIMATE_DRAW = {'budget'}
ANIMATE_CELLS = {'problem', 'perweek'}
FALLBACK_TITLES = {'protocol': 'กติกาการทดลอง', 'perweek': 'ตัวอย่าง Lab ห้องเดียว: ห้องคงที่เทียบห้องรายสัปดาห์'}
CHECK_CIRCLE = ('<svg class="x-icon" viewBox="0 0 24 24" aria-hidden="true" style="{style}">'
                '<circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/>'
                '<path d="M7.5 12.5l3 3 6-6.5" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"/></svg>')

def text(fragment):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', fragment)).replace('&nbsp;', ' ').strip()

slides = []
for i, sid in enumerate(deck['order'], 1):
    html = (src / 'slides' / f'{sid}.html').read_text(encoding='utf-8')
    note_match = re.search(r'<aside>(.*?)</aside>', html, re.S)
    note = text(note_match.group(1)) if note_match else ''
    html = re.sub(r'\s*<aside>.*?</aside>', '', html, flags=re.S)
    html = re.sub(r'<x-shape kind="arrow-right" style="([^"]*)"></x-shape>',
                  r'<div class="x-arrow" aria-hidden="true" style="\1"></div>', html)
    html = re.sub(r'<x-shape kind="line" style="([^"]*)"></x-shape>',
                  r'<div class="x-line" aria-hidden="true" style="\1"></div>', html)
    html = re.sub(r'<x-icon name="CheckCircle" style="([^"]*)"></x-icon>',
                  lambda m: CHECK_CIRCLE.format(style=m.group(1)), html)
    assert '<x-' not in html, f'unconverted custom tag in {sid}'
    # Animation hooks (style.css): bars grow, dots pop, line chart draws, grid cells appear.
    if sid in ANIMATE_BARS_Y:
        html = re.sub(r'<div style="(width:(?:160|120)px; height:)', r'<div class="grow-y" style="\1', html)
    if sid in ANIMATE_BARS_X:
        html = re.sub(r'<div style="(width:\d+px; height:56px;)', r'<div class="grow-x" style="\1', html)
    if sid in ANIMATE_DOTS:
        html = html.replace('<circle ', '<circle class="dot" ').replace('<rect x=', '<rect class="mean" x=')
    if sid in ANIMATE_DRAW:
        html = html.replace('<svg ', '<svg class="reveal-x" ', 1)
    if sid in ANIMATE_CELLS:
        html = re.sub(r'<p style="(width:(?:86|150)px; padding:12px 0)', r'<p class="cell" style="\1', html)
    # The section tag becomes the slide container; keep its inline style.
    section = re.match(r'\s*<section id="[^"]+"[^>]*?style="([^"]*)"[^>]*>(.*)</section>\s*$', html, re.S)
    assert section, sid
    style, inner = section.group(1), section.group(2).strip()
    heading = re.search(r'<h[12][^>]*>(.*?)</h[12]>', inner, re.S)
    title = text(heading.group(1)) if heading and text(heading.group(1)) else FALLBACK_TITLES.get(sid, sid)
    slides.append({'id': sid, 'title': title, 'style': style, 'html': inner, 'note': note})

payload = json.dumps(slides, ensure_ascii=False)
(dst / 'slides.json').write_text(json.dumps(slides, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
deck_js = (dst / 'deck.js').read_text(encoding='utf-8').split('\n', 1)[1]
(dst / 'deck.js').write_text(f'const slides = {payload};\n' + deck_js, encoding='utf-8')

notes = ['# บทพูดประกอบสไลด์ · Final Presentation', '',
         f'สไลด์ {len(slides)} หน้า ประมาณ 12–15 นาที เนื้อหาเดียวกับฟิลด์ `note` ใน `slides.json` และ `deck.js` '
         'ตัวเลขผลทดลองทุกตัวมาจากไฟล์ใน `experiments/`', '']
for i, s in enumerate(slides, 1):
    notes += [f'## {i}. {s["title"]}', '', s['note'] or '(ไม่มีบทพูด)', '']
(dst / 'speaker-notes.md').write_text('\n'.join(notes), encoding='utf-8')
print(len(slides), 'slides')
