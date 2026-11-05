"""Checks of the built site. Run: python3 -m unittest discover -s tests  (standard library only).

The suite builds the site first (python3 build.py), then reads docs/.
"""
from __future__ import annotations

import html
import importlib.util
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = ["index.html", "menu/index.html", "about/index.html", "contact/index.html", "allergens/index.html",
         "credits/index.html", "404.html"]

# bresaola is air-dried beef, so it needs no qualifier
PORK = r"\b(pork|bacon|ham|prosciutto|lard|pancetta|guanciale|salami|pepperoni|sausages?|chorizo|gelatin)\b"
PORK_OK = r"\bbeef\b|\bno pork\b|\bhas pork or alcohol\b"
ALCOHOL = r"\b(alcohol|wine|beer|ale|lager|liqueur|rum|vodka|whisky|brandy|cocktails?|marsala|mirin)\b"
ALCOHOL_OK = r"\bno (pork, no )?alcohol\b|\bno liqueur\b|\bwithout (wine|liqueur|alcohol)\b|\bpork or alcohol\b"


def load_build():
    spec = importlib.util.spec_from_file_location("dv_build", ROOT / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Page(HTMLParser):
    """Collects what the checks need from one HTML file."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.h1 = 0
        self.refs: list[tuple[str, str]] = []  # (tag, url)
        self.imgs: list[dict] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.jsonld: list[str] = []
        self.robots: str | None = None
        self.base: str | None = None
        self.order_triggers: list[dict] = []
        self.blank_targets: list[dict] = []
        self.in_template = 0
        self._script: str | None = None
        self._buf: list[str] = []
        self.text: list[str] = []
        self.main_words: list[str] = []
        self._stack: list[tuple[str, bool, bool]] = []  # (tag, in_main, hidden)

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def _flags(self) -> tuple[bool, bool]:
        return (self._stack[-1][1], self._stack[-1][2]) if self._stack else (False, False)

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "template":
            self.in_template += 1
        if self.in_template:
            return
        in_main, hidden = self._flags()
        cls = a.get("class", "").split()
        if tag not in self.VOID:
            self._stack.append((tag, in_main or tag == "main", hidden or "sr" in cls or "aria-hidden" in a))
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "base":
            self.base = a.get("href")
        if tag == "meta" and a.get("name") == "robots":
            self.robots = a.get("content")
        if tag in ("a", "link") and a.get("href"):
            self.refs.append((tag, a["href"]))
        if tag == "link" and a.get("rel") == "stylesheet":
            self.stylesheets.append(a["href"])
        if tag in ("img", "script") and a.get("src"):
            self.refs.append((tag, a["src"]))
        if tag == "script" and a.get("src"):
            self.scripts.append(a["src"])
        if tag == "img":
            self.imgs.append(a)
        if tag == "script" and a.get("type") == "application/ld+json":
            self._script, self._buf = "ld", []
        elif tag == "script":
            self._script, self._buf = "js", []
        if "data-order" in a:
            self.order_triggers.append({"tag": tag, **a})
        if tag == "a" and a.get("target") == "_blank":
            self.blank_targets.append(a)

    def handle_endtag(self, tag):
        if tag == "template":
            self.in_template -= 1
            return
        if self.in_template:
            return
        if tag == "script" and self._script:
            if self._script == "ld":
                self.jsonld.append("".join(self._buf))
            self._script = None
        while self._stack:
            t, _, _ = self._stack.pop()
            if t == tag:
                break

    def handle_data(self, data):
        if self._script:
            self._buf.append(data)
        elif not self.in_template:
            self.text.append(data)
            in_main, hidden = self._flags()
            if in_main and not hidden:
                self.main_words += re.findall(r"[A-Za-z0-9$][\w$'’&.,:-]*", data)


def parse(path: Path) -> Page:
    p = Page()
    p.feed(path.read_text(encoding="utf-8"))
    return p


class BuiltSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_build()
        cls.b.main()
        cls.site = json.loads((ROOT / "content/site.json").read_text())
        cls.menu = json.loads((ROOT / "content/menu.json").read_text())
        cls.photos = json.loads((ROOT / "content/photos.json").read_text())
        cls.pages = sorted(p for p in DOCS.rglob("*.html") if "assets" not in p.parts)
        cls.parsed = {p: parse(p) for p in cls.pages}
        cls.dishes = [it for c in cls.menu["categories"] for it in c["items"]]
        cls.read = staticmethod(lambda rel: (DOCS / rel).read_text(encoding="utf-8"))

    # ── pages build ──
    def test_pages_exist(self):
        for rel in PAGES + ["robots.txt", "sitemap.xml", "llms.txt", "manifest.webmanifest", "favicon.png", "og.png",
                            "apple-touch-icon.png", "assets/site.css", "assets/site.js", "assets/dishes.html", ".nojekyll"]:
            self.assertTrue((DOCS / rel).exists(), rel)

    def test_a_page_for_every_dish(self):
        frag = self.read("assets/dishes.html")
        for it in self.dishes:
            self.assertTrue((DOCS / "menu" / it["id"] / "index.html").exists(), it["id"])
            self.assertIn(f'<template data-dish="{it["id"]}">', frag)
        self.assertEqual(len(list((DOCS / "menu").glob("*/index.html"))), len(self.dishes), "no page for a dish that is gone")

    def test_no_placeholder_left(self):
        for p in list(DOCS.rglob("*.html")) + list(DOCS.rglob("*.txt")) + list(DOCS.rglob("*.xml")):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("{{", text, p)
            self.assertNotIn("{opening}", text, p)
        self.assertNotIn("__ROOT__", self.read("menu/index.html"))
        self.assertNotIn("/*GRADE*/", self.read("assets/site.css"))

    def test_one_h1(self):
        for p, pg in self.parsed.items():
            self.assertEqual(pg.h1, 1, p)

    def test_unique_ids(self):
        for p, pg in self.parsed.items():
            dupes = {i for i in pg.ids if pg.ids.count(i) > 1}
            self.assertFalse(dupes, f"{p}: {dupes}")

    def test_titles_and_descriptions(self):
        titles = set()
        for p in self.pages:
            text = p.read_text()
            t = re.search(r"<title>([^<]+)</title>", text)
            d = re.search(r'<meta name="description" content="([^"]+)"', text)
            self.assertTrue(t and d, p)
            titles.add(t.group(1))
        self.assertEqual(len(titles), len(self.pages), "every page has its own title")

    # ── links ──
    def test_local_links_resolve(self):
        base_url = "https://x.test" + self.site["base_path"]
        for p, pg in self.parsed.items():
            rel = p.relative_to(DOCS).as_posix()
            page_url = urljoin(base_url, rel)
            for tag, url in pg.refs:
                u = urlparse(url)
                if u.scheme in ("http", "https", "mailto", "tel") or url.startswith("//"):
                    continue
                if url.startswith("#"):
                    self.assertIn(url[1:], pg.ids, f"{p}: {tag} {url}")
                    continue
                target = urljoin(page_url, url)
                path = urlparse(target).path
                self.assertTrue(path.startswith(self.site["base_path"]), f"{p}: {url} leaves the site")
                local = DOCS / path[len(self.site["base_path"]):]
                if path.endswith("/"):
                    local = local / "index.html"
                self.assertTrue(local.exists(), f"{p}: {url} -> {local}")
                frag = urlparse(target).fragment
                if frag and local.suffix == ".html":
                    self.assertIn(f'id="{frag}"', local.read_text(), f"{p}: {url}")

    def test_links_relative_except_404(self):
        nf = DOCS / "404.html"
        for p, pg in self.parsed.items():
            for tag, url in pg.refs:
                if tag not in ("a", "link", "img", "script") or urlparse(url).scheme or url.startswith(("#", "//")):
                    continue
                if p == nf:
                    self.assertTrue(url.startswith(self.site["base_path"]), f"404: {url}")
                elif url.startswith("/"):
                    self.fail(f"{p}: absolute local path {url}")
        self.assertIsNone(self.parsed[nf].base)

    def test_new_tabs_are_safe_and_announced(self):
        for p, pg in self.parsed.items():
            for a in pg.blank_targets:
                self.assertIn("noopener", a.get("rel", ""), f"{p}: {a.get('href')}")
        for p in self.pages:
            for m in re.finditer(r'<a [^>]*target="_blank"[^>]*>(.*?)</a>', p.read_text(), re.S):
                self.assertIn("opens", m.group(1), f"{p}: a new tab is announced")

    def test_only_allowed_third_parties(self):
        """Google Fonts, Unsplash photos and the one Wikimedia drawing; every script is our own."""
        for p, pg in self.parsed.items():
            for s in pg.scripts:
                self.assertFalse(urlparse(s).scheme, f"{p}: third-party script {s}")
            for s in pg.stylesheets:
                self.assertTrue(not urlparse(s).scheme or s.startswith("https://fonts.googleapis.com/"), f"{p}: {s}")
            for img in pg.imgs:
                src = img["src"]
                self.assertTrue(not urlparse(src).scheme or src.startswith(("https://images.unsplash.com/",
                                                                            "https://upload.wikimedia.org/")), f"{p}: {src}")

    # ── ordering ──
    def test_order_works_without_js(self):
        for p, pg in self.parsed.items():
            self.assertIn("order", pg.ids, p)
            self.assertTrue(pg.order_triggers, p)
            for t in pg.order_triggers:
                self.assertEqual(t["tag"], "a", f"{p}: an Order trigger must be a real link")
                self.assertEqual(t["href"], "#order", p)
            text = p.read_text()
            for d in self.site["delivery"]:
                self.assertIn(d["url"], text, f"{p}: {d['name']}")
                self.assertIn(f">{html.escape(d['name'])}<", text, f"{p}: {d['name']} by name, as text")
            self.assertIn("Call for pickup", text, p)
            self.assertIn(f'href="tel:+1{re.sub(r"[^0-9]", "", self.site["contact"]["phone"])}"', text, p)
            self.assertIn("No payment on this site", text, p)

    def test_navigation_in_the_owners_words(self):
        for p in self.pages:
            text = p.read_text()
            nav = re.search(r'<nav class="nav" aria-label="Main">(.*?)</nav>', text, re.S).group(1)
            self.assertEqual(re.findall(r">([^<>]+)</a>", nav), ["Menu", "About Us", "Contact"], p)
            self.assertIn('data-status="short"', nav, f"{p}: the live status sits beside Contact")
            top = re.search(r'<header class="top".*?</header>', text, re.S).group(0)
            self.assertIn('class="lock"', top)
            self.assertIn("<span>Order Now</span>", top, p)
            self.assertIn('class="tri tri--lock"', top, f"{p}: the tricolour under the wordmark")

    # ── the owner's items ──
    def test_owner_hero(self):
        home = self.read("index.html")
        hero = re.search(r'<section class="hero".*?</section>', home, re.S).group(0)
        for needle in ("Real Pizza.", "Real Smashburgers.", "Made with Passion.",
                       "Fresh Ingredients. Flat-Rolled Pizza. Signature Smashburgers.", "<span>Order Now</span>",
                       "<span>Explore Our Menu</span>", 'class="hero__rule"', 'class="tri tri--hero"',
                       'href="menu/#pizza"', 'href="menu/#smash"'):
            self.assertIn(needle, hero, needle)
        self.assertEqual(len(re.findall(r'<img [^>]*src="https://images\.unsplash\.com/', hero)), 2, "pizza and smashburger")
        self.assertEqual(home.count('class="tri '), 2, "the tricolour twice: under the wordmark and at the hero's foot")
        self.assertIn('id="pizza"', self.read("menu/index.html"))
        self.assertIn('id="smash"', self.read("menu/index.html"))

    def test_strap_once_near_the_footer(self):
        for p in self.pages:
            text = p.read_text()
            self.assertEqual(text.count(self.site["strap"]), 1, p)
            self.assertLess(text.index("<footer"), text.index(self.site["strap"]), p)

    def test_owner_welcome_word_for_word(self):
        about = self.read("about/index.html")
        for para in self.site["welcome"]:
            self.assertIn(f"<p>{html.escape(para, quote=True)}</p>", about)

    def test_halal_mark_and_statement(self):
        h = self.site["halal"]
        mark = f'<span lang="ar" dir="rtl">{h["mark_ar"]}</span></span><span class="halal__en">{h["mark_en"]}</span>'
        home = self.read("index.html")
        hero = re.search(r'<section class="hero".*?</section>', home, re.S).group(0)
        self.assertIn(mark, hero, "in the hero tag, above the fold")
        for p in self.pages:
            text = p.read_text()
            band = re.search(r'<section class="ob[^"]*" id="order".*?</section>', text, re.S).group(0)
            self.assertIn(mark, band, f"{p}: in the order band")
            foot = re.search(r"<footer.*?</footer>", text, re.S).group(0)
            self.assertIn(mark, foot, f"{p}: in the footer")
            self.assertIn(html.escape(h["statement"]), foot, p)
        contact = self.read("contact/index.html")
        self.assertIn(mark, re.search(r"<main.*?</main>", contact, re.S).group(0))
        self.assertIn(html.escape(h["statement"]), contact)
        faq = next(q for q in self.site["faq"] if "halal" in q["q"].lower())
        self.assertIn(html.escape(faq["a"]), contact)
        self.assertIn("Noto+Kufi+Arabic", home, "the Arabic word in an Arabic face from Google Fonts")
        if not h.get("certifier"):
            self.assertNotIn("Certified by", contact)

    def test_no_pork_or_alcohol_without_a_qualifier(self):
        files = list(DOCS.rglob("*.html")) + [DOCS / "llms.txt"]
        for f in files:
            pg = parse(f) if f.suffix == ".html" else None
            chunks = pg.text if pg else f.read_text().splitlines()
            if f.name == "dishes.html":
                chunks = re.sub(r"<[^>]+>", "\n", f.read_text()).splitlines()
            for chunk in chunks:
                for s in re.split(r"(?<=[.!?])\s+", html.unescape(chunk)):
                    low = s.lower()
                    if re.search(PORK, low):
                        self.assertRegex(low, PORK_OK, f"{f}: {s!r}")
                    if re.search(ALCOHOL, low):
                        self.assertRegex(low, ALCOHOL_OK, f"{f}: {s!r}")

    def test_bresaola_renamed_and_text_only(self):
        for f in list(DOCS.rglob("*.html")) + list((ROOT / "content").glob("*.json")) + [DOCS / "llms.txt", DOCS / "sitemap.xml"]:
            self.assertNotIn("prosciutto", f.read_text(encoding="utf-8").lower(), f)
        self.assertIn("bresaola-arugula", self.photos["no_photo"])
        self.assertTrue((DOCS / "menu/bresaola-arugula/index.html").exists())

    # ── truth ──
    def test_sample_location_has_no_street_number(self):
        """The sample location is cross streets only: no house number or postal code anywhere."""
        files = list(DOCS.rglob("*.html")) + [DOCS / "llms.txt"]
        for f in files:
            text = f.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b\d{1,5}\s+(Commercial|Kitchener)\b", text), f)
            self.assertIsNone(re.search(r"\bV\d[A-Z] ?\d[A-Z]\d\b", text), f)
        self.assertNotRegex(self.site["contact"]["maps_url"], r"query=\d")
        self.assertIn("google.com/maps/search/", self.site["contact"]["maps_url"])

    def test_samples_are_marked(self):
        if not self.site.get("preview"):
            return
        self.assertIn("Sample menu", self.read("menu/index.html"))
        self.assertIn("Sample data, not for dietary decisions", self.read("allergens/index.html"))
        self.assertIn('<span class="smp">Sample location, phone and hours</span>', self.read("contact/index.html"))
        self.assertIn('<span class="smp">Sample location and hours</span>', self.read("index.html"))
        for it in self.dishes:
            self.assertIn("Sample menu: the price, calories and allergens are placeholders",
                          self.read(f"menu/{it['id']}/index.html"), it["id"])
        for p in self.pages:
            band = re.search(r'<section class="ob[^"]*" id="order".*?</section>', p.read_text(), re.S).group(0)
            self.assertIn('<span class="smp">Sample</span>', band, f"{p}: the phone is a sample")
            self.assertIn('class="pv"', p.read_text(), f"{p}: the Preview mark")

    def test_every_photo_credited(self):
        about = self.read("credits/index.html")
        used = set()
        for f in DOCS.rglob("*.html"):
            used |= set(re.findall(r"https://images\.unsplash\.com/(photo-[\w-]+)", f.read_text()))
        by_id = {p["url"].rsplit("/", 1)[1]: p for p in self.photos["photos"]}
        self.assertTrue(used)
        for pid in used:
            ph = by_id[pid]
            self.assertIn(f'href="{ph["page"]}"', about, pid)
            self.assertIn(html.escape(ph["author"]), about, pid)
        for prof in self.photos["photographers"]:
            if any(by_id[pid]["author"] == prof["name"] for pid in used):
                self.assertIn(f'href="{prof["profile"]}"', about)
        self.assertIn(html.escape(self.site["leonardo"]["credit"]), about)
        self.assertIn("stock image", about)
        self.assertIn('href="../credits/"', self.read("about/index.html"), "About Us links to the credits")

    def test_one_leonardo_per_page_with_credit(self):
        for p, pg in self.parsed.items():
            leo = [i for i in pg.imgs if i["src"].startswith("https://upload.wikimedia.org/")]
            self.assertLessEqual(len(leo), 1, p)
            if leo:
                text = p.read_text()
                self.assertIn(html.escape(self.site["leonardo"]["credit"]), text, p)
                self.assertIn(html.escape(self.site["leonardo"]["line"]).split(". ")[0], text, p)

    def test_mirror_writing_once_and_hidden(self):
        for p in self.pages:
            found = re.findall(r'<p class="mirror"([^>]*)>', p.read_text())
            self.assertEqual(len(found), 1, p)
            self.assertIn('aria-hidden="true"', found[0], p)

    def test_home_uses_each_photo_once(self):
        home = self.read("index.html")
        srcs = re.findall(r'<img [^>]*src="https://images\.unsplash\.com/(photo-[\w-]+)', home)
        self.assertEqual(len(srcs), len(set(srcs)), [s for s in srcs if srcs.count(s) > 1])

    def test_homepage_copy_under_150_words(self):
        words = self.parsed[DOCS / "index.html"].main_words
        self.assertLess(len(words), 150, " ".join(words))

    # ── menu ──
    def test_dish_photos_match_their_dishes(self):
        menu_html = self.read("menu/index.html")
        for cat in self.menu["categories"]:
            sec = re.search(rf'<section class="cat" id="{cat["id"]}".*?</section>', menu_html, re.S).group(0)
            ids = {i["id"] for i in cat["items"]}
            for d in re.findall(r'class="(?:strip__i|board__ph strip__i)"[^>]*><a href="[^"]*" data-dish="([\w-]+)"', sec):
                self.assertIn(d, ids, f"{cat['id']}: a photo of another section's dish")
                self.assertNotIn(d, self.photos["no_photo"])
        for it in self.dishes:
            page = self.read(f"menu/{it['id']}/index.html")
            art = re.search(r'<article class="dd.*?</article>', page, re.S).group(0)
            has = it["id"] in {p["key"] for p in self.photos["photos"]}
            self.assertEqual("images.unsplash.com" in art, has, it["id"])
            if has:
                ph = self.b.PHOTOS[it["id"]]
                self.assertIn(f'alt="{html.escape(ph["alt"], quote=True)}"', art, it["id"])
            else:
                self.assertIn('class="dd dd--text"', art, it["id"])

    def test_dish_sheet_contents(self):
        for it in self.dishes:
            page = self.read(f"menu/{it['id']}/index.html")
            for needle in ("Ingredients", "Nutrition", "Contains:", "May contain:", 'class="dd__dots"', "<span>Order Now</span>",
                           "Calories", "Protein", "Carbs", "Fat", "Sodium", 'class="dd__basis"'):
                self.assertIn(needle, page, f"{it['id']}: {needle}")
            self.assertLess(page.index('class="dd__pr"'), page.index('class="btn btn--red btn--big dd__order"'))
            self.assertLess(page.index("dd__order"), page.index(">Ingredients<"), "the Order button sits under the price")
            self.assertEqual(len(re.findall(r"<dt>", re.search(r'<dl class="nutri">.*?</dl>', page, re.S).group(0))), 5)

    def test_board_and_filters(self):
        menu_html = self.read("menu/index.html")
        for key, label in (("veg", "Vegetarian"), ("spicy", "Spicy"), ("gf", "Gluten-free option")):
            self.assertIn(f'aria-pressed="false" data-filter="{key}">{label}</button>', menu_html)
        self.assertEqual(len(re.findall(r'<li class="row"', menu_html)), len(self.dishes))
        self.assertIn('<p class="board__head" aria-hidden="true"><span>12″</span><span>16″</span></p>', menu_html)
        for it in self.dishes:
            row = re.search(rf'<li class="row"[^>]*>\s*<a [^>]*data-dish="{it["id"]}">.*?</li>', menu_html, re.S).group(0)
            self.assertIn(f'{it["kcal"]:,} kcal per ', row, it["id"])
            if it["allergens"]:
                self.assertIn("Contains " + ", ".join(self.b.ALLERGENS[a] for a in it["allergens"]).lower(), row, it["id"])
        for c in self.menu["combos"]:
            self.assertIn(f'id="combo-{c["id"]}"', menu_html)
            self.assertIn(f'href="menu/#combo-{c["id"]}"', self.read("index.html"))

    def test_prices_full_size_dollar(self):
        for f in DOCS.rglob("*.html"):
            self.assertNotIn("<sup>", f.read_text(), f)

    def test_every_allergen_key_is_known(self):
        keys = set(self.menu["allergen_keys"])
        self.assertEqual(keys, set(self.b.ALLERGENS))
        for it in self.dishes:
            for a in it["allergens"] + it.get("may_contain", []):
                self.assertIn(a, keys, f"{it['id']}: {a}")
            for d in it.get("diet", []):
                self.assertIn(d, self.b.DIETS, f"{it['id']}: {d}")

    def test_allergens_page_complete(self):
        page = self.read("allergens/index.html")
        rows = re.findall(r'<tr class="mx__row">.*?</tr>', page, re.S)
        self.assertEqual(len(rows), len(self.dishes))
        for r in rows:
            self.assertEqual(len(re.findall(r'<td class="mx__c', r)), len(self.menu["allergen_keys"]))
            self.assertRegex(r, r"<b>[\d,]+</b> <span>per ")
        self.assertEqual(len(re.findall(r'<li class="al__i">', page)), len(self.dishes), "the phone list")
        if self.menu.get("sample"):
            self.assertIn("Sample data, not for dietary decisions", page)

    def test_diet_labels_agree_with_allergens(self):
        for it in self.dishes:
            every = set(it["allergens"]) | set(it.get("may_contain", []))
            if "vegan" in it.get("diet", []):
                self.assertFalse(every & {"milk", "egg", "fish", "shellfish"}, it["id"])
            if "vegetarian" in it.get("diet", []):
                self.assertFalse(every & {"fish", "shellfish"}, it["id"])

    # ── contact and hours ──
    def test_contact_page(self):
        page = self.read("contact/index.html")
        c = self.site["contact"]
        self.assertIn(html.escape(c["address"]), page)
        self.assertIn(html.escape(c["maps_url"]), page)
        self.assertIn(f"mailto:{c['email']}", page)
        self.assertEqual(len(re.findall(r"<tr[^>]*data-days=", page)), len(self.site["hours"]))
        self.assertEqual(len(re.findall(r'<tr class="is-today"', page)), 1, "today is highlighted")
        self.assertIn('id="hours"', page)

    def test_opening_state(self):
        od = self.site.get("opening_date")
        home = self.read("index.html")
        if od and self.b.TODAY.isoformat() < od:
            self.assertIn('data-state="soon"', home)
            self.assertRegex(home, r'data-status="short"[^>]*>Opening [A-Z][a-z]{2} \d{1,2}<')
        if self.site.get("preview"):
            self.assertNotIn("Open now", home, "no open-now claim while the hours are samples")

    # ── images and performance ──
    def test_images(self):
        for p, pg in self.parsed.items():
            for img in pg.imgs:
                self.assertIn("alt", img, f"{p}: {img.get('src')}")
                self.assertTrue(img.get("width") and img.get("height"), f"{p}: {img.get('src')}")
                src = img["src"]
                if src.startswith("https://images.unsplash.com/"):
                    q = parse_qs(urlparse(src).query)
                    self.assertEqual(q.get("auto"), ["format"])
                    self.assertEqual(q.get("fit"), ["crop"])
                    self.assertEqual(q.get("q"), ["75"])
                    for part in img["srcset"].split(", "):
                        url, w = part.rsplit(" ", 1)
                        self.assertEqual(parse_qs(urlparse(url).query)["w"], [w[:-1]], f"{p}: srcset width")
                    self.assertTrue(img.get("sizes"), p)
                if img.get("fetchpriority") != "high":
                    self.assertIn(img.get("loading"), ("lazy", "eager"), f"{p}: {src[:60]}")
                self.assertEqual(img.get("decoding"), "async")
            # only the first screen loads at once: at most one high-priority photo per page but the hero's two,
            # and at most four photos that are not lazy
            first = [i for i in pg.imgs if i.get("loading") != "lazy"]
            self.assertLessEqual(len(first), 4, p)
            self.assertLessEqual(len([i for i in first if i.get("fetchpriority") == "high"]), 2, p)
        home = self.read("index.html")
        self.assertIn('rel="preload" as="image"', home)
        self.assertEqual(len(re.findall(r'<img [^>]*fetchpriority="high"', home)), 2, "only the hero is eager")

    def test_css_rules(self):
        css = self.read("assets/site.css")
        for v in re.findall(r"border-radius:\s*([^;]+);", css):
            self.assertIn(v.strip(), ("0", "50%"), "square corners (the round halal disc aside)")
        for d in re.findall(r"(?<![\w.-])(\d*\.?\d+)s\b", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
            self.assertTrue(0.4 <= float(d) <= 0.7, f"motion lasts 400 to 700 ms: {d}s")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertNotRegex(css.lower(), r"\bgold\b|#d9a441|#c9a227|#d4af37")
        self.assertNotIn("letter-spacing: .", css, "no tracked capitals")

    # ── SEO ──
    def test_jsonld(self):
        found = 0
        for p, pg in self.parsed.items():
            for raw in pg.jsonld:
                ld = json.loads(raw)
                self.assertEqual(ld["@type"], "Restaurant")
                if self.menu.get("sample"):
                    self.assertNotIn("hasMenu", ld)
                    self.assertNotIn("Menu", raw, p)
                if self.site.get("preview"):
                    for k in ("telephone", "openingHoursSpecification", "priceRange"):
                        self.assertNotIn(k, ld, p)
                    self.assertNotIn("streetAddress", ld["address"], p)
                found += 1
        self.assertGreaterEqual(found, 1)

    def test_noindex_while_preview(self):
        preview = self.site.get("preview") or not self.site.get("index")
        robots = self.read("robots.txt")
        for p, pg in self.parsed.items():
            if preview:
                self.assertIsNotNone(pg.robots, p)
                self.assertIn("noindex", pg.robots, p)
            else:
                self.assertIsNone(pg.robots, p)
        if preview:
            self.assertIn("Disallow: /", robots)
        self.assertIn('content="noindex"', self.read("assets/dishes.html"))

    def test_meta_files(self):
        json.loads(self.read("manifest.webmanifest"))
        sm = self.read("sitemap.xml")
        if self.site.get("preview") or not self.site.get("index"):
            self.assertNotIn("<url>", sm, "no page listed while robots.txt keeps crawlers out")
        else:
            for rel in ("menu/", "about/", "contact/", "allergens/"):
                self.assertIn(self.site["base_url"] + rel, sm)
        llms = self.read("llms.txt")
        self.assertIn(self.site["name"], llms)
        if self.site.get("preview"):
            for sample in (self.site["contact"]["phone"], self.site["contact"]["address"], "kcal", "$"):
                self.assertNotIn(sample, llms, "no sample datum in llms.txt while the preview is on")
            self.assertIn("preview", llms)
        for name, (w, h) in (("og.png", (1200, 630)), ("apple-touch-icon.png", (180, 180)), ("favicon.png", (64, 64))):
            self.assertEqual((DOCS / name).read_bytes()[16:24], w.to_bytes(4, "big") + h.to_bytes(4, "big"), name)

    def test_owner_questions_pdf_published_unlinked(self):
        pdfs = list((ROOT / "brief").glob("*.pdf"))
        self.assertTrue(pdfs)
        for src in pdfs:
            out = DOCS / "brief" / src.name
            self.assertTrue(out.exists(), src.name)
            self.assertEqual(out.read_bytes(), src.read_bytes())
            for p in list(DOCS.rglob("*.html")) + [DOCS / "llms.txt", DOCS / "sitemap.xml"]:
                self.assertNotIn(src.name, p.read_text(encoding="utf-8"), p)
                self.assertNotIn("brief/", p.read_text(encoding="utf-8"), p)


if __name__ == "__main__":
    unittest.main()
