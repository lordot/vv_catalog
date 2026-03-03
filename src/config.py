from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    logging_level: str = "INFO"
    base_url: str = "https://vkusvill.ru"
    bot_proxy: str | None = None
    db_url: str = "postgresql+psycopg2://vv:vv@postgres:5432/vv_catalog"

    # Crawler timing
    request_delay: float = 2.0          # seconds between HTTP requests
    section_pause: float = 1800.0       # seconds between sections (30 min) in CONTINUOUS mode
    retry_base_delay: float = 5.0       # base delay on 502 retry
    retry_max_delay: float = 60.0       # max delay on 502 retry

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Page URLs for product categories: (path, subtype_id, name_filter)
PAGES: tuple = (
    ("/goods/gotovaya-eda/zavtraki/omlety-i-zavtraki-s-yaytsom/", 9, None),
    ("/goods/gotovaya-eda/vtorye-blyuda/", 1, None),
    ("/goods/gotovaya-eda/zavtraki/syrniki-zapekanki-i-rikotniki/", 4, None),
    ("/goods/gotovaya-eda/zavtraki/kashi/", 10, None),
    ("/goods/gotovaya-eda/zavtraki/bliny-i-oladi/", 8, None),
    ("/goods/gotovaya-eda/supy/", 3, None),
    ("/goods/gotovaya-eda/salaty/", 2, None),
    ("/goods/gotovaya-eda/rolly-i-sety/", 7, None),
    ("/goods/gotovaya-eda/sendvichi-shaurma-i-burgery/", 5, None),
    ("/goods/gotovaya-eda/pirogi-pirozhki-i-lepyeshki/", 12, None),
    ("/goods/sladosti-i-deserty/pirozhnye-i-deserty/", 13, None),
    ("/goods/khleb-i-vypechka/kruassany/", 14, None),
    ("/goods/gotovaya-eda/onigiri/", 18, None),
)

FAMILY_PAGES: tuple = (
    "/goods/gotovaya-eda/semeynyy-format/",
    "/goods/sladosti-i-deserty/semeynyy-format/",
)

MANUAL_SUBTYPES: tuple = (
    ("паста", 15),
    ("пицца", 16),
    ("драники", 17),
    ("онигири", 18),
)
