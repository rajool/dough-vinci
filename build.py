#!/usr/bin/python3
"""Build the Dough-Vinci site: content/*.json + src/ -> docs/ (the GitHub Pages folder).

    python3 build.py

Standard library only. Page skeletons live in src/templates/ with {{placeholders}}; everything that repeats (the menu
board, the dish sheet, hours, the order list, the allergen table, the halal mark) is rendered here from content/*.json,
so a new price, dish, photo, opening date or delivery link is a JSON edit and a rebuild. Never edit docs/ by hand.

Files in docs/ that this build no longer writes are moved to the Trash with `trash` (never deleted outright).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SRC = ROOT / "src"
DOCS = ROOT / "docs"

e = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


SITE = load("site.json")
MENU = load("menu.json")
PHOTO_DOC = load("photos.json")
PHOTOS = {p["key"]: p for p in PHOTO_DOC["photos"]}
NO_PHOTO = set(PHOTO_DOC.get("no_photo", []))
PROFILES = {p["name"]: p["profile"] for p in PHOTO_DOC.get("photographers", [])}
TZ = ZoneInfo(SITE.get("timezone", "America/Vancouver"))
TODAY = dt.datetime.now(TZ).date()

ALLERGENS = {
    "wheat": "Wheat", "milk": "Milk", "egg": "Egg", "soy": "Soy", "sesame": "Sesame", "mustard": "Mustard",
    "peanut": "Peanut", "treenut": "Tree nuts", "fish": "Fish", "shellfish": "Shellfish", "sulphites": "Sulphites",
}
DIETS = {"vegetarian": "Vegetarian", "vegan": "Vegan", "spicy": "Spicy", "gluten-free-option": "Gluten-free option"}
# the menu's filters: a vegan dish also counts as vegetarian
FILTERS = [("veg", "Vegetarian"), ("spicy", "Spicy"), ("gf", "Gluten-free option")]
DAY_SHORT = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}
DAY_LONG = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday",
            "sat": "Saturday", "sun": "Sunday"}
FONTS = "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..100,400..900&display=swap"
# the serif is only «Made with Passion.» and the Arabic face only «حلال», so this sheet asks Google for those glyphs only
ACCENT_TEXT = SITE["hero"]["sub"] + SITE["halal"]["mark_ar"]
FONTS_ACCENT = ("https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@1&family=Noto+Kufi+Arabic:wght@700"
                f"&text={quote(ACCENT_TEXT)}&display=swap")

CATS = MENU["categories"]
ITEMS = {it["id"]: (cat, it) for cat in CATS for it in cat["items"]}
ORDER_IDS = [it["id"] for cat in CATS for it in cat["items"]]
USED_PHOTOS: dict[str, dict] = {}


def check_content() -> None:
    """Every dish either has its photo (same key in photos.json) or is listed as text-only, never both."""
    for i in ORDER_IDS:
        if (i in PHOTOS) == (i in NO_PHOTO):
            raise SystemExit(f"photos.json: {i} must have a photo or be listed in no_photo, not both or neither")
    for k in NO_PHOTO - set(ORDER_IDS):
        raise SystemExit(f"photos.json: no_photo lists {k}, which is not on the menu")
    for p in PHOTOS.values():
        if not p.get("alt", "").strip() or p.get("author") not in PROFILES:
            raise SystemExit(f"photos.json: {p['key']} needs alt text and a listed photographer")
    for s in SITE.get("signatures", []):
        if s not in PHOTOS:
            raise SystemExit(f"site.json: signature {s} has no photo")


def has_photo(item_id: str) -> bool:
    return item_id in PHOTOS


# ───────────────────────────────────────────────────────────── photos


def photo(key: str) -> dict:
    ph = PHOTOS[key]
    USED_PHOTOS.setdefault(ph["url"], ph)
    return ph


def img_url(ph: dict, w: int, ratio: float | None = None, q: int = 75, crop: tuple | None = None) -> str:
    """Unsplash (imgix) crops the frame to the slot's ratio around the focal point, so no pixel is sent twice."""
    parts = ["auto=format", "fit=crop", f"w={w}"]
    if ratio:
        parts.append(f"h={round(w / ratio)}")
    parts.append(f"q={q}")
    c = crop or ph.get("crop")
    if c:
        parts += ["crop=focalpoint", f"fp-x={c[0]}", f"fp-y={c[1]}", f"fp-z={c[2]}"]
    return ph["url"] + "?" + "&".join(parts)


WIDTHS = (400, 600, 800, 1000, 1200, 1600)
# Phones at 3x get the 2x file: past 2x nobody sees the difference, and the bytes compete with the hero. A <source>
# for those screens repeats the srcset with every slot in `sizes` scaled by 2/3, so the browser asks for 2x.
HI_DPR = "(min-resolution: 2.5dppx), (-webkit-min-device-pixel-ratio: 2.5)"
LO_DPR = "(max-resolution: 2.49dppx)"
PHONE = "(max-width: 899px)"
WIDE = "(min-width: 900px)"


def srcset(ph: dict, ratio: float, max_w: int = 1600, crop: tuple | None = None) -> list[tuple[str, int]]:
    return [(img_url(ph, w, ratio, crop=crop), w) for w in WIDTHS if w <= max_w]


def scale_sizes(sizes: str, f: float) -> str:
    """'(min-width: 1000px) 460px, 60vw' scaled by f: the media conditions stay, the slot lengths shrink."""
    out = []
    for part in sizes.split(","):
        m = re.fullmatch(r"\s*(\([^)]*\)\s+)?(\d+(?:\.\d+)?)(px|vw)\s*", part)
        if not m:
            raise SystemExit(f"sizes part not understood: {part!r}")
        out.append(f"{m.group(1) or ''}{round(float(m.group(2)) * f)}{m.group(3)}")
    return ", ".join(out)


def phone_sizes(sizes: str) -> str:
    """The slot length a phone uses: the last part of `sizes`, the one without a media condition."""
    return sizes.split(",")[-1].strip()


def img(key: str, sizes: str, ratio: float, *, eager: bool = False, high: bool | None = None, alt: str | None = None,
        max_w: int = 1600, crop: tuple | None = None, phone_ratio: float | None = None) -> str:
    """A responsive Unsplash photo. alt="" for a photo inside a link that its own text already names.

    eager: on the first screen, so not lazy (and fetchpriority=high unless high=False). phone_ratio: the box a phone
    shows (under 900 px) when it differs from `ratio`, so a phone loads that crop instead of cutting a taller one."""
    ph = photo(key)
    ss = srcset(ph, ratio, max_w, crop)
    src = ss[min(2, len(ss) - 1)][0]
    w = ss[-1][1]
    a = ph["alt"] if alt is None else alt
    high = eager if high is None else high
    load_attr = ('fetchpriority="high" ' if high else 'loading="eager" ' if eager else 'loading="lazy" ') + 'decoding="async"'
    set_ = e(", ".join(f"{u} {w}w" for u, w in ss))
    sources = ""
    if phone_ratio:
        pset = e(", ".join(f"{u} {w}w" for u, w in srcset(ph, phone_ratio, max_w, crop)))
        psz = phone_sizes(sizes)
        hi = ", ".join(f"{PHONE} and {m.strip()}" for m in HI_DPR.split(","))
        sources += (f'<source media="{hi}" srcset="{pset}" sizes="{scale_sizes(psz, 2 / 3)}">'
                    f'<source media="{PHONE}" srcset="{pset}" sizes="{psz}">')
    return (f'<picture>{sources}<source media="{HI_DPR}" srcset="{set_}" sizes="{scale_sizes(sizes, 2 / 3)}">'
            f'<img src="{e(src)}" srcset="{set_}" sizes="{sizes}" width="{w}" height="{round(w / ratio)}" '
            f'alt="{e(a)}" {load_attr}></picture>')


