# Dough-Vinci: placeholder and assumed data

Every line below is sample data written for the preview. Each one needs Mahdi to confirm it or give the real value.

## Contact and location

- Location: «Commercial Drive at Kitchener Street, Vancouver, BC», cross streets only, with no street number and no postal code, because any real number on the Drive belongs to a business that exists today (Commercial Drive chosen as Vancouver’s Little Italy; the real location is unknown). The real street address and postal code go in `contact.street_address` and `contact.postal_code` once the owner gives them.
- Phone: (604) 555-0142 (fictional 555-01 number)
- Email: hello@doughvinci.ca (domain not checked; it may not be registered or may belong to someone else)
- Google Maps link: a search for the two cross streets
- City shown as Vancouver (the brief says only the Vancouver area)

## Hours

- Monday to Thursday: 11:00 to 22:00
- Friday and Saturday: 11:00 to 23:00
- Sunday: 12:00 to 21:00
- Opening date: 2026-12-05 (`opening_date` in site.json, a sample about a month after the preview). Until that day the header and the Contact page say «Opening Dec 5». After it, while `preview` is on, the header shows no status and Contact says «See the hours»; the live «Open now · until 11 pm» state appears only once the preview is switched off. The FAQ answer «When do you open?» takes the same date.

## Ordering

- Uber Eats, DoorDash, SkipTheDishes and Fantuan links: each platform's home page, not the restaurant’s own store page (the Order sheet says so while `preview` is on)
- Pickup through the apps and by phone (assumed)
- Social media: none shown until the real handles are known

## Photos

- Every photo is a free Unsplash stock photo, by two photographers: Daniel (@unsplashbydan), who shot one wood-fired pizza and burger taphouse in Texas, and Nathan Dumlao (@nate_dumlao), whose smashburger frame matches that light and wood. They show other restaurants' food and plates, not Dough-Vinci's; every dish sheet, the footer and the Photo credits page say so, and they are placeholders until Dough-Vinci's own shoot.
- The pizzas in the photos are Neapolitan-style, hand-stretched and baked in a wood-fired oven (leopard-spotted, puffy rims), while the menu and the owner's pillar say «Flat-Rolled Pizza». The oven shot on About Us (`place-1`) shows live flames in a wood-fired oven; if Dough-Vinci's oven is not wood-fired, `place-1` comes off the site.
- Nine dishes have a photo: Mona Lisa, The Vitruvian, Beef Fennel Sausage, Mushroom & Balsamic, Double Smash, Fries, Soft Pretzels, Skillet Cheese Dip and Chocolate Cake. The other twelve are text-only until the shoot (`no_photo` in photos.json): Beef Pepperoni, Bresaola & Arugula, Hot Honey Beef Salami, The Original Smash, Spicy Smash, Veggie Burger, Garlic Knots, Caesar Salad, Tiramisù, Blood Orange Soda, Pink Lemonade and Fountain Pop.
- Bresaola & Arugula has no photo: the only stock frame of that pizza shows pale pink prosciutto, not deep-red beef bresaola.
- The shoot has one smashburger frame, a bunless close-up of two patties. The home hero shows a tight crop of its patties, lacy edges and cheese (`hero-burger`) and the menu a slightly wider crop under Double Smash (`double-smash`), never both on one page. The Double Smash is described with its toasted potato bun, which the frame does not show.
- The hero pizza (`hero-pizza`) is cropped to hide the logo printed on the cook's T-shirt.
- No photo in use shows alcohol or another venue's branding. The table spread with the shared pizzas is not used, because it shows a prosciutto pizza and two cocktails.
- The Vitruvian's photo shows pepperoni and mushrooms only. The owner's mock-up pizza also has green peppers and red onions, which no photo in the set shows, so the sample Vitruvian is described as photographed.
- Grade and crops (`treatment`, `strips`, `crop` and `strip_crop` in photos.json) are the design team's choice. The menu's pizza strip shows all four photographed pizzas as close-ups with the front of the crust at the foot of each frame, so the two overhead frames and the two angled ones read as one set.

## Brand copy

- Hero tag: the halal mark and the opening date with the street («Opening Sat, Dec 5 · Commercial Drive»), computed from `opening_date`
- Halal statement («All our meat is halal. No pork, no alcohol.»), its detail line, the halal FAQ answer and the «all halal» in the page description; the halal claim follows the owner's request to show the halal sign
- The Leonardo line («The pizza is the art. The smashburger is the engineering.»), written for the site, not from the brief. The welcome on About Us is the owner's own text, word for word.
- «Start here» on the home page: The Vitruvian, Mushroom & Balsamic, Soft Pretzels and Chocolate Cake (`signatures` in site.json)
- Order sheet line «Pickup or delivery: your app, your call.»
- Catering title and text, including “call a day ahead”

