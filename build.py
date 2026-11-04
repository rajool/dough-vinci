#!/usr/bin/python3
"""Build the Dough-Vinci site: content/*.json + src/ -> docs/ (the GitHub Pages folder).

    python3 build.py

Standard library only. Page skeletons live in src/templates/ with {{placeholders}}; everything that repeats (dish
cards, the dish sheet, hours, the order tiles, the allergen matrix) is rendered here from content/*.json, so a new
price, dish, address, opening date or delivery link is a JSON edit and a rebuild. Never edit docs/ by hand.

Files in docs/ that this build no longer writes are moved to the Trash with `trash` (never deleted outright).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SRC = ROOT / "src"
ART = SRC / "art"
NEW_ART = ART / "new"
DOCS = ROOT / "docs"

e = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


SITE = load("site.json")
MENU = load("menu.json")
PHOTOS = {p["key"]: p for p in load("photos.json")["photos"]}
TZ = ZoneInfo(SITE.get("timezone", "America/Vancouver"))
TODAY = dt.datetime.now(TZ).date()

ALLERGENS = {
    "wheat": "Wheat", "milk": "Milk", "egg": "Egg", "soy": "Soy", "sesame": "Sesame", "mustard": "Mustard",
    "peanut": "Peanut", "treenut": "Tree nuts", "fish": "Fish", "shellfish": "Shellfish", "sulphites": "Sulphites",
}
DIETS = {"vegetarian": "Vegetarian", "vegan": "Vegan", "spicy": "Spicy", "gluten-free-option": "GF option"}
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_SHORT = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}
CAT_WASH = {"pizza": "tomato", "smash": "cheese", "sides": "basil", "desserts": "rose", "drinks": "sky"}
DV = {"protein_g": (50, "g", "Protein"), "carbs_g": (275, "g", "Carbohydrate"), "fat_g": (75, "g", "Fat"),
      "sodium_mg": (2300, "mg", "Sodium")}
FONTS = ("https://fonts.googleapis.com/css2?family=Caveat:wght@600..700"
         "&family=Fraunces:ital,opsz,wght,SOFT@0,9..144,600..850,100;1,9..144,500..800,100"
         "&family=Instrument+Sans:wght@400..700&display=swap")

CATS = MENU["categories"]
ITEMS = {it["id"]: (cat, it) for cat in CATS for it in cat["items"]}
ORDER_IDS = [it["id"] for cat in CATS for it in cat["items"]]
USED_PHOTOS: dict[str, dict] = {}


# ───────────────────────────────────────────────────────────── photos


def photo(ref: str) -> dict:
    """A photo reference is `key`, `key.alternate`, `key.primary` (the entry's own photo, ignoring `use`) or a key
    whose entry says `"use": "alternate"` / `"other"` / `"other.alternate"`."""
    key, _, variant = ref.partition(".")
    ph = PHOTOS[key]
    if not variant and ph.get("use"):
        use = ph["use"]
        return photo(f"{key}.alternate" if use == "alternate" else use)
    if variant == "alternate":
        a = ph["alternate"]
        if not a.get("alt"):
            raise SystemExit(f"photos.json: the alternate of {key} is used but has no alt text")
        d = {"url": a["url"], "alt": a["alt"], "author": a["author"], "page": a["page"], "crop": a.get("crop")}
    else:
        d = {"url": ph["url"], "alt": ph["alt"], "author": ph["author"], "page": ph["page"], "crop": ph.get("crop")}
    USED_PHOTOS.setdefault(d["url"], d)
    return d


def img_url(ph: dict, w: int, ratio: float | None = None, q: int = 75) -> str:
    parts = ["auto=format", "fit=crop", f"w={w}"]
    if ratio:
        parts.append(f"h={round(w / ratio)}")
    parts.append(f"q={q}")
    c = ph.get("crop")
    if c:
        parts += ["crop=focalpoint", f"fp-x={c[0]}", f"fp-y={c[1]}", f"fp-z={c[2]}"]
    return ph["url"] + "?" + "&".join(parts)


WIDTHS = (400, 600, 800, 1000, 1200, 1600)
# Phones at 3x get the 2x file: past 2x nobody sees the difference, and the bytes compete with the hero. A <source>
# for those screens repeats the srcset with every slot in `sizes` scaled by 2/3, so the browser asks for 2x.
HI_DPR = "(min-resolution: 2.5dppx), (-webkit-min-device-pixel-ratio: 2.5)"
LO_DPR = "(max-resolution: 2.49dppx)"


def srcset(ph: dict, ratio: float, max_w: int = 1600) -> list[tuple[str, int]]:
    return [(img_url(ph, w, ratio), w) for w in WIDTHS if w <= max_w]


def scale_sizes(sizes: str, f: float) -> str:
    """'(min-width: 1000px) 460px, 60vw' scaled by f: the media conditions stay, the slot lengths shrink."""
    out = []
    for part in sizes.split(","):
        m = re.fullmatch(r"\s*(\([^)]*\)\s+)?(\d+(?:\.\d+)?)(px|vw)\s*", part)
        if not m:
            raise SystemExit(f"sizes part not understood: {part!r}")
        out.append(f"{m.group(1) or ''}{round(float(m.group(2)) * f)}{m.group(3)}")
    return ", ".join(out)


def img(ref: str, sizes: str, ratio: float, *, cls: str = "", eager: bool = False, alt: str | None = None,
        max_w: int = 1600, crop: tuple | None = None, low: bool = False) -> str:
    """A responsive Unsplash photo. alt="" for a photo inside a link that its own text already names."""
    ph = photo(ref)
    if crop:
        ph = {**ph, "crop": crop}
    ss = srcset(ph, ratio, max_w)
    src = ss[min(1, len(ss) - 1)][0]
    w = ss[-1][1]
    a = alt if alt is not None else ph["alt"]
    if eager:
        load_attr = 'fetchpriority="high" decoding="async"'
    else:
        load_attr = ('fetchpriority="low" ' if low else "") + 'loading="lazy" decoding="async"'
    c = f' class="{cls}"' if cls else ""
    set_ = e(", ".join(f"{u} {w}w" for u, w in ss))
    return (f'<picture><source media="{HI_DPR}" srcset="{set_}" sizes="{scale_sizes(sizes, 2 / 3)}">'
            f'<img{c} src="{e(src)}" srcset="{set_}" sizes="{sizes}" '
            f'width="{w}" height="{round(w / ratio)}" alt="{e(a)}" {load_attr}></picture>')


def preload(ref: str, sizes: str, ratio: float, max_w: int = 1600, crop: tuple | None = None) -> str:
    """Preloads that pick the same file as img(): one for 3x phones (2x file), one for everything else."""
    ph = photo(ref)
    if crop:
        ph = {**ph, "crop": crop}
    ss = srcset(ph, ratio, max_w)
    set_ = e(", ".join(f"{u} {w}w" for u, w in ss))
    return "\n".join(f'<link rel="preload" as="image" href="{e(ss[1][0])}" imagesrcset="{set_}" imagesizes="{sz}" '
                     f'media="{media}" fetchpriority="high">'
                     for media, sz in ((LO_DPR, sizes), (HI_DPR, scale_sizes(sizes, 2 / 3))))


# ───────────────────────────────────────────────────────────── icons and art


FALLBACK_SPRITE = ART / "ui-icons.svg"
NEW_SPRITE = NEW_ART / "allergens.svg"


def load_symbols() -> dict[str, str]:
    """Every <symbol> by id: the fallback sprite first, then the illustrator's allergens.svg, which wins on shared ids."""
    symbols: dict[str, str] = {}
    for path in (FALLBACK_SPRITE, NEW_SPRITE):
        if path.exists():
            text = path.read_text(encoding="utf-8")
            for m in re.finditer(r'<symbol\b[^>]*\bid="([^"]+)"[^>]*>.*?</symbol>', text, flags=re.S):
                symbols[m.group(1)] = m.group(0)
    return symbols


SYMBOLS = load_symbols()
SPRITE_IDS = set(SYMBOLS)


def sprite_for(doc: str, extra: set[str] = frozenset()) -> str:
    """Inline only the symbols a page uses (plus those the dish sheet may bring in)."""
    used = set(re.findall(r'<use href="#([^"]+)"', doc)) | set(extra)
    body = "".join(SYMBOLS[i] for i in sorted(used) if i in SYMBOLS)
    return f'<svg class="sprite" aria-hidden="true" focusable="false" width="0" height="0">{body}</svg>'


def icon(name: str, cls: str = "ico") -> str:
    if name not in SPRITE_IDS:
        raise SystemExit(f"icon #{name} is missing from the sprite")
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#{name}"></use></svg>'


def art_css() -> str:
    """Colours the drawings expect. The illustrator's art.css plus the washes of the two older studies."""
    parts = []
    if (NEW_ART / "art.css").exists():
        parts.append((NEW_ART / "art.css").read_text(encoding="utf-8"))
    parts.append((SRC / "css" / "art-studies.css").read_text(encoding="utf-8"))
    return "\n".join(parts)


def clean_svg(text: str) -> str:
    text = re.sub(r"<\?xml[^>]*>\s*", "", text)
    text = re.sub(r"<!--.*?-->\s*", "", text, flags=re.S)
    return text.strip()


def chunk_strokes(svg: str, cls: str, size: int) -> str:
    """Merge runs of stroke paths of one class into compound paths, so inking touches dozens of elements, not hundreds."""
    run = re.compile(rf'(?:<path class="{cls}" pathLength="1" style="--i:\d+" d="[^"]*"/>\s*)+')

    def merge(m: re.Match) -> str:
        ds = re.findall(r' d="([^"]*)"', m.group(0))
        return "".join(f'<path class="{cls}" pathLength="1" style="--i:{i // size}" d="{"".join(ds[i:i + size])}"/>'
                       for i in range(0, len(ds), size))

    return run.sub(merge, svg)


def bake(svg: str, extra_class: str = "") -> str:
    """A drawing that renders on its own (as <img> or inlined): its colours go inside as a <style>."""
    svg = clean_svg(svg)
    style = "<style>" + re.sub(r"\s+", " ", art_css()) + "</style>"
    svg = re.sub(r"(<svg\b[^>]*>)", lambda m: m.group(1) + style, svg, count=1)
    if extra_class:
        svg = svg.replace('class="codex-art', f'class="{extra_class} codex-art', 1)
    return svg


def line_only(svg: str) -> str:
    """The pizza study with only construction and contour lines: the footer watermark."""
    svg = re.sub(r'<g\b[^>]*class="art-group art-group--wash"[^>]*>.*?</g>', "", svg, flags=re.S)
    svg = re.sub(r'<g\b[^>]*class="art-group art-group--hatch"[^>]*>.*?</g>', "", svg, flags=re.S)
    svg = re.sub(r'<circle class="art-dot"[^>]*/>', "", svg)
    return svg


def mark_svg() -> str:
    path = NEW_ART / "vitruvian-mark.svg"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (SRC / "art" / "mark-fallback.svg").read_text(encoding="utf-8")


# ───────────────────────────────────────────────────────────── small formatters


def money(p: str | float) -> str:
    v = float(p)
    return f"${v:g}" if v == int(v) else f"${v:.2f}"


def price_from(item: dict) -> str:
    ps = sorted(float(p["price"]) for p in item["prices"])
    return money(ps[0]) if len(ps) == 1 else f"from {money(ps[0])}"


def slices(item: dict) -> int | None:
    m = re.search(r"\((\d+) slices\)", item.get("portion", ""))
    return int(m.group(1)) if m else None


def fmt_time(t: str) -> str:
    h, m = map(int, t.split(":"))
    suf = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{':' + str(m).zfill(2) if m else ''} {suf}"


def day_range(days: list[str]) -> str:
    return DAY_SHORT[days[0]] if len(days) == 1 else f"{DAY_SHORT[days[0]]}–{DAY_SHORT[days[-1]]}"


def opening() -> dt.date | None:
    od = SITE.get("opening_date")
    return dt.date.fromisoformat(od) if od else None


def opening_short(d: dt.date) -> str:
    return f"{d:%b} {d.day}"


def opening_long(d: dt.date) -> str:
    return f"{d:%a}, {d:%b} {d.day}"


def status_html(variant: str) -> str:
    """The pill. Rendered at build time (pre-opening date, or a neutral 'hours' link); site.js keeps it live."""
    od = opening()
    street = SITE["contact"]["street"]
    if od and TODAY < od:
        text = f"Opening {opening_short(od)}" if variant == "short" else f"Opening {opening_long(od)} · {street}"
        cls = "is-soon"
    else:
        text, cls = "Hours", ""
    return (f'<span class="pill {cls}" data-status="{variant}"><span class="pill__dot" aria-hidden="true"></span>'
            f'<span data-status-text>{e(text)}</span></span>')


def tel() -> str:
    return "+1" + re.sub(r"\D", "", SITE["contact"]["phone"])


# ───────────────────────────────────────────────────────────── components


def diet_pills(item: dict, cls: str = "diet") -> str:
    return "".join(f'<li class="{cls} {cls}--{d}">{icon("d-" + d)}<span>{DIETS[d]}</span></li>' for d in item.get("diet", []))


def allergen_items(keys: list[str], cls: str = "alg", commas: bool = False) -> str:
    """With commas, a hidden ", " between names, so a link that contains the list reads «Wheat, Milk», not «Wheat Milk»."""
    sep = lambda i: '<span class="sr">, </span>' if commas and i < len(keys) - 1 else ""  # noqa: E731
    return "".join(f'<li class="{cls}">{icon("a-" + k)}<span>{ALLERGENS[k]}</span>{sep(i)}</li>' for i, k in enumerate(keys))


def kcal_chips(item: dict) -> str:
    s = slices(item)
    whole = f'<span class="kcal"><b>{item["kcal"]:,}</b> kcal{" whole" if s else ""}</span>'
    per = f'<span class="kcal kcal--slice"><b>{round(item["kcal"] / s):,}</b> kcal/slice</span>' if s else ""
    return whole + per


def card(item: dict, cat: dict, root: str, n: int) -> str:
    al = item["allergens"]
    badge = f'<span class="stamp">{e(item["badge"])}</span>' if item.get("badge") else ""
    # no aria-label on the list: inside a link it would replace the allergen names in the link's accessible name.
    # The hidden label is out of flow (.sr is absolute), so it adds no gap to the flex column.
    alg = (f'<span class="sr">Contains: </span><ul class="algs">{allergen_items(al, commas=True)}</ul>' if al
           else '<p class="algs algs--none">No priority allergens</p>')
    diets = f'<ul class="diets">{diet_pills(item)}</ul>' if item.get("diet") else ""
    return f'''<li class="dish" data-id="{item['id']}" data-allergens="{' '.join(al)}" data-may="{' '.join(item.get('may_contain', []))}" data-diet="{' '.join(item.get('diet', []))}" style="--k:{n % 4}">
  <a class="dish__link" href="{root}menu/{item['id']}/" data-dish="{item['id']}">
    <span class="dish__photo wash--{CAT_WASH[cat['id']]}">{img(item['id'], '(min-width: 1180px) 280px, (min-width: 700px) 30vw, 46vw', 4 / 3, max_w=800, alt="")}{badge}<span class="folio" aria-hidden="true">f. {n}r</span></span>
    <div class="dish__body">
      <div class="dish__head"><h3 class="dish__name">{e(item['name'])}</h3><span class="dish__price">{price_from(item)}</span></div>
      <div class="dish__kcal">{kcal_chips(item)}</div>
      {diets}{alg}
    </div>
    <span class="dish__out"></span>
  </a>
</li>'''


def order_card() -> str:
    return f'''<li class="menu-cta"><div class="menu-cta__in">
  <img class="menu-cta__art" src="{{{{root}}}}assets/art/flying-machine.svg" alt="" width="1200" height="700" loading="lazy" decoding="async">
  <p class="hand menu-cta__k">Hungry already?</p>
  <p class="menu-cta__t">Delivered by your favourite app</p>
  <a class="btn btn--order" href="#order" data-order>{icon("i-bag")}<span>Order</span></a>
</div></li>'''


def menu_sections(root: str) -> str:
    """One section per category. Two small categories that fit one row together (desserts and drinks) share it."""
    out, n = [], 0
    for cat in CATS:
        cards = []
        for it in cat["items"]:
            n += 1
            cards.append(card(it, cat, root, n))
        if cat["id"] == "pizza":
            cards.append(order_card().replace("{{root}}", root))
        out.append((len(cards), f'''<section class="cat" id="{cat['id']}" aria-labelledby="cat-{cat['id']}" data-spy>
  <header class="cat__head"><h2 class="cat__title" id="cat-{cat['id']}">{e(cat['name'])} <span class="cat__it" lang="it">{e(cat['italian'])}</span></h2>
  <p class="cat__tag hand">{e(cat['tagline'])}</p></header>
  <ul class="dishes" style="--cols:{4 if len(cards) > 5 else len(cards)}">{"".join(cards)}</ul>
</section>'''))
    html_parts, i = [], 0
    while i < len(out):
        if i + 1 < len(out) and out[i][0] <= 3 and out[i + 1][0] <= 3 and out[i][0] + out[i + 1][0] <= 5:
            html_parts.append(f'<div class="cat-pair" style="grid-template-columns:{out[i][0]}fr {out[i + 1][0]}fr">{out[i][1]}{out[i + 1][1]}</div>')
            i += 2
        else:
            html_parts.append(out[i][1])
            i += 1
    return "\n".join(html_parts)


def category_tabs() -> str:
    tabs = [f'<li><a class="tab" href="#{c["id"]}" data-tab="{c["id"]}"><span class="tab__it" lang="it" aria-hidden="true">{e(c["italian"])}</span><span>{e(c["name"])}</span></a></li>'
            for c in CATS]
    tabs.append('<li><a class="tab" href="#combos" data-tab="combos"><span class="tab__it" lang="it" aria-hidden="true">Le Offerte</span><span>Combos</span></a></li>')
    return "".join(tabs)


def filter_chips() -> tuple[str, str]:
    diets = "".join(f'<button class="chip chip--diet" type="button" aria-pressed="false" data-diet="{d}">{icon("d-" + d)}<span>{DIETS[d]}</span></button>'
                    for d in DIETS)
    avoid = "".join(f'<button class="chip chip--avoid" type="button" aria-pressed="false" data-avoid="{k}">{icon("a-" + k)}<span>{ALLERGENS[k]}</span></button>'
                    for k in MENU["allergen_keys"])
    return diets, avoid


def construct_svg(cls: str) -> str:
    """Red-chalk circle-and-square construction behind a dish photo."""
    return f'''<svg class="{cls}" viewBox="0 0 400 500" aria-hidden="true" focusable="false">
  <path d="M200 40a210 210 0 1 1-.1 0z" class="c-faint"/><path d="M20 70h360v360H20z"/><path d="M200 8v484M8 250h384" class="c-faint"/>
  <path d="M20 70l360 360M380 70 20 430" class="c-faint"/><path d="M200 22v14M200 464v14M14 250h14M372 250h14"/>
  <path d="M20 470h360M20 462v16M380 462v16"/></svg>'''


def nutri_caption(item: dict) -> str:
    s = slices(item)
    if s:
        return f"Per whole 12″ pizza ({s} slices)"
    return "Per " + e(item["portion"])


def dish_detail(item: dict, cat: dict, root: str, level: int = 2) -> str:
    n = ORDER_IDS.index(item["id"]) + 1
    s = slices(item)
    h = f"h{level}"
    nut = item["nutrition"]
    note = cat["tagline"].split(".")[0].strip().lower()
    badge = f'<span class="stamp stamp--lg">{e(item["badge"])}</span>' if item.get("badge") else ""
    sizes = "".join(f'<li class="size"><span>{e(p["label"].replace(chr(34), "″")) if p["label"] != "Regular" else "Price"}</span><b>{money(p["price"])}</b></li>'
                    for p in item["prices"])
    pct = min(100, round(item["kcal"] / 20))
    rows = []
    for k, (dv, unit, label) in DV.items():
        v = nut[k]
        share = round(v / dv * 100)
        rows.append(f'<tr><th scope="row">{label}</th><td class="nutri__v">{v:,} {unit}</td>'
                    f'<td class="nutri__dv"><span class="bar" aria-hidden="true"><i style="--w:{min(100, share)}%"></i></span>{share}%</td></tr>')
    whole_label = "whole 12″ pizza" if s else e(item["portion"])
    per_slice = (f'<p class="kslice"><b>≈{round(item["kcal"] / s):,} kcal</b> per slice <span>({s} slices)</span></p>' if s else "")
    contains = allergen_items(item["allergens"], "alg") or '<li class="alg alg--none">No priority allergens</li>'
    may = allergen_items(item.get("may_contain", []), "alg") or '<li class="alg alg--none">Nothing listed</li>'
    diets = f'<ul class="dd__diets">{diet_pills(item)}</ul>' if item.get("diet") else ""
    sample = ('<p class="dd__fine">Sample menu: prices, calories and allergens are placeholders until the owner confirms them, '
              'and the photo is a stock image.</p>' if MENU.get("sample") else "")
    return f'''<article class="dd" data-dish-article="{item['id']}">
  <figure class="dd__photo">
    {construct_svg("dd__construct")}
    <span class="dd__frame wash--{CAT_WASH[cat['id']]}">{img(item['id'], '(min-width: 980px) 440px, 92vw', 4 / 5, max_w=1000)}</span>
    <span class="dd__note dd__note--1 hand" lang="it" aria-hidden="true">{e(cat['italian'])}</span>
    <span class="dd__note dd__note--2 hand" aria-hidden="true">{e(note)}</span>
    <span class="dd__fig" aria-hidden="true">Fig. {n}</span>{badge}
  </figure>
  <div class="dd__body">
    <p class="dd__cat">{e(cat['name'])}</p>
    <{h} class="dd__name" data-dish-title>{e(item['name'])}</{h}>
    <p class="dd__short">{e(item['short'])}</p>
    {diets}
    <ul class="sizes" aria-label="Sizes and prices">{sizes}</ul>
    <div class="dd__nut">
      <div class="kring" style="--pct:{pct}">
        <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false"><circle cx="60" cy="60" r="52" class="kring__bg"/><circle cx="60" cy="60" r="52" class="kring__fg" pathLength="100"/><path class="kring__ticks" d="M60 2v8M60 110v8M2 60h8M110 60h8"/></svg>
        <p><b>{item['kcal']:,}</b><span>kcal</span><span class="kring__of">{whole_label}</span></p>
      </div>
      <div class="dd__nut-r">
        {per_slice}
        <table class="nutri"><caption>{nutri_caption(item)}</caption>
          <thead class="sr"><tr><th scope="col">Nutrient</th><th scope="col">Amount</th><th scope="col">Share of a day</th></tr></thead>
          <tbody>{"".join(rows)}</tbody></table>
        <p class="dd__dvnote">% of the daily value, on a 2,000-kcal day.</p>
      </div>
    </div>
    <h{level + 1} class="dd__h">Ingredients</h{level + 1}>
    <ol class="ingr">{"".join(f"<li>{e(x)}</li>" for x in item["ingredients"])}</ol>
    <h{level + 1} class="dd__h">Allergens</h{level + 1}>
    <div class="dd__alg">
      <p class="dd__alg-l">Contains</p><ul class="algs algs--lg">{contains}</ul>
      <p class="dd__alg-l">May contain</p><ul class="algs algs--lg algs--may">{may}</ul>
    </div>
    <p class="dd__xc">Shared kitchen: traces of any allergen are possible. <a href="{root}allergens/">Allergen guide</a></p>
    {sample}
    <div class="dd__order"><p class="dd__from"><b>{price_from(item)}</b><span>{item['kcal']:,} kcal</span></p>
      <a class="btn btn--order btn--lg" href="#order" data-order>{icon("i-bag")}<span>Order</span></a></div>
  </div>
</article>'''


def app_tiles(prefix: str) -> str:
    tiles = []
    for d in SITE["delivery"]:
        tiles.append(f'<li><a class="app" href="{e(d["url"])}" target="_blank" rel="noopener" style="--brand:{e(d.get("color", "#B8432A"))}">'
                     f'<span class="app__top"><span class="app__mark" aria-hidden="true">{e(d["name"][0])}</span>'
                     f'<span class="app__name">{e(d["name"])}</span></span>'
                     f'<span class="app__go">Order now {icon("i-ext", "ico ico--sm")}<span class="sr"> (opens in a new tab)</span></span></a></li>')
    tiles.append(f'<li><a class="app app--call" href="tel:{tel()}"><span class="app__top"><span class="app__name">Call for pickup</span></span>'
                 f'<span class="app__go">{icon("i-phone", "ico ico--sm")}{e(SITE["contact"]["phone"])}</span></a></li>')
    return "".join(tiles)


def hours_rows() -> str:
    rows = []
    for h in SITE["hours"]:
        rows.append(f'<tr data-days="{" ".join(h["days"])}"><th scope="row">{day_range(h["days"])}</th>'
                    f'<td>{fmt_time(h["open"])} – {fmt_time(h["close"])}<span class="hours__today" hidden> · today</span></td></tr>')
    return "".join(rows)


def combo_cards(root: str) -> str:
    out = []
    styles = {"bottega-for-two": "cheese", "smash-study": "basil", "famiglia": "tomato"}
    kickers = {"bottega-for-two": "for two, the masterwork", "smash-study": "the classic study", "famiglia": "for the whole table"}
    order = ["bottega-for-two", "smash-study", "famiglia"]
    cmb = {c["id"]: c for c in MENU["combos"]}
    for cid in order:
        c = cmb[cid]
        refs = c.get("photos", [])
        if len(refs) >= 3:
            art = (f'<span class="combo__pizza">{img(refs[0], "(min-width: 980px) 340px, 60vw", 1, max_w=800)}</span>'
                   f'<span class="combo__burger">{img(refs[1], "(min-width: 980px) 200px, 34vw", 4 / 5, max_w=600)}</span>'
                   f'<span class="combo__fries">{img(refs[2], "(min-width: 980px) 150px, 28vw", 1, max_w=400)}</span>'
                   f'<span class="plus plus--1" aria-hidden="true">+</span><span class="plus plus--2" aria-hidden="true">+</span>')
            art = f'<div class="combo__art">{art}</div>'
        else:
            art = f'<div class="combo__photo">{img(refs[0], "(min-width: 980px) 300px, 80vw", 4 / 3, max_w=800)}</div>'
        items = "".join(f"<li>{e(x)}</li>" for x in c["contents"])
        out.append(f'''<li class="combo combo--{styles[cid]}" style="--k:{len(out)}">
  {art}
  <div class="combo__txt">
    <p class="combo__kicker hand">{e(kickers[cid])}</p>
    <h3 class="combo__name">{e(c['name'])}</h3>
    <ul class="combo__list">{items}</ul>
    <a class="btn btn--order" href="#order" data-order>{icon("i-bag")}<span>Order</span></a>
  </div>
  <p class="price-seal"><span class="price-seal__c">$</span>{e(c['price'])}</p>
</li>''')
    return "".join(out)


def combos_section(root: str, level: int = 2) -> str:
    return f'''<section class="combos page" id="combos" aria-labelledby="combos-title">
  <span class="folio-mark" aria-hidden="true">f. 6r</span>
  <header class="sec-head"><p class="kicker-s">Studies in pairs</p>
    <h{level} class="sec-title" id="combos-title">Combos <em>&amp; deals</em></h{level}></header>
  <ul class="combo-row" data-scroller>{combo_cards(root)}</ul>
</section>'''


def flying_band(root: str) -> str:
    return f'''<section class="fly" id="order" aria-labelledby="order-title">
  <div class="fly__in">
    <div class="fly__sky" aria-hidden="true">
      <div class="fly__machine" data-svg="{root}assets/art/flying-machine.svg"><img src="{root}assets/art/flying-machine.svg" alt="" width="1200" height="700" loading="lazy" decoding="async"></div>
      <svg class="fly__trail" viewBox="0 0 1200 120" preserveAspectRatio="none"><path d="M0 90c140-40 260-56 400-40s250 40 380 18 260-60 420-50"/></svg>
    </div>
    <header class="fly__head">
      <p class="kicker-s">Delivery or pickup</p>
      <h2 class="fly__title" id="order-title">We fly it <em>to your door</em></h2>
    </header>
    <ul class="apps">{app_tiles("band")}</ul>
    <p class="fly__note hand">{e(SITE.get("order_note", ""))}</p>
  </div>
</section>'''


def map_figure(root: str, small: bool = False) -> str:
    mj = json.loads((NEW_ART / "map.json").read_text()) if (NEW_ART / "map.json").exists() else {"labels": {}, "winds": {}, "rotate": {}, "pin": [500, 500]}
    labels = []
    for name, (x, y) in mj.get("labels", {}).items():
        rot = mj.get("rotate", {}).get(name, 0)
        cls = "mlab mlab--park" if "Park" in name else ("mlab mlab--main" if name.startswith("Commercial") else "mlab")
        # the drawing is shown mirrored (Grandview Park is on the west side of Commercial Drive), so x flips
        labels.append(f'<li class="{cls}" style="--x:{(1000 - x) / 10:.1f}%;--y:{y / 10:.1f}%;--r:{rot}deg">{e(name)}</li>')
    if not small:
        for name, (x, y) in mj.get("winds", {}).items():
            labels.append(f'<li class="mlab mlab--wind" lang="it" aria-hidden="true" style="--x:{x / 10:.1f}%;--y:{y / 10:.1f}%">{e(name)}</li>')
    px, py = mj.get("pin", [500, 500])
    addr = SITE["contact"].get("map_label") or SITE["contact"]["street"]
    return f'''<figure class="imola{' imola--sm' if small else ''}">
  <div class="imola__map">
    <img class="imola__img" src="{root}assets/art/map.svg" alt="" width="1000" height="1000" loading="lazy" decoding="async">
    <ul class="imola__labels" aria-label="Streets on the map">{"".join(labels)}</ul>
    <p class="imola__here" style="--x:{(1000 - px) / 10:.1f}%;--y:{py / 10:.1f}%"><span class="hand">We’re here!</span> <span>{e(addr)}</span></p>
  </div>
  <figcaption class="imola__cap">{e(SITE.get("map_caption", ""))}</figcaption>
</figure>'''


def golden_spiral() -> str:
    """A logarithmic golden spiral (growth φ per quarter turn) for the construction overlay on the pizza photo."""
    phi = (1 + 5 ** 0.5) / 2
    b = math.log(phi) / (math.pi / 2)
    cx, cy = 618, 382
    pts = []
    for i in range(0, 361):
        t = -i / 360 * 4 * math.pi
        r = 520 * math.exp(b * t)
        pts.append((cx + r * math.cos(t + math.pi), cy + r * math.sin(t + math.pi)))
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    return d


SIGNATURES = SITE.get("signatures", [])


def signature_cards(root: str) -> str:
    out = []
    for i, s in enumerate(SIGNATURES):
        cat, it = ITEMS[s["id"]]
        catname = "Smashburger" if cat["id"] == "smash" else cat["name"].rstrip("s") if cat["id"] != "pizza" else "Pizza"
        out.append(f'''<li class="study" style="--k:{i}">
  <a class="study__link" href="{root}menu/{it['id']}/" data-dish="{it['id']}">
    <span class="study__fig" aria-hidden="true">Fig. {ORDER_IDS.index(it['id']) + 1}</span>
    <span class="study__frame"><span class="tick tick--tl"></span><span class="tick tick--tr"></span><span class="tick tick--bl"></span><span class="tick tick--br"></span>
      <span class="study__photo">{img(it['id'], '(min-width: 1180px) 290px, (min-width: 700px) 44vw, 74vw', 4 / 5, max_w=800, alt="", low=True)}</span></span>
    <span class="study__note hand" aria-hidden="true">{e(s.get('note', ''))}</span>
    <span class="study__cat">{e(catname)}</span>
    <h3 class="study__name">{e(it['name'])}</h3>
    <span class="study__meta"><b>{price_from(it)}</b>{kcal_chips(it)}</span>
  </a>
</li>''')
    return "".join(out)


def category_tiles(root: str) -> str:
    """One tile per category. The photo is `home_tiles` in site.json, chosen so no photo repeats on the home page."""
    out = []
    picks = SITE.get("home_tiles", {})
    for cat in CATS:
        ref = picks.get(cat["id"]) or cat["items"][0]["id"]
        out.append(f'''<li><a class="ctile wash--{CAT_WASH[cat['id']]}" href="{root}menu/#{cat['id']}">
  <span class="tick tick--tl" aria-hidden="true"></span><span class="tick tick--br" aria-hidden="true"></span>
  <span class="ctile__photo">{img(ref, '(min-width: 1180px) 240px, (min-width: 700px) 30vw, 44vw', 1, max_w=600, alt="", low=True)}</span>
  <span class="ctile__it" lang="it" aria-hidden="true">{e(cat['italian'])}</span>
  <span class="ctile__name">{e(cat['name'])}</span><span class="ctile__n">{len(cat['items'])} dishes</span></a></li>''')
    return "".join(out)


BURGER_LABELS = [("crown", "a", "toasted potato bun"), ("pickles", "b", "pickles & house sauce"),
                 ("cheese-top", "c", "American cheese"), ("patty-top", "d", "smashed thin"),
                 ("cheese-low", "e", "melted cheese"), ("patty-low", "f", "crispy lace edge"), ("heel", "g", "toasted heel")]


def burger_labels() -> tuple[str, str]:
    bj = json.loads((ART / "burger-study.json").read_text())
    marks, legend = [], []
    for layer, letter, label in BURGER_LABELS:
        x, y = bj["anchors"][layer]
        dy = bj["explode"][layer]
        marks.append(f'<li class="blab" style="--y:{y / 10:.1f};--dy:{dy / 10:.2f}"><span class="blab__l">{letter}</span><span class="blab__t">{e(label)}</span></li>')
        legend.append(f'<li><span class="blab__l" aria-hidden="true">{letter}</span>{e(label)}</li>')
    return "".join(marks), "".join(legend)


PIZZA_NOTES = [("crust", "golden rim", "r"), ("cheese", "melted mozzarella", "r"), ("sauce", "tomato sauce", "l")]


def pizza_notes() -> str:
    pj = json.loads((ART / "pizza-study.json").read_text())
    out = []
    for a, t, side in PIZZA_NOTES:
        x, y = pj["anchors"][a]
        out.append(f'<li class="pnote pnote--{side}" style="--x:{x / 10:.1f};--y:{y / 10:.1f}"><span class="hand">{e(t)}</span></li>')
    return "".join(out)


def faq() -> str:
    """`{opening}` in an answer becomes the opening date, so the FAQ and the pills never disagree."""
    od = opening()
    when = f"{od:%A}, {od:%B} {od.day}" if od else "a date we will post here soon"
    return "".join(f'<details class="faq__q"><summary>{e(q["q"])}</summary><p>{e(q["a"].replace("{opening}", when))}</p></details>'
                   for q in SITE["faq"])


def allergen_matrix(root: str) -> str:
    head = "".join(f'<th scope="col" class="mx__h"><span class="mx__hin">{icon("a-" + k)}<span>{ALLERGENS[k]}</span></span></th>'
                   for k in MENU["allergen_keys"])
    groups = []
    for cat in CATS:
        rows = [f'<tr class="mx__cat"><th scope="rowgroup" colspan="{len(MENU["allergen_keys"]) + 2}">{e(cat["name"])} <span lang="it">{e(cat["italian"])}</span></th></tr>']
        for it in cat["items"]:
            cells = []
            for k in MENU["allergen_keys"]:
                if k in it["allergens"]:
                    cells.append('<td class="mx__c mx__c--yes"><span aria-hidden="true">●</span><span class="sr">Contains</span></td>')
                elif k in it.get("may_contain", []):
                    cells.append('<td class="mx__c mx__c--may"><span aria-hidden="true">○</span><span class="sr">May contain</span></td>')
                else:
                    cells.append('<td class="mx__c mx__c--no"><span aria-hidden="true">·</span><span class="sr">No</span></td>')
            s = slices(it)
            kc = f'{it["kcal"]:,}' + (f'<span class="mx__slice"> · {round(it["kcal"] / s):,}/slice</span>' if s else "")
            rows.append(f'<tr><th scope="row" class="mx__dish"><a href="{root}menu/{it["id"]}/" data-dish="{it["id"]}">{e(it["name"])}</a></th>{"".join(cells)}<td class="mx__k">{kc}</td></tr>')
        groups.append(f'<tbody>{"".join(rows)}</tbody>')
    cols = '<col class="mx__col-dish">' + '<col>' * len(MENU["allergen_keys"]) + '<col class="mx__col-k">'
    return f'''<table class="mx">
  <caption class="sr">Allergens and calories of every dish</caption>
  <colgroup>{cols}</colgroup>
  <thead><tr><th scope="col" class="mx__dish">Dish</th>{head}<th scope="col" class="mx__k">kcal</th></tr></thead>
  {"".join(groups)}
</table>'''


def about_studies() -> str:
    studies = [("ing-flour", "farina"), ("ing-tomato", "pomodoro"), ("ing-basil", "basilico"),
               ("atmo-griddle", "smashed thin"), ("ing-mozzarella", "mozzarella"), ("ing-cheesepull.alternate", "the pull")]
    out = []
    for i, (ref, note) in enumerate(studies):
        it = ' lang="it"' if note in ("farina", "pomodoro", "basilico", "mozzarella") else ""
        out.append(f'<li class="astudy" style="--k:{i}"><span class="astudy__ph">{img(ref, "(min-width: 980px) 300px, 44vw", 4 / 5, max_w=800)}</span>'
                   f'<span class="astudy__note hand"{it}>{e(note)}</span></li>')
    return "".join(out)


def credits() -> str:
    rows = []
    for d in sorted(USED_PHOTOS.values(), key=lambda d: d["author"].lower()):
        rows.append(f'<li><a href="{e(d["page"])}" target="_blank" rel="noopener">{e(d["alt"])}<span class="sr"> (opens in a new tab)</span></a> <span class="credits__by">by {e(d["author"])}</span></li>')
    return "".join(rows)


# ───────────────────────────────────────────────────────────── JSON-LD, meta


def jsonld() -> str:
    """While `preview` is on, only what is true today: the name, the idea and the city. The phone, hours, price range
    and street address are samples, so they join the markup only when the preview is switched off."""
    c = SITE["contact"]
    names = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}
    ld = {
        "@context": "https://schema.org", "@type": "Restaurant", "name": SITE["name"],
        "url": SITE["base_url"], "image": SITE["base_url"] + "og.png", "logo": SITE["base_url"] + "apple-touch-icon.png",
        "description": SITE["description"], "slogan": SITE["tagline"], "servesCuisine": ["Pizza", "Burgers"],
        "address": {"@type": "PostalAddress", "addressLocality": c["city"], "addressRegion": c.get("region", "BC"),
                    "addressCountry": "CA"},
    }
    if not SITE.get("preview"):
        ld["telephone"] = tel()
        if c.get("street_address"):
            ld["address"]["streetAddress"] = c["street_address"]
        if c.get("postal_code"):
            ld["address"]["postalCode"] = c["postal_code"]
        ld["openingHoursSpecification"] = [{"@type": "OpeningHoursSpecification", "dayOfWeek": [names[d] for d in h["days"]],
                                            "opens": h["open"], "closes": h["close"]} for h in SITE["hours"]]
    if not MENU.get("sample"):
        ld["hasMenu"] = SITE["base_url"] + "menu/"
    return '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>"