def preload(key: str, sizes: str, ratio: float, max_w: int = 1600, crop: tuple | None = None,
            phone_ratio: float | None = None) -> str:
    """Preloads that pick the same file as img(): the 2x file for 3x screens, the crop a phone shows, and each with a
    media query that excludes the others, so a browser fetches one file."""
    ph = PHOTOS[key]
    ss = srcset(ph, ratio, max_w, crop)
    set_ = e(", ".join(f"{u} {w}w" for u, w in ss))
    hi, lo = "(min-resolution: 2.5dppx)", LO_DPR
    rows = [(set_, ss, media, sz) for media, sz in ((lo, sizes), (HI_DPR, scale_sizes(sizes, 2 / 3)))]
    if phone_ratio:
        pss = srcset(ph, phone_ratio, max_w, crop)
        pset = e(", ".join(f"{u} {w}w" for u, w in pss))
        psz = phone_sizes(sizes)
        rows = [(pset, pss, f"{PHONE} and {lo}", psz), (pset, pss, f"{PHONE} and {hi}", scale_sizes(psz, 2 / 3)),
                (set_, ss, f"{WIDE} and {lo}", sizes), (set_, ss, f"{WIDE} and {hi}", scale_sizes(sizes, 2 / 3))]
    return "\n".join(f'<link rel="preload" as="image" href="{e(lst[min(2, len(lst) - 1)][0])}" imagesrcset="{st}" '
                     f'imagesizes="{sz}" media="{media}" fetchpriority="high">' for st, lst, media, sz in rows)


# ───────────────────────────────────────────────────────────── marks and icons

ICONS = {
    # a delivery scooter with its box, drawn as plain square-ended lines
    "scooter": '<rect x="2" y="5.5" width="7" height="5.5"/><path d="M2 14h8.5l3-6.5H17"/><path d="M14.5 7.5l4 9.5"/>'
               '<path d="M8 17h8"/><circle cx="5.5" cy="17" r="2.5"/><circle cx="19" cy="17" r="2.5"/>',
    "arrow": '<path d="M3 12h16M13 6l6 6-6 6"/>',
    "back": '<path d="M21 12H5M11 6l-6 6 6 6"/>',
    "out": '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "mail": '<rect x="3" y="5" width="18" height="14"/><path d="M3 6l9 7 9-7"/>',
}


def icon(name: str, cls: str = "ico") -> str:
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="square">{ICONS[name]}</svg>')


def halal_mark(cls: str = "") -> str:
    """The owner's neon sign, drawn flat: «حلال» inside a ring on a basil disc, the word Halal beside it."""
    h = SITE["halal"]
    return (f'<span class="halal {cls}"><span class="halal__disc" aria-hidden="true"><span lang="ar" dir="rtl">'
            f'{e(h["mark_ar"])}</span></span><span class="halal__en">{e(h["mark_en"])}</span></span>')


def halal_statement() -> str:
    """The halal statement, each sentence on its own line."""
    parts = re.split(r"(?<=\.)\s+", SITE["halal"]["statement"])
    return " ".join(f"<span>{e(x)}</span>" for x in parts)


def certification() -> str:
    """«Halal certification by the BC Muslim Association (BCMA).», from `halal.certifier`; no logo until the owner
    sends the certificate's."""
    h = SITE["halal"]
    return f"Halal certification by {h['certifier']}." if h.get("certifier") else ""


def tricolour(cls: str) -> str:
    return f'<span class="tri {cls}" aria-hidden="true"><i></i><i></i><i></i></span>'


def wordmark(tag: str = "span") -> str:
    return f'<{tag} class="wm">Dough<span class="wm__dash">-</span>Vinci</{tag}>'


# ───────────────────────────────────────────────────────────── small formatters


def money(p: str | float) -> str:
    v = float(p)
    return f"${v:g}" if v == int(v) else f"${v:.2f}"


def size_label(label: str) -> str:
    """12" for the eye, «12-inch» for screen readers."""
    m = re.fullmatch(r'(\d+)"', label)
    if m:
        return f'<span aria-hidden="true">{m.group(1)}″</span><span class="sr">{m.group(1)}-inch</span>'
    return e(label)


def sr_size(label: str) -> str:
    """On the board the column heads show 12″ and 16″; each price still says its size to a screen reader."""
    m = re.fullmatch(r'(\d+)"', label)
    return f'<span class="sr">{m.group(1)}-inch </span>' if m else f'<span class="sr">{e(label)} </span>'


def inches(text: str) -> str:
    """A size written 12" in the content reads 12″ on the page and «12-inch» to a screen reader."""
    return re.sub(r'(\d+)&quot;', r'<span aria-hidden="true">\1″</span><span class="sr">\1-inch</span>', e(text))


def is_pizza(item: dict) -> bool:
    return bool(re.match(r"12-inch pizza", item.get("portion", "")))


def basis(item: dict) -> str:
    """What the calories are for, in the board's short form."""
    if is_pizza(item):
        return "per 12″ pie, whole"
    return "per " + item["portion"]


def basis_long(item: dict) -> str:
    p = item["portion"]
    if is_pizza(item):
        return "Per 12″ pie, whole" + (f" ({m.group(1)} slices)" if (m := re.search(r"\((\d+) slices\)", p)) else "")
    return "Per " + p


def fmt_time(t: str) -> str:
    h, m = map(int, t.split(":"))
    return f"{h % 12 or 12}{':' + str(m).zfill(2) if m else ''} {'am' if h < 12 else 'pm'}"


def day_range(days: list[str]) -> str:
    return DAY_SHORT[days[0]] if len(days) == 1 else f"{DAY_SHORT[days[0]]}–{DAY_SHORT[days[-1]]}"


def opening() -> dt.date | None:
    od = SITE.get("opening_date")
    return dt.date.fromisoformat(od) if od else None


def opening_approx() -> bool:
    """`opening_approx`: the owner gave the date as approximate, so no page shows its weekday or day number."""
    return bool(SITE.get("opening_approx"))


def part_of_month(d: dt.date, month: str) -> str:
    """«early December», «mid-December», «late December»: an approximate date said the way a person would."""
    return f"early {month}" if d.day <= 10 else f"mid-{month}" if d.day <= 20 else f"late {month}"


def opening_short(d: dt.date) -> str:
    return part_of_month(d, f"{d:%b}") if opening_approx() else f"{d:%b} {d.day}"


def opening_long(d: dt.date) -> str:
    return part_of_month(d, f"{d:%B}") if opening_approx() else f"{d:%a}, {d:%b} {d.day}"


def opening_phrase(d: dt.date) -> str:
    """What `{opening}` in a FAQ answer becomes: «in early December 2026», or «on Tuesday, December 1»."""
    return f"in {part_of_month(d, f'{d:%B}')} {d.year}" if opening_approx() else f"on {d:%A}, {d:%B} {d.day}"


def keep(s: str) -> str:
    """Escaped text whose «No. 1» and postal code never break across lines."""
    out = e(s).replace("No. ", "No.&nbsp;")
    pc = SITE["contact"].get("postal_code", "")
    return out.replace(e(pc), e(pc).replace(" ", "&nbsp;")) if pc else out


def email_html(addr: str) -> str:
    """An email address that may break only after the @, never at the hyphen of the domain."""
    user, _, dom = addr.partition("@")
    return f'{e(user)}@<wbr><span class="nw">{e(dom)}</span>'


def tel() -> str:
    return "+1" + re.sub(r"\D", "", SITE["contact"]["phone"])


def preview() -> bool:
    return bool(SITE.get("preview"))


def confirmed(field: str) -> bool:
    """Whether the owner has confirmed a field (`confirmed` in site.json); the menu follows menu.json `sample`."""
    if field == "menu":
        return not MENU.get("sample")
    return bool(SITE.get("confirmed", {}).get(field))


def is_sample(field: str) -> bool:
    """A datum shown as a sample: the preview is on and the owner has not confirmed it."""
    return preview() and not confirmed(field)


def sample_tag(field: str, what: str = "Sample") -> str:
    """A quiet label beside a datum a customer would rely on, while it is still a sample."""
    return f'<span class="smp">{e(what)}</span>' if is_sample(field) else ""


