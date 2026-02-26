from sqlalchemy.orm import Session

from src.models import Type, SubType
from src.logger import logger


TYPES = [
    {"id": 1, "name": "Курица"},
    {"id": 2, "name": "Рыба"},
    {"id": 3, "name": "Мясо"},
    {"id": 4, "name": "Вегетарианское"},
]

SUBTYPES = [
    {"id": 1, "name": "Вторые блюда"},
    {"id": 2, "name": "Салаты"},
    {"id": 3, "name": "Супы"},
    {"id": 4, "name": "Сырники и запеканки"},
    {"id": 5, "name": "Сэндвичи и бургеры"},
    {"id": 7, "name": "Роллы и сеты"},
    {"id": 8, "name": "Блины и оладьи"},
    {"id": 9, "name": "Омлеты и завтраки"},
    {"id": 10, "name": "Каши"},
    {"id": 12, "name": "Пироги и лепёшки"},
    {"id": 13, "name": "Сладости и десерты"},
    {"id": 14, "name": "Круассаны"},
    {"id": 15, "name": "Паста"},
    {"id": 16, "name": "Пицца"},
    {"id": 17, "name": "Драники"},
    {"id": 18, "name": "Онигири"},
]


def seed_reference_data(db: Session):
    """Insert types and subtypes if they don't exist."""
    for t in TYPES:
        if not db.query(Type).filter_by(id=t["id"]).first():
            db.add(Type(**t))
            logger.info(f"Seeded type: {t['name']}")

    for st in SUBTYPES:
        if not db.query(SubType).filter_by(id=st["id"]).first():
            db.add(SubType(**st))
            logger.info(f"Seeded subtype: {st['name']}")

    db.commit()
