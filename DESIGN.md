# Dough-Vinci: design direction «Codex Vivo»

The name is a pun on Leonardo da Vinci, and the site is one of his notebooks left open on a sunny kitchen counter:
clean cream pages, real food photos pasted in as studies, red-chalk construction lines, handwritten notes on leader
lines, a little mirror writing, folio numbers. **The pizza is the art, the smashburger is the engineering.** Food
leads every section; text is headlines and labels. There is no dark section anywhere.

## Type (Google Fonts, only the weights used)

| Role | Family | Weights |
|---|---|---|
| Display, prices in the sheet | Fraunces (SOFT 100, optical size auto) | 600–850, italic 500–800 |
| Interface, data, nutrition | Instrument Sans | 400–700 |
| Handwritten notes | Caveat | 600–700 |

Handwriting and mirror writing are decoration: every fact they show is also in plain text, and mirror notes are
hidden from screen readers.

## Colour

| Token | Hex | Use |
|---|---|---|
| `--paper` | `#FFF8EC` | page |
| `--paper-2` | `#FCEFD8` | book spread, footer, panels |
| `--card` | `#FFFDF8` | cards, pasted photo paper |
| `--ink` | `#2B1D14` | text (15.4:1 on paper) |
| `--ink-line` | `#4A2D1A` | drawing contours |
| `--sepia` | `#6E4529` | secondary text (7.8:1) |
| `--sanguine` | `#B8432A` | red-chalk lines, kickers, folios (5.1:1 on paper, 4.8:1 on the spread) |
| `--tomato` | `#D63A22` | buttons (white text 4.7:1), big display accents |
| `--tomato-ink` | `#B8341C` | tomato-coloured small text and stamps |
| `--basil` / `--basil-ink` | `#2F7A3A` / `#255F2D` | vegetarian, fresh (6.4:1 on the basil pill) |
| `--cheese` / `--cheese-soft` | `#F7B32B` / `#FFE3A1` | sticky notes, kcal chips, the opening pill |
| `--sky` / `--sky-ink` / `--sky-soft` | `#3F6F88` / `#2E5D73` / `#DCEAF0` | focus ring, the delivery band |
| washes | tomato, cheese, basil, rose, sky tints | one per menu category, behind the photos |

## Signature pieces

- **Hero**: a top-down margherita in a self-drawing Vitruvian circle and square (Fig. 1 · L'Arte) beside a
  smashburger frame with a height ruler and a «lace edge» tag (Fig. 2 · L'Ingegneria). On phones the food comes
  first, above the headline.
- **Book spread**: «The pizza is the art» with a sketch-to-photo wipe (a real range input: the photo of The Vitruvian,
  the pizza the drawing shows, paints in from the left as the value rises) and a golden-spiral overlay; «The smashburger is the engineering» with the exploded burger drawing inking itself, lettered a–g, and a
  taped griddle photo with a ruler («pressed flat · hot griddle»).
- **Menu**: photo cards (one 4:3 crop) on category washes; name, price, kcal whole and per slice, diet and
  allergen icons. Filters dim what does not fit with a stamp («Contains milk»), never hide it: the photo fades, the
  text stays fully readable, and in each section the dishes that fit move first. Each dish opens a sheet with the photo on construction lines, sizes, a kcal ring, a nutrition table, lettered ingredients,
  «Contains» and «May contain», and an Order bar.
- **We fly it to your door**: Leonardo's flying machine carries a pizza box across a sky wash over the four delivery
  apps and «Call for pickup». Each app tile carries its brand colour as a band and an initial. The same tiles are in
  the Order sheet.
- **Home category tiles**: pasted studies on paper with sanguine hairline frames and registration ticks; no photo
  repeats on the home page.
- **Mobile dock** (Menu, Allergens, Visit, Order): on the home page it slides in once the hero's own Order button has
  scrolled away; dish pages have their own price-and-Order bar instead.
- **Visit**: a round Imola-style map (mirrored so Grandview Park sits west of Commercial Drive) with HTML labels.

## Motion

Transform, opacity and stroke-dashoffset only. Reveals use IntersectionObserver; the gears and the flying machine
follow the scroll through CSS scroll timelines where supported and stand still elsewhere. Springs use CSS
`linear()` with a cubic-bezier fallback. The ribbons and the seal loop, so a «Pause motion» button sits beside the
ribbons and in the footer. With `prefers-reduced-motion` every piece is shown finished and still.
