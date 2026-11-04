# Dough-Vinci Pizza & Burger

The website of Dough-Vinci, a pizza and smashburger restaurant opening on Commercial Drive, Vancouver. The design,
«Codex Vivo» (Leonardo's notebook: the pizza is the art, the smashburger is the engineering), is in
[DESIGN.md](DESIGN.md).

**Preview:** https://rajool.github.io/dough-vinci/ (every page carries `noindex` and a small «Preview» mark while
`preview` is on; the menu, prices, calories, allergens, address and phone are samples, listed in
[content/placeholders.md](content/placeholders.md)).

## How it is built

Plain HTML, CSS and JavaScript, rendered by a Python standard-library build. No framework, no package, no
third-party script; fonts from Google Fonts, photos by URL from images.unsplash.com.

    python3 build.py                          # content/ + src/ -> docs/ (the GitHub Pages folder)
    python3 -m unittest discover -s tests     # builds, then checks the pages
    python3 tools/render_images.py            # share image and home-screen icon into src/img/ (needs Chrome)

Never edit `docs/` by hand: change `content/` or `src/`, then rebuild. Files the build no longer writes are moved
to the Trash.

| Path | What |
|---|---|
| `content/site.json` | name, copy, opening date, contact, hours, delivery links, FAQ, catering, signature dishes, `preview` and `index` switches |
| `content/menu.json` | categories, dishes (ingredients, kcal, nutrition, allergens, may-contain, diet, prices, badges), combos, allergen note, `sample` switch |
| `content/photos.json` | every Unsplash photo with alt text, author and an alternate; `use` picks the alternate, `crop` sets the focal point |
| `src/templates/` | page skeletons with `{{placeholders}}` |
| `src/css/site.css`, `src/js/site.js` | the whole design system and the enhancements (dialogs, filters, open-now, wipe, inking) |
| `src/art/` | the pizza and burger studies; `src/art/new/` holds the illustrator's map, flying machine, gears, mark and icons |
| `docs/` | the built site: Home, Menu (+ one page per dish), Allergens & nutrition, Visit, About, 404 |

## Editing the content

- **A dish**: edit it in `content/menu.json` (name, `short`, `ingredients`, `kcal`, `nutrition`, `allergens`,
  `may_contain`, `diet`, `prices`, optional `badge`). Its photo is the entry with the same `key` in
  `content/photos.json`; every dish needs one, with `alt` text.
- **A photo**: change `url`, `page`, `author` and `alt` in `content/photos.json`, or set `"use"` to `"alternate"`, to
  another key, or to `"key.alternate"` / `"key.primary"` (an alternate needs its own `alt`). `"crop": [x, y, zoom]`
  moves the crop. `home_tiles` in `content/site.json` picks the category tiles' photos so no photo repeats on the
  home page (a test checks it).
- **Hours**: `"hours"` in `content/site.json`, in Vancouver time. The pills and the hours table follow them.
- **Opening date**: `"opening_date": "YYYY-MM-DD"`. Until that day the pills say «Opening Dec 5»; after it they say
  «Hours» while `preview` is on, and show the live «Open now · until 10 pm» state once it is off. `{opening}` in a FAQ
  answer becomes the date. Leave it empty once open.
- **Delivery and contact**: `delivery[].url` (the restaurant's own store page on each app) and `delivery[].color`
  (the tile's band), `contact.phone`, `contact.address` (shown as written), `contact.street` (the pills),
  `contact.map_label` (the map's sticky note), `contact.neighbourhood`, `contact.maps_url`, and for the JSON-LD after
  launch `contact.street_address` and `contact.postal_code`.
- Then run `python3 build.py`, and commit `content/` and `docs/` together.

## Launching

1. Replace every sample in `content/placeholders.md` with the owner's real details (until then the location is cross
   streets only, because any real number on the Drive belongs to a business that exists today).
2. In `content/menu.json` set `"sample": false` (removes the sample notes and adds `hasMenu` to the JSON-LD).
3. In `content/site.json` set `"preview": false` and `"index": true` (removes `noindex`, the «Preview» mark and the
   robots `Disallow`, adds the sitemap to robots.txt, turns on the live open-now pill, and adds the phone, hours and
   street address to the JSON-LD).
4. Rebuild and run the tests.
