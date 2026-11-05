# Dough-Vinci: design direction «Nero»

A pizzeria at night. A warm black ground, cream type, tomato-red blocks, heavy condensed capitals, and the food in
warm, single-shoot photos running edge to edge. Colour comes from the food and from full-width flat bands, one
saturated band per screen. The Leonardo nod is one real drawing and one line; the rest is plain, grown-up and quick to
read.

## Type (Google Fonts, only what is used)

| Role | Family | Use |
|---|---|---|
| Display, prices, buttons, the wordmark | Archivo, width 62, weight 800–900, capitals | headings, dish names, prices with a full-size `$` and tabular figures |
| Text | Archivo, width 100, weight 400–700 | everything a customer reads at length, in sentence case |
| One phrase | Instrument Serif italic | «Made with Passion.» only (the sheet asks Google for those glyphs only) |
| The halal mark | Noto Kufi Arabic 700 | «حلال» only |

No small tracked capitals, no handwriting, no script. Meta text on black is cream at 82% or more and at least 15 px on
phones.

## Colour

| Token | Hex | Use |
|---|---|---|
| `--nero` | `#121010` | the ground |
| `--panna` | `#F5EBDA` | type on black (15.9:1), the price boards, the dish sheet, the Leonardo panel |
| `--panna-80` | cream at 82% | meta text on black (10.9:1) |
| `--rosso` | `#C8261B` | the Order band, Order buttons, the hero rule; cream on it 4.8:1 |
| `--rosso-ink` | `#B3241A` | prices on cream (5.6:1); red is only prices and Order |
| `--ink` / `--ink-2` | `#1A1412` / `#4F463F` | text on cream (15.4:1) and meta on cream (7.8:1) |
| `--basil` | `#286E37` | the Combos band (cream on it 5.3:1), the halal disc |
| `--basil-ink` | `#1F5A2C` | «Vegetarian» on cream (7:1) |
| `--cheese` | `#F2B632` | the halal and location band, sample warnings (ink on it 10:1) |
| tricolour | `#2F8A45`, cream, `#C8261B` | flat, straight, square-ended bands: under the wordmark and at the foot of the hero |

No gold anywhere, no gradients but the photos' own light, no pastels.

## Pieces

- **Header**: the wordmark «DOUGH-VINCI» over «Pizza & Burger» and a short tricolour; Menu, About Us, Contact and the
  live status beside Contact («Opening early Dec», later «Open now · until 10 pm»); a red «Order Now» with a line scooter.
  On phones it is two rows, and a sticky Order bar slides up once the hero has gone, while the header button steps
  aside; on wider screens the header button stays at all times.
- **Hero**: the halal mark and the opening with the city («Opening early December · Richmond», its Sample label kept
  beside it), «REAL PIZZA. REAL SMASH BURGER.» (two lines sized to the column; «Smash Burger» is the owner's wording
  for the headline, while the menu section, the photo label and his pillar say «Smashburgers»), a
  straight red rule, «Made with Passion.», the owner's sub-line and his two buttons on black at left; the pizza and the
  smashburger side by side at right, each labelled and linked to its menu section, with the tricolour at their foot. The
  smashburger tile is a close crop of the patties, their lacy edge and the cheese. No scrim on the photos.
- **Order band**: full-width red, «ORDER», the four apps by name as text, Call for pickup and the halal mark. Every page
  has it (it is where Order links land without JavaScript); the Order sheet repeats it with Eat in and «No payment on
  this site», and fits a laptop screen of 800 px without scrolling.
- **Start here**: four dishes with photos at one 4:5 crop. **Combos**: the basil band, each combo linked to its place
  on the menu. **Leonardo**: Codex Atlanticus f. 29r in its own ink on a cream panel with its credit, a supporting
  figure about a third of the width (two thirds of a phone) beside the larger line «The pizza is the art. The
  smashburger is the engineering.»; one per page at most (Home and About Us). **Halal and location**: the cheese band,
  in ink, the halal statement, then the address as its big heading, the city and postal code, and the opening.
- **Menu**: a one-line head, so the pizzas show on the first screen, then a sticky bar of sections (Pizza,
  Smashburgers, Pasta, Sides, Desserts, Drinks, Combos) and three filters
  (Vegetarian, Spicy, Gluten-free option). Each section has a photo strip of its own photographed dishes only (one
  ratio and one composition per strip; a section's single photo fills the width; a small section's only photo sits
  beside its board), then the cream price board: name, leader dots, prices under 12″ and 16″ heads, one
  line of ingredients, then calories with what they are for, allergens and diet as text. Text-only dishes are simply
  rows on the board. A diet mark never breaks, and no meta line starts with its «·». While a filter is on, an emptied column goes and the counts say how many dishes show.
- **Dish sheet**: a drawer from the right (full screen on phones, photo on top): sizes and prices with leader dots, a
  big Order button under them, ingredients, a five-cell nutrition grid with its basis, Contains and May contain, the
  sample and photo notes. The same article is each dish's own page.
- **Contact**: the address as its heading, the city and postal code, the parking and eat-in lines, the opening, the
  hours table, Directions, Call and email (a Sample label sits inside its button); the cheese band in three columns on
  wide screens: the halal mark, the statement, then the certification and the detail; the questions.
- **Footer**: «GREAT FOOD. GREAT TASTE. EVERY BITE.», the order, location and page lists (the address on two lines,
  «No. 1» and the postal code never split, the email breaking only after its @; under 600 px «Find us» takes the
  full row first), the halal mark and statement,
  the huge wordmark, the preview and photo notes (linking the Photo credits page), and one mirrored line, «Dough-Vinci,
  Richmond» (aria-hidden), the only mirror writing.

## Photos

One grade on every photo (`saturate(1.06) contrast(1.04)`, from `photos.json`), full saturation, no dark overlay. One
crop ratio per grid. Start here shows the overhead pizzas whole; the menu's pizza strip shows all four photographed
pizzas as close-ups, each with the front of its crust at the foot of the frame (`strip_crop`), so the overhead and the
angled frames read as one set; the hero pizza is the 3/4 frame. A phone loads the crop its box shows (4:3 where the
photo sits on top). No photo appears twice on one page (the hero burger and the double-smash crop are one frame), no
frame shows alcohol or another venue's branding, and dishes without a true photo stay text-only. Alt text says what
the frame shows and never names a meat nobody can verify in a stock photo.

## Motion and access

Fades, slide-ups and one colour wipe (the Order band), 400 to 700 ms with an ease-out and no overshoot; sheets slide
in. Everything stops under `prefers-reduced-motion`, and if the script never runs nothing stays hidden. Square corners
everywhere but the round halal disc. Visible focus in the text colour of its ground (on a photo, a cream ring with a
black halo drawn above it), never under the sticky header, section bar, table head or phone Order bar; on phones the
focus order follows the order on screen. Real links and buttons, native modal dialogs that trap focus and return it,
targets of 24 px or more, WCAG 2.2 AA contrast throughout, a forced-colours mode that keeps the close cross, the pressed
filter and the current page visible, and no sideways scrolling at 320 px, even with larger text spacing. Until Archivo
arrives the type falls back to narrow and plain faces already on the device, scaled to its width, so nothing jumps
when it swaps.
