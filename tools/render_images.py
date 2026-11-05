#!/usr/bin/python3
"""Render the share image and the icons in the Nero style:

    src/img/og.png               1200x630  the share image (headline, halal mark, the pizza and the smashburger)
    src/img/apple-touch-icon.png  180x180  the home-screen icon (the wordmark stacked over the tricolour)
    src/img/favicon.png            64x64   the browser-tab icon (DV over the tricolour)

Each is a small HTML page printed to PNG by Chrome headless, with the site's own fonts (Google Fonts), colours and hero
photos (by URL from images.unsplash.com), so the images match the site. Standard library plus macOS `sips` to scale
the icons down (headless Chrome will not open a window narrower than 500 px). Run, then rebuild:

    python3 tools/render_images.py && python3 build.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  (reads content/)

CHROME = next((p for p in ("/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") if os.path.exists(p)), None)
FONTS = [build.FONTS.replace("display=swap", "display=block"), build.FONTS_ACCENT.replace("display=swap", "display=block")]
LINKS = "".join(f'<link rel="stylesheet" href="{build.e(f)}">' for f in FONTS)
BASE = """*{margin:0;padding:0;box-sizing:border-box}
body{overflow:hidden;background:#121010;color:#f5ebda;font-family:Archivo,sans-serif;-webkit-font-smoothing:antialiased}
.d{font-stretch:62%;font-weight:900;text-transform:uppercase;line-height:.86}
.tri{display:flex}.tri i{flex:1}.tri i:nth-child(1){background:#2f8a45}.tri i:nth-child(2){background:#f5ebda}.tri i:nth-child(3){background:#c8261b}"""


def og_html() -> str:
    pizza = build.img_url(build.PHOTOS["hero-pizza"], 600, 2 / 3)
    burger = build.img_url(build.PHOTOS["hero-burger"], 600, 2 / 3)
    return f"""<!doctype html><html><head><meta charset="utf-8">{LINKS}<style>{BASE}
body{{width:1200px;height:630px;position:relative}}
.copy{{position:absolute;left:60px;top:54px;width:600px}}
.wm{{font-size:46px}} .sub{{display:flex;align-items:center;gap:10px;margin-top:6px;font-stretch:62%;font-weight:800;font-size:21px}}
.sub .tri{{width:96px;height:6px}}
h1{{margin-top:58px;font-size:66px}} h1 span{{display:block}}
.rule{{width:132px;height:8px;background:#c8261b;margin-top:22px}}
.it{{margin-top:18px;font:italic 400 44px/1 "Instrument Serif",serif}}
.tag{{position:absolute;left:60px;bottom:50px;display:flex;align-items:center;gap:14px;font-weight:600;font-size:21px}}
.disc{{width:46px;height:46px;border-radius:50%;display:grid;place-items:center;background:#286e37;color:#f5ebda;
  box-shadow:inset 0 0 0 3.4px #286e37,inset 0 0 0 5.6px #f5ebda;font:700 14px/1 "Noto Kufi Arabic",sans-serif}}
.food{{position:absolute;right:0;top:0;width:560px;height:620px;display:grid;grid-template-columns:1fr 1fr;gap:3px}}
.food img{{width:100%;height:100%;object-fit:cover;display:block;filter:{build.PHOTO_DOC["treatment"]["filter"]}}}
.foot{{position:absolute;right:0;bottom:0;width:560px;height:10px}}
</style></head><body>
<div class="copy">
  <p class="wm d">Dough-Vinci</p>
  <p class="sub">Pizza &amp; Burger <span class="tri"><i></i><i></i><i></i></span></p>
  <h1 class="d"><span>Real Pizza.</span><span>Real Smashburgers.</span></h1>
  <div class="rule"></div>
  <p class="it">{build.e(build.SITE["hero"]["sub"])}</p>
</div>
<p class="tag"><span class="disc" lang="ar" dir="rtl">{build.e(build.SITE["halal"]["mark_ar"])}</span>{build.e(build.SITE["halal"]["mark_en"])}</p>
<div class="food"><img src="{build.e(pizza)}" alt=""><img src="{build.e(burger)}" alt=""></div>
<div class="foot tri"><i></i><i></i><i></i></div>
</body></html>"""


def icon_html(kind: str) -> str:
    if kind == "touch":
        inner = """<p class="d a">Dough</p><div class="tri bar"><i></i><i></i><i></i></div><p class="d b">Vinci</p>"""
        css = """.a,.b{font-size:150px;line-height:.8}.bar{width:300px;height:18px;margin:26px 0}"""
    else:
        inner = """<p class="d m">DV</p><div class="tri bar"><i></i><i></i><i></i></div>"""
        css = """.m{font-size:330px;line-height:.78}.bar{width:300px;height:44px;margin-top:34px}"""
    return f"""<!doctype html><html><head><meta charset="utf-8">{LINKS}<style>{BASE}
body{{width:540px;height:540px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}}
{css}
</style></head><body>{inner}</body></html>"""


def shoot(html: str, w: int, h: int, out: Path) -> None:
    page = Path(tempfile.mkdtemp(prefix="dv-render-")) / "page.html"  # left for the OS to clear
    page.write_text(html, encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", f"--window-size={w},{h}", "--virtual-time-budget=15000",
                    f"--screenshot={out}", page.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    if not CHROME:
        raise SystemExit("Chrome not found")
    img = ROOT / "src" / "img"
    img.mkdir(parents=True, exist_ok=True)
    shoot(og_html(), 1200, 630, img / "og.png")
    shoot(icon_html("touch"), 540, 540, img / "apple-touch-icon.png")
    subprocess.run(["sips", "-z", "180", "180", str(img / "apple-touch-icon.png")], check=True, stdout=subprocess.DEVNULL)
    shoot(icon_html("tab"), 540, 540, img / "favicon.png")
    subprocess.run(["sips", "-z", "64", "64", str(img / "favicon.png")], check=True, stdout=subprocess.DEVNULL)
    print("rendered", *(img / n for n in ("og.png", "apple-touch-icon.png", "favicon.png")))


if __name__ == "__main__":
    main()
