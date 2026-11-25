"""Labelled example questions for the intent classifier (English, Kinyarwanda, French).

Entities are written as placeholders (CROPX, DISTX, PROVX, YEARX, SEASONX). At question time the same placeholders
replace the names the entity finder detects, so the model learns how a question is phrased, not which crop or
district it names. Examples are expanded with light typo noise so the model stays robust to misspellings.
"""

import random

INTENTS = {
    "greeting": "Greeting",
    "thanks": "Thanks",
    "goodbye": "Goodbye",
    "help": "What Analiza can do",
    "about_data": "About the data",
    "ranking": "District ranking",
    "crop_in_district": "Crop in a district",
    "practices": "How a crop is grown",
    "compare": "Comparison",
    "why_gap": "Explaining a gap",
    "trend": "Trend over seasons",
    "input_effect": "Input effect",
    "scenario": "What-if scenario",
    "priorities": "Priority districts",
    "gender": "Women and men farmers",
    "best_crops": "Best crops",
    "profile": "District profile",
    "overview": "National overview",
    "out_of_scope": "Outside our data",
}

EXAMPLES: dict[str, list[str]] = {
    "greeting": [
        "hi", "hello", "hey", "hey there", "hello analiza", "hi there", "good morning", "good afternoon",
        "good evening", "hello how are you", "how are you", "how are you doing", "greetings", "yo", "hiya",
        "muraho", "mwaramutse", "mwiriwe", "bite", "amakuru", "amakuru yawe", "muraho neza", "mwaramutse neza",
        "bonjour", "bonsoir", "salut", "coucou", "bonjour comment ca va", "ca va", "hello friend", "hi analiza",
        "good day", "morning", "mwaramutseho", "uraho", "muraho analiza",
    ],
    "thanks": [
        "thanks", "thank you", "thank you so much", "thanks a lot", "many thanks", "great thanks", "ok thanks",
        "that helps thank you", "perfect thank you", "nice thanks", "cheers", "appreciate it", "good job",
        "murakoze", "urakoze", "murakoze cyane", "urakoze cyane", "merci", "merci beaucoup", "merci bien",
        "super merci", "thanks for the help", "awesome thank you", "very helpful thanks",
    ],
    "goodbye": [
        "bye", "goodbye", "see you", "see you later", "bye bye", "that is all", "i am done", "good night",
        "talk later", "murabeho", "mugire amahoro", "ni ah'ubutaha", "tuzongera", "au revoir", "a plus",
        "a bientot", "bonne nuit", "that's all for now", "ok bye", "thanks bye",
    ],
    "help": [
        "what can you do", "what can i ask", "what can i ask you", "help", "help me", "how does this work",
        "how do i use this", "what do you know", "what questions can you answer", "who are you", "what are you",
        "what is analiza", "what is this app", "give me examples", "show me examples of questions",
        "what topics do you cover", "can you help me", "i need help", "ushobora iki", "wamfasha iki",
        "uri nde", "ndabaza iki", "nkoresha nte iyi porogaramu", "mfasha", "que peux-tu faire", "aide",
        "aide moi", "qui es-tu", "comment ca marche", "quelles questions puis-je poser", "what should i ask",
        "how can you help", "what is your purpose", "what data can you show me",
    ],
    "about_data": [
        "where does the data come from", "what is the source of the data", "which surveys do you use",
        "what data do you use", "how is yield calculated", "how do you calculate yield", "what is the methodology",
        "are these numbers official", "is this data reliable", "how many farmers were surveyed",
        "how many plots are in the data", "what years does the data cover", "what is season a", "what is season c",
        "what are seasons a b and c", "what does low reliability mean", "how accurate is the model",
        "how was the model trained", "what is the seasonal agricultural survey", "what is nisr",
        "are the numbers weighted", "why are some districts missing", "amakuru akomoka he",
        "imibare ivuye he", "ubushakashatsi bwakozwe na nde", "d'ou viennent les donnees",
        "quelle est la source des donnees", "comment le rendement est calcule", "what does kg/ha mean",
        "how up to date is the data", "how do you know this", "data sources",
    ],
    "ranking": [
        "which districts have the highest CROPX yield", "which district has the highest CROPX yield",
        "which districts have the lowest CROPX yield", "best district for CROPX", "best districts for CROPX",
        "top districts for CROPX", "worst district for CROPX", "where is CROPX yield highest",
        "where is CROPX yield lowest", "rank districts by CROPX yield", "ranking of districts for CROPX",
        "which districts produce the most CROPX", "which district produces the most CROPX",
        "top 5 districts CROPX production", "where do farmers get the best CROPX harvest",
        "which districts use the most fertilizer", "which districts use the least fertilizer",
        "which districts have the lowest fertilizer use", "which districts have the highest improved seed use",
        "where is irrigation most used", "which districts irrigate the most",
        "which districts have the lowest extension access", "which districts have the most cooperative members",
        "which district has the highest crop insurance", "rank districts by improved seed use",
        "which districts in PROVX have the highest CROPX yield", "best CROPX district in PROVX",
        "highest CROPX yield YEARX", "highest CROPX yield season SEASONX", "lowest CROPX yield season SEASONX",
        "which districts use the most organic fertilizer for CROPX", "where is anti erosion most used",
        "which districts have the most land consolidation", "districts with the highest CROPX production",
        "where is CROPX grown the most", "which districts grow the most CROPX",
        "ni akahe karere keza mu musaruro w CROPX", "ni akahe karere kabona umusaruro mwinshi wa CROPX",
        "uturere dufite umusaruro mwinshi wa CROPX", "akarere kabona CROPX nyinshi",
        "ni utuhe turere dukoresha ifumbire nyinshi", "uturere dukoresha imbuto z indobanure",
        "quel district a le meilleur rendement de CROPX", "quels districts produisent le plus de CROPX",
        "classement des districts pour le CROPX", "quel district utilise le plus d engrais",
        "district with best CROPX", "most productive districts for CROPX", "highest yield district",
        "which areas have the highest CROPX yields", "compare all districts on CROPX yield",
    ],
    "crop_in_district": [
        "CROPX in DISTX", "DISTX CROPX", "CROPX DISTX", "CROPX yield in DISTX", "how is CROPX in DISTX",
        "how is CROPX doing in DISTX", "what is the CROPX yield in DISTX", "how much CROPX does DISTX produce",
        "CROPX production in DISTX", "CROPX harvest in DISTX", "is CROPX good in DISTX",
        "how good is DISTX at CROPX", "CROPX in DISTX season SEASONX", "CROPX in DISTX YEARX",
        "what about CROPX in DISTX", "show me CROPX in DISTX", "DISTX CROPX yield", "yield of CROPX in DISTX",
        "CROPX yields DISTX district", "does DISTX grow CROPX well", "CROPX in DISTX compared to national",
        "is DISTX above average for CROPX", "umusaruro wa CROPX i DISTX", "CROPX i DISTX",
        "CROPX mu karere ka DISTX", "umusaruro w CROPX mu DISTX", "rendement du CROPX a DISTX",
        "le CROPX a DISTX", "production de CROPX a DISTX", "and in DISTX", "what about DISTX",
        "how many tonnes of CROPX in DISTX", "CROPX yield DISTX vs Rwanda",
    ],
    "practices": [
        "how is CROPX planted in DISTX", "how is CROPX grown in DISTX", "how is CROPX cultivated in DISTX",
        "how do farmers grow CROPX in DISTX", "farming practices for CROPX in DISTX",
        "do farmers in DISTX use fertilizer on CROPX", "fertilizer use for CROPX in DISTX",
        "improved seed use for CROPX in DISTX", "do DISTX farmers use improved seed",
        "how many CROPX farmers use fertilizer in DISTX", "inputs used for CROPX in DISTX",
        "seed and fertilizer use in DISTX", "is irrigation used in DISTX", "irrigation in DISTX",
        "fertilizer use in DISTX", "how is CROPX farmed", "how is CROPX grown in Rwanda",
        "what practices do CROPX farmers use", "practices of CROPX farmers", "CROPX farming methods in DISTX",
        "anti erosion measures in DISTX", "land consolidation in DISTX", "do they use manure for CROPX in DISTX",
        "organic fertilizer use CROPX DISTX", "how much fertilizer is used on CROPX",
        "CROPX ihingwa gute i DISTX", "abahinzi ba CROPX i DISTX bakoresha ifumbire",
        "bahinga bate CROPX i DISTX", "imbuto z indobanure i DISTX", "ifumbire mu karere ka DISTX",
        "comment le CROPX est cultive a DISTX", "pratiques agricoles CROPX DISTX",
        "utilisation d engrais a DISTX", "how is CROPX planted", "how do farmers plant CROPX in DISTX",
        "what inputs do DISTX farmers use", "extension access in DISTX",
    ],
    "compare": [
        "compare DISTX and DISTX", "compare CROPX in DISTX and DISTX", "DISTX vs DISTX",
        "DISTX versus DISTX CROPX", "difference between DISTX and DISTX", "CROPX DISTX vs DISTX",
        "compare how CROPX is planted in DISTX and DISTX", "compare how CROPX is cultivated in DISTX and DISTX",
        "which is better for CROPX DISTX or DISTX", "is DISTX better than DISTX at CROPX",
        "DISTX or DISTX for CROPX", "compare CROPX yields in DISTX DISTX and DISTX",
        "compare PROVX and PROVX", "PROVX vs PROVX CROPX", "compare CROPX and CROPX",
        "compare CROPX and CROPX in DISTX", "CROPX vs CROPX yield", "compare DISTX with DISTX on fertilizer use",
        "how does DISTX compare to DISTX", "gereranya DISTX na DISTX", "gereranya CROPX i DISTX na DISTX",
        "itandukaniro rya DISTX na DISTX", "comparer DISTX et DISTX", "comparaison CROPX DISTX DISTX",
        "DISTX contre DISTX", "side by side DISTX and DISTX", "DISTX and DISTX CROPX",
        "compare DISTX to the national average", "compare season SEASONX and season SEASONX for CROPX",
    ],
    "why_gap": [
        "why is DISTX behind DISTX in CROPX", "why is CROPX yield low in DISTX", "why is DISTX yield low",
        "why does DISTX produce less CROPX", "why is DISTX better than DISTX", "what explains the gap",
        "what explains the difference between DISTX and DISTX", "reasons for low CROPX yield in DISTX",
        "why are CROPX yields so low", "why is DISTX the best for CROPX", "what makes DISTX so productive",
        "why do farmers in DISTX get more CROPX", "explain the yield gap in DISTX",
        "what can improve CROPX yield in DISTX", "how can DISTX catch up with DISTX",
        "what is holding back CROPX in DISTX", "why is DISTX below average", "why is DISTX above average",
        "kubera iki DISTX ifite umusaruro muke wa CROPX", "ni iki gituma DISTX irusha DISTX",
        "kuki umusaruro wa CROPX ari muke i DISTX", "pourquoi le rendement est faible a DISTX",
        "pourquoi DISTX produit moins de CROPX", "qu est ce qui explique l ecart", "why the difference",
        "why is DISTX behind", "how to increase CROPX yield in DISTX", "what should DISTX do to improve CROPX",
    ],
    "trend": [
        "how has CROPX yield changed", "how has CROPX yield changed across seasons", "CROPX trend",
        "CROPX yield over time", "is CROPX yield increasing", "is CROPX yield decreasing",
        "did CROPX yield go up", "CROPX yield YEARX vs YEARX", "CROPX yield season SEASONX vs season SEASONX",
        "trend of CROPX in DISTX", "how has CROPX changed in DISTX", "evolution of CROPX yields",
        "has fertilizer use increased", "trend in improved seed use", "how has irrigation changed",
        "change in CROPX production", "CROPX production over the seasons", "seasonal trend for CROPX",
        "compare YEARX and YEARX for CROPX", "is DISTX improving in CROPX", "progress of CROPX yields",
        "umusaruro wa CROPX wahindutse ute", "uko umusaruro wa CROPX wagiye uhinduka",
        "umusaruro wa CROPX wiyongereye", "evolution du rendement du CROPX", "tendance du CROPX",
        "le rendement du CROPX a-t-il augmente", "what changed between YEARX and YEARX",
        "CROPX last season vs this season",
    ],
    "input_effect": [
        "does improved seed increase CROPX yield", "does fertilizer increase CROPX yield",
        "effect of fertilizer on CROPX", "effect of improved seed on CROPX", "does irrigation help CROPX",
        "is fertilizer worth it for CROPX", "impact of organic fertilizer on CROPX", "do inputs improve yield",
        "which input increases CROPX yield the most", "how much does fertilizer add to CROPX yield",
        "yield with and without fertilizer", "yield with and without improved seed", "does manure help",
        "does irrigation increase yield", "benefit of improved seeds", "is improved seed better",
        "does anti erosion improve yield", "fertilizer premium for CROPX", "what is the best input for CROPX",
        "imbuto z indobanure zongera umusaruro wa CROPX", "ifumbire yongera umusaruro wa CROPX",
        "ifumbire ifasha CROPX", "kuhira byongera umusaruro", "l engrais augmente-t-il le rendement du CROPX",
        "effet des semences ameliorees", "impact de l irrigation sur le rendement",
        "does fertilizer work", "is it worth using improved seed",
    ],
    "scenario": [
        "what if farmers in DISTX used improved seed", "what if farmers in DISTX used fertilizer for CROPX",
        "what if farmers in DISTX used improved seed and fertilizer for CROPX",
        "what would happen if DISTX farmers used fertilizer", "simulate fertilizer for CROPX in DISTX",
        "simulate improved seed in DISTX", "predict CROPX yield in DISTX with improved seed",
        "if all CROPX farmers in DISTX used irrigation", "what if everyone in DISTX irrigated",
        "how much would CROPX yield rise in DISTX with fertilizer", "scenario fertilizer DISTX CROPX",
        "what if we give improved seed to DISTX", "what if farmers used fertilizer",
        "what yield could DISTX reach with improved seed and fertilizer", "estimate yield if farmers adopt fertilizer",
        "potential CROPX yield in DISTX", "how much could DISTX gain with better inputs",
        "bigenda bite abahinzi ba DISTX bakoresheje ifumbire", "abahinzi bakoresheje imbuto z indobanure byagenda bite",
        "umusaruro wa CROPX wakwiyongera gute i DISTX", "et si les agriculteurs de DISTX utilisaient de l engrais",
        "simulation engrais DISTX CROPX", "que se passerait-il avec des semences ameliorees a DISTX",
        "what if DISTX used manure and fertilizer", "model prediction for DISTX CROPX",
    ],
    "priorities": [
        "where should support go for CROPX", "where should support be prioritised for CROPX",
        "priority districts for CROPX", "which districts need help with CROPX", "which districts need support",
        "where to invest in CROPX", "where should government invest", "where should we target fertilizer",
        "which districts should get improved seed", "where is support most needed", "priority ranking CROPX",
        "where can we close the biggest yield gap", "which districts have the biggest potential for CROPX",
        "where would support have the most impact", "targeting districts for CROPX programmes",
        "where should extension officers focus", "uturere dukeneye ubufasha", "ni hehe hakenewe ubufasha bwa CROPX",
        "ni utuhe turere dukwiye gufashwa", "ou prioriser le soutien au CROPX", "quels districts aider en priorite",
        "where should the ministry focus for CROPX", "most in need districts CROPX",
    ],
    "gender": [
        "compare women and men farmers", "women vs men CROPX yields", "do women farmers get lower yields",
        "gender gap in CROPX yield", "female farmers CROPX yield", "are women less productive",
        "yield of female managed plots", "men and women farmers in DISTX", "gender difference in agriculture",
        "women farmers in DISTX", "how do women farmers do", "gender gap by district",
        "abagore n abagabo mu buhinzi", "umusaruro w abagore", "abahinzi b abagore", "femmes et hommes agriculteurs",
        "ecart entre femmes et hommes", "rendement des femmes", "female vs male CROPX",
        "do men get higher yields than women",
    ],
    "best_crops": [
        "which crops grow best in DISTX", "best crops in DISTX", "what crop should i grow in DISTX",
        "what grows well in DISTX", "highest yielding crops in DISTX", "main crops in DISTX",
        "which crops do well in DISTX", "top crops in DISTX", "which crop has the highest yield",
        "which crops have the highest yield in Rwanda", "most productive crops", "which crops are grown in DISTX",
        "what crops does DISTX produce", "best crops in PROVX", "which crop is most produced",
        "crop with the biggest production", "rank crops by yield", "rank crops in DISTX",
        "ni ibihe bihingwa byera neza i DISTX", "ibihingwa byera cyane i DISTX", "nahinga iki i DISTX",
        "quelles cultures poussent bien a DISTX", "meilleures cultures a DISTX", "which crops are strongest in DISTX",
    ],
    "profile": [
        "tell me about DISTX", "DISTX", "DISTX district", "show me DISTX district", "DISTX profile",
        "describe DISTX", "overview of DISTX", "summary of DISTX", "what about DISTX district",
        "how is DISTX doing", "how is agriculture in DISTX", "farming in DISTX", "agriculture in DISTX",
        "give me DISTX statistics", "DISTX key figures", "everything about DISTX", "DISTX at a glance",
        "mbwira ibya DISTX", "amakuru ya DISTX", "ubuhinzi i DISTX", "akarere ka DISTX",
        "parle-moi de DISTX", "agriculture a DISTX", "profil de DISTX", "tell me about PROVX province",
        "how is PROVX doing", "agriculture in PROVX",
    ],
    "overview": [
        "tell me about rwanda", "rwanda agriculture", "summary of agriculture", "national overview",
        "rwanda agriculture at a glance", "key statistics", "give me a summary", "overall picture",
        "how is agriculture in rwanda", "national figures", "main numbers", "overview",
        "what are the main crop yields", "national yields", "rwanda summary YEARX", "how are farmers doing",
        "state of farming in rwanda", "incamake y ubuhinzi", "ubuhinzi mu rwanda", "amakuru y ubuhinzi mu gihugu",
        "resume national", "agriculture au rwanda", "vue d ensemble", "big picture", "highlights",
    ],
    "out_of_scope": [
        "what is the price of CROPX", "CROPX price in DISTX", "how much does fertilizer cost", "market prices",
        "where can i sell my CROPX", "what will the weather be tomorrow", "will it rain in DISTX",
        "rainfall forecast", "climate change effects", "how do i control fall armyworm",
        "how to kill pests on CROPX", "what pesticide should i use", "best fertilizer brand",
        "how do i plant CROPX", "when should i plant CROPX", "what spacing for CROPX",
        "how to make compost", "can i get a loan", "bank loans for farmers", "where to rent a tractor",
        "CROPX in kenya", "uganda maize yield", "agriculture in tanzania", "CROPX yield in 2026",
        "forecast CROPX yield 2027", "who is the president of rwanda", "who won the football match",
        "tell me a joke", "write a poem", "write me an essay", "what is the capital of france",
        "how do i cook CROPX", "recipe for CROPX", "what is bitcoin", "translate this", "what time is it",
        "how old are you", "do you love me", "igiciro cya CROPX", "imvura izagwa ryari",
        "prix du CROPX", "meteo demain", "how much is a kilo of CROPX", "export of coffee",
        "how to treat cassava disease", "livestock numbers", "how many cows in DISTX", "fish farming",
        "population of DISTX", "schools in DISTX", "hospital in DISTX", "best restaurant in DISTX",
        "what is gdp of rwanda", "income of farmers", "how much do farmers earn",
    ],
}


