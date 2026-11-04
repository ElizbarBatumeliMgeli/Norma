"""The checks NORMA makes: requirements of Government of Georgia Resolution №41 (28 January 2016).

Each rule states the requirement as it stands after the amendments in data/regulation/amendments.
`quote` is a verbatim passage: test_rulebook.py fails if it is not in the regulation or the
amendment named by `source`. The model picks rules by id, so a clause number or a quote in a
report always comes from this file, never from the model.

Requirements here are a selection that can be checked on drawings, not the whole regulation.
"""

CATEGORIES = (
    # key, Georgian, English, chapters of the regulation
    ('scope', 'დანიშნულება და სიმაღლე', 'Use & height', '1–3'),
    ('egress', 'გასასვლელი საშუალებები', 'Means of egress', '10'),
    ('fire_systems', 'სახანძრო სისტემები', 'Fire protection systems', '4, 9'),
    ('fire_resistance', 'ცეცხლმედეგობა', 'Fire resistance', '7, 10'),
    ('accessibility', 'მისაწვდომობა', 'Accessibility', '10, 11'),
    ('interior', 'შიგა გარემო', 'Interior environment', '12'),
)

BASE = '2016'


def rule(id, category, ka, en, req_ka, req_en, quote, source=BASE, check=''):
    return dict(id=id, category=category, ka=ka, en=en, req_ka=req_ka, req_en=req_en, quote=quote, source=source, check=check)