## Halal and the owner

- Halal: every meat on the menu is halal beef (beef pepperoni, beef salami, halal beef fennel sausage, beef bresaola, beef patties), and no recipe has pork, lard, gelatin or alcohol. The halal mark (`halal` in site.json) is the Arabic word حلال in a ring on a green disc with the word Halal, drawn after the owner's neon sign, with no certification body's logo.
- No alcohol: the claim also needs the suppliers to confirm the vanilla in the chocolate cake and the tiramisù (vanilla extract is usually made with alcohol), the fountain-pop flavours, the grainy and Dijon mustards (see Menu: general) and the balsamic glaze. While `preview` is on, the footer, About Us and the Contact halal block mark the halal details as samples.
- Halal certifier: unknown. Its name goes in `halal.certifier` (the Contact page then says «Certified by …») and its logo on the site once the owner names it.
- Cheese rennet: the mozzarella, cheddar, pepper jack and American cheese are assumed made with microbial rennet (the vegetarian marks on Mona Lisa, the Veggie Burger and the Skillet Cheese Dip rest on that), cream cheese and mascarpone are acid-set with no rennet, and only the parmesan is assumed animal rennet. The supplier must confirm each, for the vegetarian marks and for the certifier.
- Parmesan rennet: the parmesan on Bresaola & Arugula, the Garlic Knots and the Caesar is assumed made with animal rennet; whether the certifier accepts it is unknown. A microbial-rennet grana, as on Mushroom & Balsamic, would also make the Garlic Knots vegetarian.
- Owner's earlier restaurant: the owner ran a restaurant on Davie Street in downtown Vancouver before. Its name, and whether the site mentions it, are unknown.

## Menu: general

- Every dish and every recipe below is invented and fitted to the stock photos. Two names keep a Leonardo nod (Mona Lisa, The Vitruvian); every other name is a plain dish name.
- Category taglines; menu.json also keeps an Italian name for each category, which the site does not show
- Pizza sizes 12" and 16"; nutrition is given for a whole 12" pizza of 6 slices
- Burger bun: toasted potato bun (assumed contains wheat, milk, egg, soy; no sesame, but may contain sesame from the bakery)
- House sauce: mayonnaise-based, with egg and mustard (assumed)
- Mustard: the grainy mustard on the Soft Pretzels and the Dijon in the Caesar dressing are made without wine (assumed; many grainy and Dijon mustards contain white wine, so the supplier must confirm)
- Creamy slaw on The Original Smash: cabbage, mayonnaise and cider vinegar, with no mustard (assumed)
- Lettuce-wrap option on the beef smashburgers, marked gluten-free option (assumed offered)
- Caesar without croutons as a gluten-free option (assumed)
- Shared fryer: fries and the skillet's fried dough chips may contain wheat, milk, egg (assumed)
- Kitchen-wide allergen note: traces of wheat, milk, egg, soy, sesame, mustard and fish possible. No sample dish contains tree nuts or peanuts.
- The cake's chocolate contains soy lecithin (assumed); Tiramisù made with no liqueur, as the menu and the halal FAQ say
- The balsamic glaze contains sulphites (declared on Mushroom & Balsamic)
- Mushroom & Balsamic is vegetarian only because its grated hard cheese is a vegetarian grana made with microbial rennet (assumed). Fries are marked vegetarian, not vegan, because the shared fryer may add milk and egg; Bresaola & Arugula, Garlic Knots and the Caesar carry no vegetarian mark because parmesan is usually made with animal rennet
- Soft Pretzels: the creamy white dip in the photo is described as garlic aioli and the grainy one as grainy mustard (assumed from colour)
- Skillet Cheese Dip: the photo shows a smooth paprika-dusted cheese dip, so the sample recipe is a three-cheese dip, not spinach and artichoke
- All calorie and nutrition figures are estimates from typical published values for comparable dishes, not lab-tested
- Badges: Signature (The Vitruvian, The Original Smash); no «Owner's pick» or «New» until the owner chooses them


## Menu: Pizza

