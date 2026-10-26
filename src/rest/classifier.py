"""Product type from the name and description.

Type IDs: 1 = chicken (any poultry), 2 = fish, 3 = meat, 4 = vegetarian.

The rules run in this order; the first that matches wins:
1. an explicitly plant-based dish («растительная котлета», «немясной люля»,
   «биточки морковные», «веган», «постный», «вегетарианский») is vegetarian
   whatever else the name says;
2. fish and seafood, sushi vocabulary included («фила», «сяке», «эби»);
3. a pork/beef ingredient or a dish that is meat by definition («бекон»,
   «телятина», «харчо», «карбонара») — meat even next to chicken («биточки
   куриные с беконом»);
4. poultry;
5. a roll with no other clue is sushi, so fish («Лавандовый ролл "Бали"»);
6. a generic meat word («котлеты», «фрикадельки», «сосиски», «ветчина»,
   «мясо», «бургер») with no poultry mentioned anywhere — meat. With poultry
   in the text («котлета куриная», «сосиски из птицы», «мясо индейки») rule 4
   has already made it chicken;
7. everything else is vegetarian. The default also covers dishes the rules
   do not know, which is why rule 6 errs on the side of meat: a meat eater
   losing a dish is cheaper than a vegetarian getting one.

Before 2026-10-26 only a short list of pork/beef words existed and everything
else fell through to «Вегетарианское» — meat balls, ham and sausage dishes
included. Patterns are regexes over the text with «ё» folded to «е»; short
words carry boundaries so that «сом» does not match «соусом» and «печень»
does not match «печенье».
"""
import re


def _rules(*patterns: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(p) for p in patterns)


PLANT_BASED = _rules(
    r"растительн", r"немясн", r"веган", r"\bпостн", r"вегетариан", r"\bтофу\b", r"соев",
)

# A meat-shaped word made of vegetables («биточки морковные», «котлеты капустные»,
# «стейк из тыквы») is cut out of the text before the meat rules run; what is
# left decides («стейк из тыквы с куриным рулетом» → chicken).
VEGETABLE_DISHES = _rules(
    r"(биточк|котлет|стейк|оладь|шницел)\w*\s+(морковн|капустн|свекольн|овощн|грибн|картофельн|из тыквы|из цветной капусты)\w*",
    r"(морковн|капустн|свекольн|овощн|грибн|картофельн)\w*\s+(биточк|котлет|оладь)\w*",
)

FISH = _rules(
    r"форел", r"семг", r"\bрыб", r"креветк", r"минта[йе]", r"лосос", r"\bнерк", r"\bикр[аоуы]",
    r"судак", r"тунец", r"тунц", r"угорь", r"угрем", r"дорадо", r"наваг", r"\bсом(а|ом|у|е)?\b",
    r"треск", r"камбал", r"корюшк", r"\bщук", r"мойв", r"палтус", r"скумбри",
    r"сибас", r"\bсайд[аы]\b", r"\bкет[аыо]й?\b", r"горбуш", r"сельд[ьию]?\b", r"селедк", r"кальмар",
    r"\bкраб", r"мидии", r"мидия", r"осьминог", r"морепродукт", r"\bуха\b", r"\bуху\b",
    r"\bсуши", r"\bфила\b", r"филадельф", r"\bсяке\b", r"\bэби\b", r"\bкани\b", r"унаги", r"сурими",
    r"мимоз", r"нисуаз", r"том ям", r"\bфиш\b",
)

STRONG_MEAT = _rules(
    r"говядин", r"говяж", r"свин", r"буженин", r"кролик", r"кролич",
    r"печен(ь|и|ью|очн)\b|печеночн", r"бекон", r"ростбиф", r"баран", r"телят",
    r"окорок", r"карбонад", r"карбонар", r"\bшпик", r"тушенк", r"копченост",
    r"харчо", r"\bазу\b", r"лагман", r"мусак", r"по-флотски", r"солянк", r"фо-бо", r"фо бо",
    r"мясн",
)

POULTRY = _rules(
    r"курин", r"куриц", r"\bкур\.", r"индейк", r"индюш", r"цыпл", r"\bптиц",
    r"\bутк", r"утин", r"цезар", r"чикен",
)

WEAK_FISH = _rules(r"(?<![-\w])ролл", r"сандочи")

WEAK_MEAT = _rules(
    r"мясо\b", r"мясом\b", r"мяса\b",
    r"ветчин", r"колбас", r"сосис", r"сардел", r"пастрам", r"хот-дог", r"хотдог",
    r"котлет", r"фрикадел", r"тефтел", r"\bежик", r"биточк", r"голубц", r"митбол",
    r"бефстрог", r"пельмен", r"шашлык", r"люля", r"долма", r"болонь", r"гуляш", r"бифштекс",
    r"\bмант(ы|ов)\b", r"жарко[ею]", r"чебурек", r"кебаб",
    r"стейк", r"бургер", r"шницел", r"наггетс",
)

CHICKEN_ID, FISH_ID, MEAT_ID, VEG_ID = 1, 2, 3, 4
DEFAULT_TYPE_ID = VEG_ID


def _matches(text: str, rules: tuple[re.Pattern, ...]) -> bool:
    return any(r.search(text) for r in rules)


def classify_product(name: str, description: str) -> int:
    """Return the type id (1 chicken, 2 fish, 3 meat, 4 vegetarian) for a dish."""
    text = f"{name} {description}".lower().replace("ё", "е")
    if _matches(text, PLANT_BASED):
        return VEG_ID
    for rule in VEGETABLE_DISHES:
        text = rule.sub(" ", text)
    if _matches(text, FISH):
        return FISH_ID
    if _matches(text, STRONG_MEAT):
        return MEAT_ID
    if _matches(text, POULTRY):
        return CHICKEN_ID
    if _matches(text, WEAK_FISH):
        return FISH_ID
    if _matches(text, WEAK_MEAT):
        return MEAT_ID
    return DEFAULT_TYPE_ID
