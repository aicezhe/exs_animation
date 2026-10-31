/* The one list of blocks: the home page draws its cards from it, swipe.js finds the neighbours in it.
   href is relative to docs/blocks/. A block opens only when ready is true.
   nb = the block number in the notebook. The main tour shows only the blocks without hidden: true;
   to bring the others back, delete hidden: true from their lines. Hidden pages stay open by their direct address. */
window.EXS_BLOCKS = [
  { n: 1, nb: 1, hidden: true,  title: 'Imports',      sub: 'Libraries and settings',    href: './01-imports/', ready: true },
  { n: 2, nb: 2, hidden: true,  title: 'Dataset',      sub: 'From files to a table',     href: './02-data/',    ready: true },
  { n: 3, nb: 3,  title: 'Sound',        sub: 'From a wave to numbers',    href: './03-sound/',   ready: true, chip: 'animation' },
  { n: 4, nb: 4, hidden: true,  title: 'Clips',        sub: 'Make every clip 1 second',  href: './04-clips/',   ready: true },
  { n: 5, nb: 5, hidden: true,  title: 'MFCC',         sub: 'The 99 × 13 matrix',        href: './05-mfcc/',    ready: true, chip: 'animation' },
  { n: 6, nb: 6,  title: 'Split',        sub: 'Train, validation, test',   href: './06-split/',   ready: true },
  { n: 7, nb: 7,  title: 'Model',        sub: 'A small CNN',               href: './07-model/',   ready: true },
  { n: 8, nb: 8,  title: 'Training',     sub: 'Learning from examples',    href: './08-training/', ready: true },
  { n: 9, nb: 9,  title: 'Evaluation',   sub: 'Accuracy and errors',       href: './09-evaluation/', ready: true },
  { n: 10, nb: 10, hidden: true, title: 'Quantization', sub: 'Shrink to int8',            href: null,            ready: false },
  { n: 11, nb: 11, hidden: true, title: 'Deployment',   sub: 'Board to laptop',           href: null,            ready: false },
  { n: 12, nb: 12, hidden: true, title: 'Experiments',  sub: 'What moves the accuracy',   href: null,            ready: false },
];

/* The main tour: the visible blocks in order. Everything that counts or links blocks reads this list. */
window.EXS_TOUR = window.EXS_BLOCKS.filter(b => !b.hidden);
window.EXS_NOTEBOOK_TOTAL = window.EXS_BLOCKS.length;

/* Block pages: the kicker, the "not in the main tour" mark, and the previous / next links follow the tour. */
document.addEventListener('DOMContentLoaded', () => {
  const N = parseInt(document.body && document.body.dataset.block, 10);
  if (!N) return;
  const me = window.EXS_BLOCKS.find(b => b.n === N); if (!me) return;
  const tour = window.EXS_TOUR, idx = tour.indexOf(me);
  const prev = tour.filter(b => b.n < N).pop() || null, next = tour.find(b => b.n > N) || null;
  const page = b => '../' + b.href.replace(/^\.\//, '') + 'index.html';
  const k = document.querySelector('.kicker');
  if (k) {
    k.textContent = (idx >= 0 ? 'Key block ' + (idx + 1) + ' of ' + tour.length + ' \u00b7 notebook block ' + me.nb
      : 'Notebook block ' + me.nb + ' of ' + window.EXS_NOTEBOOK_TOTAL);
    if (idx < 0) {
      const note = document.createElement('div'); note.className = 'exs-note'; note.textContent = 'not in the main tour';
      note.style.cssText = 'font:12px var(--mono);color:var(--muted);letter-spacing:.08em;margin-bottom:4px';
      k.parentNode.insertBefore(note, k);
    }
  }
  // links back: the previous block of the tour (or none at the start)
  document.querySelectorAll('.prevblock, a.back[href^="../0"]').forEach(a => {
    if (prev) { a.href = page(prev); a.textContent = '\u2190 Previous: ' + prev.title; } else a.remove();
  });
  // link on: the next block of the tour, or back to the blocks after the last one
  const o = document.getElementById('onward');
  if (o) {
    if (next) { o.href = page(next); o.textContent = 'Next block: ' + next.title + ' \u2192'; o.removeAttribute('aria-disabled'); }
    else { o.href = '../index.html#how'; o.textContent = 'Back to blocks'; o.removeAttribute('aria-disabled'); }
  }
});