def page_data() -> str:
    d = {"tz": SITE.get("timezone"), "opening": SITE.get("opening_date") or "", "hours": SITE["hours"],
         "street": SITE["contact"]["street"], "preview": bool(SITE.get("preview")), "allergens": ALLERGENS, "diets": DIETS}
    return '<script type="application/json" id="dv-data">' + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "</script>"


# ───────────────────────────────────────────────────────────── page assembly


def tpl(name: str) -> str:
    return (SRC / "templates" / name).read_text(encoding="utf-8")


def fill(text: str, values: dict) -> str:
    def rep(m: re.Match) -> str:
        k = m.group(1)
        if k not in values:
            raise SystemExit(f"template placeholder {{{{{k}}}}} has no value")
        return str(values[k])
    return re.sub(r"\{\{([a-z_0-9]+)\}\}", rep, text)


ASSET_V: dict[str, str] = {}
WRITTEN: set[Path] = set()


def write(rel: str, data: str | bytes) -> None:
    path = DOCS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    WRITTEN.add(path.resolve())


NAV = [("Menu", "menu/"), ("Combos", "menu/#combos"), ("Allergens", "allergens/"), ("Visit", "visit/"), ("About", "about/")]


def header(root: str, current: str) -> str:
    cur = ' aria-current="page"'
    links = "".join(f'<a href="{root}{href}"{cur if href == current else ""}>{label}</a>' for label, href in NAV)
    home = root or "./"
    preview = ('<span class="preview-tag" title="A preview: menu, prices and details are samples">Preview</span>'
               if SITE.get("preview") else "")
    return f'''<header class="top" data-top>
  <div class="top__in">
    <a class="brand" href="{home}"><img class="brand__mark" src="{root}favicon.svg" alt="" width="44" height="44"><span class="brand__word">Dough<span class="brand__dash">-</span>Vinci</span></a>
    {preview}
    <nav class="nav" aria-label="Main">{links}</nav>
    {status_html("short")}
    <a class="btn btn--order top__order" href="#order" data-order>{icon("i-bag")}<span>Order</span></a>
  </div>
</header>'''


