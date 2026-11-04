/* Dough-Vinci · Codex Vivo · plain JavaScript, no dependencies.
   Everything here is an enhancement: without it every Order link jumps to the delivery band, every dish opens its
   own page, and every drawing is a finished picture. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const html = document.documentElement;
  const ROOT = html.dataset.root || "";
  const D = JSON.parse(($("#dv-data") || {}).textContent || "{}");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canIO = "IntersectionObserver" in window;
  const raf2 = (fn) => requestAnimationFrame(() => requestAnimationFrame(fn));
  html.classList.add("ready");
  const motion = canIO && !reduce;
  if (motion) html.classList.add("io");

  /* ── Pause motion (ribbons, seal, pulses) ── */
  const MKEY = "dv-motion-off";
  function setMotion(off, save) {
    html.classList.toggle("motion-off", off);
    $$("[data-motion]").forEach((b) => {
      b.setAttribute("aria-pressed", String(off));
      const u = $("use", b); if (u) u.setAttribute("href", off ? "#i-play" : "#i-pause");
    });
    if (save) { try { localStorage.setItem(MKEY, off ? "1" : ""); } catch (_) { /* private mode */ } }
  }
  let stored = ""; try { stored = localStorage.getItem(MKEY) || ""; } catch (_) { /* ignore */ }
  setMotion(!!stored || reduce, false);
  $$("[data-motion]").forEach((b) => b.addEventListener("click", () => setMotion(b.getAttribute("aria-pressed") !== "true", true)));

  /* ── reveal on scroll: sections slide in, mirror notes turn readable ── */
  const rvSel = ".sec-head, .study, .ctile, .combo, .fly__head, .leaf, .vteaser__info, .imola, .astudy, .dgrid__i, .faq__q, .cater__in, .about__head";
  if (motion) {
    // The observer's first report says where each piece is without forcing a layout: only what starts below the fold
    // is hidden (.rv) to slide in later; what is already on screen or above it is left alone.
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        const el = en.target;
        const mirror = el.classList.contains("mirror");
        if (!el._seen) {
          el._seen = true;
          const fold = en.rootBounds ? en.rootBounds.bottom : innerHeight * 0.9;
          if (!mirror && !en.isIntersecting && en.boundingClientRect.top >= fold) { el.classList.add("rv"); return; }
          if (!mirror) { io.unobserve(el); return; }
        }
        if (en.isIntersecting) { el.classList.add("in"); io.unobserve(el); }
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.1 });
    $$(rvSel + ", .mirror").forEach((el) => io.observe(el));
  }
  addEventListener("beforeprint", () => $$(".rv, .mirror, .ink").forEach((el) => el.classList.add("in")));

  /* ── drawings: inline the SVG file when it comes near, so it can ink itself ── */
  const svgCache = new Map();
  const getSvg = (url) => {
    if (!svgCache.has(url)) svgCache.set(url, fetch(url).then((r) => (r.ok ? r.text() : Promise.reject(new Error(r.status)))));
    return svgCache.get(url);
  };
  function inlineSvg(el) {
    if (el._inline) return el._inline;
    el._inline = getSvg(el.dataset.svg).then((txt) => {
      const doc = new DOMParser().parseFromString(txt, "image/svg+xml");
      const svg = doc.documentElement;
      if (!svg || svg.nodeName.toLowerCase() !== "svg") throw new Error("not svg");
      svg.querySelectorAll("style").forEach((s) => s.remove());
      el.replaceChildren(document.importNode(svg, true));
      el.classList.add("is-inline");
    });
    return el._inline;
  }
  const svgEls = $$("[data-svg]");
  if (canIO) {
    const lazy = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) { lazy.unobserve(en.target); inlineSvg(en.target).catch(() => {}); } });
    }, { rootMargin: "700px 0px" });
    svgEls.forEach((el) => lazy.observe(el));
    const inkIO = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        inkIO.unobserve(en.target);
        inlineSvg(en.target).then(() => raf2(() => { en.target.classList.add("in"); en.target.dispatchEvent(new Event("inked")); }))
          .catch(() => en.target.classList.add("in"));
      });
    }, { threshold: 0.2 });
    $$(".ink[data-svg]").forEach((el) => inkIO.observe(el));
  }

  /* ── header shadow ── */
  const top = $("[data-top]");
  const onScroll = () => top && top.classList.toggle("is-scrolled", scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true }); raf2(onScroll); // reading scrollY before first paint forces a layout

  /* ── opening date, then open-now from the hours table, in Vancouver time ── */
  const fmtT = (hm) => { let [h, m] = hm.split(":").map(Number); const s = h < 12 ? "am" : "pm"; h = h % 12 || 12; return `${h}${m ? ":" + String(m).padStart(2, "0") : ""} ${s}`; };
  const toMin = (hm) => { const [h, m] = hm.split(":").map(Number); return h * 60 + m; };
  const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  function vanNow() {
    const f = new Intl.DateTimeFormat("en-CA", { timeZone: D.tz || "America/Vancouver", year: "numeric", month: "2-digit", day: "2-digit", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    const p = {}; f.formatToParts(new Date()).forEach((x) => { p[x.type] = x.value; });
    return { date: `${p.year}-${p.month}-${p.day}`, day: p.weekday.slice(0, 3).toLowerCase(), mins: (+p.hour % 24) * 60 + +p.minute };
  }
  const fmtDate = (iso, long) => {
    const [y, m, d] = iso.split("-").map(Number);
    const opts = { timeZone: "UTC", month: "short", day: "numeric" }; if (long) opts.weekday = "short";
    return new Intl.DateTimeFormat("en-US", opts).format(new Date(Date.UTC(y, m - 1, d, 12)));
  };
  const hoursFor = (day) => (D.hours || []).find((h) => h.days.includes(day));
  function openState() {
    const n = vanNow();
    if (D.opening && n.date < D.opening) {
      return { cls: "is-soon", short: `Opening ${fmtDate(D.opening)}`, long: `Opening ${fmtDate(D.opening, true)} · ${D.street}`, day: n.day };
    }
    // the hours are samples while the site is a preview, so it never claims the restaurant is open right now
    if (D.preview) return { cls: "", short: "Hours", long: "See the hours", day: n.day };
    const h = hoursFor(n.day);
    if (!h) return { cls: "", short: "Hours", long: "See the hours", day: n.day };
    const o = toMin(h.open), c = toMin(h.close);
    if (n.mins >= o && n.mins < c) {
      if (c - n.mins <= 45) return { cls: "is-late", short: `Closing ${fmtT(h.close)}`, long: `Closing soon · ${fmtT(h.close)}`, day: n.day };
      return { cls: "is-open", short: `Open · until ${fmtT(h.close)}`, long: `Open now · until ${fmtT(h.close)}`, day: n.day };
    }
    if (n.mins < o) return { cls: "is-closed", short: `Opens ${fmtT(h.open)}`, long: `Closed · opens ${fmtT(h.open)}`, day: n.day };
    const nx = hoursFor(DAYS[(DAYS.indexOf(n.day) + 1) % 7]);
    return { cls: "is-closed", short: "Closed now", long: nx ? `Closed · opens ${fmtT(nx.open)} tomorrow` : "Closed now", day: n.day };
  }
  function paintOpen() {
    const s = openState();
    $$("[data-status]").forEach((p) => {
      p.classList.remove("is-soon", "is-open", "is-closed", "is-late");
      if (s.cls) p.classList.add(s.cls);
      $("[data-status-text]", p).textContent = p.dataset.status === "short" ? s.short : s.long;
    });
    $$(".hours tr[data-days]").forEach((tr) => {
      const today = tr.dataset.days.split(" ").includes(s.day);
      tr.classList.toggle("is-today", today);
      const t = $(".hours__today", tr); if (t) t.hidden = !today;
    });
  }
  paintOpen(); setInterval(paintOpen, 60000);

  /* ── horizontal scrollers: fade the edge that has more ── */
  $$("[data-scroller]").forEach((sc) => {
    const upd = () => {
      const max = sc.scrollWidth - sc.clientWidth;
      sc.classList.toggle("can-l", sc.scrollLeft > 4);
      sc.classList.toggle("can-r", sc.scrollLeft < max - 4);
    };
    sc.addEventListener("scroll", upd, { passive: true });
    addEventListener("resize", upd, { passive: true });
    raf2(upd); // after the first frame: reading scrollWidth now would force a layout before first paint
  });

  /* ── the wipe: the photo paints in from the left over the sketch; the value is how much is photo ── */
  $$("[data-wipe]").forEach((wipe) => {
    const input = $("[data-wipe-input]", wipe.parentElement);
    if (!input) return;
    const set = (v) => {
      v = Math.max(0, Math.min(100, Math.round(v)));
      input.value = v;
      wipe.style.setProperty("--w", v + "%");
      input.setAttribute("aria-valuetext", v <= 1 ? "all sketch" : v >= 99 ? "all photo" : `${v}% photo`);
    };
    input.addEventListener("input", () => set(+input.value));
    input.addEventListener("focus", () => wipe.classList.add("is-focus"));
    input.addEventListener("blur", () => wipe.classList.remove("is-focus"));
    let drag = false;
    const fromX = (x) => { const r = wipe.getBoundingClientRect(); set(((x - r.left) / r.width) * 100); };
    wipe.addEventListener("pointerdown", (e) => { if (e.button) return; drag = true; wipe.setPointerCapture(e.pointerId); fromX(e.clientX); });
    wipe.addEventListener("pointermove", (e) => { if (drag) fromX(e.clientX); });
    const end = () => { drag = false; };
    wipe.addEventListener("pointerup", end); wipe.addEventListener("pointercancel", end);
    set(+input.value);
  });

  /* ── the exploded smashburger ── */
  $$("[data-explode]").forEach((eng) => {
    const btn = $("[data-explode-toggle]", eng.closest(".leaf") || document);
    const label = btn && $("[data-explode-label]", btn);
    let touched = false;
    const show = (on) => { eng.classList.toggle("is-exploded", on); if (label) label.textContent = on ? "Assemble it" : "Explode it"; };
    show(!motion);
    if (btn) btn.addEventListener("click", () => { touched = true; show(!eng.classList.contains("is-exploded")); });
    const art = $(".ink", eng);
    if (art && motion) art.addEventListener("inked", () => setTimeout(() => { if (!touched) show(true); }, 1500), { once: true });
  });

  /* ── menu: filters dim what does not fit (never hide), with a reason; in each section what fits comes first ── */
  const dishes = $$(".dish");
  const lists = $$(".dishes");
  lists.forEach((ul) => $$(":scope > .dish", ul).forEach((li, i) => { li._i = i; }));
  const status = $("[data-filter-status]");
  const clear = $("[data-clear]");
  function sortLists() {
    lists.forEach((ul) => {
      const items = $$(":scope > .dish", ul);
      const sorted = [...items].sort((a, b) => (a.classList.contains("is-out") - b.classList.contains("is-out")) || a._i - b._i);
      if (sorted.every((li, k) => li === items[k])) return;
      const cta = $(":scope > .menu-cta", ul);
      sorted.forEach((li) => ul.insertBefore(li, cta));
    });
  }
  function applyFilters(cleared) {
    const avoid = $$('.chip--avoid[aria-pressed="true"]').map((c) => c.dataset.avoid);
    const diets = $$('.chip--diet[aria-pressed="true"]').map((c) => c.dataset.diet);
    let shown = 0;
    dishes.forEach((d) => {
      const al = d.dataset.allergens.split(" ").filter(Boolean);
      const may = d.dataset.may.split(" ").filter(Boolean);
      const dt = d.dataset.diet.split(" ").filter(Boolean);
      const hit = avoid.find((a) => al.includes(a));
      const mayHit = !hit && avoid.find((a) => may.includes(a));
      const miss = diets.find((x) => !(dt.includes(x) || (x === "vegetarian" && dt.includes("vegan"))));
      const out = !!(hit || mayHit || miss);
      d.classList.toggle("is-out", out);
      const why = hit ? `Contains ${D.allergens[hit].toLowerCase()}` : mayHit ? `May contain ${D.allergens[mayHit].toLowerCase()}` : miss ? `Not ${D.diets[miss].toLowerCase()}` : "";
      const o = $(".dish__out", d); if (o) o.textContent = why;
      if (!out) shown++;
    });
    const any = avoid.length + diets.length > 0;
    sortLists();
    if (status) {
      status.textContent = any ? `${shown} of ${dishes.length} sample dishes match.`
        : cleared ? `Filters cleared. All ${dishes.length} dishes shown.` : "";
    }
    if (clear) clear.hidden = !any;
  }
  $$(".chip--avoid, .chip--diet").forEach((c) => c.addEventListener("click", () => {
    c.setAttribute("aria-pressed", String(c.getAttribute("aria-pressed") !== "true")); applyFilters();
  }));
  if (clear) clear.addEventListener("click", () => {
    $$('.chip[aria-pressed="true"]').forEach((c) => c.setAttribute("aria-pressed", "false"));
    applyFilters(true);
    const first = $(".chip--diet"); if (first) first.focus(); // the Clear button hides itself, so focus moves to the first filter
  });

  /* ── menu: sticky section tabs follow the scroll ── */
  const tabsNav = $("[data-tabs]");
  if (tabsNav && canIO) {
    const tabs = $$(".tab", tabsNav);
    const sc = $("[data-scroller]", tabsNav);
    const mark = (id) => tabs.forEach((t) => {
      const on = t.dataset.tab === id;
      if (on) {
        t.setAttribute("aria-current", "true");
        if (sc) sc.scrollTo({ left: t.offsetLeft - sc.clientWidth / 2 + t.offsetWidth / 2, behavior: reduce ? "auto" : "smooth" });
      } else t.removeAttribute("aria-current");
    });
    const first = $("[data-spy]");
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) mark(en.target.id);
        // above the first section (back at the top of the page) the first tab is the current one
        else if (en.target === first && en.boundingClientRect.top > (en.rootBounds ? en.rootBounds.top : innerHeight * 0.4)) mark(first.id);
      });
    }, { rootMargin: "-40% 0px -55% 0px" });
    $$("[data-spy], #combos").forEach((s) => spy.observe(s));
    tabs.forEach((t) => t.addEventListener("click", () => mark(t.dataset.tab)));
    const sentinel = document.createElement("div");
    tabsNav.before(sentinel);
    new IntersectionObserver(([en]) => tabsNav.classList.toggle("is-stuck", !en.isIntersecting && en.boundingClientRect.top < 0),
      { rootMargin: `-${parseInt(getComputedStyle(html).getPropertyValue("--top-h"), 10) || 72}px 0px 0px 0px` }).observe(sentinel);
  }

  /* ── dialogs: Order and the dish sheet ── */
  const orderDlg = $("#order-dialog");
  const dishDlg = $("#dish-dialog");
  const openers = new Map();
  const canDialog = orderDlg && typeof orderDlg.showModal === "function";
  function openDialog(dlg, from) {
    if (dlg.open) return;
    openers.set(dlg, from || document.activeElement);
    dlg.showModal();
    raf2(() => dlg.classList.add("is-shown"));
  }
  if (canDialog) {
    [orderDlg, dishDlg].forEach((dlg) => {
      dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
      dlg.addEventListener("close", () => {
        dlg.classList.remove("is-shown");
        if (dlg === dishDlg && location.hash.startsWith("#dish=")) history.replaceState(null, "", location.pathname + location.search);
        const o = openers.get(dlg);
        if (o && o.isConnected && typeof o.focus === "function") o.focus({ preventScroll: true });
      });
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
    const slot = $("[data-dish-slot]", dishDlg);
    let doc;
    try { doc = await frags(); } catch (_) { if (href) location.href = href; return; }
    const tpl = doc.querySelector(`template[data-dish="${CSS.escape(id)}"]`);
    if (!tpl) { if (href) location.href = href; return; }
    slot.replaceChildren(document.importNode(tpl.content, true));
    const h = $("[data-dish-title]", slot); if (h) h.id = "dish-dialog-title";
    dishDlg.classList.remove("is-shown");
    openDialog(dishDlg, from);
    $(".sheet__card", dishDlg).scrollTop = 0;
    history.replaceState(null, "", location.pathname + location.search + "#dish=" + id);
  }
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const o = e.target.closest("[data-order]");
    if (o && canDialog) { e.preventDefault(); openDialog(orderDlg, o); return; }
    const d = e.target.closest("a[data-dish]");
    if (d && canDialog && dishDlg) { e.preventDefault(); openDish(d.dataset.dish, d, d.href); return; }
  });
  if (canDialog && location.hash.startsWith("#dish=")) openDish(decodeURIComponent(location.hash.slice(6)), null, null);
  // the dish sheets (one file) load on intent, after the page itself: a pointer or focus on any dish link
  if ($("a[data-dish]")) {
    const evs = ["pointerover", "focusin", "touchstart"];
    const warm = (e) => {
      if (!(e.target.closest && e.target.closest("a[data-dish]"))) return;
      evs.forEach((t) => document.removeEventListener(t, warm, true));
      frags().catch(() => {});
    };
    addEventListener("load", () => evs.forEach((t) => document.addEventListener(t, warm, { capture: true, passive: true })), { once: true });
  }

  /* ── the mobile dock: on the home page it waits until the hero's own Order button has scrolled away ── */
  const dockEl = $(".dock");
  const heroCta = $(".hero__cta");
  if (dockEl && heroCta) {
    if (canIO) new IntersectionObserver(([en]) => dockEl.classList.toggle("is-on", !en.isIntersecting)).observe(heroCta);
    else dockEl.classList.add("is-on");
  }
})();
