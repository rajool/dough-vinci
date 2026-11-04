#!/usr/bin/python3
"""Render the share image (src/img/og.png, 1200x630) and the home-screen icon (src/img/apple-touch-icon.png, 180x180).

Both are small HTML pages printed to PNG by Chrome headless, with the site's own fonts, colours, Vitruvian mark and hero
photo (by URL from images.unsplash.com), so the images match the site. Standard library plus macOS `sips` (to scale
the icon down; headless Chrome will not open a window narrower than 500 px). Run, then rebuild:

    python3 tools/render_images.py && python3 build.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  (reads content/ and src/art/)

CHROME = next((p for p in ("/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") if os.path.exists(p)), None)
FONTS = build.FONTS.replace("display=swap", "display=block")


def mark() -> str:
    svg = build.bake(build.mark_svg())
    return re.sub(r"<\?xml[^>]*>", "", svg)


def og_html() -> str:
    pizza = build.photo("hero-pizza")
    burger = build.photo("hero-burger")
    p_url = build.img_url(pizza, 1000, 1)
    b_url = build.img_url(burger, 600, 4 / 5)
    css = build.art_css()
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}"><style>{css}
*{{margin:0;box-sizing:border-box}}
body{{width:1200px;height:630px;overflow:hidden;position:relative;background:#FFF8EC;color:#2B1D14;font-family:"Instrument Sans",sans-serif}}
body::before{{content:"";position:absolute;inset:0;background:radial-gradient(60% 50% at 10% 0%,rgba(247,179,43,.16),transparent 70%),radial-gradient(50% 50% at 100% 100%,rgba(214,58,34,.08),transparent 70%)}}
.stripe{{position:absolute;left:0;right:0;bottom:0;height:12px;background:repeating-linear-gradient(90deg,#C4532F 0 40px,#E2A33A 40px 80px,#7C8B3A 80px 120px,#3E6A9C 120px 160px)}}
.copy{{position:absolute;left:64px;top:62px;width:600px}}
.brand{{display:flex;align-items:center;gap:14px;font:italic 800 44px/1 Fraunces,serif;font-variation-settings:"SOFT" 100}}
.brand svg{{width:64px;height:64px}} .brand b{{color:#D63A22;font-weight:800}}
h1{{margin-top:54px;font:850 86px/.94 Fraunces,serif;letter-spacing:-.035em;font-variation-settings:"SOFT" 100}}
h1 span{{display:block}} h1 .t{{color:#D63A22}}
.hand{{font:700 50px/1.1 Caveat,cursive;margin-top:14px}}
.where{{margin-top:34px;display:inline-flex;align-items:center;gap:10px;background:#FFE3A1;color:#5A3A00;padding:10px 18px;border-radius:999px;font:600 22px/1 "Instrument Sans",sans-serif}}
.where i{{width:12px;height:12px;border-radius:50%;background:#D63A22}}
.stage{{position:absolute;right:-60px;top:12px;width:600px;height:600px}}
.construct{{position:absolute;inset:0;fill:none;stroke:#B8432A;stroke-width:1.6;opacity:.85}}
.pizza{{position:absolute;left:50%;top:50%;width:430px;height:430px;translate:-50% -50%;border-radius:50%;overflow:hidden;box-shadow:0 30px 40px -18px rgba(110,50,15,.45)}}
.pizza img{{width:100%;height:100%;object-fit:cover}}
.burger{{position:absolute;right:70px;bottom:18px;width:170px;background:#FFFDF8;padding:8px;rotate:-5deg;box-shadow:0 20px 34px -18px rgba(110,58,20,.6)}}
.burger img{{width:100%;aspect-ratio:4/5;object-fit:cover;display:block}}
.note{{position:absolute;font:700 30px/1 Caveat,cursive;color:#2B1D14}}
.n1{{right:110px;top:24px;rotate:4deg}} .n2{{left:40px;bottom:40px;background:#F7B32B;padding:4px 12px;rotate:-3deg}}
</style></head><body>
<div class="copy">
  <div class="brand">{mark()}<span>Dough<b>-</b>Vinci</span></div>
  <h1><span>Real Pizza.</span><span class="t">Real Smashburgers.</span></h1>
  <p class="hand">Made with Passion.</p>
  <p class="where"><i></i>Commercial Drive · Vancouver</p>
</div>
<div class="stage">
  <svg class="construct" viewBox="0 0 600 600"><path d="M300 52a248 248 0 1 1-.1 0z"/><path d="M86 96h428v428H86z"/><path d="M300 18v564M18 300h564" opacity=".5"/><path d="M86 96l428 428M514 96 86 524" opacity=".4"/></svg>
  <div class="pizza"><img src="{p_url}" alt=""></div>
  <div class="burger"><img src="{b_url}" alt=""></div>
  <p class="note n1">la pizza è l’arte</p>
  <p class="note n2">…and the engineering</p>
</div>
<div class="stripe"></div>
</body></html>"""


def icon_html() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{build.art_css()}
*{{margin:0}} body{{width:540px;height:540px;overflow:hidden;background:#FFF8EC;display:grid;place-items:center}}
.ring{{width:540px;height:540px;display:grid;place-items:center;background:radial-gradient(circle,#FFF8EC 0 62%,#F7B32B 62.2% 100%)}}
svg{{width:400px;height:400px}}
</style></head><body><div class="ring">{mark()}</div></body></html>"""


def shoot(html: str, w: int, h: int, out: Path) -> None:
    page = Path(tempfile.mkdtemp(prefix="dv-render-")) / "page.html"  # left for the OS to clear
    page.write_text(html, encoding="utf-8")
    if True:
        subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", f"--window-size={w},{h}", "--virtual-time-budget=15000",
                        f"--screenshot={out}", page.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    if not CHROME:
        raise SystemExit("Chrome not found")
    img = ROOT / "src" / "img"
    img.mkdir(parents=True, exist_ok=True)
    shoot(og_html(), 1200, 630, img / "og.png")
    shoot(icon_html(), 540, 540, img / "apple-touch-icon.png")
    subprocess.run(["sips", "-z", "180", "180", str(img / "apple-touch-icon.png")], check=True, stdout=subprocess.DEVNULL)
    print("rendered", img / "og.png", img / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