def dock(root: str) -> str:
    items = [("Menu", "menu/", "i-slice"), ("Allergens", "allergens/", "a-wheat"), ("Visit", "visit/", "i-pin")]
    links = "".join(f'<a class="dock__link" href="{root}{href}">{icon(ic)}<span>{label}</span></a>' for label, href, ic in items)
    return f'''<nav class="dock" aria-label="Quick links">{links}<a class="btn btn--order dock__order" href="#order" data-order>{icon("i-bag")}<span>Order</span></a></nav>'''


def footer(root: str) -> str:
    c = SITE["contact"]
    apps = "".join(f'<li><a href="{e(d["url"])}" target="_blank" rel="noopener">{e(d["name"])}<span class="sr"> (opens in a new tab)</span></a></li>' for d in SITE["delivery"])
    fine = ("Preview: the menu, prices, calories, allergens, location, phone, hours and opening date are samples until "
            "Dough-Vinci confirms them, and the photos are stock images, not our dishes. " if SITE.get("preview") else "")
    strap = e(SITE.get("strap", ""))
    return f'''<footer class="foot">
  <img class="foot__water" src="{root}assets/art/pizza-lines.svg" alt="" width="1000" height="1000" loading="lazy" decoding="async">
  <div class="foot__in">
    <p class="foot__word">Dough<span>-</span>Vinci</p>
    <p class="foot__tag">Real Pizza. Real Smashburgers. <span class="hand">Made with Passion.</span></p>
    <p class="mirror foot__mirror"><span class="sr">{strap}</span><span class="mirror__in hand" aria-hidden="true">{strap}</span></p>
    <div class="foot__cols">
      <div><h2 class="foot__h">Order</h2><ul class="foot__list">{apps}<li><a href="tel:{tel()}">Call for pickup</a></li></ul></div>
      <div><h2 class="foot__h">Visit</h2><ul class="foot__list"><li>{e(c["address"])}</li><li><a href="tel:{tel()}">{e(c["phone"])}</a></li><li><a href="{root}visit/">Hours &amp; map</a></li></ul></div>
      <div><h2 class="foot__h">Eat well</h2><ul class="foot__list"><li><a href="{root}menu/">Menu</a></li><li><a href="{root}allergens/">Allergens &amp; nutrition</a></li><li><a href="{root}about/">About &amp; photo credits</a></li></ul></div>
    </div>
    <div class="foot__fine"><p>{fine}Photos from <a href="{root}about/#credits">Unsplash</a>.</p>
      <button class="motion-btn" type="button" data-motion aria-pressed="false">{icon("i-pause", "ico ico--sm")}<span data-motion-label>Pause motion</span></button></div>
  </div>
</footer>'''