- Category tagline: “Flat-rolled and baked hot.”
- Mona Lisa: recipe (flat-rolled dough; San Marzano-style tomato sauce; fresh mozzarella; basil; extra-virgin olive oil); price 12" $18, 16" $26; 1600 kcal per 12-inch pizza, whole (6 slices); protein 68 g, carbs 200 g, fat 56 g, sodium 3200 mg; allergens wheat, milk, diet: vegetarian; photo
- The Vitruvian: recipe (flat-rolled dough; tomato sauce; fresh mozzarella; beef pepperoni; roasted mushrooms); price 12" $22, 16" $31; 1860 kcal per 12-inch pizza, whole (6 slices); protein 80 g, carbs 204 g, fat 80 g, sodium 4200 mg; allergens wheat, milk; photo
- Beef Pepperoni: recipe (flat-rolled dough; tomato sauce; mozzarella; double cup-and-char beef pepperoni; oregano); price 12" $21, 16" $30; 2100 kcal per 12-inch pizza, whole (6 slices); protein 92 g, carbs 198 g, fat 104 g, sodium 5200 mg; allergens wheat, milk; text-only (no photo)
- Beef Fennel Sausage: recipe (flat-rolled dough; tomato sauce; fresh mozzarella; smoked halal beef fennel sausage); price 12" $22, 16" $31; 2040 kcal per 12-inch pizza, whole (6 slices); protein 92 g, carbs 202 g, fat 96 g, sodium 4400 mg; allergens wheat, milk; photo
- Mushroom & Balsamic: recipe (flat-rolled dough; garlic olive-oil base; mozzarella; roasted mushrooms; green olives; balsamic glaze; vegetarian grana (microbial rennet)); price 12" $21, 16" $29; 1760 kcal per 12-inch pizza, whole (6 slices); protein 72 g, carbs 214 g, fat 68 g, sodium 3700 mg; allergens wheat, milk, sulphites, diet: vegetarian; photo
- Bresaola & Arugula: recipe (flat-rolled dough; garlic olive-oil base; mozzarella; beef bresaola; baby arugula; shaved parmesan; extra-virgin olive oil); price 12" $23, 16" $32; 1740 kcal per 12-inch pizza, whole (6 slices); protein 94 g, carbs 192 g, fat 66 g, sodium 4200 mg; allergens wheat, milk; text-only (no photo)
- Hot Honey Beef Salami: recipe (flat-rolled dough; tomato sauce; mozzarella; spicy beef salami; jalapeño; chili flakes; hot honey); price 12" $23, 16" $32; 1980 kcal per 12-inch pizza, whole (6 slices); protein 86 g, carbs 220 g, fat 84 g, sodium 4800 mg; allergens wheat, milk, diet: spicy; text-only (no photo)

## Menu: Smashburgers

