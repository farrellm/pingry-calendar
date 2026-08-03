// Two behaviours: the spine reads out the day under the pointer, and opening a
// feed isolates its dates everywhere else on the page. Without JS the accordion
// still opens and every date is still readable — only the highlighting is lost.

(() => {
  const sheet = document.querySelector('.sheet');
  const ticks = document.querySelector('.spine__ticks');
  const readout = document.getElementById('readout');
  const feeds = [...document.querySelectorAll('.feed')];

  const dayFormat = new Intl.DateTimeFormat('en-GB', {
    weekday: 'short', day: 'numeric', month: 'long', year: 'numeric',
  });

  // --- spine readout -------------------------------------------------

  if (ticks && readout) {
    const idle = readout.dataset.idle;

    ticks.addEventListener('pointermove', (event) => {
      const tick = event.target.closest('.tick');
      if (!tick) return;
      // dataset.d is an ISO date; append T00 so it is read as local, not UTC.
      const label = dayFormat.format(new Date(`${tick.dataset.d}T00:00`));
      readout.innerHTML = tick.dataset.l
        ? `${label} — <b>${tick.dataset.l}</b>`
        : label;
    });

    ticks.addEventListener('pointerleave', () => { readout.textContent = idle; });
  }

  // --- one feed open at a time, and it isolates ----------------------

  feeds.forEach((feed) => {
    feed.addEventListener('toggle', () => {
      if (feed.open) {
        feeds.forEach((other) => { if (other !== feed) other.open = false; });
        sheet.dataset.iso = feed.dataset.cat;
      } else if (sheet.dataset.iso === feed.dataset.cat) {
        delete sheet.dataset.iso;
      }
    });
  });
})();