def dialogs(root: str) -> str:
    return f'''<dialog class="sheet sheet--order" id="order-dialog" aria-labelledby="order-dialog-title">
  <div class="sheet__card">
    <form method="dialog" class="sheet__x-f"><button class="sheet__x" type="submit" aria-label="Close" autofocus>{icon("i-close")}</button></form>
    <img class="sheet__fly" src="{root}assets/art/flying-machine.svg" alt="" width="1200" height="700" loading="lazy" decoding="async">
    <p class="kicker-s">Delivery or pickup</p>
    <h2 class="sheet__title" id="order-dialog-title">Order</h2>
    <ul class="apps apps--sheet">{app_tiles("dlg")}</ul>
    <p class="sheet__line hand">{e(SITE.get("order_note", ""))}</p>
  </div>
</dialog>
<dialog class="sheet sheet--dish" id="dish-dialog" aria-labelledby="dish-dialog-title">
  <div class="sheet__card">
    <form method="dialog" class="sheet__x-f"><button class="sheet__x" type="submit" aria-label="Close" autofocus>{icon("i-close")}</button></form>
    <div data-dish-slot></div>
  </div>
</dialog>'''


def page(rel: str, *, title: str, description: str, main: str, current: str = "", body_class: str = "",
         head_extra: str = "", jsonld_on: bool = False, is_404: bool = False) -> None:
    depth = rel.count("/")
    # GitHub Pages serves 404.html at any missing address, so its links start from the site root. No <base>: with one,
    # the skip link and the #order links would resolve to the home page instead of staying on this page.
    root = SITE["base_path"] if is_404 else "../" * depth
    url_path = "" if rel == "index.html" else rel.replace("index.html", "")
    canonical = SITE["base_url"] + url_path
    robots = '<meta name="robots" content="noindex, nofollow">' if SITE.get("preview") or not SITE.get("index") else ""
    full_title = title if title.startswith(SITE["name"]) else f"{title} · {SITE['name']}"
    og = SITE["base_url"] + "og.png"
    doc = fill(tpl("base.html"), {
        "title": e(full_title), "description": e(description), "robots": robots,
        "canonical": e(canonical), "og_image": e(og), "og_title": e(full_title), "og_url": e(canonical),
        "site_name": e(SITE["name"]), "root": root, "fonts": e(FONTS), "css_v": ASSET_V["site.css"],
        "js_v": ASSET_V["site.js"], "head_extra": head_extra, "jsonld": jsonld() if jsonld_on else "",
        "data": page_data(), "sprite": "<!--SPRITE-->", "header": header(root, current), "main": main,
        "order_band": flying_band(root), "footer": footer(root), "dock": dock(root), "dialogs": dialogs(root),
        "body_class": body_class, "lang": SITE.get("lang", "en"),
    })
    extra = DISH_ICONS if "data-dish=" in doc else set()
    doc = doc.replace("<!--SPRITE-->", sprite_for(doc, extra), 1)
    write(rel, doc)


