# Dough-Vinci: placeholder and assumed data

Every line below is sample data written for the preview. Each one needs Mahdi to confirm it or give the real value.

## Contact and location

- Location: «Commercial Drive at Kitchener Street, Vancouver, BC», cross streets only, with no street number and no postal code, because any real number on the Drive belongs to a business that exists today (Commercial Drive chosen as Vancouver’s Little Italy; the real location is unknown). Kitchener is the corner the map's pin is drawn at. The real street address and postal code go in `contact.street_address` and `contact.postal_code` once the owner gives them.
- Phone: (604) 555-0142 (fictional 555-01 number)
- Email: hello@doughvinci.ca (domain not checked; it may not be registered or may belong to someone else)
- Google Maps link: a search for the two cross streets
- Map: hand-drawn and not to scale; the drawing is shown mirrored so Grandview Park sits on the west side of Commercial Drive, as it does in reality
- City shown as Vancouver (the brief says only the Vancouver area)

## Hours

- Monday to Thursday: 11:00 to 22:00
- Friday and Saturday: 11:00 to 23:00
- Sunday: 12:00 to 21:00
- Opening date: 2026-12-05 (`opening_date` in site.json, a sample about a month after the preview; the pills say «Opening Dec 5» until that day, then «Hours» while `preview` is on, and the live open-now state only once the preview is switched off). The FAQ answer «When do you open?» takes the same date.

## Ordering

- Uber Eats link: platform home page, not the restaurant’s own store page
- DoorDash link: platform home page, not the restaurant’s own store page
- SkipTheDishes link: platform home page, not the restaurant’s own store page
- Fantuan link: platform home page, not the restaurant’s own store page
- Delivery tile colours (`delivery[].color`): approximations of each app's brand colour, not checked against their brand guides
- Pickup through the apps and by phone (assumed)
- Social media: none listed until the real handles are known

## Brand copy

- Hero kicker: the opening date pill («Opening Sat, Dec 5 · Commercial Drive»), computed from `opening_date`
- About title and lines (the art and engineering idea; written for the site, not from the brief). The welcome card beside them is the owner's own text, word for word.
- Signature notes on the home page («cupped & charred», «lace edge, crispy», «hot honey!», «always smiling») and which four dishes are the signature studies
- Photos: stock images from Unsplash, not Dough-Vinci's dishes; the footer and every dish sheet say so
- Catering title and text, including “call a day ahead”

## Menu: general

- Every dish name (Leonardo puns) and every recipe below is invented
- Pizza sizes 12" and 16"; nutrition is given for a whole 12" pizza of 6 slices
- Burger bun: toasted potato bun (assumed contains wheat, milk, egg, soy; no sesame)
- House sauce: mayonnaise-based, with egg and mustard (assumed)
- Lettuce-wrap option on the beef smashburgers, marked gluten-free option (assumed offered)
- Caesar without croutons as a gluten-free option (assumed)
- Shared fryer: fries and onion rings may contain wheat, milk, egg (assumed)
- Kitchen-wide allergen note: traces of wheat, milk, egg, soy, sesame, mustard, fish and tree nuts possible
- Tiramisù made alcohol-free (not stated on the site until confirmed); cannoli shells contain egg and the chocolate contains soy (assumed)
- Fries and onion rings are marked vegetarian, not vegan, because the shared fryer may add milk and egg; Gioconda Bianca and Garlic Knots carry no vegetarian mark because parmesan is usually made with animal rennet
- All calorie and nutrition figures are estimates from typical published values for comparable dishes, not lab-tested
- Badges: Signature (The Vitruvian, Double Smash); no «Owner's pick» or «New» until the owner chooses them

## Menu: Pizza (L’Arte)