- Category tagline: “Smashed thin for crispy edges.”
- The Original Smash: recipe (toasted potato bun; smashed beef patty; creamy slaw (cabbage, mayonnaise, cider vinegar); pickled red onion; dill pickle chips); price Regular $12; 570 kcal per 1 burger, without sides; protein 26 g, carbs 39 g, fat 34 g, sodium 1150 mg; allergens wheat, milk, egg, soy, may contain sesame, diet: gluten-free-option; text-only (no photo)
- Double Smash: recipe (toasted potato bun; 2 smashed beef patties; 2 slices American cheese; pickles; diced onion; house sauce); price Regular $16; 860 kcal per 1 burger, without sides; protein 50 g, carbs 37 g, fat 56 g, sodium 1650 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: gluten-free-option; photo (Nathan Dumlao's frame)
- Spicy Smash: recipe (toasted potato bun; 2 smashed beef patties; pepper jack; pickled jalapeño; shredded lettuce; chipotle mayo); price Regular $18; 910 kcal per 1 burger, without sides; protein 51 g, carbs 39 g, fat 61 g, sodium 1750 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: spicy, gluten-free-option; text-only (no photo)
- Veggie Burger: recipe (toasted potato bun; crispy vegetable patty (chickpea, carrot, peas, breadcrumb); cheddar; lettuce; tomato; pickles; house sauce); price Regular $15; 640 kcal per 1 burger, without sides; protein 20 g, carbs 66 g, fat 33 g, sodium 1300 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: vegetarian; text-only (no photo)

## Menu: Sides

- Category tagline: “Golden, crisp and made for sharing.”
- Fries: recipe (skinny-cut skin-on potatoes; canola oil; sea salt); price Regular $6; 420 kcal per regular portion (about 170 g); protein 5 g, carbs 54 g, fat 20 g, sodium 520 mg; allergens none, may contain wheat, milk, egg, diet: vegetarian; photo
- Soft Pretzels: recipe (pretzel dough; butter; coarse salt; grainy mustard (made without wine); garlic aioli); price Regular $9; 860 kcal per 4 pretzel sticks with 2 dips, for sharing; protein 22 g, carbs 130 g, fat 28 g, sodium 2600 mg; allergens wheat, milk, egg, mustard, diet: vegetarian; photo
- Skillet Cheese Dip: recipe (cream cheese; mozzarella; white cheddar; garlic; smoked paprika; microgreens; fried pizza-dough chips); price Regular $11; 750 kcal per 1 skillet with dough chips, for sharing; protein 26 g, carbs 60 g, fat 45 g, sodium 1350 mg; allergens wheat, milk, may contain egg, diet: vegetarian; photo
- Garlic Knots: recipe (pizza dough; garlic butter; parmesan; parsley; marinara); price Regular $8; 560 kcal per 6 knots with marinara; protein 16 g, carbs 74 g, fat 22 g, sodium 1100 mg; allergens wheat, milk; text-only (no photo)
- Caesar Salad: recipe (romaine; parmesan; garlic croutons; Caesar dressing (anchovy, egg yolk, Dijon mustard made without wine); lemon); price Regular $11; 380 kcal per full salad; protein 11 g, carbs 18 g, fat 30 g, sodium 820 mg; allergens wheat, milk, egg, fish, mustard, diet: gluten-free-option; text-only (no photo)

## Menu: Desserts

- Category tagline: “Something sweet to finish.”
- Chocolate Cake: recipe (chocolate sponge (flour, cocoa, egg, butter, sugar); dark chocolate ganache; whipped cream; mint); price Regular $8; 570 kcal per 1 slice; protein 7 g, carbs 64 g, fat 32 g, sodium 360 mg; allergens wheat, milk, egg, soy, diet: vegetarian; photo
- Tiramisù: recipe (ladyfingers; mascarpone; espresso (no liqueur); egg; sugar; cocoa); price Regular $8; 450 kcal per 1 slice; protein 8 g, carbs 42 g, fat 28 g, sodium 120 mg; allergens wheat, milk, egg, diet: vegetarian; text-only (no photo)

## Menu: Drinks

- Category tagline: “Ice-cold sodas and fresh lemonade.”
- Blood Orange Soda: recipe (sparkling water; blood-orange syrup; blood-orange wheel; ice); price 16 oz $5; 180 kcal per 16 oz; protein 0 g, carbs 45 g, fat 0 g, sodium 30 mg; allergens none, diet: vegan; text-only (no photo)
- Pink Lemonade: recipe (fresh lemon juice; cane sugar; raspberry purée; water; crushed ice; lemon peel); price 16 oz $5; 210 kcal per 16 oz; protein 0 g, carbs 54 g, fat 0 g, sodium 15 mg; allergens none, diet: vegan; text-only (no photo)
- Fountain Pop: recipe (cola, diet cola, lemon-lime or orange; the flavours depend on the fountain supplier); price 16 oz $3; 190 kcal per 16 oz regular cola (diet: 0 kcal); protein 0 g, carbs 48 g, fat 0 g, sodium 45 mg; allergens none, diet: vegan; text-only (no photo)

## Combos

- Smash Combo: The Original Smash, Fries, Fountain Pop for $18
- Pizza & Burger for Two: Any 12" pizza, Any smashburger, Fries, 2 Fountain Pops for $40 (below the cheapest choices bought separately, $42)
- Family Meal: Two 16" pizzas, Garlic Knots, Caesar Salad for $68

## FAQ answers

- How do I order delivery? Find us on Uber Eats, DoorDash, SkipTheDishes or Fantuan. We don’t take payment on this site.
- Can I pick up my order? Yes. Choose pickup in any of the delivery apps, or call us and collect it at the counter.
- Is your food halal? Yes. All our meat is halal, and we use no pork and no alcohol. Our pepperoni, salami, sausage and bresaola are beef, and our tiramisù is made without liqueur.
- Do you have vegetarian options? Yes: the Mona Lisa and Mushroom & Balsamic pizzas, the Veggie Burger, most sides and both desserts.
- How do I check allergens? Every dish lists its allergens and calories. Our kitchen is shared, so tell us about severe allergies.
- Can you handle large orders? Yes. Call us a day ahead for office lunches, parties and team events.
- When do you open? We plan to open on Saturday, December 5 (from `opening_date`). The date is confirmed here and on the delivery apps before the first order.
