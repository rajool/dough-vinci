/* Dough-Vinci «Nero»: plain JavaScript, no dependencies.
   Everything here is an enhancement: without it every Order link jumps to the red Order band on the same page, every
   dish opens its own page, and the hours show what was true when the site was built. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const html = document.documentElement;
  const ROOT = html.dataset.root || "";
  const D = JSON.parse(($("#dv-data") || {}).textContent || "{}");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canIO = "IntersectionObserver" in window;

  /* ── open now, in Pacific time ──
     Before the opening date: «Opening» and the date, or only its part of the month («Opening early Dec») while the date
     is approximate, with no weekday or day. While the site is a preview after that: no open-now claim. Live: «Open now · until 10 pm», «Closed · opens
     11 am». ?now=2026-12-11T19:30 checks a moment. */
  const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  const fmtT = (hm) => { let [h, m] = hm.split(":").map(Number); const s = h < 12 ? "am" : "pm"; h = h % 12 || 12; return `${h}${m ? ":" + String(m).padStart(2, "0") : ""} ${s}`; };
  const toMin = (hm) => { const [h, m] = hm.split(":").map(Number); return h * 60 + m; };
  function vanNow() {
    const q = new URLSearchParams(location.search).get("now");
    if (q && /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(q)) {
      const [d, t] = q.split("T");
      const [y, mo, da] = d.split("-").map(Number);
      return { date: d, day: DAYS[new Date(Date.UTC(y, mo - 1, da)).getUTCDay()], mins: toMin(t) };
    }
    const f = new Intl.DateTimeFormat("en-CA", { timeZone: D.tz || "America/Vancouver", year: "numeric", month: "2-digit", day: "2-digit", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    const p = {}; f.formatToParts(new Date()).forEach((x) => { p[x.type] = x.value; });
    return { date: `${p.year}-${p.month}-${p.day}`, day: p.weekday.slice(0, 3).toLowerCase(), mins: (+p.hour % 24) * 60 + +p.minute };
  }
  const fmtDate = (iso, long) => {
    const [y, m, d] = iso.split("-").map(Number);
    const at = new Date(Date.UTC(y, m - 1, d, 12));
    if (D.approx) {
      const mon = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: long ? "long" : "short" }).format(at);
      return d <= 10 ? `early ${mon}` : d <= 20 ? `mid-${mon}` : `late ${mon}`;
    }
    const opts = { timeZone: "UTC", month: "short", day: "numeric" }; if (long) opts.weekday = "short";
    return new Intl.DateTimeFormat("en-US", opts).format(at);
  };
  const hoursFor = (day) => (D.hours || []).find((h) => h.days.includes(day));
  function openState() {
    const n = vanNow();
    if (D.opening && n.date < D.opening) return { state: "soon", short: `Opening ${fmtDate(D.opening)}`, long: `Opening ${fmtDate(D.opening, true)}`, day: n.day };
    if (D.preview) return { state: "", short: "", long: "See the hours", day: n.day };
    const h = hoursFor(n.day);
    if (!h) return { state: "closed", short: "Closed today", long: "Closed today", day: n.day };
    const o = toMin(h.open), c = toMin(h.close);
    if (n.mins >= o && n.mins < c) return { state: "open", short: `Open now · until ${fmtT(h.close)}`, long: `Open now · until ${fmtT(h.close)}`, day: n.day };
    if (n.mins < o) return { state: "closed", short: `Closed · opens ${fmtT(h.open)}`, long: `Closed · opens ${fmtT(h.open)}`, day: n.day };
    const nx = hoursFor(DAYS[(DAYS.indexOf(n.day) + 1) % 7]);
    const t = nx ? `Closed · opens ${fmtT(nx.open)} tomorrow` : "Closed now";
    return { state: "closed", short: t, long: t, day: n.day };
  }
  function paintOpen() {
    const s = openState();
    $$("[data-status]").forEach((el) => {
      const text = el.dataset.status === "short" ? s.short : s.long;
      el.textContent = text;
      el.hidden = !text;
      el.dataset.state = s.state;
    });
    $$(".hours tr[data-days]").forEach((tr) => {
      const today = tr.dataset.days.split(" ").includes(s.day);
      tr.classList.toggle("is-today", today);
      const t = $(".hours__today", tr); if (t) t.hidden = !today;
    });
  }
  paintOpen(); setInterval(paintOpen, 60000);

  /* ── reveal: fades and slides, and the colour wipe of the Order band; nothing moves under reduced motion ── */
  const rv = $$(".rv, .wipe");
  if (reduce || !canIO) rv.forEach((el) => el.classList.add("in"));
  else {
    const io = new IntersectionObserver((es) => es.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
    }), { rootMargin: "0px 0px -6% 0px" });
    rv.forEach((el) => io.observe(el));
  }
  addEventListener("beforeprint", () => rv.forEach((el) => el.classList.add("in")));
  html.classList.add("js-on"); // the reveal runs: the inline fallback in <head> leaves the classes alone

  /* ── the phone Order bar: after the hero, on phones only; the header's Order button steps aside while it shows ── */
  const hero = $("[data-hero]");
  if ($("[data-mbar]") && hero && canIO) {
    const phone = matchMedia("(max-width: 899px)");
    let past = false;
    const sync = () => html.classList.toggle("mbar-on", past && phone.matches);
    new IntersectionObserver(([en]) => { past = !en.isIntersecting && en.boundingClientRect.top < 0; sync(); }).observe(hero);
    phone.addEventListener("change", sync);
  }

  /* ── dialogs: Order and the dish sheet (native modal dialogs trap focus; focus returns to the opener) ── */
  const orderDlg = $("#order-dialog");
  const dishDlg = $("#dish-dialog");
  const canDialog = !!(orderDlg && typeof orderDlg.showModal === "function");
  const openers = new Map();
  // Cleanup runs on our own close paths and again on the native close event (Escape), whichever comes first: some
  // browsers deliver the close event late in a background tab.
  function cleanup(dlg) {
    if (dlg._clean) return;
    dlg._clean = true;
    const another = $("dialog[open]");
    if (!another) html.style.overflow = "";
    if (dlg === dishDlg && location.hash.startsWith("#dish=")) history.replaceState(null, "", location.pathname + location.search);
    const o = openers.get(dlg);
    if (!another && o && o.isConnected && typeof o.focus === "function") o.focus({ preventScroll: true });
  }
  function closeDialog(dlg) { if (dlg.open) dlg.close(); cleanup(dlg); }
  function openDialog(dlg, from) {
    const other = $("dialog[open]");
    openers.set(dlg, other && other !== dlg ? openers.get(other) : (from || document.activeElement));
    dlg._clean = false;
    if (!dlg.open) dlg.showModal();
    if (other && other !== dlg) closeDialog(other); // the dish sheet hands over to the Order sheet
    html.style.overflow = "hidden";
    const h = $("[data-dish-title], .os__h", dlg);
    if (h) h.focus({ preventScroll: true });
  }
  if (canDialog) {
    [orderDlg, dishDlg].forEach((dlg) => {
      dlg.addEventListener("click", (e) => { if (e.target === dlg) closeDialog(dlg); }); // the backdrop
      dlg.addEventListener("close", () => cleanup(dlg));
      dlg.addEventListener("cancel", () => setTimeout(() => { if (!dlg.open) cleanup(dlg); }, 0)); // Escape
    });
  }
  let fragP = null;
  const frags = () => {
    if (!fragP) {
      fragP = fetch(ROOT + "assets/dishes.html").then((r) => (r.ok ? r.text() : Promise.reject(new Error(r.status))))
        .then((t) => new DOMParser().parseFromString(t.split("__ROOT__").join(ROOT), "text/html"));
      fragP.catch(() => { fragP = null; });
    }
    return fragP;
  };
  async function openDish(id, from, href) {
    let doc;
    // a tap is acknowledged at once if the sheets are still on their way
    const slow = from ? setTimeout(() => { from.setAttribute("aria-busy", "true"); from.classList.add("is-wait"); }, 150) : 0;
    try { doc = await frags(); } catch (_) { if (href) location.href = href; return; }
    finally { clearTimeout(slow); if (from) { from.removeAttribute("aria-busy"); from.classList.remove("is-wait"); } }
    const tpl = doc.querySelector(`template[data-dish="${CSS.escape(id)}"]`);
    if (!tpl) { if (href) location.href = href; return; }
    const slot = $("[data-dish-slot]", dishDlg);
    slot.replaceChildren(document.importNode(tpl.content, true));
    const h = $("[data-dish-title]", slot); if (h) h.id = "dish-dialog-title";
    dishDlg.classList.toggle("is-text", !!$(".dd--text", slot));
    openDialog(dishDlg, from);
    $(".sheet__in", dishDlg).scrollTop = 0;
    history.replaceState(null, "", location.pathname + location.search + "#dish=" + id);
  }
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const x = e.target.closest("[data-close]");
    if (x) { closeDialog(x.closest("dialog")); return; }
    const o = e.target.closest("[data-order]");
    if (o && canDialog) { e.preventDefault(); openDialog(orderDlg, o); return; }
    const d = e.target.closest("a[data-dish]");
    if (d && canDialog && dishDlg) { e.preventDefault(); openDish(d.dataset.dish, d, d.href); }
  });
  if (canDialog) {
    $$("[data-order]").forEach((a) => a.setAttribute("aria-haspopup", "dialog"));
    $$("a[data-dish]").forEach((a) => a.setAttribute("aria-haspopup", "dialog"));
    if (location.hash.startsWith("#dish=")) openDish(decodeURIComponent(location.hash.slice(6)), null, null);
    if (location.hash === "#order-now") openDialog(orderDlg, null);
  }
  // the dish sheets (one file) load on intent (a pointer or focus on any dish link) or once the page is idle,
  // so a tap on a slow phone opens its sheet at once
  if ($("a[data-dish]") && canDialog) {
    const evs = ["pointerover", "focusin", "touchstart"];
    const warm = (e) => {
      if (e && !(e.target.closest && e.target.closest("a[data-dish]"))) return;
      evs.forEach((t) => document.removeEventListener(t, warm, true));
      frags().catch(() => {});
    };
    evs.forEach((t) => document.addEventListener(t, warm, { capture: true, passive: true }));
    const idle = () => (window.requestIdleCallback || ((f) => setTimeout(f, 1500)))(() => warm(), { timeout: 4000 });
    if (document.readyState === "complete") idle(); else addEventListener("load", idle, { once: true });
  }

  /* ── menu: filters (Vegetarian, Spicy, Gluten-free option), each section says when nothing in it matches ── */
  const togs = $$(".tog[data-filter]");
  const clear = $("[data-clear]");
  const say = $("[data-filter-status]");
  // each section's count line keeps its built text, and says how many of its dishes show while a filter is on
  const counts = $$(".cat").map((c) => [c, $(".cat__n", c)]).filter(([, n]) => n);
  counts.forEach(([, n]) => { n.dataset.all = n.textContent; });
  function applyFilters() {
    const on = togs.filter((t) => t.getAttribute("aria-pressed") === "true").map((t) => t.dataset.filter);
    let shown = 0, all = 0;
    $$(".row").forEach((r) => {
      const ok = on.every((f) => r.dataset[f] === "true");
      r.hidden = !ok; all++; if (ok) shown++;
    });
    $$(".strip__i").forEach((s) => { s.hidden = !on.every((f) => s.dataset[f] === "true"); });
    $$(".board").forEach((b) => { const none = b.querySelector(".row:not([hidden])") === null; $(".board__none", b).hidden = !none; });
    // a board column left without dishes goes (unless the whole board is empty), so the other reads as one list
    $$(".board__col").forEach((c) => {
      c.hidden = !c.querySelector(".row:not([hidden])") && !!c.closest(".board").querySelector(".row:not([hidden])");
    });
    $$(".strip").forEach((s) => {
      const n = $$(".strip__i:not([hidden])", s).length;
      s.hidden = !n;
      if (on.length) s.dataset.shown = String(n); else s.removeAttribute("data-shown");
    });
    counts.forEach(([c, n]) => {
      const rows = $$(".row", c), vis = rows.filter((r) => !r.hidden).length;
      n.textContent = on.length ? `${vis} of ${rows.length} ${rows.length === 1 ? "dish" : "dishes"} shown.` : n.dataset.all;
    });
    if (clear) clear.hidden = !on.length;
    if (say) {
      const names = togs.filter((t) => on.includes(t.dataset.filter)).map((t) => t.textContent.toLowerCase());
      say.textContent = on.length ? `${shown} of ${all} dishes: ${names.join(" and ")}.` : `All ${all} dishes shown.`;
    }
  }
  togs.forEach((t) => t.addEventListener("click", () => { t.setAttribute("aria-pressed", String(t.getAttribute("aria-pressed") !== "true")); applyFilters(); }));
  if (clear) clear.addEventListener("click", () => { togs.forEach((t) => t.setAttribute("aria-pressed", "false")); applyFilters(); togs[0].focus(); });

  /* ── menu: the section tabs follow the scroll ──
     The current section is the last one whose top has passed 35% of the screen, or the first when none has, so the bar
     is right after any scroll, back to the top included. */
  const tabsNav = $("[data-tabs]");
  if (tabsNav) {
    const tabs = $$("a[data-tab]", tabsNav);
    const sc = $(".cats__nav", tabsNav);
    let cur = "";
    const mark = (id) => {
      if (id === cur) return; cur = id;
      const t = tabs.find((x) => x.dataset.tab === id);
      // layout is read before any attribute changes, so a section change costs one style pass, not a forced layout
      const left = t && sc && sc.scrollWidth > sc.clientWidth ? t.offsetLeft - 16 : null;
      tabs.forEach((x) => { if (x === t) x.setAttribute("aria-current", "true"); else x.removeAttribute("aria-current"); });
      if (left !== null) sc.scrollTo({ left, behavior: reduce ? "auto" : "smooth" });
    };
    const secs = $$("[data-spy]");
    let ticking = false;
    const pick = () => {
      ticking = false;
      const line = innerHeight * 0.35;
      let id = secs[0] ? secs[0].id : "";
      for (const s of secs) { if (s.getBoundingClientRect().top <= line) id = s.id; else break; }
      if (id) mark(id);
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(pick); } }, { passive: true });
    addEventListener("resize", pick);
    pick();
  }
})();
