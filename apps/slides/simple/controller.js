const stage = document.querySelector('#stage'), toc = document.querySelector('#toc');
const position = document.querySelector('#position'), progress = document.querySelector('#progress');
const prevButton = document.querySelector('#prev'), nextButton = document.querySelector('#next');
const notes = document.querySelector('#notes'), notesButton = document.querySelector('#notes-toggle');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
const escapeAttr = s => s.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
// Forward transitions that zoom into a small spot on the current slide which turns out to be the next slide.
const ZOOMS = [];
let page = 0, running = [];

stage.innerHTML = slides.map((s, i) =>
  `<section class="slide" id="slide-${s.id}" data-page="${i}" aria-label="${i + 1}. ${escapeAttr(s.title)}" style="${s.style}">${s.html}</section>`
).join('');
slides.forEach((s, i) => {
  const option = document.createElement('option');
  option.value = i;
  option.textContent = `${i + 1}. ${s.title}`;
  toc.append(option);
});
// Stagger index for chart animations, per slide and per kind.
[...stage.children].forEach(slide => ['grow-y', 'grow-x', 'dot', 'cell', 'mean'].forEach(kind =>
  slide.querySelectorAll(`.${kind}`).forEach((el, i) => el.style.setProperty('--i', i))));

const slideScale = () => +getComputedStyle(document.documentElement).getPropertyValue('--scale') || 1;

function chrome() {
  [...stage.children].forEach((el, i) => {
    el.classList.toggle('active', i === page);
    el.setAttribute('aria-hidden', i !== page);
  });
  toc.value = page;
  position.textContent = `${page + 1} / ${slides.length}`;
  progress.style.width = `${(page + 1) / slides.length * 100}%`;
  prevButton.disabled = page === 0;
  nextButton.disabled = page === slides.length - 1;
  showNote();
  history.replaceState(null, '', `#${page + 1}`);
}

function play(slide) {
  slide.classList.remove('play');
  void slide.offsetWidth;
  slide.classList.add('play');
}

function settle() {
  running.forEach(a => a.cancel());
  running = [];
  stage.querySelectorAll('.leaving, .entering').forEach(el => {
    el.classList.remove('leaving', 'entering');
    el.style.removeProperty('transform-origin');
  });
}

function animate(el, keyframes, options) {
  const a = el.animate(keyframes, { fill: 'both', ...options });
  running.push(a);
  return a.finished.catch(() => {});
}

function fade(from, to, dir) {
  from.classList.add('leaving');
  to.classList.add('entering');
  animate(from, [{ opacity: 1 }, { opacity: 0 }], { duration: 180, easing: 'ease-in' });
  return animate(to, [
    { opacity: 0, transform: `translateY(${dir * 24}px)` },
    { opacity: 1, transform: 'translateY(0)' }
  ], { duration: 320, delay: 80, easing: 'cubic-bezier(.2,.8,.2,1)' });
}

function zoom(from, to, spotText) {
  const spot = [...from.querySelectorAll('p, h2, h3')].find(el => el.textContent.trim() === spotText) || from;
  const r = spot.getBoundingClientRect(), s = stage.getBoundingClientRect(), k = slideScale();
  const x = (r.left + r.width / 2 - s.left) / k, y = (r.top + r.height / 2 - s.top) / k;
  const K = 60, steps = 32, ease = t => t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
  const origin = `${x}px ${y}px`;
  from.style.transformOrigin = origin;
  to.style.transformOrigin = origin;
  from.classList.add('leaving');
  to.classList.add('entering', 'zoom-dot');
  // 1. a tiny copy of the next slide pops up on the spot, 2. the camera dives into it.
  const pop = animate(to, [
    { transform: 'scale(0)', opacity: 0 },
    { transform: `scale(${1.6 / K})`, opacity: 1, offset: 0.7 },
    { transform: `scale(${1 / K})`, opacity: 1 }
  ], { duration: 420, easing: 'ease-out' });
  return pop.then(() => {
    if (!to.classList.contains('entering')) return;
    const outer = [], inner = [];
    for (let i = 0; i <= steps; i++) {
      const f = K ** ease(i / steps);
      outer.push({ transform: `scale(${f})`, opacity: i > steps * 0.85 ? 0 : 1 });
      inner.push({ transform: `scale(${f / K})` });
    }
    to.classList.remove('zoom-dot');
    animate(from, outer, { duration: 1100, delay: 250 });
    return animate(to, inner, { duration: 1100, delay: 250 });
  });
}

function go(i) {
  i = Math.max(0, Math.min(slides.length - 1, i));
  if (i === page) return;
  settle();
  const from = stage.children[page], to = stage.children[i];
  const forward = i > page;
  const z = forward && i === page + 1 && ZOOMS.find(z => z.from === slides[page].id && z.to === slides[i].id);
  from.classList.add('leaving'); // keep it laid out so the zoom spot can be measured
  page = i;
  chrome();
  if (reduceMotion.matches) { play(to); return; }
  if (z) {
    to.classList.remove('play');
    zoom(from, to, z.spot).then(() => { if (stage.children[page] === to) { settle(); play(to); } });
  } else {
    play(to);
    fade(from, to, forward ? 1 : -1).then(() => { if (stage.children[page] === to) settle(); });
  }
}

// Speaker script of the current slide, in a panel under the stage (button or N). Closed on every load.
function showNote() {
  if (notes.hidden) return;
  notes.replaceChildren(...slides[page].note.split('\n').map(line => {
    const p = document.createElement('p');
    p.textContent = line;
    if (line.startsWith('———')) p.className = 'ask';
    else if (line.startsWith('ถาม:')) p.className = 'question';
    return p;
  }));
  notes.scrollTop = 0;
}
function toggleNotes() {
  notes.hidden = !notes.hidden;
  notesButton.setAttribute('aria-pressed', !notes.hidden);
  document.body.classList.toggle('notes-open', !notes.hidden);
  showNote();
  scale();
}

async function full() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch (e) {
    document.querySelector('#full').textContent = 'ใช้เต็มจอของเบราว์เซอร์';
  }
}
function scale() {
  const navHeight = document.querySelector('nav').offsetHeight;
  const room = innerHeight - navHeight - notes.offsetHeight; // the notes panel is 0 high while hidden
  document.documentElement.style.setProperty('--scale', Math.min(innerWidth / 1920, room / 1080));
}

prevButton.addEventListener('click', () => go(page - 1));
nextButton.addEventListener('click', () => go(page + 1));
toc.addEventListener('change', () => go(+toc.value));
document.querySelector('#full').addEventListener('click', full);
// Drop focus after the click so the arrow keys keep turning slides.
notesButton.addEventListener('click', () => { toggleNotes(); notesButton.blur(); });
addEventListener('keydown', e => {
  if (/INPUT|SELECT|TEXTAREA|BUTTON|A/.test(e.target.tagName)) return;
  if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); go(page + 1); }
  if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) { e.preventDefault(); go(page - 1); }
  if (e.key === 'Home') go(0);
  if (e.key === 'End') go(slides.length - 1);
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key.toLowerCase() === 'f') full();
  if (e.key.toLowerCase() === 'n') toggleNotes();
});
addEventListener('hashchange', () => {
  const m = location.hash.match(/^#(\d+)/);
  if (m && +m[1] - 1 !== page) go(+m[1] - 1);
});
addEventListener('resize', scale);
addEventListener('fullscreenchange', scale);
scale();
const match = location.hash.match(/^#(\d+)/);
if (match) page = Math.min(slides.length - 1, Math.max(0, +match[1] - 1));
chrome();
if (!reduceMotion.matches) play(stage.children[page]);
