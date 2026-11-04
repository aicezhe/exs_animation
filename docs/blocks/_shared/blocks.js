/* The one list of the 12 notebook blocks: the How page draws its tiles from it, swipe.js and the block pages find their neighbours in it.
   animated: the block has its own animation page (a folder here); the others open the code page (code/index.html?block=N).
   href is relative to docs/blocks/ and ends with index.html, so it also works from file://. */
const ANIM = { 1: '01-imports', 2: '02-data', 3: '03-sound', 4: '04-clips', 5: '05-mfcc', 6: '06-split', 7: '07-model', 8: '08-training', 9: '09-evaluation' };
window.EXS_BLOCKS = [
  [1, 'Imports', 'Libraries and settings'], [2, 'Dataset', 'From files to a table'], [3, 'Sound', 'From a wave to numbers'],
  [4, 'Clips', 'Make every clip 1 second'], [5, 'MFCC', 'The 99 × 13 matrix'], [6, 'Split', 'Train, validation, test'],
  [7, 'Model', 'A small CNN'], [8, 'Training', 'Learning from examples'], [9, 'Evaluation', 'Accuracy and errors'],
  [10, 'Quantization', 'Shrink to int8'], [11, 'Deployment', 'Board to laptop'], [12, 'Experiments', 'What moves the accuracy'],
].map(([n, title, subtitle]) => ({ n, title, subtitle, animated: n in ANIM,
  href: n in ANIM ? './' + ANIM[n] + '/index.html' : './code/index.html?block=' + n }));

/* Animation pages: the kicker and the previous / next links follow the list above. */
document.addEventListener('DOMContentLoaded', () => {
  const N = parseInt(document.body && document.body.dataset.block, 10);
  if (!N) return;
  const all = window.EXS_BLOCKS, me = all.find(b => b.n === N); if (!me) return;
  const prev = all.find(b => b.n === N - 1) || null, next = all.find(b => b.n === N + 1) || null;
  const page = b => '../' + b.href.replace(/^\.\//, '');
  const k = document.querySelector('.kicker');
  if (k) k.textContent = 'Block ' + N + ' of ' + all.length;
  // link back: the previous block (none at the start)
  document.querySelectorAll('.prevblock, a.back[href^="../0"]').forEach(a => {
    if (prev) { a.href = page(prev); a.textContent = '\u2190 Previous: ' + prev.title; } else a.remove();
  });
  // link on: the next block, or back to the blocks after the last one
  const o = document.getElementById('onward');
  if (o) {
    if (next) { o.href = page(next); o.textContent = 'Next block: ' + next.title + ' \u2192'; }
    else { o.href = '../index.html#how'; o.textContent = 'Back to blocks'; }
    o.removeAttribute('aria-disabled');
  }
});
