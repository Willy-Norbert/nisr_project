"""Find what a question is about: crops, districts, provinces, indicator, inputs, year, season (EN / RW / FR).

Every match is recorded, and typo corrections ("mesanze" -> Musanze) are returned so the answer can say what was
understood. The same pass replaces each entity with a placeholder (CROPX, DISTX...) for the intent model.
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from app.data import store

# --- vocabularies -------------------------------------------------------------------------------------------------

CROP_SYNONYMS = {
    "maize": "Maize", "corn": "Maize", "ibigori": "Maize", "igigori": "Maize", "mais": "Maize",
    "potato": "Irish potato", "potatoes": "Irish potato", "irish potatoes": "Irish potato", "ibirayi": "Irish potato",
    "pomme de terre": "Irish potato", "pommes de terre": "Irish potato",
    "sweet potatoes": "Sweet potato", "ibijumba": "Sweet potato", "patate douce": "Sweet potato",
    "rice": "Paddy rice", "umuceri": "Paddy rice", "riz": "Paddy rice",
    "cassava": "Cassava", "manioc": "Cassava", "imyumbati": "Cassava", "umwumbati": "Cassava",
    "banana": "Cooking banana", "bananas": "Cooking banana", "matoke": "Cooking banana", "ibitoki": "Cooking banana",
    "cooking bananas": "Cooking banana", "beer banana": "Banana for beer", "beer bananas": "Banana for beer",
    "dessert bananas": "Dessert banana", "imineke": "Dessert banana",
    "soya": "Soybean", "soy": "Soybean", "soybeans": "Soybean", "soja": "Soybean", "soya beans": "Soybean",
    "peas": "Pea", "amashaza": "Pea", "petit pois": "Pea", "groundnuts": "Groundnut", "peanut": "Groundnut",
    "peanuts": "Groundnut", "ubunyobwa": "Groundnut", "arachide": "Groundnut", "tomatoes": "Tomato",
    "inyanya": "Tomato", "tomate": "Tomato", "sorgho": "Sorghum", "amasaka": "Sorghum", "eggplants": "Eggplant",
    "aubergine": "Eggplant", "intoryi": "Eggplant", "napier grass": "Napia grass for fodder",
    "napier": "Napia grass for fodder", "napia grass": "Napia grass for fodder", "fodder": "Napia grass for fodder",
    "ikawa": "Coffee", "cafe": "Coffee", "taro": "Taro", "amateke": "Taro", "climbing beans": "Climbing bean",
    "bush beans": "Bush bean",
}
TRANSLATED = {k for k in CROP_SYNONYMS if k.split()[0] in {
    "ibigori", "igigori", "mais", "ibirayi", "pomme", "pommes", "ibijumba", "patate", "umuceri", "riz", "manioc",
    "imyumbati", "umwumbati", "matoke", "ibitoki", "imineke", "soja", "amashaza", "petit", "ubunyobwa", "arachide",
    "inyanya", "tomate", "sorgho", "amasaka", "aubergine", "intoryi", "ikawa", "cafe", "amateke"}}
GENERIC_BEANS = {"bean", "beans", "ibishyimbo", "igishyimbo", "haricot", "haricots"}

PROVINCE_SYNONYMS = {
    "kigali city": "Kigali", "umujyi wa kigali": "Kigali", "northern": "North", "northern province": "North",
    "amajyaruguru": "North", "nord": "North", "southern": "South", "southern province": "South",
    "amajyepfo": "South", "sud": "South", "eastern": "East", "eastern province": "East",
    "iburasirazuba": "East", "est": "East", "western": "West", "western province": "West",
    "iburengerazuba": "West", "ouest": "West",
}

# (indicator, words). First match wins, so specific practices come before the general yield words.
INDICATOR_WORDS = [
    ("organic_fertilizer_pct", ["organic", "manure", "compost", "imborera", "fumier"]),
    ("inorganic_fertilizer_pct", ["fertilizer", "fertiliser", "fertilisers", "fertilizers", "ifumbire", "engrais",
                                  "npk", "dap", "urea", "mvaruganda"]),
    ("improved_seed_pct", ["seed", "seeds", "imbuto", "semence", "semences"]),
    ("irrigation_pct", ["irrigat", "kuhira", "irrigu"]),
    ("anti_erosion_pct", ["erosion", "isuri", "terrace", "amaterasi"]),
    ("land_consolidation_pct", ["consolidat", "guhuza ubutaka", "remembrement"]),
    ("extension_access_pct", ["extension", "advisory", "ubujyanama", "vulgarisation", "agronome"]),
    ("cooperative_member_pct", ["cooperative", "koperative", "cooperatives", "association"]),
    ("crop_insurance_pct", ["insurance", "ubwishingizi", "assurance"]),
    ("agri_support_pct", ["agricultural support", "subsid", "inkunga", "grant", "subvention"]),
    ("fertilizer_risk_aware_pct", ["aware", "awareness", "risk"]),
    ("production_t", ["production", "produce", "produces", "produced", "tonnes", "tons", "toni", "total harvest"]),
    ("yield_kg_ha", ["yield", "yields", "productivity", "per hectare", "kg/ha", "rendement", "umusaruro"]),
]

INPUT_WORDS = {
    "improved_seed": ["seed", "seeds", "imbuto", "semence", "semences"],
    "organic_fertilizer": ["organic", "manure", "compost", "imborera", "fumier"],
    "inorganic_fertilizer": ["fertilizer", "fertiliser", "fertilizers", "fertilisers", "ifumbire", "engrais", "npk",
                             "dap", "urea", "mvaruganda"],
    "irrigated": ["irrigat", "kuhira", "irrigu"],
}

LOW_WORDS = ["lowest", "worst", "least", "poorest", "bottom", "minimum", "smallest", "fewest", "weakest", "muke",
             "nkeya", "faible", "plus bas", "moins", "lower", "behind"]

FOREIGN = ["kenya", "uganda", "tanzania", "burundi", "congo", "drc", "kampala", "nairobi", "ethiopia", "france",
           "usa", "america", "china", "india", "nigeria", "ghana", "europe", "zambia", "malawi", "dar es salaam",
           "bujumbura", "goma"]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalise(text: str) -> str:
    text = strip_accents(str(text or "").lower())
    text = text.replace("’", " ").replace("'", " ")
    text = re.sub(r"[^a-z0-9/%\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache
def _districts() -> dict[str, str]:
    return {d.lower(): d for d in store.district_provinces()}


@lru_cache
def _provinces() -> dict[str, str]:
    names = {p.lower(): p for p in set(store.district_provinces().values())}
    return names | PROVINCE_SYNONYMS


@lru_cache
def _crops() -> dict[str, str]:
    names = {c.lower(): c for c in store.manifest()["crops"]}
    names |= {c.lower() + "s": c for c in store.manifest()["crops"]}
    return names | CROP_SYNONYMS


@lru_cache
def _known_words() -> frozenset[str]:
    """Real words that must never be 'corrected' into a place or crop (e.g. price -> rice)."""
    from app.nlp.training_data import EXAMPLES

    words = set()
    for examples in EXAMPLES.values():
        for example in examples:
            words.update(normalise(example).split())
    words.update("""price prices since twice nice advice police slice spice dice mice twice choice voice office
    notice service device rise wise maize mazes amaze areas years season seasons potential compare compared
    district districts province provinces farmers farmer harvest manure better between change changed nyuma
    which there where these those their other about should would could rwanda rwandan national average""".split())
    return frozenset(w for w in words if w.isalpha() and not w.endswith("x"))


# --- result -------------------------------------------------------------------------------------------------------


@dataclass
class Entities:
    crops: list[str] = field(default_factory=list)
    beans_generic: bool = False
    districts: list[str] = field(default_factory=list)
    provinces: list[str] = field(default_factory=list)
    national: bool = False
    indicator_id: str | None = None
    inputs: list[str] = field(default_factory=list)
    year: int | None = None
    other_year: int | None = None
    season: str | None = None
    seasons: list[str] = field(default_factory=list)
    ascending: bool = False
    foreign: str | None = None
    corrections: list[dict] = field(default_factory=list)
    masked: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "masked"}


def _fuzzy(word: str, options: dict[str, str], cutoff: float) -> str | None:
    hit = difflib.get_close_matches(word, list(options), n=1, cutoff=cutoff)
    return options[hit[0]] if hit else None


def extract(question: str) -> Entities:
    text = normalise(question)
    tokens = text.split()
    found = Entities()
    out: list[str] = []
    districts, provinces, crops = _districts(), _provinces(), _crops()
    known = _known_words()

    def add(lst: list, value) -> None:
        if value not in lst:
            lst.append(value)

    i = 0
    while i < len(tokens):
        matched = False
        for size in (4, 3, 2, 1):
            if i + size > len(tokens):
                continue
            phrase = " ".join(tokens[i:i + size])
            if phrase in districts:
                add(found.districts, districts[phrase]); out.append("distx")
            elif phrase in crops:
                add(found.crops, crops[phrase]); out.append("cropx")
                if phrase in TRANSLATED:
                    found.corrections.append({"typed": phrase, "understood": crops[phrase], "kind": "translation"})
            elif phrase in GENERIC_BEANS:
                found.beans_generic = True
                add(found.crops, "Bush bean"); add(found.crops, "Climbing bean"); out.append("cropx")
            elif phrase in provinces and phrase not in ("est",) or (phrase == "est" and i > 0
                                                                     and tokens[i - 1] in ("l", "province", "de")):
                add(found.provinces, provinces[phrase]); out.append("provx")
            else:
                continue
            i += size
            matched = True
            break
        if matched:
            continue

        token = tokens[i]
        if re.fullmatch(r"(19|20)\d\d", token):
            year = int(token)
            if year in (2024, 2025):
                found.year = found.year or year
            else:
                found.other_year = year
            out.append("yearx")
        elif token in ("a", "b", "c") and out and out[-1] in ("season", "igihembwe", "saison"):
            add(found.seasons, token.upper())
            found.season = found.season or token.upper()
            out.append("seasonx")
        elif re.fullmatch(r"season[abc]", token):
            add(found.seasons, token[-1].upper())
            found.season = found.season or token[-1].upper()
            out += ["season", "seasonx"]
        elif token in ("rwanda", "national", "nationally", "country", "igihugu"):
            found.national = True
            out.append(token)
        elif token.isalpha() and len(token) >= 4 and token not in known:
            district = _fuzzy(token, districts, 0.8) if len(token) >= 5 else None
            crop = None if district else _fuzzy(token, {k: v for k, v in crops.items() if " " not in k}, 0.84)
            if district:
                add(found.districts, district); out.append("distx")
                found.corrections.append({"typed": token, "understood": district, "kind": "typo"})
            elif crop:
                add(found.crops, crop); out.append("cropx")
                found.corrections.append({"typed": token, "understood": crop, "kind": "typo"})
            elif _fuzzy(token, {b: b for b in GENERIC_BEANS}, 0.8):
                found.beans_generic = True
                add(found.crops, "Bush bean"); add(found.crops, "Climbing bean"); out.append("cropx")
                found.corrections.append({"typed": token, "understood": "beans", "kind": "typo"})
            else:
                out.append(token)
        else:
            out.append(token)
        i += 1

    padded = f" {text} "
    for indicator_id, words in INDICATOR_WORDS:
        if any(re.search(rf"\b{re.escape(w)}", padded) for w in words):
            found.indicator_id = indicator_id
            break
    for key, words in INPUT_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}", padded) for w in words):
            found.inputs.append(key)
    if "imborera" in padded and "inorganic_fertilizer" in found.inputs and "mvaruganda" not in padded:
        found.inputs.remove("inorganic_fertilizer")  # "ifumbire y'imborera" is organic fertilizer
    found.ascending = any(re.search(rf"\b{re.escape(w)}\b", padded) for w in LOW_WORDS)
    found.foreign = next((c for c in FOREIGN if re.search(rf"\b{re.escape(c)}\b", padded)), None)
    found.masked = " ".join(out)
    return found
