// Three behaviours: the spine reads out the day under the pointer, opening a
// feed isolates its dates everywhere else on the page, and clicking a day in the
// month grids opens a popup describing it. Without JS the accordion still opens
// and every date is still readable in the feed rows — only these lose out.

(() => {
  const sheet = document.querySelector('.sheet');
  const ticks = document.querySelector('.spine__ticks');
  const readout = document.getElementById('readout');
  const feeds = [...document.querySelectorAll('.feed')];

  const dayFormat = new Intl.DateTimeFormat('en-GB', {
    weekday: 'short', day: 'numeric', month: 'long', year: 'numeric',
  });
  const longDayFormat = new Intl.DateTimeFormat('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  // An ISO date read as local rather than UTC, so the weekday never slips.
  const asLocalDate = (iso) => new Date(`${iso}T00:00`);

  // --- spine readout -------------------------------------------------

  if (ticks && readout) {
    const idle = readout.dataset.idle;

    ticks.addEventListener('pointermove', (event) => {
      const tick = event.target.closest('.tick');
      if (!tick) return;
      const label = dayFormat.format(asLocalDate(tick.dataset.d));
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

  // --- clicking a day in the month grids -----------------------------

  const pop = document.getElementById('daypop');
  const island = document.getElementById('day-events');
  const months = document.querySelector('.months');
  if (!pop || !island || !months) return;

  const dayEvents = JSON.parse(island.textContent);
  // Older engines predate the popover API; there the popup is a plain element
  // shown by class, with dismissal wired up by hand below.
  const native = typeof pop.showPopover === 'function';
  let openDay = null;
  // Light dismiss fires on pointerdown, before our click handler runs, so a
  // second click on the open day would close it and then reopen it. Remember
  // what just closed and let that click fall through instead.
  let justClosed = null;
  let justClosedAt = 0;

  const escapeHtml = (text) => text.replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const render = (iso) => {
    const entries = dayEvents[iso] || [];
    return `<p class="daypop__date">${escapeHtml(longDayFormat.format(asLocalDate(iso)))}</p>`
      + entries.map((entry) => `<div class="daypop__event">
          <p class="daypop__name">${escapeHtml(entry.name)}</p>
          ${entry.description ? `<p class="daypop__desc">${escapeHtml(entry.description)}</p>` : ''}
          ${entry.categories.map((category) => `<p class="daypop__cat">
            <span class="daypop__chip" style="--c:var(--${category.key})"></span>
            ${escapeHtml(category.name)}</p>`).join('')}
        </div>`).join('');
  };

  // Fixed coordinates, so re-run this whenever the page moves under the popup.
  const place = () => {
    if (!openDay) return;
    const cell = openDay.getBoundingClientRect();
    const box = pop.getBoundingClientRect();
    const margin = 8;

    let top = cell.bottom + 6;
    if (top + box.height > innerHeight - margin) {
      const above = cell.top - box.height - 6;
      top = above >= margin ? above : Math.max(margin, innerHeight - box.height - margin);
    }
    let left = cell.left + cell.width / 2 - box.width / 2;
    left = Math.min(Math.max(margin, left), innerWidth - box.width - margin);

    pop.style.top = `${Math.round(top)}px`;
    pop.style.left = `${Math.round(left)}px`;
  };

  const close = ({ refocus = false } = {}) => {
    const day = openDay;
    openDay = null;
    if (native) { if (pop.matches(':popover-open')) pop.hidePopover(); }
    else pop.classList.remove('is-open');
    if (refocus && day) day.focus();
  };

  const open = (day) => {
    openDay = day;
    pop.innerHTML = render(day.dataset.d);
    if (native) { if (!pop.matches(':popover-open')) pop.showPopover(); }
    else pop.classList.add('is-open');
    place();
    pop.focus();
  };

  months.addEventListener('click', (event) => {
    const day = event.target.closest('.day[data-d]');
    if (!day) return;
    if (openDay === day) { close({ refocus: true }); return; }
    if (justClosed === day && performance.now() - justClosedAt < 400) {
      justClosed = null;
      return;
    }
    open(day);
  });

  // The platform fires this for Esc and for light dismiss; keep openDay in step.
  // showPopover() has no invoker to restore focus to, so hand it back ourselves
  // when the popup was holding it — otherwise Esc drops the user at the top.
  pop.addEventListener('toggle', (event) => {
    if (event.newState !== 'closed') return;
    const wasInside = pop.contains(document.activeElement);
    justClosed = openDay;
    justClosedAt = performance.now();
    const day = openDay;
    openDay = null;
    if (wasInside && day) day.focus();
  });

  if (!native) {
    document.addEventListener('click', (event) => {
      if (openDay && !pop.contains(event.target) && !event.target.closest('.day[data-d]')) close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && openDay) close({ refocus: true });
    });
  }

  // Capture, because scroll does not bubble — this catches the page scrolling
  // and any nested scroller alike.
  document.addEventListener('scroll', place, { capture: true, passive: true });
  addEventListener('resize', place);
})();