# ───────────────────────────────────────────────────────────── pages


def build_home() -> None:
    root = ""
    # slot widths as laid out: the pizza is 71% of the stage (620px, 470px on tablets, 92% of a phone's column)
    hero_sizes = "(min-width: 1000px) 460px, (min-width: 600px) 340px, 60vw"
    burger_sizes = "(min-width: 1000px) 200px, (min-width: 600px) 160px, 28vw"
    marks, legend = burger_labels()
    diet_f, avoid_f = filter_chips()
    main = fill(tpl("home.html"), {
        "root": root,
        "status_long": status_html("long"),
        "hero_pizza": img("hero-pizza", hero_sizes, 1, eager=True, max_w=1200,
                          alt="Margherita pizza seen from above: tomato, melted mozzarella and torn basil on a leopard-spotted crust"),
        "hero_burger": img("hero-burger", burger_sizes, 4 / 5, eager=False, max_w=600, low=True),
        "title_1": e(SITE["hero"]["title_lines"][0]).replace("Real ", ""),
        "title_2": e(SITE["hero"]["title_lines"][1]).replace("Real ", ""),
        "sub": e(SITE["hero"]["sub"]),
        "pillars": "".join(f"<li>{icon(i)}{e(p)}</li>" for p, i in zip(SITE["pillars"], ["d-vegetarian", "a-wheat", "i-gear"])),
        "signatures": signature_cards(root),
        # the drawing is The Vitruvian (pepperoni, mushroom, pepper, onion), so the photo under it is that pizza
        "wipe_photo": img("vitruvian", "(min-width: 600px) 360px, 60vw", 1, max_w=800, crop=(0.47, 0.56, 1.9), low=True),
        "spiral": golden_spiral(),
        "pizza_notes": pizza_notes(),
        "burger_marks": marks, "burger_legend": legend,
        "griddle": img("atmo-griddle", "(min-width: 681px) 170px, 40vw", 4 / 5, max_w=600, low=True),
        "tiles": category_tiles(root),
        "combos": combos_section(root),
        "map": map_figure(root, small=True),
        "address": e(SITE["contact"]["address"]),
        "cross": e(SITE["contact"].get("neighbourhood", "")),
        "maps": e(SITE["contact"]["maps_url"]),
        "hours": hours_rows(),
        "phone": e(SITE["contact"]["phone"]), "tel": tel(),
    })
    page("index.html", title=SITE["title"], description=SITE["description"], main=main, body_class="home",
         head_extra=preload("hero-pizza", hero_sizes, 1, max_w=1200), jsonld_on=True)