RULES = (
    # ---------- Use & height ----------
    rule('Art. 2', 'scope', 'რეგულირების სფერო', 'Scope of the resolution',
         'დადგენილება ვრცელდება მხოლოდ III, IV და V კლასის შენობებზე.',
         'The resolution applies only to class III, IV and V buildings.',
         'ამ დადგენილების მოქმედება ვრცელდება მხოლოდ კანონმდებლობის შესაბამისად განსაზღვრულ III, IV და V კლასს დაქვემდებარებული შენობებისა და ნაგებობების დაგეგმარებაზე',
         check='Is the building class stated? If it is class I or II this report does not apply: say so.'),
    rule('302.1', 'scope', 'დაკავებულობის ჯგუფი', 'Occupancy classification',
         'შენობა ან მისი ნაწილები უნდა მიეკუთვნოს დაკავებულობის ჯგუფს (თვ, სქ, სგ, სმ, დსშ, დწ, სვ, სც, სწ, დს).',
         'The building or its parts must be classified into an occupancy group (თვ, სქ, სგ, სმ, დსშ, დწ, სვ, სც, სწ, დს).',
         'ნაგებობები ან მათი ნაწილები დაკავებულობის მიხედვით კლასიფიცირდება ქვემოთ ჩამოთვლილ ერთ ან მეტ ჯგუფად',
         check='Is the occupancy group stated, or clear from room names? Most other rules depend on it.'),
    rule('202', 'scope', 'მაღლივი შენობა', 'High-rise building',
         'შენობა მაღლივია, თუ დაკავებული იატაკი სახანძრო მანქანის მისადგომი უდაბლესი დონიდან 23 მ-ზე მაღლაა.',
         'A building is high-rise if an occupied floor is more than 23 m above the lowest fire-vehicle access level.',
         'მაღლივი შენობა. შენობა, რომლის დაკავებული იატაკი მდებარეობს სახანძრო მანქანის მისადგომი ყველაზე დაბალი დონიდან 23 მ-ზე ზემოთ.',
         check='Work out the top occupied floor level. Pass means the status is clear; it decides the 403 rules.'),
    rule('1004.1.2', 'scope', 'დაკავებულობის დატვირთვა', 'Occupant load',
         'დატვირთვა ითვლება ცხრილით 1004.1.2 (მაგ. საქმიანი ფართობები — 9,3 მ² მთლიანი ერთ ადამიანზე).',
         'Occupant load is calculated from table 1004.1.2 (e.g. business areas: 9.3 m² gross per person).',
         'საქმიანობის წარმოების (ბიზნეს) ფართობები',
         check='Is the occupant load stated or can it be calculated from room areas? Exit widths depend on it.'),

    # ---------- Means of egress ----------
    rule('1003.2', 'egress', 'ჭერის სიმაღლე გასასვლელზე', 'Ceiling height in egress',
         'გასასვლელი საშუალებების ჭერის სიმაღლე ≥ 2,3 მ.', 'Ceiling height of means of egress ≥ 2.3 m.',
         'გასასვლელი საშუალებების ჭერის სიმაღლე 2,3 მ-ზე ნაკლები არ უნდა იყოს.'),
    rule('1005.3.1', 'egress', 'კიბის გამტარუნარიანობა', 'Stair capacity',
         'კიბის სიგანე: 7,6 მმ ერთ დამკავებელზე.', 'Stair width: 7.6 mm per occupant.',
         'გასასვლელი საშუალებების გამტარუნარიანობის ფაქტორზე, რომელიც 7,6 მმ-ია თითო დამკავებელზე',
         check='Only if occupant load is known.'),
    rule('1005.3.2', 'egress', 'კარებისა და დერეფნების გამტარუნარიანობა', 'Door & corridor capacity',
         'სხვა კომპონენტების სიგანე: 5,1 მმ ერთ დამკავებელზე.', 'Width of other components: 5.1 mm per occupant.',
         'გამტარუნარიანობის ფაქტორზე, რომელიც თითო დამკავებელზე 5,1 მმ-ია',
         check='Only if occupant load is known.'),
    rule('1008.1.1', 'egress', 'კარის თავისუფალი სიგანე', 'Door clear width',
         'კარის თავისუფალი სიგანე ≥ 82 სმ.', 'Door clear width ≥ 82 cm.',
         'უნდა უზრუნველყოფდეს, არანაკლებ, 82 სმ თავისუფალ სიგანეს',
         check='Every door on an egress path. A nominal leaf size is not clear width.'),
    rule('1009.4', 'egress', 'კიბის სიგანე', 'Stair width',
         'კიბის თავისუფალი სიგანე ≥ 1,1 მ.', 'Stair clear width ≥ 1.1 m.',
         'თავისუფალი სიგანე არ უნდა იყოს 1.1 მ-ზე ნაკლები', source='№737 (2020)'),
    rule('1009.5', 'egress', 'კიბის გასავლელის სიმაღლე', 'Stair headroom',
         'კიბის ზემოთ თავისუფალი სიმაღლე ≥ 2,05 მ.', 'Clear headroom above stairs ≥ 2.05 m.',
         'უნდა იყოს, სულ მცირე, 2,05 მ თავისუფალი გასავლელის სიმაღლე'),
    rule('1009.7.2', 'egress', 'საფეხურის ზომები', 'Stair riser and tread',
         'საფეხურის ამაღლება 10–18 სმ, საბიჯელი ≥ 28 სმ.', 'Riser 10–18 cm, tread ≥ 28 cm.',
         'კიბის საფეხურის ამაღლება უნდა იყოს, არაუმეტეს, 18 სმ და, სულ მცირე, 10 სმ', source='№737 (2020)'),
    rule('1009.7.3', 'egress', 'მოხვევის საფეხურები', 'Winder treads',
         'გასასვლელ კიბეებზე მოხვევის საფეხურები დაუშვებელია (გამონაკლისი: საცხოვრებელი ერთეულის შიგნით).',
         'Winders are not allowed on egress stairs (except inside a dwelling unit).',
         'მოხვევის საფეხურები დაუშვებელია გასასვლელი საშუალებების გზა-კიბეებზე'),
    rule('1010.3', 'egress', 'პანდუსის დახრა', 'Ramp slope',
         'გასასვლელი პანდუსის დახრა ≤ 1:12.', 'Egress ramp slope ≤ 1:12.',
         'დახრა არ უნდა აღემატებოდეს 1 შვეულ ერთეულს 12 თარაზულ ერთეულთან', source='№737 (2020)'),
    rule('1010.5', 'egress', 'პანდუსის სვლის ამაღლება', 'Ramp rise',
         'პანდუსის ერთი სვლის ამაღლება ≤ 75 სმ.', 'Rise of one ramp run ≤ 75 cm.',
         'ნებისმიერი პანდუსის სვლის ამაღლება უნდა იყოს, არაუმეტეს, 75 სმ'),
    rule('1011.1', 'egress', 'გასასვლელის ნიშნები', 'Exit signs',
         'გასასვლელებსა და მათ კარებს უნდა ჰქონდეს გასასვლელის ნიშანი.', 'Exits and exit access doors must have exit signs.',
         'გასასვლელებსა და გასასვლელთან მისადგომის კარებს უნდა ჰქონდეს გასასვლელის აღმნიშვნელი ნიშანი',
         check='Often shown on electrical or evacuation sheets: if those are not in the file, the status is unverifiable.'),
    rule('1015.1', 'egress', 'ორი გასასვლელი სივრციდან', 'Two exits from a space',
         'ორი გასასვლელია საჭირო, თუ დატვირთვა აღემატება: თვ, სქ, სგ, სმ, სვ, დს — 49; დწ-1, დწ-3, დწ-4, სც — 10; სწ — 29.',
         'Two exits are needed above these loads: თვ, სქ, სგ, სმ, სვ, დს 49; დწ-1, დწ-3, დწ-4, სც 10; სწ 29.',
         'ნებისმიერი სივრციდან გამომავალი ორი გასასვლელის გზა-კარი ან გასასვლელთან მისადგომის გზა-კარი საჭიროა'),
    rule('1015.1.1', 'egress', 'სამი ან მეტი გასასვლელი', 'Three or more exits',
         '501–1000 დატვირთვაზე — 3 გასასვლელი, 1000-ზე მეტზე — 4.', 'Load 501–1000: 3 exits. Over 1000: 4 exits.',
         '501-დან 1000-მდე დაკავებულობის დატვირთვიან სივრცეს გასასვლელის ან გასასვლელთან მისადგომის სამი გზა-კარი უნდა ჰქონდეს'),
    rule('1015.2.1', 'egress', 'გასასვლელების დაშორება', 'Exit separation',
         'ორი გასასვლელი ერთმანეთს უნდა დაშორდეს სივრცის მაქსიმალური დიაგონალის ნახევარზე მეტით.',
         'Two exits must be apart by more than half the maximum diagonal of the area served.',
         'საერთო მაქსიმალური დიაგონალური სიგრძის ნახევარზე მეტ მანძილზე', source='№498 (2017)',
         check='The clause has exceptions (e.g. sprinklered buildings). Note them when the result depends on it.'),
    rule('1016.2', 'egress', 'სავალი მანძილი გასასვლელამდე', 'Exit access travel distance',
         'საშხეფი სისტემის გარეშე / სისტემით: თვ, სგ, სმ-1, სვ, სც, სწ-1 — 60 / 75 მ; სქ — 60 / 90 მ; სმ-2, სწ-2, დს — 90 / 120 მ.',
         'Without / with sprinklers: თვ, სგ, სმ-1, სვ, სც, სწ-1 60 / 75 m; სქ 60 / 90 m; სმ-2, სწ-2, დს 90 / 120 m.',
         'წესების ცხრილი 1016.2 ჩამოყალიბდეს შემდეგი რედაქციით', source='№498 (2017)',
         check='Other groups are in table 1016.2. Sections 402.8, 404.9, 407.4 and 1021.2 modify the distance.'),
    rule('1018.2', 'egress', 'დერეფნის სიგანე', 'Corridor width',
         'დერეფანი ≥ 1,2 მ; დატვირთვა 50-ზე ნაკლები (გარდა სც-2 მრავალბინიანი სახლის საერთო დერეფნისა) და ბინის შიგნით — 90 სმ; სგ, დატვირთვა 100+ — 1,8 მ; დწ-2 საწოლებით — 2,4 მ.',
         'Corridor ≥ 1.2 m; load under 50 (except common corridors of სც-2 apartment buildings) and inside a dwelling 90 cm; სგ with load 100+ 1.8 m; დწ-2 with beds 2.4 m.',
         'დაკავებულობის დატვირთვა 50-ზე ნაკლებია, გარდა სც-2 ჯგუფის მრავალბინიანი შენობების საერთო დერეფნებისა', source='№498 (2017)'),
    rule('1018.4', 'egress', 'ჩიხი დერეფანში', 'Dead-end corridors',
         'ჩიხი ≤ 6,0 მ; ავტოსაშხეფი სისტემით (სქ, სგ, სმ, დწ-1, სვ, სც-1, სც-2, სც-4, დს) ≤ 15 მ; შეზღუდვა არ არის, თუ სიგრძე ≤ 2,5 × უმცირესი სიგანე.',
         'Dead end ≤ 6.0 m; with sprinklers (სქ, სგ, სმ, დწ-1, სვ, სც-1, სც-2, სც-4, დს) ≤ 15 m; no limit if length ≤ 2.5 × least width.',
         'დერეფნებში არ შეიქმნას 6,0 მ-ზე გრძელი ჩიხები', source='№87 (2022)'),
    rule('1021.2', 'egress', 'გასასვლელების რაოდენობა სართულზე', 'Exits per storey',
         'სართულს სჭირდება ორი გასასვლელი, თუ არ არის დაცული ცხრილები 1021.2(1)/(2). სც-2: ერთი გასასვლელი მხოლოდ მე-8 სართულის ჩათვლით, არამაღლივ შენობაში, ≤ 400 მ², ≤ 5 ბინა, ≤ 38 მ.',
         'A storey needs two exits unless tables 1021.2(1)/(2) allow one. სც-2: one exit only up to the 8th storey, not high-rise, ≤ 400 m², ≤ 5 units, ≤ 38 m.',
         'ნებისმიერ სართულს ან დაკავებულ სახურავს უნდა ემსახურებოდეს ორი გასასვლელი ან გასასვლელთან მისადგომის გზა-კიბე, ან პანდუსი', source='№444 (2025)'),
    rule('1027.1', 'egress', 'გასვლა შენობიდან', 'Exit discharge',
         'გასასვლელები პირდაპირ შენობის გარეთ უნდა გადიოდეს.', 'Exits must discharge directly outside the building.',
         'გასასვლელები უნდა გადიოდეს პირდაპირ შენობის გარეთ',
         check='The clause has exceptions, e.g. discharge through a lobby.'),
    rule('403.5.1', 'egress', 'კიბეების დაშორება მაღლივში', 'High-rise stair separation',
         'მაღლივში გასასვლელი კიბეები ≥ 9,0 მ-ით ან დიაგონალის ¼-ით უნდა დაშორდეს (რომელიც ნაკლებია). მაკრატელა კიბე ერთ კიბედ ითვლება.',
         'In high-rises exit stairs must be at least 9.0 m or ¼ of the diagonal apart, whichever is less. A scissor stair counts as one stair.',
         'უნდა გაიმიჯნოს არანაკლებ 9,0 მეტრით ან შენობის ან ფართობის საერთო დიაგონალის მაქსიმალური სიგრძის არანაკლებ მეოთხედით', source='№498 (2017)',
         check='High-rise buildings only; otherwise not_applicable.'),

    # ---------- Fire protection systems ----------
    rule('903.2.8', 'fire_systems', 'ავტოსაშხეფი სისტემა — სც ჯგუფი', 'Sprinklers — group სც',
         'სც ჯგუფი მთლიანად ავტოსაშხეფი სისტემით. გამონაკლისი: სც-2 მრავალბინიანი სახლი, სადაც იატაკი 37 მ-ს არ აღემატება; 2028 წლის 1 აპრილამდე არ არის საჭირო სც-2 მაღლივის ბინებში.',
         'Group სც fully sprinklered. Exceptions: სც-2 apartment buildings with no occupied floor above 37 m; until 1 April 2028 not required inside apartments of სც-2 high-rises.',
         '2028 წლის 1 აპრილამდე სც-2 ჯგუფის მრავალბინიანი საცხოვრებელი მაღლივი შენობის საცხოვრებელ ერთეულებში (ბინებში) ავტოსაშხეფი სისტემის დაყენება აუცილებელი არ არის', source='№131 (2023)',
         check='Group სც only; otherwise not_applicable.'),
    rule('403.3', 'fire_systems', 'ავტოსაშხეფი სისტემა — მაღლივი', 'Sprinklers — high-rise',
         'მაღლივი შენობა მთლიანად ავტოსაშხეფი სისტემით. გამონაკლისი: სც-2 მრავალბინიანი სახლი, სადაც დაკავებული იატაკი 37 მ-ს არ აღემატება.',
         'High-rise buildings fully sprinklered. Exception: სც-2 apartment buildings with no occupied floor above 37 m.',
         'შენობები და ნაგებობები მთლიანად უნდა აღიჭურვოს 903.3.1.1 ქვეთავის შესაბამისად დაყენებული ავტოსაშხეფი სისტემით',
         check='High-rise only; otherwise not_applicable. Exceptions as amended by №180 (2019).'),
    rule('403.4.3', 'fire_systems', 'სახანძრო მილდგარები — მაღლივი', 'Standpipes — high-rise',
         'მაღლივი შენობა სახანძრო მილდგარების სისტემით უნდა აღიჭურვოს.', 'High-rise buildings must have a standpipe system.',
         'მაღლივი შენობა უნდა აღიჭურვოს 905.3 ქვეთავის მოთხოვნების შესაბამისი სახანძრო მილდგარების სისტემით',
         check='High-rise only; otherwise not_applicable.'),
    rule('403.4.5', 'fire_systems', 'ხანძრის საკონტროლო ცენტრი', 'Fire command centre',
         'მაღლივში ხანძრის საკონტროლო ცენტრი უნდა მოეწყოს; ადგილი თანხმდება სახანძრო დანაყოფთან.',
         'High-rises need a fire command centre; its location is agreed with the fire service.',
         'ხანძრის საკონტროლო ცენტრის განთავსების ადგილი თანხმდება სახანძრო-სამაშველო დანაყოფთან',
         check='High-rise only; otherwise not_applicable.'),
    rule('906.1', 'fire_systems', 'ხელის ცეცხლმაქრები', 'Portable fire extinguishers',
         'ხელის ცეცხლმაქრები საჭიროა თვ, სქ, სგ, სმ, დსშ, დწ, სვ, სც-1, სც-2, სც-4 და სწ ჯგუფებში.',
         'Portable extinguishers are required in groups თვ, სქ, სგ, სმ, დსშ, დწ, სვ, სც-1, სც-2, სც-4 and სწ.',
         'ხელის ცეცხლმაქრები უნდა განთავსდეს შემდეგ ადგილებში',
         check='Often on fire sheets: if those are not in the file, the status is unverifiable.'),
    rule('907.2.9.1', 'fire_systems', 'სახანძრო განგაში — სც-2', 'Fire alarm — group სც-2',
         'სც-2: განგაშის ხელით სამართავი სისტემა, თუ ერთეული ≥ 3 სართულით მაღლაა გამოსასვლელიდან, 1 სართულით დაბლაა, ან შენობაში 16-ზე მეტი ერთეულია.',
         'სც-2: manual alarm if a unit is 3+ storeys above the exit level, one storey below it, or there are more than 16 units.',
         'შენობა მოიცავს 16-ზე მეტ საცხოვრებელ ან საძინებელ ერთეულს',
         check='Group სც-2 only; otherwise not_applicable. The clause has exceptions.'),
    rule('915.12', 'fire_systems', 'სახანძრო ავტოკიბის გზა', 'Fire ladder access road',
         'სც-2, სახანძრო-ტექნიკური სიმაღლე > 30 მ: გზა ღიობების მქონე ფასადის მხრიდან, მთელ სიგრძეზე. სც, თვ, სვ, სქ, დწ, დს, > 23 მ: სულ მცირე ორი მხრიდან.',
         'სც-2 over 30 m fire-technical height: road along the full façade with openings. სც, თვ, სვ, სქ, დწ, დს over 23 m: on at least two sides.',
         'რომელთა სახანძრო-ტექნიკური სიმაღლე 30 მეტრზე მაღლაა, გზა უნდა მოეწყოს ღიობების მქონე ფასადის მხრიდან შენობის მთელ სიგრძეზე', source='№444 (2025)',
         check='Needs a site plan. Sections 915–916 are suspended until 1 March 2027 for objects outside state fire supervision (Art. 23, №426 of 2026): mention this.'),

    # ---------- Fire resistance ----------
    rule('1022.2', 'fire_resistance', 'კიბის უჯრედის შემოზღუდვა', 'Stair enclosure rating',
         'შიგა გასასვლელი კიბე შემოზღუდული: ცეცხლმედეგობა ≥ 2 სთ, თუ აერთებს 4+ სართულს; ≥ 1 სთ — 4-ზე ნაკლებს.',
         'Interior exit stairs enclosed: ≥ 2 h if connecting 4+ storeys, ≥ 1 h if fewer.',
         'ცეცხლმედეგობის ხარისხი, სულ მცირე, 2 საათი უნდა იყოს, სადაც აერთებს ოთხ სართულს ან მეტს', source='№498 (2017)',
         check='Storeys below ground count; mezzanines do not.'),
    rule('1018.1', 'fire_resistance', 'დერეფნის ცეცხლმედეგობა', 'Corridor fire rating',
         'საშხეფის გარეშე / საშხეფით: თვ, სქ, სგ, სმ, სვ, სწ, დს (დატვირთვა > 30) — 1 სთ / 0; სც (> 10) — 1 სთ / 0,5 სთ.',
         'Without / with sprinklers: თვ, სქ, სგ, სმ, სვ, სწ, დს (load > 30) 1 h / 0; სც (> 10) 1 h / 0.5 h.',
         'დერეფნების ცეცხლმედეგობის ხარისხი', source='№498 (2017)',
         check='Other groups are in table 1018.1. Usually only stated in notes or wall legends.'),

    # ---------- Accessibility ----------
    rule('1105.1', 'accessibility', 'მისაწვდომი შესასვლელები', 'Accessible entrances',
         'მთავარი შესასვლელების სულ მცირე 60% მისაწვდომი უნდა იყოს.', 'At least 60% of main entrances must be accessible.',
         'ყველა მთავარი შესასვლელის, სულ მცირე, 60% მისაწვდომი უნდა იყოს', source='№737 (2020)'),
    rule('1106.1', 'accessibility', 'მისაწვდომი ავტოსადგომი', 'Accessible parking',
         'ავტოსადგომს ცხრილი 1106.1-ის შესაბამისი მისაწვდომი სივრცეები სჭირდება; სც-2 და სც-3 — სულ მცირე 2%, მინიმუმ ერთი.',
         'Parking needs accessible spaces per table 1106.1; სც-2 and სც-3 at least 2%, minimum one.',
         'ავტოსადგომი უზრუნველყოფილი უნდა იყოს 1106.1 ცხრილის შესაბამისი მისაწვდომი სივრცეებით', source='№737 (2020)',
         check='Only if parking is shown; otherwise not_applicable.'),
    rule('1107.5.1.1', 'accessibility', 'მისაწვდომი ერთეულები — დწ-1', 'Accessible units — group დწ-1',
         'დწ-1: ერთეულების სულ მცირე 4%, მინიმუმ ერთი, მისაწვდომი უნდა იყოს.',
         'დწ-1: at least 4% of units, minimum one, must be accessible.',
         'საცხოვრებელი და საძინებელი ერთეულების, სულ მცირე, 4%, მაგრამ, არანაკლებ, თითო საცხოვრებელი და საძინებელი ერთეული მისაწვდომი ერთეული უნდა იყოს', source='№737 (2020)',
         check='Group დწ-1 only; otherwise not_applicable. Other occupancies are in the rest of 1107.5 and 1107.6.'),
    rule('1107.6.2.1.1', 'accessibility', 'ა ტიპის ერთეულები — სც-2', 'Type A units — group სც-2',
         'სც-2, 20-ზე მეტი ერთეული: ა ტიპის ერთეულები სულ მცირე 2%, მინიმუმ 1.',
         'სც-2 with more than 20 units: at least 2% Type A units, minimum 1.',
         'ა ტიპის ერთეული უნდა იყოს 2%, მაგრამ, არანაკლებ, 1',
         check='Group სც-2 with more than 20 units; otherwise not_applicable.'),
    rule('1109.2', 'accessibility', 'მისაწვდომი ტუალეტი', 'Accessible toilet',
         'თითოეული ტუალეტი და სააბაზანო მისაწვდომი უნდა იყოს; თითოეულ მათგანში სულ მცირე ერთი მისაწვდომი მოწყობილობა.',
         'Each toilet and bathing room must be accessible, with at least one accessible fixture of each type.',
         'თითოეული ტუალეტის ოთახი და სააბაზანო ოთახი მისაწვდომი უნდა იყოს', source='№737 (2020)',
         check='Public toilets. Exceptions exist, e.g. inside dwelling units.'),
    rule('1007.3', 'accessibility', 'მისაწვდომი კიბე', 'Accessible egress stair',
         'მისაწვდომი გასასვლელი კიბე: სახელურებს შორის ≥ 1,2 მ და თავშესაფრის ფართობი. არ არის საჭირო სრულად დაშხეფებულ შენობაში; თავშესაფარი არ სჭირდება სც-2-ს.',
         'Accessible egress stair: ≥ 1.2 m between handrails and an area of refuge. Not needed in fully sprinklered buildings; სც-2 needs no refuge area.',
         'სართულებს შორის მდებარე გზა-კიბის თავისუფალი სიგანე სახელურებს შორის, სულ მცირე, 1,2 მ უნდა იყოს', source='№180 (2019)'),

    # ---------- Interior environment ----------
    rule('1205.2', 'interior', 'ბუნებრივი განათება', 'Natural light',
         'შუქგამტარი ფართობი ≥ ოთახის იატაკის ფართობის 8%.', 'Glazed area ≥ 8% of the room floor area.',
         'შუქგამტარი მინიმალური სუფთა ფართობი არ უნდა იყოს ოთახის იატაკის ფართობის 8%-ზე ნაკლები',
         check='Habitable rooms where areas and window sizes are shown.'),
    rule('1208.1', 'interior', 'ოთახის მინიმალური სიგანე', 'Minimum room width',
         'საცხოვრებელი სივრცის ზომა გეგმაში ≥ 2,2 მ (სამზარეულოს გარდა).', 'Habitable space dimension ≥ 2.2 m (kitchens excepted).',
         'საცხოვრებელი სივრცეების არცერთი ზომა გეგმაში არ უნდა იყოს 2.2 მ-ზე ნაკლები'),
    rule('1208.2', 'interior', 'ჭერის მინიმალური სიმაღლე', 'Minimum ceiling height',
         'საცხოვრებელი სივრცეები და დერეფნები ≥ 2,3 მ; სააბაზანო, ტუალეტი, სამზარეულო, საწყობი, სამრეცხაო ≥ 2,15 მ.',
         'Habitable spaces and corridors ≥ 2.3 m; bathrooms, toilets, kitchens, storage, laundry ≥ 2.15 m.',
         'დასაკავებელი სივრცეების, საცხოვრებელი სივრცეებისა და დერეფნების ჭერის სიმაღლე არ უნდა იყოს 2,3 მ-ზე ნაკლები'),
    rule('1208.3', 'interior', 'ოთახის მინიმალური ფართობი', 'Minimum room area',
         'თითო საცხოვრებელ ერთეულში ერთი ოთახი ≥ 14,0 მ²; სხვა საცხოვრებელი ოთახები ≥ 7,0 მ². სტუდიოებზე იხ. 1208.4.',
         'Each dwelling has one room ≥ 14.0 m²; other habitable rooms ≥ 7.0 m². For studios see 1208.4.',
         'ყველა საცხოვრებელ ერთეულს უნდა ჰქონდეს, არანაკლებ, 14,0 მ2 ფართობის ერთი ოთახი მაინც',
         check='Dwellings only; otherwise not_applicable.'),
)

BY_ID = {r['id']: r for r in RULES}
CATEGORY_KEYS = tuple(c[0] for c in CATEGORIES)


def prompt_text():
    """The rulebook as the model reads it. Stable text, so it stays in the prompt cache."""
    lines = []
    for key, _, en, chapters in CATEGORIES:
        lines.append(f'\n## {en} (chapters {chapters})')
        for r in (r for r in RULES if r['category'] == key):
            note = f' Check: {r["check"]}' if r['check'] else ''
            lines.append(f'- [{r["id"]}] {r["en"]}: {r["req_en"]}{note}')
    return '\n'.join(lines).strip()