def and_list(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


# what each field is called in the lists of samples: (in the header, in a sentence)
SAMPLE_WORDS = {
    "menu": (["the menu", "prices"], ["the menu, prices, calories and allergens"]),
    "location": (["place"], ["the location"]),
    "hours": (["hours"], ["the hours"]),
    "phone": (["phone"], ["the phone number"]),
    "email": ([], ["the email address"]),
    "opening_date": (["date"], ["the opening date"]),
    "halal": ([], ["the halal details"]),
    "delivery": ([], ["the delivery-app links"]),
}


def samples(short: bool = False) -> list[str]:
    """The fields still shown as samples, in words, from `confirmed` (the photos have their own sentence)."""
    out: list[str] = []
    for field, (s_words, l_words) in SAMPLE_WORDS.items():
        if is_sample(field):
            words = s_words if short else l_words
            if field == "opening_date" and opening_approx() and not short:
                words = ["the exact opening day"]
            out += words
    return out


def soon() -> bool:
    od = opening()
    return bool(od and TODAY < od)


def date_tag() -> str:
    """The Sample label beside the opening date, while there is one to show and it is unconfirmed."""
    return sample_tag("opening_date", "Sample date") if soon() else ""


def status(variant: str) -> str:
    """The open-now line, as true at build time; site.js keeps it live. Before the opening date it gives the date;
    while the preview is on after that it says nothing about being open, because the hours are samples."""
    if soon():
        od = opening()
        text = f"Opening {opening_short(od)}" if variant == "short" else f"Opening {opening_long(od)}"
        state = "soon"
    else:
        text, state = ("", "") if variant == "short" else ("See the hours", "")
    hidden = " hidden" if not text else ""
    return f'<span class="status" data-status="{variant}" data-state="{state}"{hidden}>{e(text)}</span>'


# ───────────────────────────────────────────────────────────── shared blocks


def apps_list(cls: str) -> str:
    """The four apps by name as plain text, then Call for pickup. No payment on this site."""
    rows = [f'<li><a href="{e(d["url"])}" target="_blank" rel="noopener"><span class="{cls}__name">{e(d["name"])}</span>'
            f'{icon("out", "ico ico--sm")}<span class="sr"> (opens in a new tab)</span></a></li>' for d in SITE["delivery"]]
    return "".join(rows)


def order_band(level: int = 2) -> str:
    """The red band: every page has it, with id="order", so every Order link works without JavaScript."""
    c = SITE["contact"]
    return f'''<section class="ob wipe" id="order" aria-labelledby="ob-title">
  <div class="ob__in">
    <h{level} class="ob__h d" id="ob-title">Order</h{level}>
    <div class="ob__apps"><p class="ob__lbl">Delivery or pickup</p><ul class="ob__list">{apps_list("ob")}</ul></div>
    <div class="ob__call"><p class="ob__lbl">Call for pickup {sample_tag("phone")}</p><a class="ob__tel" href="tel:{tel()}">{e(c["phone"])}</a></div>
    {halal_mark("halal--band")}
  </div>
</section>'''


def hours_table(cls: str = "hours") -> str:
    rows = []
    for h in SITE["hours"]:
        today = " is-today" if TODAY.strftime("%a").lower()[:3] in h["days"] else ""
        rows.append(f'<tr class="{today.strip()}" data-days="{" ".join(h["days"])}"><th scope="row">{day_range(h["days"])}'
                    f'<span class="hours__today"{"" if today else " hidden"}> · today</span></th>'
                    f'<td>{fmt_time(h["open"])} – {fmt_time(h["close"])}</td></tr>')
    return f'<table class="{cls}"><caption class="sr">Opening hours, Pacific time</caption><tbody>{"".join(rows)}</tbody></table>'


def leonardo(heading: str = "p") -> str:
    """One real drawing in its own ink on a cream panel, its credit, and the one line beside it."""
    L = SITE["leonardo"]
    w0, h0 = L["ratio"]
    ws = L["widths"]
    set_ = e(", ".join(f"{L['file'].format(w=w)} {w}w" for w in ws))
    # the drawing is a supporting figure: about a third of the width on wide screens, two thirds of a phone's
    sizes = "(min-width: 900px) 34vw, (min-width: 600px) 36vw, 60vw"
    line = e(L["line"])
    first, _, rest = L["line"].partition(". ")
    line = f'<span>{e(first)}.</span> <span class="leo__b">{e(rest)}</span>' if rest else line
    return f'''<section class="leo" aria-label="The idea">
  <div class="leo__in">
    <figure class="leo__fig rv">
      <picture><source media="{HI_DPR}" srcset="{set_}" sizes="{scale_sizes(sizes, 2 / 3)}"><img src="{e(L['file'].format(w=ws[1]))}" srcset="{set_}" sizes="{sizes}" width="{w0}" height="{h0}" alt="{e(L['alt'])}" loading="lazy" decoding="async"></picture>
      <figcaption><a href="{e(L['page'])}" target="_blank" rel="noopener">{e(L['credit'])}<span class="sr"> (opens in a new tab)</span></a></figcaption>
    </figure>
    <{heading} class="leo__line d rv">{line}</{heading}>
  </div>
</section>'''


# ───────────────────────────────────────────────────────────── menu


def diet_words(item: dict) -> list[str]:
    out = []
    if item.get("badge"):
        out.append(f'<b class="t-sig">{e(item["badge"])}</b>')
    for d in item.get("diet", []):
        cls = {"vegetarian": "t-veg", "vegan": "t-veg", "spicy": "t-hot"}.get(d, "t-gf")
        out.append(f'<b class="{cls}">{DIETS[d]}</b>')
    return out


def allergen_text(keys: list[str], none: str) -> str:
    return ", ".join(ALLERGENS[k] for k in keys) if keys else none


def flags(item: dict) -> str:
    d = item.get("diet", [])
    return (f'data-veg="{str("vegetarian" in d or "vegan" in d).lower()}" data-spicy="{str("spicy" in d).lower()}" '
            f'data-gf="{str("gluten-free-option" in d).lower()}"')


def board_row(item: dict, root: str) -> str:
    multi = len(item["prices"]) > 1
    prices = "".join(f'<span class="row__p">{sr_size(p["label"]) if multi else ""}'
                     f'<span class="row__n">{money(p["price"])}</span></span>' for p in item["prices"])
    meta = [f'{item["kcal"]:,} kcal {basis(item)}', "Contains " + allergen_text(item["allergens"], "no major allergens").lower()
            if item["allergens"] else "No major allergens"] + diet_words(item)
    return f'''<li class="row" {flags(item)}>
  <a class="row__a" href="{root}menu/{item['id']}/" data-dish="{item['id']}">
    <span class="row__top"><span class="row__name">{e(item['name'])}</span><span class="row__dots" aria-hidden="true"></span><span class="row__ps">{prices}</span></span>
    <span class="row__short">{e(item['short'])}</span>
    <span class="row__meta">{'<span class="sep" aria-hidden="true">&nbsp;· </span>'.join(meta)}</span>
  </a>
</li>'''


def board(cat: dict, root: str, side: dict | None = None) -> str:
    """The cream price board: two columns of rows, or one column beside the section's only photo."""
    items = cat["items"]
    multi = len(items[0]["prices"]) > 1
    half = (len(items) + 1) // 2
    cols = [items] if side or len(items) < 2 else [items[:half], items[half:]]
    head = ""
    if multi:
        head = ('<p class="board__head" aria-hidden="true">' +
                "".join(f'<span>{e(p["label"]).replace("&quot;", "″")}</span>' for p in items[0]["prices"]) + "</p>")
    body = "".join(f'<div class="board__col">{head}<ul class="board__list">{"".join(board_row(i, root) for i in col)}</ul></div>'
                   for col in cols)
    ph = ""
    if side:
        ph = (f'<div class="board__ph strip__i" {flags(side)}><a href="{root}menu/{side["id"]}/" data-dish="{side["id"]}">'
              f'<span class="ph">{img(side["id"], "(min-width: 900px) 40vw, 100vw", 4 / 3, alt="", max_w=1200)}</span>'
              f'<span class="strip__lab"><span class="strip__name">{e(side["name"])}</span>'
              f'<span class="strip__p">{money(side["prices"][0]["price"])}</span></span></a></div>')
    cls = "board" + (" board--side" if side else "") + (" board--one" if len(cols) == 1 and not side else "")
    return (f'<div class="{cls}"><div class="board__cols">{body}'
            f'<p class="board__none" hidden>No dishes in this section match.</p></div>{ph}</div>')


STRIP_RATIO = {1: 21 / 9, 2: 16 / 10, 3: 1, 4: 4 / 5}


def shots_for(cat: dict) -> list[dict]:
    """The section's photos: photos.json `strips` picks them (one angle family per strip), else every photographed dish."""
    pick = PHOTO_DOC.get("strips", {}).get(cat["id"])
    if pick:
        return [ITEMS[i][1] for i in pick]
    return [i for i in cat["items"] if has_photo(i["id"])]


def strip_sizes(n: int) -> str:
    return "100vw" if n == 1 else (f"(min-width: 900px) {round(100 / n)}vw, 86vw" if n == 2 else
                                   f"(min-width: 900px) {round(100 / n)}vw, 78vw")


def strip(cat: dict, root: str, first: bool = False) -> str:
    """Photos only of this category's own dishes, each opening its dish; none when the section has no photos.
    A photo's `strip_crop` in photos.json frames it for the strip (so a strip reads as one family); the dish sheet keeps
    its `crop`. The menu's first strip is on the first screen, so it loads at once, its first photo first."""
    shots = shots_for(cat)
    if not shots:
        return ""
    n = len(shots)
    ratio = STRIP_RATIO[min(n, 4)]
    sizes = strip_sizes(n)
    cells = []
    for k, it in enumerate(shots):
        c = PHOTOS[it["id"]].get("strip_crop")
        pic = img(it['id'], sizes, ratio, alt="", max_w=1600 if n == 1 else 1200, crop=tuple(c) if c else None,
                  eager=first, high=first and k == 0, phone_ratio=4 / 3 if n == 1 else None)
        cells.append(f'''<li class="strip__i" {flags(it)}><a href="{root}menu/{it['id']}/" data-dish="{it['id']}">
  <span class="ph">{pic}</span>
  <span class="strip__lab"><span class="strip__name">{e(it['name'])}</span><span class="strip__p">{money(it['prices'][0]['price'])}</span></span>
</a></li>''')
    return f'<ul class="strip strip--{n}" style="--r:{ratio:.4f}">{"".join(cells)}</ul>'


def from_price(cat: dict) -> str:
    return money(min(float(i["prices"][0]["price"]) for i in cat["items"]))


def section_body(cat: dict, root: str, first: bool = False) -> str:
    """A wide strip above the board; a small section's only photo sits beside its board instead."""
    shots = shots_for(cat)
    if len(shots) == 1 and len(cat["items"]) <= 3:
        return board(cat, root, side=shots[0])
    return strip(cat, root, first) + board(cat, root)


def menu_preload() -> str:
    """The first photo of the menu's first strip, on the first screen of the page."""
    cat = CATS[0]
    shots = shots_for(cat)
    if not shots or (len(shots) == 1 and len(cat["items"]) <= 3):
        return ""
    n = len(shots)
    c = PHOTOS[shots[0]["id"]].get("strip_crop")
    return preload(shots[0]["id"], strip_sizes(n), STRIP_RATIO[min(n, 4)], max_w=1600 if n == 1 else 1200,
                   crop=tuple(c) if c else None, phone_ratio=4 / 3 if n == 1 else None)


def menu_sections(root: str) -> str:
    out = []
    for ci, cat in enumerate(CATS):
        n = len(cat["items"])
        out.append(f'''<section class="cat" id="{cat['id']}" aria-labelledby="h-{cat['id']}" data-spy>
  <header class="cat__head rv"><h2 class="cat__h d" id="h-{cat['id']}">{e(cat['name'])}</h2>
    <p class="cat__tag">{e(cat['tagline'])} <span class="cat__n">{n} {'dish' if n == 1 else 'dishes'}, from {from_price(cat)}.</span></p></header>
  {section_body(cat, root, first=ci == 0)}
</section>''')
    return "\n".join(out)


def combos_html(level: int, link: bool, root: str) -> str:
    cards = []
    for c in MENU["combos"]:
        inner = (f'<h{level + 1} class="combo__name d">{e(c["name"])}</h{level + 1}>'
                 f'<p class="combo__price d">{money(c["price"])}</p>'
                 f'<p class="combo__in">{inches(", ".join(c["contents"]))}</p>')
        if link:
            cards.append(f'<li class="combo rv"><a href="{root}menu/#combo-{c["id"]}">{inner}'
                         f'<span class="combo__go">{icon("arrow")}</span></a></li>')
        else:
            cards.append(f'<li class="combo rv" id="combo-{c["id"]}">{inner}</li>')
    return "".join(cards)


# ───────────────────────────────────────────────────────────── the dish sheet


DISH_PAGE_SIZES = "(min-width: 900px) 50vw, 100vw"      # half the page, as tall as the screen under the header
DISH_SHEET_SIZES = "(min-width: 1080px) 540px, (min-width: 900px) 50vw, 100vw"  # half the sheet, full height
DISH_SHEET_RATIO = 3 / 5


def dish_photo(item_id: str, page: bool, eager: bool = False) -> str:
    """The dish's photo as its own page shows it (a 4:5 panel) or as the sheet does (a full-height 3:5 panel); 4:3 on
    phones, where it sits on top."""
    if page:
        return img(item_id, DISH_PAGE_SIZES, 4 / 5, max_w=1200, eager=eager, phone_ratio=4 / 3)
    return img(item_id, DISH_SHEET_SIZES, DISH_SHEET_RATIO, max_w=1200, phone_ratio=4 / 3)


def dish_detail(item: dict, cat: dict, root: str, level: int = 2, page: bool = False) -> str:
    h = f"h{level}"
    sub = f"h{level + 1}"
    nut = item["nutrition"]
    pic = has_photo(item["id"])
    kick = [e(cat["name"])] + diet_words(item)
    sizes = "".join(f'<li><span class="dd__sl">{size_label(p["label"]) if p["label"] != "Regular" else "Price"}</span>'
                    f'<span class="dd__dots" aria-hidden="true"></span><span class="dd__pr">{money(p["price"])}</span></li>'
                    for p in item["prices"])
    cells = [("Calories", f'{item["kcal"]:,}', "kcal"), ("Protein", f'{nut["protein_g"]:,}', "g"),
             ("Carbs", f'{nut["carbs_g"]:,}', "g"), ("Fat", f'{nut["fat_g"]:,}', "g"),
             ("Sodium", f'{nut["sodium_mg"]:,}', "mg")]
    nutri = "".join(f'<div><dt>{k}</dt><dd><b>{v}</b> <span>{u}</span></dd></div>' for k, v, u in cells)
    ph = ""
    credit = ""
    if pic:
        p = photo(item["id"])
        ph = f'<figure class="dd__ph">{dish_photo(item["id"], page, eager=page)}</figure>'
        credit = (f' The photo is a stock image by <a href="{e(PROFILES[p["author"]])}">{e(p["author"])}</a> on '
                  f'<a href="{e(p["page"])}">Unsplash</a>, standing in until our own shoot.')
    else:
        credit = " Photo coming after our own shoot."
    sample = (f'<p class="dd__fine">Sample menu: the price, calories and allergens are placeholders until Dough-Vinci '
              f'confirms them.{credit}</p>' if MENU.get("sample") else (f'<p class="dd__fine">{credit.strip()}</p>' if pic else ""))
    return f'''<article class="dd{'' if pic else ' dd--text'}" data-dish-article="{item['id']}">
  {ph}
  <div class="dd__body">
    <p class="dd__kick">{'<span aria-hidden="true"> · </span>'.join(kick)}</p>
    <{h} class="dd__name d" data-dish-title tabindex="-1">{e(item['name'])}</{h}>
    <p class="dd__short">{e(item['short'])}</p>
    <ul class="dd__sizes" aria-label="Sizes and prices">{sizes}</ul>
    <a class="btn btn--red btn--big dd__order" href="#order" data-order>{icon("scooter")}<span>Order Now</span></a>
    <{sub} class="dd__h">Ingredients</{sub}>
    <p class="dd__ing">{e(", ".join(item["ingredients"])[0].upper() + ", ".join(item["ingredients"])[1:])}.</p>
    <{sub} class="dd__h">Nutrition</{sub}>
    <dl class="nutri">{nutri}</dl>
    <p class="dd__basis">{e(basis_long(item))}. Estimates, not lab-tested.</p>
    <{sub} class="dd__h">Allergens</{sub}>
    <p class="dd__alg"><b>Contains:</b> {e(allergen_text(item["allergens"], "none of the major allergens"))}.</p>
    <p class="dd__alg"><b>May contain:</b> {e(allergen_text(item.get("may_contain", []), "nothing beyond the shared-kitchen note below"))}.</p>
    <p class="dd__fine">{e(MENU["allergen_note"])} <a href="{root}allergens/">Allergens for every dish</a></p>
    {sample}
  </div>
</article>'''


# ───────────────────────────────────────────────────────────── page parts


NAV = [("Menu", "menu/"), ("About Us", "about/"), ("Contact", "contact/")]


def header(root: str, current: str) -> str:
    home = root or "./"
    links = []
    for label, href in NAV:
        cur = ' aria-current="page"' if href == current else ""
        links.append(f'<li><a href="{root}{href}"{cur}>{label}</a></li>')
    left = samples(short=True)
    more = f'<span class="pv__more"> · {and_list(left)} {"is a sample" if len(left) == 1 else "are samples"}</span>' if left else ""
    pv = f'<span class="pv">Preview{more}</span>' if preview() else ""
    home_cur = ' aria-current="page"' if current == "" else ""
    return f'''<header class="top" data-top>
  <a class="lock" href="{home}"{home_cur}>{wordmark()}<span class="lock__sub">Pizza &amp; Burger {tricolour("tri--lock")}</span><span class="sr">, home</span></a>
  {pv}
  <nav class="nav" aria-label="Main"><ul>{"".join(links)}<li class="nav__st">{status("short")}</li></ul></nav>
  <a class="btn btn--red top__order" href="#order" data-order>{icon("scooter")}<span>Order Now</span></a>
</header>'''


def footer(root: str) -> str:
    c = SITE["contact"]
    apps = "".join(f'<li><a href="{e(d["url"])}" target="_blank" rel="noopener">{e(d["name"])}<span class="sr"> (opens in a new tab)</span></a></li>'
                   for d in SITE["delivery"])
    left = samples()
    fine = (f"Preview: {and_list(left)} {'is a sample' if len(left) == 1 else 'are samples'} until Dough-Vinci "
            "confirms them. " if preview() and left else "")
    authors = sorted({p["author"] for p in PHOTOS.values()})
    return f'''<footer class="foot">
  <p class="foot__strap d">{e(SITE["strap"])}</p>
  <div class="foot__cols">
    <div><h2 class="foot__h">Order</h2><ul class="foot__list">{apps}<li><a href="tel:{tel()}">Call for pickup</a></li></ul></div>
    <div class="foot__find"><h2 class="foot__h">Find us</h2><ul class="foot__list"><li class="foot__addr">{keep(c["street_address"])}<br>{keep(c["locality"])}</li><li><a href="tel:{tel()}">{e(c["phone"])}</a></li>
      <li><a href="mailto:{e(c["email"])}">{email_html(c["email"])}</a></li><li><a href="{root}contact/#hours">Hours</a></li></ul></div>
    <div><h2 class="foot__h">Dough-Vinci</h2><ul class="foot__list"><li><a href="{root}menu/">Menu</a></li><li><a href="{root}about/">About Us</a></li>
      <li><a href="{root}contact/">Contact</a></li><li><a href="{root}allergens/">Allergens &amp; nutrition</a></li></ul></div>
    <div class="foot__halal">{halal_mark("halal--foot")}<p>{e(SITE["halal"]["statement"])}</p></div>
  </div>
  <p class="foot__wm d" aria-hidden="true">Dough<span class="wm__dash">-</span>Vinci</p>
  <div class="foot__fine">
    <p>{fine}Photos: {" and ".join(e(a) for a in authors)} on Unsplash, stock images until our own shoot (<a href="{root}credits/">credits</a>).</p>
    <p class="mirror" aria-hidden="true">Dough-Vinci, {e(c["city"])}</p>
  </div>
</footer>'''


def dialogs(root: str) -> str:
    c = SITE["contact"]
    links_note = (" The app links open each app’s home page until our own store pages are live."
                  if is_sample("delivery") else "")
    eat_in = (f'<p class="os__lbl">Eat in</p><p class="os__eat">Tables and free parking at {keep(c["street_address"])}.</p>' if SITE.get("confirmed", {}).get("dine_in") else "")
    return f'''<dialog class="sheet sheet--order" id="order-dialog" aria-labelledby="order-dialog-title">
  <div class="sheet__in os">
    <button class="x" type="button" data-close><span class="sr">Close</span></button>
    <h2 class="os__h d" id="order-dialog-title" tabindex="-1">Order Now</h2>
    <p class="os__sub">{e(SITE.get("order_note", ""))}</p>
    <p class="os__lbl">Delivery or pickup in the app</p>
    <ul class="os__list">{apps_list("os")}</ul>
    <p class="os__lbl">Pickup by phone</p>
    <ul class="os__list"><li><a href="tel:{tel()}"><span class="os__name">Call for pickup</span><span class="os__tel">{e(c["phone"])} {sample_tag("phone")}</span></a></li></ul>
    {eat_in}    <div class="os__foot">{halal_mark("halal--sheet")}<p>No payment on this site.{links_note}</p></div>
  </div>
</dialog>
<dialog class="sheet sheet--dish" id="dish-dialog" aria-labelledby="dish-dialog-title">
  <div class="sheet__in">
    <button class="x" type="button" data-close><span class="sr">Close</span></button>
    <div data-dish-slot></div>
  </div>
</dialog>'''


def mbar() -> str:
    return f'<div class="mbar" data-mbar><a class="btn btn--red" href="#order" data-order>{icon("scooter")}<span>Order Now</span></a></div>'


# ───────────────────────────────────────────────────────────── JSON-LD, page data


def jsonld() -> str:
    """Only what is true: the street address, hours, phone and email join the markup once the owner has confirmed
    each (`confirmed`) or the preview is switched off. No Menu markup while the menu is a sample."""
    c = SITE["contact"]
    ld = {
        "@context": "https://schema.org", "@type": "Restaurant", "name": SITE["name"],
        "url": SITE["base_url"], "image": SITE["base_url"] + "og.png", "logo": SITE["base_url"] + "apple-touch-icon.png",
        "description": SITE["description"], "slogan": SITE["tagline"], "servesCuisine": ["Pizza", "Burgers", "Pasta"],
        "address": {"@type": "PostalAddress", "addressLocality": c["city"], "addressRegion": c.get("region", "BC"),
                    "addressCountry": "CA"},
    }
    if not is_sample("phone"):
        ld["telephone"] = tel()
    if not is_sample("email"):
        ld["email"] = c["email"]
    if not is_sample("location"):
        if c.get("street_address"):
            ld["address"]["streetAddress"] = c["street_address"]
        if c.get("postal_code"):
            ld["address"]["postalCode"] = c["postal_code"]
        ld["hasMap"] = c["maps_url"]
    if not is_sample("hours"):
        ld["openingHoursSpecification"] = [{"@type": "OpeningHoursSpecification", "dayOfWeek": [DAY_LONG[d] for d in h["days"]],
                                            "opens": h["open"], "closes": h["close"]} for h in SITE["hours"]]
    if not MENU.get("sample"):
        ld["hasMenu"] = SITE["base_url"] + "menu/"
    return '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>"


def page_data() -> str:
    d = {"tz": SITE.get("timezone"), "opening": SITE.get("opening_date") or "", "approx": opening_approx(),
         "hours": SITE["hours"], "preview": preview()}
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


def page(rel: str, *, title: str, description: str, main: str, current: str | None = None, body_class: str = "",
         head_extra: str = "", jsonld_on: bool = False, is_404: bool = False, band_level: int = 2) -> None:
    depth = rel.count("/")
    # GitHub Pages serves 404.html at any missing address, so its links start from the site root. No <base>: with one,
    # the skip link and the #order links would resolve to the home page instead of staying on this page.
    root = SITE["base_path"] if is_404 else "../" * depth
    url_path = "" if rel == "index.html" else rel.replace("index.html", "")
    canonical = SITE["base_url"] + url_path
    robots = '<meta name="robots" content="noindex, nofollow">' if preview() or not SITE.get("index") else ""
    full_title = title if title.startswith(SITE["name"]) else f"{title} · {SITE['name']}"
    band = "" if body_class == "home" else order_band(band_level)
    doc = fill(tpl("base.html"), {
        "title": e(full_title), "description": e(description), "robots": robots,
        "canonical": e(canonical), "og_image": e(SITE["base_url"] + "og.png"), "og_title": e(full_title),
        "og_alt": e(OG_ALT),
        "og_url": e(canonical), "site_name": e(SITE["name"]), "root": root, "fonts": e(FONTS),
        "fonts_accent": e(FONTS_ACCENT), "css_v": ASSET_V["site.css"], "js_v": ASSET_V["site.js"],
        "head_extra": head_extra, "jsonld": jsonld() if jsonld_on else "", "data": page_data(),
        "header": header(root, current if current is not None else "-"), "main": main, "order_band": band,
        "footer": footer(root), "mbar": mbar(), "dialogs": dialogs(root), "body_class": body_class,
        "lang": SITE.get("lang", "en"),
    })
    write(rel, doc)


# ───────────────────────────────────────────────────────────── pages

# the share image (tools/render_images.py)
OG_ALT = (f"Dough-Vinci Pizza & Burger: «{SITE['tagline']}» beside a margherita and a smashburger close-up, with the "
          f"halal mark and {SITE['contact']['city']}, {SITE['contact']['region']}.")
HERO_SIZES = "(min-width: 900px) 30vw, 50vw"
HERO_RATIO = 2 / 3


def build_home() -> None:
    root = ""
    od = opening()
    c = SITE["contact"]
    when = f"Opening {opening_long(od)}" if soon() else "Now open"
    hero = SITE["hero"]
    tiles = []
    for sid in SITE.get("signatures", []):
        cat, it = ITEMS[sid]
        p = it["prices"][0]
        lab = (size_label(p["label"]) + " ") if len(it["prices"]) > 1 else ""
        tiles.append(f'''<li class="tile rv"><a href="{root}menu/{sid}/" data-dish="{sid}">
  <span class="ph">{img(sid, "(min-width: 900px) 25vw, 50vw", 4 / 5, alt="", max_w=1000)}</span>
  <span class="tile__cap"><span class="tile__name">{e(it['name'])}</span><span class="tile__p">{lab}{money(p['price'])}</span></span>
</a></li>''')
    main = fill(tpl("home.html"), {
        "root": root,
        "tag": f'{halal_mark("halal--tag")}<span class="tag__g"><span class="tag__t">{e(when)} · {e(c["city"])}</span>{date_tag()}</span>',
        "title_1": e(hero["title_lines"][0]), "title_2": e(hero["title_lines"][1]),
        "sub": e(hero["sub"]),
        "line": e(" ".join(p + "." for p in SITE["pillars"])),
        "btn_order": e(hero["buttons"]["order"]), "btn_menu": e(hero["buttons"]["menu"]),
        "scooter": icon("scooter"), "arrow": icon("arrow", "ico ico--sm"),
        "hero_pizza": img("hero-pizza", HERO_SIZES, HERO_RATIO, eager=True, max_w=1200, alt=""),
        "hero_burger": img("hero-burger", HERO_SIZES, HERO_RATIO, eager=True, max_w=1200, alt=""),
        "pizza_alt": e(photo("hero-pizza")["alt"]), "burger_alt": e(photo("hero-burger")["alt"]),
        "pizza_from": from_price(ITEMS["mona-lisa"][0]), "smash_from": from_price(ITEMS["original-smash"][0]),
        "tri": tricolour("tri--hero"),
        "order_band": order_band(2),
        "tiles": "".join(tiles),
        "combos": combos_html(2, True, root),
        "leonardo": leonardo("p"),
        "halal": halal_mark("halal--big"),
        "halal_statement": halal_statement(),
        "where": keep(c["map_label"]), "locality": keep(c["locality"]),
        "status": status("long"), "date_tag": date_tag(), "maps": e(c["maps_url"]),
        "smp": sample_tag("location", "Sample location"),
    })
    page("index.html", title=SITE["title"], description=SITE["description"], main=main, current="", body_class="home",
         head_extra=preload("hero-pizza", HERO_SIZES, HERO_RATIO, max_w=1200), jsonld_on=True)


def build_menu() -> None:
    root = "../"
    filters = "".join(f'<button class="tog" type="button" aria-pressed="false" data-filter="{k}">{label}</button>' for k, label in FILTERS)
    tabs = "".join(f'<li><a href="#{c["id"]}" data-tab="{c["id"]}">{e(c["name"])}</a></li>' for c in CATS)
    tabs += '<li><a href="#combos" data-tab="combos">Combos</a></li>'
    note = (f'<p class="mhead__note">{e(MENU["note"])} Prices in CAD.</p>' if MENU.get("sample")
            else '<p class="mhead__note">Prices in CAD.</p>')
    main = fill(tpl("menu.html"), {
        "root": root, "tabs": tabs, "filters": filters, "note": note,
        "sections": menu_sections(root), "combos": combos_html(2, False, root),
        "combo_order": icon("scooter"), "count": len(ORDER_IDS),
        "allergen_note": e(MENU["allergen_note"]),
    })
    page("menu/index.html", title="Menu", description="Pizza, smashburgers, pasta, sides, desserts and drinks at Dough-Vinci, "
         "with prices, calories and allergens for every dish." + (" Sample menu." if MENU.get("sample") else ""),
         main=main, current="menu/", body_class="menu-page", head_extra=menu_preload())
    for cat in CATS:
        for it in cat["items"]:
            r = "../../"
            main = f'''<div class="dish-page" data-hero>
  <p class="crumbs"><a href="{r}menu/#{cat['id']}">{icon("back", "ico ico--sm")}<span>Menu</span></a> <span aria-hidden="true">/</span> {e(cat['name'])}</p>
  {dish_detail(it, cat, r, level=1, page=True)}
</div>'''
            ps = ", ".join((p["label"].replace('"', "-inch") + " " if p["label"] != "Regular" else "") + money(p["price"]) for p in it["prices"])
            desc = f"{it['name']}: {it['short']} {ps}, {it['kcal']:,} kcal {basis(it).replace('″', '-inch')}."
            if MENU.get("sample"):
                desc += " Sample menu."
            extra = preload(it["id"], DISH_PAGE_SIZES, 4 / 5, max_w=1200, phone_ratio=4 / 3) if has_photo(it["id"]) else ""
            page(f"menu/{it['id']}/index.html", title=it["name"], description=desc, main=main, current="menu/",
                 body_class="dish-page-body", head_extra=extra)


def build_dish_fragments() -> None:
    frags = [f'<template data-dish="{it["id"]}">{dish_detail(it, cat, "__ROOT__", level=2)}</template>'
             for cat in CATS for it in cat["items"]]
    write("assets/dishes.html", '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
          "<title>Dish sheets</title>\n" + "\n".join(frags))


def allergen_table(root: str) -> str:
    keys = MENU["allergen_keys"]
    head = "".join(f'<th scope="col">{ALLERGENS[k]}</th>' for k in keys)
    groups = []
    for cat in CATS:
        rows = [f'<tr class="mx__cat"><th scope="colgroup" colspan="{len(keys) + 2}">{e(cat["name"])}</th></tr>']
        for it in cat["items"]:
            cells = []
            for k in keys:
                if k in it["allergens"]:
                    cells.append('<td class="mx__c is-yes"><span aria-hidden="true">●</span><span class="sr">Contains</span></td>')
                elif k in it.get("may_contain", []):
                    cells.append('<td class="mx__c is-may"><span aria-hidden="true">○</span><span class="sr">May contain</span></td>')
                else:
                    cells.append('<td class="mx__c is-no"><span class="sr">No</span></td>')
            rows.append(f'<tr class="mx__row"><th scope="row" class="mx__dish"><a href="{root}menu/{it["id"]}/" data-dish="{it["id"]}">{e(it["name"])}</a></th>'
                        f'{"".join(cells)}<td class="mx__k"><b>{it["kcal"]:,}</b> <span>{basis(it)}</span></td></tr>')
        groups.append(f'<tbody>{"".join(rows)}</tbody>')
    return f'''<div class="mx-wrap"><table class="mx">
  <caption class="sr">Allergens and calories of every dish</caption>
  <thead><tr><th scope="col" class="mx__dish">Dish</th>{head}<th scope="col" class="mx__k">Calories</th></tr></thead>
  {"".join(groups)}
</table></div>'''


def allergen_list(root: str) -> str:
    out = []
    for cat in CATS:
        items = []
        for it in cat["items"]:
            items.append(f'''<li class="al__i"><a class="al__name" href="{root}menu/{it['id']}/" data-dish="{it['id']}">{e(it['name'])}</a>
  <p class="al__k"><b>{it['kcal']:,} kcal</b> {basis(it)}</p>
  <p><b>Contains:</b> {e(allergen_text(it['allergens'], 'none of the major allergens'))}</p>
  <p><b>May contain:</b> {e(allergen_text(it.get('may_contain', []), 'nothing listed'))}</p></li>''')
        out.append(f'<section class="al__cat" aria-labelledby="al-{cat["id"]}"><h2 class="al__h d" id="al-{cat["id"]}">{e(cat["name"])}</h2><ul>{"".join(items)}</ul></section>')
    return f'<div class="al">{"".join(out)}</div>'


def build_allergens() -> None:
    root = "../"
    warn = ('<p class="warn"><b>Sample data, not for dietary decisions.</b> The dishes, allergens and calories below are '
            'placeholders until Dough-Vinci confirms its real recipes.</p>') if MENU.get("sample") else ""
    main = fill(tpl("allergens.html"), {"root": root, "warn": warn, "table": allergen_table(root),
                                        "list": allergen_list(root), "note": e(MENU["allergen_note"])})
    page("allergens/index.html", title="Allergens & nutrition", description="Every Dough-Vinci dish against the eleven "
         "priority allergens, with the calories of each dish and what they are for.", main=main, current="allergens/",
         body_class="allergens-page")


def faq() -> str:
    """`{opening}` in an answer becomes the opening date, so the FAQ and the status never disagree."""
    od = opening()
    when = opening_phrase(od) if od else "soon, on a date we will post here"
    return "".join(f'<details class="faq__q"><summary>{e(q["q"])}</summary><p>{e(q["a"].replace("{opening}", when))}</p></details>'
                   for q in SITE["faq"])


def build_contact() -> None:
    root = "../"
    c = SITE["contact"]
    h = SITE["halal"]
    cert = (f'<p class="hb__cert">{e(certification())}</p>' if h.get("certifier") else "")
    main = fill(tpl("contact.html"), {
        "root": root, "where": keep(c["map_label"]), "locality": keep(c["locality"]),
        "parking": e(c.get("parking", "")), "dine_in": e(c.get("dine_in", "")),
        "status": status("long"), "date_tag": date_tag(), "hours": hours_table(), "maps": e(c["maps_url"]), "tel": tel(),
        "phone": e(c["phone"]), "email": e(c["email"]), "email_label": email_html(c["email"]), "pin": icon("pin"), "phone_i": icon("phone"),
        "mail_i": icon("mail"),
        "photo": img("mona-lisa", "(min-width: 900px) 50vw, 100vw", 4 / 5, max_w=1200, eager=True, high=False, phone_ratio=4 / 3),
        "smp": sample_tag("location", "Sample location"), "smp_hours": sample_tag("hours", "Sample hours"),
        # a Sample label sits inside its button, so it never reads as a control of its own
        "smp_phone": sample_tag("phone"), "smp_email": sample_tag("email"),
        "halal": halal_mark("halal--big"), "halal_statement": halal_statement(), "cert": cert,
        # the detail names dishes of the menu, so it is a sample while the menu is
        "halal_detail": e(h.get("detail", "")) + (" " + sample_tag("menu", "Sample menu") if is_sample("menu") else ""),
        "faq": faq(), "catering_title": e(SITE["catering"]["title"]), "catering_text": e(SITE["catering"]["text"]),
    })
    page("contact/index.html", title="Contact", description="Hours, directions, parking, phone and email for Dough-Vinci "
         f"at {c['address']}, with our halal statement and answers to common questions.", main=main, current="contact/",
         body_class="contact-page", jsonld_on=True)


def credits() -> str:
    rows = []
    for d in sorted(USED_PHOTOS.values(), key=lambda d: (d["author"].lower(), d["key"])):
        rows.append(f'<li><a href="{e(d["page"])}" target="_blank" rel="noopener">{e(d["alt"])}<span class="sr"> (opens in a new tab)</span></a>'
                    f' <span class="cr__by">by <a href="{e(PROFILES[d["author"]])}" target="_blank" rel="noopener">{e(d["author"])}<span class="sr"> (opens in a new tab)</span></a></span></li>')
    L = SITE["leonardo"]
    rows.append(f'<li><a href="{e(L["page"])}" target="_blank" rel="noopener">{e(L["alt"])}<span class="sr"> (opens in a new tab)</span></a>'
                f' <span class="cr__by">{e(L["credit"])}</span></li>')
    return "".join(rows)


def license_link() -> str:
    """«Unsplash License (https://…)» in photos.json becomes a link named «the Unsplash License»."""
    m = re.fullmatch(r"(.+?) \((https://[^)]+)\)", PHOTO_DOC.get("license", ""))
    if not m:
        return e(PHOTO_DOC.get("license", ""))
    return f'under the <a href="{e(m.group(2))}" target="_blank" rel="noopener">{e(m.group(1))}<span class="sr"> (opens in a new tab)</span></a>'


ABOUT_SIZES = "(min-width: 900px) 50vw, 100vw"
NF_SIZES = "(min-width: 900px) 50vw, 100vw"


def build_about() -> None:
    root = "../"
    sample = ""
    if preview():
        left = samples()
        known = [w for f, w in (("location", "location"), ("hours", "hours"), ("email", "email address"),
                                ("halal", "halal statement")) if confirmed(f)]
        parts = []
        if known:
            parts.append(f"The {and_list(known)} {'are' if len(known) > 1 or known == ['hours'] else 'is'} confirmed")
        if left:
            parts.append(f"{and_list(left)} {'is a sample' if len(left) == 1 else 'are samples'} until Dough-Vinci "
                         "confirms them")
        body = "; ".join(parts)
        photos = (" Every food photo is a stock image standing in until our own shoot." if is_sample("photos") else "")
        sample = f'<p class="ab__sample"><b>This site is a preview.</b> {body}.{photos}</p>' if body else ""
    main = fill(tpl("about.html"), {
        "root": root,
        "welcome": "".join(f"<p>{e(x)}</p>" for x in SITE["welcome"]),
        "photo": img("place-1", ABOUT_SIZES, 4 / 5, max_w=1200, eager=True, phone_ratio=4 / 3),
        "leonardo": leonardo("p"),
        "sample": sample,
        "arrow": icon("arrow", "ico ico--sm"),
    })
    page("about/index.html", title="About Us", description="Dough-Vinci: the owner’s welcome and the idea behind the "
         "name.", main=main, current="about/", body_class="about-page",
         head_extra=preload("place-1", ABOUT_SIZES, 4 / 5, max_w=1200, phone_ratio=4 / 3))


def build_credits() -> None:
    """Who took every photo the other pages use, and the drawing's source; built last, once they are all known."""
    main = fill(tpl("credits.html"), {"credits": credits(), "license": license_link()})
    page("credits/index.html", title="Photo credits", description="The stock photos and the Leonardo drawing on the "
         "Dough-Vinci site, with their photographers and sources.", main=main, body_class="credits-page")


def build_404() -> None:
    main = fill(tpl("404.html"), {"root": SITE["base_path"], "arrow": icon("arrow", "ico ico--sm"),
                                  "photo": img("soft-pretzels", NF_SIZES, 4 / 5, max_w=1200, eager=True, phone_ratio=4 / 3)})
    page("404.html", title="Page not found", description="This page is not on the menu.", main=main,
         body_class="nf-page", is_404=True, head_extra=preload("soft-pretzels", NF_SIZES, 4 / 5, max_w=1200, phone_ratio=4 / 3))


# ───────────────────────────────────────────────────────────── static files


def build_assets() -> None:
    css = (SRC / "css" / "site.css").read_text(encoding="utf-8")
    css = css.replace("/*GRADE*/", PHOTO_DOC["treatment"]["filter"])
    js = (SRC / "js" / "site.js").read_text(encoding="utf-8")
    write("assets/site.css", css)
    write("assets/site.js", js)
    ASSET_V["site.css"] = hashlib.sha1(css.encode()).hexdigest()[:8]
    ASSET_V["site.js"] = hashlib.sha1(js.encode()).hexdigest()[:8]
    for name in ("og.png", "apple-touch-icon.png", "favicon.png", "favicon.svg"):
        p = SRC / "img" / name
        if p.exists():
            write(name, p.read_bytes())
    for p in (ROOT / "brief").glob("*.pdf"):
        write(f"brief/{p.name}", p.read_bytes())
    write(".nojekyll", "")


def build_meta(pages: list[str]) -> None:
    pv = preview() or not SITE.get("index")
    base = SITE["base_url"]
    write("robots.txt", "User-agent: *\nDisallow: /\n" if pv else f"User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n")
    # while the site is a preview the sitemap lists nothing: robots.txt already keeps crawlers out
    urls = "" if pv else "".join(f"<url><loc>{e(base + p)}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>" for p in pages)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    manifest = {"name": f"{SITE['name']} {SITE['subtitle']}", "short_name": SITE["name"], "start_url": "./",
                "scope": "./", "display": "standalone", "background_color": "#121010", "theme_color": "#121010",
                "description": SITE["description"],
                "icons": [{"src": "apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
                          {"src": "favicon.png", "sizes": "64x64", "type": "image/png"}]}
    write("manifest.webmanifest", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    c = SITE["contact"]
    hours = "; ".join(f"{day_range(h['days'])} {fmt_time(h['open'])}–{fmt_time(h['close'])}" for h in SITE["hours"])
    od = opening()
    ok = lambda f: not is_sample(f)  # noqa: E731  (a fact a machine reader may quote)
    lines = [f"# {SITE['name']} {SITE['subtitle']}", "",
             f"> {SITE['tagline']} A {'halal ' if ok('halal') else ''}pizza, smashburger and pasta restaurant "
             f"{'coming to' if soon() else 'in'} {c['city']}, {c.get('region', 'BC')}.", ""]
    left = samples() + (["the food photos (stock images)"] if is_sample("photos") else [])
    if left:
        lines += [f"This site is a preview. {and_list(left)[0].upper()}{and_list(left)[1:]} shown on it "
                  f"{'is a sample' if len(left) == 1 else 'are samples'} until the restaurant confirms "
                  f"{'it' if len(left) == 1 else 'them'}. Do not quote {'it' if len(left) == 1 else 'them'} as facts.", ""]
    if od and soon() and opening_approx():
        lines += [f"Opening: planned for {opening_long(od)} {od.year}; the exact day is not set yet.", ""]
    elif od and soon() and ok("opening_date"):
        lines += [f"Opening date: {od.isoformat()}.", ""]
    facts = []
    if ok("location"):
        facts.append(f"- Location: {c['address']}")
    if ok("parking") and c.get("parking"):
        facts.append(f"- Parking: {c['parking']}")
    if ok("hours"):
        facts.append(f"- Hours (Pacific time): {hours}")
    if ok("phone"):
        facts.append(f"- Phone: {c['phone']}")
    if ok("email"):
        facts.append(f"- Email: {c['email']}")
    if ok("halal"):
        facts.append(f"- Halal: {SITE['halal']['statement']} {certification()}".rstrip())
    if ok("dine_in") and c.get("dine_in"):
        facts.append("- Service: eat in (the restaurant has seating), pickup and delivery.")
    apps = ", ".join(f"[{d['name']}]({d['url']})" if ok("delivery") else d["name"] for d in SITE["delivery"])
    facts.append(f"- Ordering: {apps}" + ("; or call for pickup" if ok("phone") else "") + ". No payment on this site.")
    lines += facts + [""]
    pages_md = ["## Pages", "",
                f"- [Menu]({base}menu/): every dish with price, calories, ingredients and allergens",
                f"- [About Us]({base}about/): the owner's welcome and the idea behind the name",
                f"- [Contact]({base}contact/): location, parking, hours, phone, halal statement, FAQ",
                f"- [Allergens & nutrition]({base}allergens/): every dish by allergen with calories",
                f"- [Photo credits]({base}credits/): the stock photos and the drawing, with their sources", ""]
    lines += pages_md
    if ok("menu"):
        lines += ["## Menu", ""]
        for cat in CATS:
            lines.append(f"### {cat['name']}")
            for it in cat["items"]:
                ps = ", ".join(f"{p['label'].replace(chr(34), ' in')} {money(p['price'])}" if p["label"] != "Regular" else money(p["price"]) for p in it["prices"])
                al = ", ".join(ALLERGENS[a] for a in it["allergens"]) or "none of the major allergens"
                lines.append(f"- {it['name']}: {it['short']} {ps}. {it['kcal']:,} kcal ({it['portion']}). Contains: {al}.")
            lines.append("")
    else:
        lines += ["The menu has three kinds of food: pizza, smashburgers and pasta, with sides, desserts and drinks. "
                  "Its dishes are samples until the restaurant confirms them.", ""]
    write("llms.txt", "\n".join(lines))


def trash_stale() -> None:
    stale = [p for p in DOCS.rglob("*") if p.is_file() and p.resolve() not in WRITTEN]
    if stale:
        subprocess.run(["trash", *map(str, stale)], check=True)
    for d in sorted((p for p in DOCS.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            subprocess.run(["trash", str(d)], check=True)


def main() -> None:
    check_content()
    USED_PHOTOS.clear()
    WRITTEN.clear()
    DOCS.mkdir(exist_ok=True)
    build_assets()
    build_dish_fragments()
    build_home()
    build_menu()
    build_allergens()
    build_contact()
    build_404()
    build_about()
    build_credits()  # every photo the other pages used
    pages = ["", "menu/", "about/", "contact/", "allergens/", "credits/"] + [f"menu/{i}/" for i in ORDER_IDS]
    build_meta(pages)
    trash_stale()
    print(f"built {len(WRITTEN)} files into docs/")


if __name__ == "__main__":
    main()
