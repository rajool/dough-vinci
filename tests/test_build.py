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
        self.jsonld: list[str] = []
        self.robots: str | None = None
        self.base: str | None = None
        self.order_triggers: list[dict] = []
        self.blank_targets: list[dict] = []
        self.in_template = 0
        self._script: str | None = None
        self._buf: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "template":
            self.in_template += 1
        if self.in_template:
            return
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
        if tag in ("img", "script") and a.get("src"):
            self.refs.append((tag, a["src"]))
        if tag == "use" and a.get("href"):
            self.refs.append((tag, a["href"]))
        if tag == "img":
            self.imgs.append(a)
        if tag == "script" and a.get("type") == "application/ld+json":
            self._script, self._buf = "ld", []
        if "data-order" in a:
            self.order_triggers.append({"tag": tag, **a})
        if tag == "a" and a.get("target") == "_blank":
            self.blank_targets.append(a)

    def handle_endtag(self, tag):
        if tag == "template":
            self.in_template -= 1
        if tag == "script" and self._script == "ld":
            self.jsonld.append("".join(self._buf))
            self._script = None

    def handle_data(self, data):
        if self._script:
            self._buf.append(data)
        elif not self.in_template:
            self.text.append(data)


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
        cls.pages = sorted(p for p in DOCS.rglob("*.html") if "assets" not in p.parts)
        cls.parsed = {p: parse(p) for p in cls.pages}

    # ── pages build ──
    def test_pages_exist(self):
        for rel in ["index.html", "menu/index.html", "allergens/index.html", "visit/index.html", "about/index.html", "404.html",
                    "robots.txt", "sitemap.xml", "llms.txt", "manifest.webmanifest", "favicon.svg", "assets/site.css",
                    "assets/site.js", "assets/dishes.html"]:
            self.assertTrue((DOCS / rel).exists(), rel)
        for cat in self.menu["categories"]:
            for it in cat["items"]:
                self.assertTrue((DOCS / "menu" / it["id"] / "index.html").exists(), it["id"])

    def test_no_placeholder_left(self):
        for p in list(DOCS.rglob("*.html")) + list(DOCS.rglob("*.txt")) + list(DOCS.rglob("*.xml")):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("{{", text, p)
            self.assertNotIn("<!--SPRITE-->", text, p)
        self.assertNotIn("__ROOT__", (DOCS / "menu/index.html").read_text())

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
            if pg.base:
                page_url = urljoin("https://x.test", pg.base)
            for tag, url in pg.refs:
                u = urlparse(url)
                if u.scheme in ("http", "https", "mailto", "tel") or url.startswith("//"):
                    continue
                if url.startswith("#"):
                    if pg.base and tag == "a" and url != "#main":
                        target = urljoin(page_url, url)
                    else:
                        self.assertIn(url[1:], pg.ids, f"{p}: {tag} {url}")
                        continue
                else:
                    target = urljoin(page_url, url)
                path = urlparse(target).path
                self.assertTrue(path.startswith(self.site["base_path"]), f"{p}: {url} leaves the site")
                local = DOCS / path[len(self.site["base_path"]):]
                if path.endswith("/"):
                    local = local / "index.html"
                self.assertTrue(local.exists(), f"{p}: {url} -> {local}")
                frag = urlparse(target).fragment
                if frag and local.suffix == ".html" and not frag.startswith("dish="):
                    self.assertIn(f'id="{frag}"', local.read_text(), f"{p}: {url}")

    def test_links_relative_except_404(self):
        nf = DOCS / "404.html"
        for p, pg in self.parsed.items():
            for tag, url in pg.refs:
                if tag not in ("a", "link", "img", "script") or urlparse(url).scheme or url.startswith(("#", "//")):
                    continue
                if p == nf:
                    # served at any missing address, so every local link starts from the site root
                    self.assertTrue(url.startswith(self.site["base_path"]), f"404: {url}")
                elif url.startswith("/"):
                    self.fail(f"{p}: absolute local path {url}")
        # no <base>: with one, the skip link and the Order links would leave the 404 page
        self.assertIsNone(self.parsed[nf].base)

    def test_new_tabs_are_safe_and_announced(self):
        for p, pg in self.parsed.items():
            for a in pg.blank_targets:
                self.assertIn("noopener", a.get("rel", ""), f"{p}: {a.get('href')}")

    def test_order_works_without_js(self):
        for p, pg in self.parsed.items():
            self.assertIn("order", pg.ids, p)
            for t in pg.order_triggers:
                self.assertEqual(t["tag"], "a", f"{p}: an Order trigger must be a real link")
                self.assertEqual(t["href"], "#order", p)
            html = p.read_text()
            for d in self.site["delivery"]:
                self.assertIn(d["url"], html, f"{p}: {d['name']}")

    # ── menu data ──
    def test_every_dish_has_photo_and_alt(self):
        menu_html = (DOCS / "menu/index.html").read_text()
        for cat in self.menu["categories"]:
            for it in cat["items"]:
                ph = self.b.photo(it["id"])
                self.assertTrue(ph["alt"].strip(), it["id"])
                self.assertTrue(ph["url"].startswith("https://images.unsplash.com/"), it["id"])
                card = re.search(rf'<li class="dish" data-id="{re.escape(it["id"])}".*?</a>', menu_html, re.S)
                self.assertTrue(card, it["id"])
                # the card is one link named by its text: the photo is alt="" and the allergens are part of the name
                self.assertIsNotNone(re.search(r'<img [^>]*alt=""', card.group(0)), it["id"])
                self.assertNotIn("aria-label", card.group(0), it["id"])
                if it["allergens"]:
                    self.assertIn('<span class="sr">Contains: </span>', card.group(0), it["id"])
                page = (DOCS / "menu" / it["id"] / "index.html").read_text()
                self.assertIn(f'alt="{html.escape(ph["alt"], quote=True)}"', page, it["id"])

    def test_every_allergen_key_is_known(self):
        keys = set(self.menu["allergen_keys"])
        self.assertEqual(keys, set(self.b.ALLERGENS), "the build knows every allergen key")
        for cat in self.menu["categories"]:
            for it in cat["items"]:
                for a in it["allergens"] + it.get("may_contain", []):
                    self.assertIn(a, keys, f"{it['id']}: {a}")
                for d in it.get("diet", []):
                    self.assertIn(d, self.b.DIETS, f"{it['id']}: {d}")
        for k in keys:
            self.assertIn(f"a-{k}", self.b.SPRITE_IDS, k)

    def test_allergen_matrix_complete(self):
        html = (DOCS / "allergens/index.html").read_text()
        rows = re.findall(r'<tr><th scope="row" class="mx__dish">.*?</tr>', html, re.S)
        n = sum(len(c["items"]) for c in self.menu["categories"])
        self.assertEqual(len(rows), n)
        for r in rows:
            self.assertEqual(len(re.findall(r'<td class="mx__c', r)), len(self.menu["allergen_keys"]))
        if self.menu.get("sample"):
            self.assertIn("Sample data, not for dietary decisions", html)

    def test_dish_sheets(self):
        frag = (DOCS / "assets/dishes.html").read_text()
        for cat in self.menu["categories"]:
            for it in cat["items"]:
                self.assertIn(f'<template data-dish="{it["id"]}">', frag)
        page = (DOCS / "menu/vitruvian/index.html").read_text()
        for needle in ("Ingredients", "Contains", "May contain", '<table class="nutri">', "kcal"):
            self.assertIn(needle, page)

    # ── images ──
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
                        self.assertTrue(400 <= int(w[:-1]) <= 1600)
                    self.assertTrue(img.get("sizes"), p)
                    if img.get("fetchpriority") != "high":
                        self.assertEqual(img.get("loading"), "lazy", f"{p}: {src[:60]}")
                    self.assertEqual(img.get("decoding"), "async")
        home = (DOCS / "index.html").read_text()
        self.assertIn('rel="preload" as="image"', home)
        self.assertIn('fetchpriority="high"', home)

    def test_lang_on_italian(self):
        home = (DOCS / "index.html").read_text()
        self.assertIn('lang="it">L’Arte', home)

    # ── SEO ──
    def test_jsonld_parses(self):
        found = 0
        for p, pg in self.parsed.items():
            for raw in pg.jsonld:
                ld = json.loads(raw)
                self.assertEqual(ld["@type"], "Restaurant")
                if self.menu.get("sample"):
                    self.assertNotIn("hasMenu", ld)
                    self.assertNotIn("Menu", raw.replace("hasMenu", ""), p)
                found += 1
        self.assertGreaterEqual(found, 1)

    def test_noindex_while_preview(self):
        preview = self.site.get("preview") or not self.site.get("index")
        robots = (DOCS / "robots.txt").read_text()
        for p, pg in self.parsed.items():
            if preview:
                self.assertIsNotNone(pg.robots, p)
                self.assertIn("noindex", pg.robots, p)
            else:
                self.assertIsNone(pg.robots, p)
        if preview:
            self.assertIn("Disallow: /", robots)
        if self.site.get("preview"):
            self.assertIn('class="preview-tag"', (DOCS / "index.html").read_text())

    def test_meta_files(self):
        json.loads((DOCS / "manifest.webmanifest").read_text())
        sm = (DOCS / "sitemap.xml").read_text()
        self.assertIn(self.site["base_url"] + "menu/", sm)
        self.assertIn(self.site["name"], (DOCS / "llms.txt").read_text())
        og = DOCS / "og.png"
        self.assertTrue(og.exists())
        self.assertEqual(og.read_bytes()[16:24], (1200).to_bytes(4, "big") + (630).to_bytes(4, "big"))
        icon = DOCS / "apple-touch-icon.png"
        self.assertEqual(icon.read_bytes()[16:24], (180).to_bytes(4, "big") + (180).to_bytes(4, "big"))

    def test_sample_location_has_no_street_number(self):
        """The sample location is cross streets only: no house number or postal code anywhere."""
        files = list(DOCS.rglob("*.html")) + [DOCS / "llms.txt"]
        for f in files:
            text = f.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b\d{3,5} Commercial", text), f)
            self.assertIsNone(re.search(r"\bV\d[A-Z] ?\d[A-Z]\d\b", text), f)
        self.assertNotRegex(self.site["contact"]["maps_url"], r"query=\d")
        if self.site.get("preview"):
            for p, pg in self.parsed.items():
                for raw in pg.jsonld:
                    ld = json.loads(raw)
                    for k in ("telephone", "priceRange", "acceptsReservations", "openingHoursSpecification"):
                        self.assertNotIn(k, ld, p)
                    self.assertNotIn("streetAddress", ld["address"], p)

    def test_owner_questions_pdf_published_unlinked(self):
        pdf = DOCS / "brief" / "dough-vinci-questions.pdf"
        self.assertTrue(pdf.exists())
        self.assertEqual(pdf.read_bytes(), (ROOT / "brief" / "dough-vinci-questions.pdf").read_bytes())
        for p in DOCS.rglob("*.html"):
            self.assertNotIn("dough-vinci-questions", p.read_text(encoding="utf-8"), p)

    def test_owner_welcome_word_for_word(self):
        about = (DOCS / "about/index.html").read_text(encoding="utf-8")
        for para in self.site["welcome"]:
            self.assertIn(html.escape(para, quote=True), about)

    def test_home_uses_each_photo_once(self):
        home = (DOCS / "index.html").read_text(encoding="utf-8")
        srcs = re.findall(r'<img [^>]*src="https://images\.unsplash\.com/(photo-[\w-]+)', home)
        self.assertEqual(len(srcs), len(set(srcs)), [s for s in srcs if srcs.count(s) > 1])

    def test_diet_labels_agree_with_allergens(self):
        for cat in self.menu["categories"]:
            for it in cat["items"]:
                every = set(it["allergens"]) | set(it.get("may_contain", []))
                if "vegan" in it.get("diet", []):
                    self.assertFalse(every & {"milk", "egg", "fish", "shellfish"}, it["id"])
                if "vegetarian" in it.get("diet", []):
                    self.assertFalse(every & {"fish", "shellfish"}, it["id"])

    def test_faq_opening_filled(self):
        visit = (DOCS / "visit/index.html").read_text(encoding="utf-8")
        self.assertNotIn("{opening}", visit)

    def test_opening_state(self):
        od = self.site.get("opening_date")
        if od and self.b.TODAY.isoformat() < od:
            self.assertIn("Opening ", (DOCS / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()
