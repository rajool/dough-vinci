# Dough-Vinci Pizza & Burger

The website of Dough-Vinci, a halal pizza, smashburger and pasta restaurant opening in early December 2026 at 12420
No. 1 Road, Richmond, BC. The design,
«Nero» (a pizzeria at night: warm black, cream type, tomato-red blocks, the food edge to edge), is in
[DESIGN.md](DESIGN.md).

**Preview:** https://rajool.github.io/dough-vinci/ (every page carries `noindex` and a small «Preview» mark while
`preview` is on). The location, parking, hours, email, dine-in and halal statement come from the owner; the menu,
prices, calories, allergens, phone, exact opening day, delivery links and photos are samples. Both lists are in
[content/placeholders.md](content/placeholders.md).

## Pages

Home, Menu (with one page per dish, which the dish sheet opens over the menu), About Us, Contact, Allergens & nutrition,
Photo credits, and the 404 page. Every page ends with the red Order band (the four apps and Call for pickup), and every «Order Now»
opens the Order sheet. There is no payment on the site.

## How it is built

Plain HTML, CSS and JavaScript, rendered by a Python standard-library build. No framework, no package, no
third-party script; fonts from Google Fonts, photos by URL from images.unsplash.com, the one Leonardo drawing by URL
from upload.wikimedia.org.

    python3 build.py                          # content/ + src/ -> docs/ (the GitHub Pages folder)
    python3 -m unittest discover -s tests     # builds, then checks the pages
    python3 tools/render_images.py            # share image, home-screen icon and favicon into src/img/ (needs Chrome)

Never edit `docs/` by hand: change `content/` or `src/`, then rebuild. Files the build no longer writes are moved to
the Trash. The build also copies `brief/*.pdf` into `docs/brief/`; no page links to it.

| Path | What |
|---|---|
| `content/site.json` | name, copy, the owner's welcome, opening date, contact, hours, delivery links, the halal block, FAQ, catering, «Start here» dishes, the Leonardo drawing, `preview` and `index` switches, and `confirmed` (which fields the owner has confirmed) |
| `content/menu.json` | categories, dishes (ingredients, kcal, nutrition, allergens, may-contain, diet, prices, badges), combos, allergen note, `sample` switch |
| `content/photos.json` | every Unsplash photo (alt text, author, crop), the photographers, the shared grade, the menu strips, and `no_photo`: the dishes shown as text only |
| `content/placeholders.md` | the owner's confirmed facts, and every sample datum still to confirm |
| `src/templates/` | page skeletons with `{{placeholders}}` |
| `src/css/site.css`, `src/js/site.js` | the whole design system, and the enhancements (sheets, filters, open-now, the phone Order bar) |
| `src/img/` | `og.png`, `apple-touch-icon.png` and `favicon.png`, made by `tools/render_images.py` |
| `docs/` | the built site |

## Editing the content

The owner does not edit the site himself; every change is a JSON edit and a rebuild.

- **A dish**: edit it in `content/menu.json` (name, `short`, `ingredients`, `kcal`, `portion` (what the calories are
  for), `nutrition`, `allergens`, `may_contain`, `diet`, `prices`, optional `badge`). A new dish either gets a photo in
  `content/photos.json` under the same `key`, or goes in `no_photo` there; the build stops if it has neither.
- **A photo**: change `url`, `page`, `author` and `alt` of its entry in `content/photos.json` (the author must be in
  `photographers`). `"crop": [x, y, zoom]` is the focal point and zoom Unsplash crops to; `"strip_crop"` frames the
  photo for its menu strip instead (the dish sheet keeps `crop`). `strips` picks which photos a menu section shows (one
  composition per strip); without it a section shows every photographed dish. When the
  restaurant's own shoot arrives, a dish leaves `no_photo` and gets its entry.
- **Start here**: `signatures` in `content/site.json`, four dishes with photos.
- **Hours**: `hours` in `content/site.json`, in Pacific time (`timezone` America/Vancouver). The status and the hours
  table follow them.
- **Opening date**: `opening_date` (`YYYY-MM-DD`) and `opening_approx`. While `opening_approx` is true the date is the
  owner's «around» date: the header says «Opening early Dec», the hero, the yellow band and Contact «Opening early
  December» and `{opening}` in a FAQ answer «in early December 2026», with no weekday or day number. With
  `opening_approx` false they say «Opening Dec 1», «Opening Tue, Dec 1» and «on Tuesday, December 1». After the date,
  while `preview` is on, they make no open-now claim; once `preview` is off they show «Open now · until 10 pm» or
  «Closed · opens 11 am». A page address with `?now=2026-12-11T19:30` shows the status at that moment, for checking.
- **Confirmed fields**: `confirmed` in `content/site.json` (`location`, `hours`, `email`, `halal`, `dine_in`,
  `parking`, `opening_date`, `phone`, `delivery`, `photos`; the menu follows `sample` in menu.json). While `preview` is
  on, every «Sample» label and every list of samples (the header's Preview line, the footer's fine print, About Us,
  Contact, llms.txt) comes from it, and the JSON-LD and llms.txt carry only confirmed facts. When the owner confirms a
  field, set it to `true` and rebuild.
- **Delivery and contact**: `delivery[].url` (the restaurant's own store page on each app), `contact.phone`,
  `contact.email`, `contact.address` (the full address, in the Contact description and llms.txt), `contact.city` (the
  hero tag and the footer's mirrored line), `contact.map_label` (the big location heading on the yellow band and
  Contact), `contact.locality` (the line under it), `contact.street_address` and `contact.locality` again (the footer's
  two address lines and the Order sheet), `contact.parking` and `contact.dine_in` (Contact), `contact.maps_url`, and
  for the JSON-LD `contact.street_address` and `contact.postal_code`.
- **Halal**: `halal.statement`, `halal.detail` and `halal.certifier` (Contact, the FAQ and llms.txt say «Halal
  certification by …»); `halal.certifier_logo` stays empty until the owner sends the certifier's logo with the issued
  certificate. The site says nothing about pork or alcohol, at the owner's request.
- Then run `python3 build.py` and the tests, and commit `content/` and `docs/` together.

## Launching

1. Replace every sample in `content/placeholders.md` with the owner's real details and set its field in `confirmed`
   to `true`; the dough-vinci.com domain and the info@dough-vinci.com mailbox must exist.
2. In `content/menu.json` set `"sample": false` (removes the sample notes and adds `hasMenu` to the JSON-LD).
3. In `content/site.json` set `"preview": false` and `"index": true` (removes `noindex`, the «Preview» mark, the
   «Sample» labels and the robots `Disallow`, adds the sitemap to robots.txt, turns on the live open-now status, and
   adds every field to the JSON-LD and llms.txt).
4. Rebuild and run the tests.