def build_menu() -> None:
    root = "../"
    diet_f, avoid_f = filter_chips()
    main = fill(tpl("menu.html"), {
        "root": root, "tabs": category_tabs(), "diet_filters": diet_f, "avoid_filters": avoid_f,
        "sections": menu_sections(root), "combos": combos_section(root),
        "note": e(MENU.get("note", "")) if MENU.get("sample") else "",
        "count": sum(len(c["items"]) for c in CATS),
        "warn": ('<p class="warn warn--sm" role="note">' + icon("i-warn", "ico warn__i") +
                 '<span><b>Sample menu.</b> Allergens and calories are placeholders, not for dietary decisions.</span></p>')
                if MENU.get("sample") else "",
    })
    page("menu/index.html", title="Menu", description="Pizzas, smashburgers, sides, desserts and drinks at Dough-Vinci, "
         "with prices, calories and allergens for every dish.", main=main, current="menu/", body_class="menu-page")
    for cat in CATS:
        for it in cat["items"]:
            r = "../../"
            main = f'''<div class="dish-page page">
  <p class="crumbs"><a href="{r}menu/#{cat['id']}">{icon("i-arrow", "ico ico--back")}Menu</a> <span aria-hidden="true">/</span> {e(cat['name'])}</p>
  {dish_detail(it, cat, r, level=1)}
</div>'''
            desc = f"{it['name']}: {it['short']} {price_from(it)}, {it['kcal']:,} kcal."
            page(f"menu/{it['id']}/index.html", title=it["name"], description=desc, main=main, current="menu/",
                 body_class="dish-page-body")


