import html
import re
from typing import Optional

from bs4 import BeautifulSoup

from src import schemas
from src.config import MANUAL_SUBTYPES
from src.logger import logger
from src.rest.classifier import classify_product


class ProductParser:
    """Parses VkusVill HTML pages into product data."""

    @staticmethod
    def parse_catalog_page(
        html_content: str, subtype_id: int, name_filter: Optional[str] = None
    ) -> list[schemas.Product]:
        """Parse a catalog listing page into product schemas."""
        soup = BeautifulSoup(html_content, "html.parser")
        products_list = soup.find(
            "div", {"class": "ProductCards__list", "data-place": "catalog_section"}
        )
        if not products_list:
            return []

        products = products_list.find_all("div", {"class": "ProductCard"})
        result = []

        for product in products:
            product_id = product.get("data-id")
            link_elem = product.find("a", {"class": "ProductCard__link"})
            if not link_elem:
                continue

            name = link_elem.get("title", "")
            link = link_elem.get("href", "")

            if name_filter and name_filter not in name.lower():
                break

            result.append(
                schemas.Product(
                    id=product_id,
                    name=html.unescape(name).replace("\xa0", " "),
                    link=link,
                    subtype_id=subtype_id,
                    count=1,
                )
            )

        return result

    @staticmethod
    def parse_family_page(html_content: str) -> list[schemas.Product]:
        """Parse family-format page -- extracts IDs with count=2."""
        soup = BeautifulSoup(html_content, "html.parser")
        products_list = soup.find(
            "div", {"class": "ProductCards__list", "data-place": "catalog_section"}
        )
        if not products_list:
            return []

        products = products_list.find_all("div", {"class": "ProductCard"})
        return [
            schemas.Product(id=p.get("data-id"), count=2) for p in products
        ]

    @staticmethod
    def parse_product_details(
        html_content: bytes, current_subtype_id: int
    ) -> dict:
        """Parse individual product page for nutrition, weight, rating, type."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Rating
        rate_tag = soup.find(class_="Rating__text")
        rate = 0
        if rate_tag:
            rate_text = rate_tag.get_text(strip=True)
            if rate_text not in ("Я новенький", "Ждёт оценку"):
                try:
                    rate = float(rate_text)
                except ValueError:
                    rate = 0

        # Weight
        weight_tag = soup.find(class_="ProductCard__weight")
        weight = 0
        if weight_tag:
            digits = re.findall(r"\d+", weight_tag.get_text(strip=True))
            weight = int("".join(digits)) if digits else 0

        # Name
        name_elem = soup.find("meta", property="og:title")
        name = html.unescape(name_elem["content"]) if name_elem else ""

        # Description
        desc_elem = soup.find(class_="VV23_DetailProdPageInfoDescItem__Desc")
        desc_text = desc_elem.get_text() if desc_elem else ""

        # Subtype override from name
        subtype_id = current_subtype_id
        for keyword, manual_subtype_id in MANUAL_SUBTYPES:
            if keyword in name.lower():
                subtype_id = manual_subtype_id
                break

        # Type classification
        type_id = classify_product(name, desc_text)

        # Nutrition
        nutrition = {"ccals": 0, "prots": 0, "fats": 0, "carbs": 0}
        nutrition = _parse_nutrition_structured(soup, nutrition)
        if all(v == 0 for v in nutrition.values()):
            nutrition = _parse_nutrition_freetext(soup, nutrition)

        return {
            "rate": rate,
            "weight": weight,
            "type_id": type_id,
            "subtype_id": subtype_id,
            **nutrition,
        }

    @staticmethod
    def parse_green_products(html_content: str) -> list[schemas.Product]:
        """Parse green-label products from modal HTML."""
        if not html_content:
            logger.info("Green products HTML is empty")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        cards = soup.find_all(class_="ProductCard")
        result = []

        for card in cards:
            try:
                link_elem = card.find(class_="ProductCard__link")
                if not link_elem:
                    continue

                product_id = link_elem.get("data-id")
                price_tag = card.find(class_="js-datalayer-catalog-list-price")
                price_text = price_tag.get_text() if price_tag else "0"
                image_tag = card.find(class_="ProductCard__imageImg")
                image = image_tag.get("src", "") if image_tag else ""
                button = card.find(class_="CartButton__content")
                exist = button.get("data-max", "0") if button else "0"

                price_match = re.findall(r"^([0-9]*[.]?[0-9]*)", price_text)
                price = float(price_match[0]) if price_match and price_match[0] else 0

                result.append(
                    schemas.Product(id=product_id, price=price, image=image, exist=exist)
                )
            except Exception as e:
                logger.exception(f"Error parsing green product: {e}")

        logger.info(f"Green products parsed: {len(result)}")
        return result


def _parse_nutrition_structured(soup: BeautifulSoup, nutrition: dict) -> dict:
    """Try to parse nutrition from structured energy elements."""
    replace_map = {
        "Ккал": "ccals",
        "Белки,г": "prots",
        "Жиры,г": "fats",
        "Углеводы,г": "carbs",
    }
    descs = soup.find_all(class_="VV23_DetailProdPageAccordion__EnergyDesc")
    values = soup.find_all(class_="VV23_DetailProdPageAccordion__EnergyValue")

    if not descs or not values:
        return nutrition

    for desc_el, val_el in zip(descs, values):
        key = desc_el.get_text(strip=True).replace(" ", "")
        if key in replace_map:
            try:
                nutrition[replace_map[key]] = float(
                    val_el.get_text(strip=True).replace(" ", "")
                )
            except ValueError:
                pass

    return nutrition


def _parse_nutrition_freetext(soup: BeautifulSoup, nutrition: dict) -> dict:
    """Fallback: parse nutrition from free-form text."""
    info = soup.find("div", {"id": "vv23-detail-page-tabs-id-1"})
    if not info:
        return nutrition

    text = info.get_text(strip=True)

    def extract(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1) or (m.group(2) if m.lastindex >= 2 else None)
            return float(val.replace(",", ".")) if val else 0
        return 0

    nutrition["ccals"] = extract(
        r"(\d+(?:[.,]\d+)?)\s*[Кк][Кк]?[Аа][Лл]|[Кк][Кк]?[Аа][Лл]\s*(\d+(?:[.,]\d+)?)"
    )
    nutrition["prots"] = extract(r"белки\s*[-:]?\s*(\d+(?:[.,]\d+)?)")
    nutrition["fats"] = extract(r"жиры\s*[-:]?\s*(\d+(?:[.,]\d+)?)")
    nutrition["carbs"] = extract(r"углеводы\s*[-:]?\s*(\d+(?:[.,]\d+)?)")

    return nutrition
