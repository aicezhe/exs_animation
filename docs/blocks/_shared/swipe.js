/* Two-finger swipe between blocks: a trackpad swipe (wheel) or two fingers on a touch screen.
   Fingers moving left go to the next block, fingers moving right go to the previous one.
   Goes through all 12 blocks; before the first block it returns to the blocks, after the last it stays.
   Reads the block number from <body data-block="N"> and the neighbours from window.EXS_BLOCKS.
   One-finger gestures are left alone unless the page has data-swipe1; pinches are always left alone. Works from file:// (links end with index.html). */
(() => {
  'use strict';
  const N = parseInt(document.body && document.body.dataset.block, 10);
  const list = window.EXS_BLOCKS || [];   // all 12 blocks: an animation page where there is one, otherwise the code page
  if (!N) return;
  const prev = list.filter(b => b.n < N).pop() || null, next = list.find(b => b.n > N) || null;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const url = b => '../' + b.href.replace(/^\.\//, '');
  const WHEEL_MIN = 90, LOCK_MS = 800, SHIFT = 40, FADE_MS = 200;
  const TOUCH_DX = 70, TOUCH_MS = 700, PINCH_MAX = .15;

  const css = document.createElement('style');
  css.textContent = `
    html, body { overscroll-behavior-x: none; }
    body.exs-sw { transition: transform ${FADE_MS}ms ease, opacity ${FADE_MS}ms ease; }
    body.exs-out-next { transform: translateX(-${SHIFT}px); opacity: 0; }
    body.exs-out-prev { transform: translateX(${SHIFT}px); opacity: 0; }
    body.exs-in-next { transform: translateX(${SHIFT}px); opacity: 0; }
    body.exs-in-prev { transform: translateX(-${SHIFT}px); opacity: 0; }
    body.exs-bump-next { transform: translateX(-14px); }
    body.exs-bump-prev { transform: translateX(14px); }
    #exs-toast { position: fixed; z-index: 30; left: 50%; bottom: 112px; transform: translate(-50%, 8px); max-width: calc(100vw - 32px);
      padding: 9px 16px; border-radius: 999px; border: 1px solid var(--panel-border); background: var(--panel); color: var(--ink);
      font: 13px var(--body); box-shadow: var(--panel-glow); opacity: 0; pointer-events: none; transition: opacity .2s, transform .2s; text-align: center; }
    #exs-toast.on { opacity: 1; transform: translate(-50%, 0); }`;
  document.head.appendChild(css);

  const toast = document.createElement('div'); toast.id = 'exs-toast'; toast.setAttribute('role', 'status'); document.body.appendChild(toast);
  let toastTimer = 0;
  function say(text, ms) {
    toast.textContent = text; toast.classList.add('on'); clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('on'), ms);
  }

  // arriving from another block: slide in from the opposite side
  let dir = null;
  try { dir = sessionStorage.getItem('exs-dir'); sessionStorage.removeItem('exs-dir'); } catch (e) { /* no storage: no animation */ }
  if ((dir === 'next' || dir === 'prev') && !reduce) {
    document.body.classList.add('exs-in-' + dir);
    requestAnimationFrame(() => requestAnimationFrame(() => { document.body.classList.add('exs-sw'); document.body.classList.remove('exs-in-' + dir); }));
  }
  addEventListener('pageshow', e => { if (e.persisted) document.body.classList.remove('exs-out-next', 'exs-out-prev'); });

  // the first visit: a hint
  try {
    if (!localStorage.getItem('exs-swipe-hint')) { localStorage.setItem('exs-swipe-hint', '1'); setTimeout(() => say('Swipe with two fingers to change block', 3000), 600); }
  } catch (e) { /* private mode: no hint */ }

  let lockedUntil = 0;
  const locked = () => performance.now() < lockedUntil;
  function go(d) {   // d = 1: next, -1: previous
    if (locked()) return;
    lockedUntil = performance.now() + LOCK_MS;
    const target = d > 0 ? next : prev, name = d > 0 ? 'next' : 'prev';
    if (!target && d < 0) {   // before the first block of the tour: back to the blocks
      if (reduce) { location.href = '../index.html#how'; return; }
      document.body.classList.add('exs-sw', 'exs-out-prev');
      setTimeout(() => { location.href = '../index.html#how'; }, FADE_MS);
      return;
    }
    if (!target) {
      say('This is the last block', 1500);
      if (!reduce) {
        const b = document.body; b.classList.add('exs-sw', 'exs-bump-' + name);
        setTimeout(() => b.classList.remove('exs-bump-' + name), 140);
      }
      return;
    }
    try { sessionStorage.setItem('exs-dir', name); } catch (e) { /* ignore */ }
    if (reduce) { location.href = url(target); return; }
    document.body.classList.add('exs-sw', 'exs-out-' + name);
    setTimeout(() => { location.href = url(target); }, FADE_MS);
  }

  window.EXS_GO = go;   // used by tapstep.js: a tap or arrow key past the last / first step changes the block

  // trackpad: a horizontal-dominant wheel gesture, summed until it is long enough
  let sum = 0, sumT = 0;
  addEventListener('wheel', e => {
    if (e.ctrlKey || Math.abs(e.deltaX) <= 1.5 * Math.abs(e.deltaY)) return;   // vertical or a pinch-zoom: not ours
    e.preventDefault();   // no browser back/forward
    if (locked()) { sum = 0; return; }   // the inertia of the last swipe
    const t = performance.now(); if (t - sumT > 250) sum = 0; sumT = t;
    sum += e.deltaX;
    if (Math.abs(sum) >= WHEEL_MIN) { const d = sum > 0 ? 1 : -1; sum = 0; go(d); }
  }, { passive: false });

  // touch: exactly two fingers moving together sideways
  let g = null;
  const mid = ts => ({ x: (ts[0].clientX + ts[1].clientX) / 2, y: (ts[0].clientY + ts[1].clientY) / 2, d: Math.hypot(ts[0].clientX - ts[1].clientX, ts[0].clientY - ts[1].clientY) });
  // pages with data-swipe1 (no one-finger drags inside) also accept one finger moving sideways
  const one = document.body.hasAttribute('data-swipe1'); let f = null;
  addEventListener('touchstart', e => {
    if (e.touches.length === 2) { g = { ...mid(e.touches), t: performance.now() }; f = null; }
    else if (e.touches.length > 2) { g = null; f = null; }
    else if (one) f = { x: e.touches[0].clientX, y: e.touches[0].clientY, t: performance.now() };
  }, { passive: true });
  addEventListener('touchend', e => {
    if (!f || e.touches.length) return;
    const s = f, c = e.changedTouches[0]; f = null;
    const dx = c.clientX - s.x, dy = c.clientY - s.y;
    if (performance.now() - s.t < TOUCH_MS && Math.abs(dx) >= TOUCH_DX && Math.abs(dx) >= 1.5 * Math.abs(dy)) go(dx < 0 ? 1 : -1);
  }, { passive: true });
  addEventListener('touchmove', e => { if (g && e.touches.length === 2) g.last = mid(e.touches); else if (e.touches.length !== 2) { /* one finger lifted: the end decides */ } }, { passive: true });
  addEventListener('touchend', e => {
    if (!g) return;
    const s = g, l = s.last; g = null;
    if (!l || performance.now() - s.t > TOUCH_MS) return;
    const dx = l.x - s.x, dy = l.y - s.y, pinch = Math.abs(l.d - s.d) / Math.max(1, s.d);
    if (Math.abs(dx) >= TOUCH_DX && Math.abs(dx) >= 1.5 * Math.abs(dy) && pinch < PINCH_MAX) go(dx < 0 ? 1 : -1);
  }, { passive: true });
  addEventListener('touchcancel', () => { g = null; }, { passive: true });
})();