- Category tagline: “Rolled flat. Baked into a masterpiece.”
- Mona Lisa: recipe (flat-rolled dough; San Marzano-style tomato sauce; fresh mozzarella; basil; extra-virgin olive oil); price 12" $18, 16" $26; 1600 kcal per 12-inch pizza, whole (6 slices); protein 68 g, carbs 200 g, fat 56 g, sodium 3200 mg; allergens wheat, milk, diet: vegetarian
- The Vitruvian: recipe (flat-rolled dough; tomato sauce; mozzarella; pepperoni; mushrooms; green pepper; red onion); price 12" $22, 16" $31; 1840 kcal per 12-inch pizza, whole (6 slices); protein 80 g, carbs 206 g, fat 76 g, sodium 4300 mg; allergens wheat, milk
- Pepperoni Codex: recipe (flat-rolled dough; tomato sauce; mozzarella; double cup-and-char pepperoni; oregano); price 12" $21, 16" $30; 2100 kcal per 12-inch pizza, whole (6 slices); protein 92 g, carbs 198 g, fat 104 g, sodium 5200 mg; allergens wheat, milk
- Sfumato BBQ: recipe (flat-rolled dough; smoky BBQ sauce; mozzarella; roasted chicken; red onion; cilantro); price 12" $23, 16" $32; 1900 kcal per 12-inch pizza, whole (6 slices); protein 104 g, carbs 236 g, fat 58 g, sodium 4400 mg; allergens wheat, milk, mustard, sulphites
- Il Giardino: recipe (flat-rolled dough; tomato sauce; mozzarella; mushrooms; green pepper; red onion; black olives; cherry tomatoes; baby spinach); price 12" $21, 16" $29; 1640 kcal per 12-inch pizza, whole (6 slices); protein 66 g, carbs 210 g, fat 58 g, sodium 3500 mg; allergens wheat, milk, diet: vegetarian
- Flying Machine: recipe (flat-rolled dough; tomato sauce; mozzarella; spicy salami; jalapeño; chili flakes; hot honey); price 12" $23, 16" $32; 1980 kcal per 12-inch pizza, whole (6 slices); protein 86 g, carbs 220 g, fat 84 g, sodium 4800 mg; allergens wheat, milk, diet: spicy
- Gioconda Bianca: recipe (flat-rolled dough; garlic olive-oil base; mozzarella; ricotta; baby spinach; roasted garlic; parmesan; black pepper); price 12" $22, 16" $31; 1860 kcal per 12-inch pizza, whole (6 slices); protein 88 g, carbs 196 g, fat 80 g, sodium 3600 mg; allergens wheat, milk

## Menu: Smashburgers (L’Ingegneria)

- Category tagline: “Smashed thin. Engineered for crispy edges.”
- The Original Smash: recipe (toasted potato bun; smashed beef patty; American cheese; pickles; diced onion; house sauce); price Regular $12; 560 kcal per 1 burger, without sides; protein 29 g, carbs 36 g, fat 33 g, sodium 1150 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: gluten-free-option
- Double Smash: recipe (toasted potato bun; 2 smashed beef patties; 2 slices American cheese; pickles; diced onion; house sauce); price Regular $16; 860 kcal per 1 burger, without sides; protein 50 g, carbs 37 g, fat 56 g, sodium 1650 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: gluten-free-option
- The Inventor: recipe (toasted potato bun; 2 smashed beef patties; aged cheddar; caramelized onion; garlic aioli); price Regular $18; 940 kcal per 1 burger, without sides; protein 52 g, carbs 42 g, fat 62 g, sodium 1500 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: gluten-free-option
- Codex Inferno: recipe (toasted potato bun; 2 smashed beef patties; pepper jack; pickled jalapeño; shredded lettuce; chipotle mayo); price Regular $18; 910 kcal per 1 burger, without sides; protein 51 g, carbs 39 g, fat 61 g, sodium 1750 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: spicy, gluten-free-option
- Il Verde: recipe (toasted potato bun; crispy vegetable patty (chickpea, carrot, peas, breadcrumb); cheddar; lettuce; tomato; pickles; house sauce); price Regular $15; 640 kcal per 1 burger, without sides; protein 20 g, carbs 66 g, fat 33 g, sodium 1300 mg; allergens wheat, milk, egg, soy, mustard, may contain sesame, diet: vegetarian

## Menu: Sides (I Contorni)