def _typo(text: str, rng: random.Random) -> str:
    """Add one realistic typo to a word that is not a placeholder."""
    words = text.split()
    candidates = [i for i, w in enumerate(words) if len(w) > 3 and not w.endswith("X")]
    if not candidates:
        return text
    i = rng.choice(candidates)
    w = words[i]
    pos = rng.randrange(1, len(w) - 1)
    kind = rng.random()
    if kind < 0.35:
        w = w[:pos] + w[pos + 1:]  # dropped letter
    elif kind < 0.7:
        w = w[:pos - 1] + w[pos] + w[pos - 1] + w[pos + 1:]  # swapped letters
    else:
        w = w[:pos] + rng.choice("aeioursnt") + w[pos:]  # extra letter
    words[i] = w
    return " ".join(words)


def dataset(seed: int = 7, typo_copies: int = 2) -> tuple[list[str], list[str]]:
    """All examples plus typo-noised copies, with their intent labels."""
    rng = random.Random(seed)
    texts, labels = [], []
    for intent, examples in EXAMPLES.items():
        for example in examples:
            base = example.lower()
            variants = {base, base + "?"}
            for _ in range(typo_copies):
                variants.add(_typo(base, rng))
            for v in variants:
                texts.append(v)
                labels.append(intent)
    return texts, labels


