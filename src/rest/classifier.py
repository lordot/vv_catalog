# Type IDs: 1=chicken, 2=fish, 3=meat, 4=vegetarian
CLASSIFICATION_RULES: list[tuple[int, tuple[str, ...]]] = [
    (3, (  # Meat
        "говядин", "говяж", "свин", "буженин", "кролик",
        "печенью", "печени", "бекон", "ростбиф", "баран",
    )),
    (2, (  # Fish
        "форел", "семг", "рыб", "креветк", "минтай", "лосос",
        "судак", "тунец", "тунцом", "угорь", "угрем", "дорадо",
        "треска", "трески", "камбал", "корюшк", "щук", "мойв",
        "сибас", "сайд", "кета", "кетой", "горбуш", "сельдь",
        "селедк", "кальмар",
    )),
    (1, (  # Chicken
        "курин", "куриц", "индейк", "цезарь", "цыплён", "карбонар",
    )),
]

DEFAULT_TYPE_ID = 4  # Vegetarian


def classify_product(name: str, description: str) -> int:
    """Classify product type by checking name and description against keyword rules.
    Returns type_id (1=chicken, 2=fish, 3=meat, 4=vegetarian).
    """
    text = (name + " " + description).lower()
    for type_id, keywords in CLASSIFICATION_RULES:
        if any(kw in text for kw in keywords):
            return type_id
    return DEFAULT_TYPE_ID