- Category tagline: “Golden, crisp and made for sharing.”
- Golden Ratio Fries: recipe (skin-on potatoes; canola oil; sea salt); price Regular $6; 420 kcal per regular portion (about 170 g); protein 5 g, carbs 54 g, fat 20 g, sodium 520 mg; allergens none, may contain wheat, milk, egg, diet: vegetarian
- Garlic Knots: recipe (pizza dough; garlic butter; parmesan; parsley; marinara); price Regular $8; 560 kcal per 6 knots with marinara; protein 16 g, carbs 74 g, fat 22 g, sodium 1100 mg; allergens wheat, milk
- Orbit Onion Rings: recipe (sweet onion; wheat-flour batter; canola oil; sea salt); price Regular $8; 480 kcal per regular portion (about 8 rings); protein 6 g, carbs 52 g, fat 28 g, sodium 780 mg; allergens wheat, may contain milk, egg, diet: vegetarian
- Mozzarella Sticks: recipe (mozzarella; seasoned breadcrumbs; egg wash; marinara); price Regular $10; 620 kcal per 6 sticks with marinara; protein 28 g, carbs 48 g, fat 35 g, sodium 1400 mg; allergens wheat, milk, egg, diet: vegetarian
- Codex Caesar: recipe (romaine; parmesan; garlic croutons; Caesar dressing (anchovy, egg yolk, Dijon); lemon); price Regular $11; 380 kcal per full salad; protein 11 g, carbs 18 g, fat 30 g, sodium 820 mg; allergens wheat, milk, egg, fish, mustard, diet: gluten-free-option

## Menu: Desserts (I Dolci)

- Category tagline: “The final brushstroke.”
- Tiramisù: recipe (ladyfingers; mascarpone; espresso; egg; sugar; cocoa); price Regular $8; 450 kcal per 1 slice; protein 8 g, carbs 42 g, fat 28 g, sodium 120 mg; allergens wheat, milk, egg, diet: vegetarian
- Cannoli: recipe (fried pastry shell; sweetened ricotta; chocolate chips; pistachio; icing sugar); price Regular $7; 520 kcal per 2 cannoli; protein 14 g, carbs 56 g, fat 27 g, sodium 160 mg; allergens wheat, milk, egg, soy, treenut, diet: vegetarian

## Menu: Drinks (Le Bevande)

- Category tagline: “Cold, fizzy, freshly squeezed.”
- Italian Soda: recipe (sparkling water; fruit syrup (blood orange or raspberry); ice); price 16 oz $5; 180 kcal per 16 oz; protein 0 g, carbs 45 g, fat 0 g, sodium 30 mg; allergens none, diet: vegan
- House Lemonade: recipe (fresh lemon juice; cane sugar; water; mint); price 16 oz $5; 200 kcal per 16 oz; protein 0 g, carbs 52 g, fat 0 g, sodium 15 mg; allergens none, diet: vegan
- Fountain Pop: recipe (cola, diet cola, lemon-lime or root beer); price 16 oz $3; 190 kcal per 16 oz regular cola (diet: 0 kcal); protein 0 g, carbs 48 g, fat 0 g, sodium 45 mg; allergens none, diet: vegan

## Combos

- The Smash Study: Double Smash, Golden Ratio Fries, Fountain Pop for $21
- Bottega for Two: Any 12" pizza, Any smashburger, Golden Ratio Fries, 2 Fountain Pops for $44
- La Famiglia: Two 16" pizzas, Garlic Knots, Codex Caesar for $68

## FAQ answers

- How do I order delivery? Find us on Uber Eats, DoorDash, SkipTheDishes or Fantuan. We don’t take payment on this site.
- Can I pick up my order? Yes. Choose pickup in any of the delivery apps, or call us and collect it at the counter.
- Do you have vegetarian options? Yes: the Mona Lisa and Il Giardino pizzas, the Il Verde burger, and most sides and desserts.
- How do I check allergens? Every dish lists its allergens and calories. Our kitchen is shared, so tell us about severe allergies.
- Can you handle large orders? Yes. Call us a day ahead for office lunches, parties and team events.
- When do you open? We plan to open on Saturday, December 5 (from `opening_date`). The date is confirmed here and on the delivery apps before the first order.