DISH_ICONS: set[str] = set()


def build_dish_fragments() -> None:
    frags = []
    for cat in CATS:
        for it in cat["items"]:
            frags.append(f'<template data-dish="{it["id"]}">{dish_detail(it, cat, "__ROOT__", level=2)}</template>')
    text = "\n".join(frags)
    DISH_ICONS.update(re.findall(r'<use href="#([^"]+)"', text))
    write("assets/dishes.html", "<!doctype html><meta charset=\"utf-8\"><meta name=\"robots\" content=\"noindex\"><title>Dish sheets</title>\n" + text)


def build_allergens() -> None:
    root = "../"
    keys = "".join(f'<li>{icon("a-" + k)}<span>{ALLERGENS[k]}</span></li>' for k in MENU["allergen_keys"])
    warn = ('<div class="warn" role="note">' + icon("i-warn", "ico warn__i") +
            '<p><b>Sample data, not for dietary decisions.</b> The dishes, allergens and calories below are placeholders '
            'until Dough-Vinci confirms its real recipes.</p></div>') if MENU.get("sample") else ""
    main = fill(tpl("allergens.html"), {"root": root, "warn": warn, "matrix": allergen_matrix(root),
                                        "note": e(MENU["allergen_note"]), "keys": keys})
    page("allergens/index.html", title="Allergens & nutrition", description="Every Dough-Vinci dish against the eleven "
         "priority allergens, with calories for the whole dish and per slice.", main=main, current="allergens/",
         body_class="allergens-page")


