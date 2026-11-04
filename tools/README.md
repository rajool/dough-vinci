# Tools and drawing contracts

Everything here is the standard library of Python 3 (`/usr/bin/python3`) or plain browser JavaScript: no package,
no npm, no CDN script. Colours, type and drawing rules are in [DESIGN.md](../DESIGN.md).

## `codex_art.py` → `src/art/`

`python3 tools/codex_art.py` regenerates every drawing deterministically (fixed seeds). Output files:

| File | viewBox | What |
|---|---|---|
| `pizza-study.svg` + `pizza-study.json` | `0 0 1000 1000` | whole pizza seen from above inside a Vitruvian circle-and-square construction |
| `burger-study.svg` + `burger-study.json` | `0 0 1000 1000` | double smashburger seen from the side, drawn stacked (rest state), each layer movable |
| `ribbon.svg` | `0 0 1200 120` | tricolore brush ribbon (not used by the site) |
| `icons.svg` | sprite of `<symbol>`s, each `0 0 48 48` | hand-inked icons (not used by the site; the icons come from `src/art/new/allergens.svg`) |

Rules shared by the two studies:

- Root: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="…" class="codex-art codex-art--pizza|burger"
  aria-hidden="true" focusable="false">`, no `width`/`height`, no `<style>`, no inline colour, no `<text>`.
- Every id is prefixed (`pz-` for the pizza, `bg-` for the burger, `rb-` for the ribbon) because all drawings are
  inlined into one HTML page.
- `<defs>` holds one wash filter per drawing (`#pz-wash`, `#bg-wash`, `#rb-wash`): `feTurbulence` +
  `feDisplacementMap` (and at most a light blur) for organic, bleeding watercolour edges.
- Stroke paths: `fill="none"`, `pathLength="1"`, and `style="--i:N"` where N is the drawing order (0, 1, 2, …) so
  CSS can stagger them. Classes: `art-construction` (hair-thin guides), `art-line` (contours), `art-hatch`
  (left-handed hatching `\`), `art-dim` (engineering dimension lines, burger only).
- Wash shapes: filled paths with class `wash wash-<name>` from DESIGN.md (plus `wash-basil`, `wash-cream`,
  `wash-tomato` for the ribbon). Washes sit under the ink.
- Anchor dots for the page's notes: `<circle class="art-dot" r="5" data-note="<name>" …/>`.
- Paths are written with at most one decimal place; each study stays under about 120 KB.

### Pizza groups (DOM order, bottom to top)

`<g id="pz-construction" class="art-group art-group--construction">` (circle, square, axes, golden-ratio arcs,
compass ticks), `<g id="pz-wash" class="art-group art-group--wash" filter="url(#pz-wash)">`, `<g id="pz-hatch"
class="art-group art-group--hatch">`, `<g id="pz-line" class="art-group art-group--line">`, `<g id="pz-anchors">`.
Toppings follow the owner's mock-up: pepperoni, mushrooms, green-pepper strips, red-onion rings, melted cheese with
browned spots, a puffy crust, and eight faint slice cuts. Anchors: `crust`, `sauce`, `cheese`, `pepperoni`,
`pepper`, `onion`, `mushroom`.

### Burger groups

Layers in DOM order, bottom to top: `heel`, `patty-low`, `cheese-low`, `patty-top`, `cheese-top`, `pickles`,
`sauce`, `crown`. Each is `<g id="bg-<layer>" class="layer" data-layer="<layer>" style="--explode:<user units>">`
holding three groups, `art-group--wash` (with `filter="url(#bg-wash)"`), `art-group--hatch`, `art-group--line`, and
its own anchor dot (`data-note="<layer>"`). `--explode` is the vertical offset of that layer in the fully exploded
view (negative is up); the page translates each layer by `--explode × progress`. Static engineering guides (centre
axis, ruler with ticks, width dimension under the heel) are in `<g id="bg-dims" class="art-group art-group--dims">`,
painted last.

### JSON sidecars

`{"viewBox": [0, 0, 1000, 1000], "anchors": {"<name>": [x, y], …}, "explode": {"<layer>": dy, …}}` with
coordinates in viewBox units at rest (`explode` only for the burger).

## The illustrator's drawings → `src/art/new/`

`map.svg` + `map.json` (anchors for the HTML street labels, wind names and the pin), `flying-machine.svg` (+ json with
wing pivots), `gears.svg` (+ json with gear ratios), `vitruvian-mark.svg` (the logo mark, also the favicon), and
`allergens.svg` (the icon sprite: `a-<allergen>`, `d-<diet>`, `i-<ui>`). They carry no colour; `art.css` holds the
classes they expect, and `build.py` bakes that CSS into each copy in `docs/assets/art/` so the files also render as
plain images. `src/art/ui-icons.svg` supplies the interface icons the sprite does not have (it loses to the sprite on
a shared id).

## `render_images.py` → `src/img/`

`python3 tools/render_images.py` prints `og.png` (1200×630 share image) and `apple-touch-icon.png` (180×180) with
Chrome headless from two small HTML pages that use the site's fonts, mark and hero photo. Run it after a change to
the mark or the hero photo, then rebuild.
