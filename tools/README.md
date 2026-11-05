# Tools

Everything here is the standard library of Python 3 (`/usr/bin/python3`) plus Chrome headless and macOS `sips`: no
package, no npm, no CDN script. Colours and type are in [DESIGN.md](../DESIGN.md).

## `render_images.py` → `src/img/`

`python3 tools/render_images.py` prints three images with Chrome headless from small HTML pages that use the site's own
fonts (Google Fonts), colours and hero photos (by URL from images.unsplash.com):

| File | Size | What |
|---|---|---|
| `og.png` | 1200×630 | the share image: the lockup, «REAL PIZZA. REAL SMASHBURGERS.», the red rule, «Made with Passion.», the halal mark and the street on black; the hero pizza and smashburger at right over the tricolour |
| `apple-touch-icon.png` | 180×180 | «DOUGH» over the tricolour over «VINCI», cream on black |
| `favicon.png` | 64×64 | «DV» over the tricolour |

Headless Chrome will not open a window narrower than 500 px, so the icons are drawn at 540 px and scaled down with
`sips`. Run it after a change to the wordmark, the colours or the hero photos, then rebuild.