def build_visit() -> None:
    root = "../"
    c = SITE["contact"]
    main = fill(tpl("visit.html"), {
        "root": root, "status_long": status_html("long"), "address": e(c["address"]), "cross": e(c.get("neighbourhood", "")),
        "maps": e(c["maps_url"]), "hours": hours_rows(), "phone": e(c["phone"]), "tel": tel(), "email": e(c["email"]),
        "map": map_figure(root), "faq": faq(), "catering_title": e(SITE["catering"]["title"]),
        "catering_text": e(SITE["catering"]["text"]),
    })
    page("visit/index.html", title="Visit", description=f"Dough-Vinci on {c['address']}: hours, map, directions, "
         "phone, FAQ and catering.", main=main, current="visit/", body_class="visit-page", jsonld_on=True)


def about_title() -> str:
    first, _, rest = SITE["about"]["title"].partition(". ")
    return e(first + ".") + (f" <em>{e(rest)}</em>" if rest else "")


def build_about() -> str:
    root = "../"
    main = fill(tpl("about.html"), {
        "root": root, "title": about_title(),
        "lines": "".join(f"<p>{e(x)}</p>" for x in SITE["about"].get("lines", [])),
        # the owner's own welcome, word for word
        "welcome": "".join(f"<p>{e(x)}</p>" for x in SITE.get("welcome", [])),
        "studies": about_studies(),
        "credits": "{{credits_late}}",
    })
    # credits list every photo used on the site, so it is filled after all other pages are built
    return main


def build_404() -> None:
    main = fill(tpl("404.html"), {"root": SITE["base_path"]})
    page("404.html", title="Page not found", description="This page is missing from the codex.", main=main,
         body_class="nf-page", is_404=True)


# ───────────────────────────────────────────────────────────── static files


def build_assets() -> None:
    css = (SRC / "css" / "site.css").read_text(encoding="utf-8")
    css = css.replace("/*ART-CSS*/", art_css())
    js = (SRC / "js" / "site.js").read_text(encoding="utf-8")
    write("assets/site.css", css)
    write("assets/site.js", js)
    ASSET_V["site.css"] = hashlib.sha1(css.encode()).hexdigest()[:8]
    ASSET_V["site.js"] = hashlib.sha1(js.encode()).hexdigest()[:8]

    pizza = (ART / "pizza-study.svg").read_text(encoding="utf-8")
    burger = (ART / "burger-study.svg").read_text(encoding="utf-8")
    write("assets/art/pizza-study.svg", bake(chunk_strokes(chunk_strokes(pizza, "art-hatch", 20), "art-line", 3)))
    write("assets/art/burger-study.svg", bake(chunk_strokes(chunk_strokes(burger, "art-hatch", 20), "art-line", 2)))
    write("assets/art/pizza-lines.svg", bake(chunk_strokes(line_only(pizza), "art-line", 6), "codex-art--water"))
    for name in ("map", "flying-machine", "gears"):
        p = NEW_ART / f"{name}.svg"
        src = p if p.exists() else ART / f"{name}-fallback.svg"
        write(f"assets/art/{name}.svg", bake(src.read_text(encoding="utf-8")))
    write("favicon.svg", bake(mark_svg()))  # also the header mark: one file, one download
    for name in ("og.png", "apple-touch-icon.png"):
        p = SRC / "img" / name
        if p.exists():
            write(name, p.read_bytes())
    for p in (ROOT / "brief").glob("*.pdf"):
        write(f"brief/{p.name}", p.read_bytes())
    write(".nojekyll", "")


def build_meta(pages: list[str]) -> None:
    preview = SITE.get("preview") or not SITE.get("index")
    base = SITE["base_url"]
    robots = "User-agent: *\nDisallow: /\n" if preview else f"User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n"
    write("robots.txt", robots)
    urls = "".join(f"<url><loc>{e(base + p)}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>" for p in pages)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    manifest = {"name": f"{SITE['name']} {SITE['subtitle']}", "short_name": SITE["name"], "start_url": "./",
                "scope": "./", "display": "standalone", "background_color": "#FFF8EC", "theme_color": "#FFF8EC",
                "description": SITE["description"],
                "icons": [{"src": "apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
                          {"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"}]}
    write("manifest.webmanifest", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    c = SITE["contact"]
    hours = "; ".join(f"{day_range(h['days'])} {fmt_time(h['open'])}–{fmt_time(h['close'])}" for h in SITE["hours"])
    od = opening()
    lines = [f"# {SITE['name']} {SITE['subtitle']}", "", f"> {SITE['tagline']} A pizza and smashburger restaurant on "
             f"{c['street']}, {c['city']}.", ""]
    if SITE.get("preview"):
        lines += ["This site is a preview: the menu, prices, calories, allergens, location, phone, hours and opening date "
                  "are samples, and the photos are stock images.", ""]
    if od and TODAY < od:
        lines += [f"Opening date: {od.isoformat()}.", ""]
    lines += [f"- Location: {c['address']} ({c.get('neighbourhood', '')})", f"- Phone: {c['phone']}", f"- Hours: {hours}",
              "- Ordering: " + ", ".join(f"[{d['name']}]({d['url']})" for d in SITE["delivery"]) + "; or call for pickup.",
              "", "## Pages", "", f"- [Menu]({base}menu/): every dish with price, calories, ingredients and allergens",
              f"- [Allergens & nutrition]({base}allergens/): the allergen matrix", f"- [Visit]({base}visit/): hours, map, FAQ, catering",
              f"- [About]({base}about/): the idea and photo credits", "", "## Menu", ""]
    for cat in CATS:
        lines.append(f"### {cat['name']}")
        for it in cat["items"]:
            ps = ", ".join(f"{p['label'].replace(chr(34), ' in')} {money(p['price'])}" if p["label"] != "Regular" else money(p["price"]) for p in it["prices"])
            al = ", ".join(ALLERGENS[a] for a in it["allergens"]) or "none of the priority allergens"
            lines.append(f"- {it['name']}: {it['short']} {ps}. {it['kcal']:,} kcal ({it['portion']}). Contains: {al}.")
        lines.append("")
    write("llms.txt", "\n".join(lines))


def trash_stale() -> None:
    stale = [p for p in DOCS.rglob("*") if p.is_file() and p.resolve() not in WRITTEN]
    if stale:
        subprocess.run(["trash", *map(str, stale)], check=True)
    for d in sorted((p for p in DOCS.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            subprocess.run(["trash", str(d)], check=True)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    build_assets()
    build_dish_fragments()
    build_home()
    build_menu()
    build_allergens()
    build_visit()
    build_404()
    about_main = build_about()
    about_main = about_main.replace("{{credits_late}}", credits())
    page("about/index.html", title="About", description="Dough-Vinci: the pizza is the art, the smashburger is the "
         "engineering. The idea, the drawings and the photo credits.", main=about_main, current="about/", body_class="about-page")
    pages = ["", "menu/", "allergens/", "visit/", "about/"] + [f"menu/{i}/" for i in ORDER_IDS]
    build_meta(pages)
    trash_stale()
    print(f"built {len(WRITTEN)} files into docs/")


if __name__ == "__main__":
    main()