# Hand-written questions NOT generated from the examples above, written the way real users type (typos, casual,
# mixed languages). Used only to measure accuracy honestly; never used for training.
EVALUATION: list[tuple[str, str]] = [
    ("helo", "greeting"), ("Muraho neza", "greeting"), ("bonjour analiza", "greeting"),
    ("thx", "thanks"), ("Murakoze cyane!", "thanks"), ("byee", "goodbye"),
    ("what kind of questions can i ask?", "help"), ("who made you and what do you do", "help"),
    ("is the data from NISR?", "about_data"), ("how did you compute the yields", "about_data"),
    ("which district is the best in maize", "ranking"), ("top beans districts", "ranking"),
    ("where do they use the least fertiliser", "ranking"), ("lowest potato yield district", "ranking"),
    ("mesanze beans", "crop_in_district"), ("ibigori i Musanze", "crop_in_district"),
    ("maize yield nyagatare 2024", "crop_in_district"), ("Huye cassava?", "crop_in_district"),
    ("how is maize planted in musanze", "practices"), ("do farmers in rubavu use fertilizer for potatoes", "practices"),
    ("compare how maize is planted in musanze and nyagatare", "compare"),
    ("compare how beans is cultivated ib musanze and nyabihu", "compare"),
    ("Kirehe vs Ngoma maize", "compare"), ("compare maize and beans", "compare"),
    ("why is musanze behind nyagatare in maize", "why_gap"), ("why are bean yields low in Huye", "why_gap"),
    ("how has bean yield changed across seasons?", "trend"), ("is potato production going up", "trend"),
    ("does improved seed increase maize yield?", "input_effect"), ("is fertiliser useful for beans", "input_effect"),
    ("what if farmers in Nyagatare used improved seed and fertilizer for maize?", "scenario"),
    ("simulate irrigation for rice in bugesera", "scenario"),
    ("where should support be prioritised for Irish potato?", "priorities"), ("which districts need help most", "priorities"),
    ("compare women and men farmers' maize yields", "gender"), ("do women get less harvest", "gender"),
    ("what crops are best in rubavu", "best_crops"), ("which crop yields the most in Huye", "best_crops"),
    ("show me Musanze district", "profile"), ("tell me about kayonza", "profile"),
    ("give me the national picture", "overview"), ("tell me about Rwanda", "overview"),
    ("price of beans today", "out_of_scope"), ("will it rain tomorrow in kigali", "out_of_scope"),
    ("how to control armyworm", "out_of_scope"), ("maize yield in uganda", "out_of_scope"),
    ("tell me a joke", "out_of_scope"), ("what is the capital of Kenya", "out_of_scope"),
]
