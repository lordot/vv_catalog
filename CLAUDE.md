# vv_catalog — Shared Catalog Service

> **IMPORTANT**: Update this file whenever architectural changes are made (new endpoints, crawler changes, parser changes, new product categories).

**Repo**: github.com/lordot/vv_catalog
**Stack**: Python, FastAPI, PostgreSQL, SQLAlchemy, aiohttp
**Entry**: `main.py` -> `src/api.py` — Uvicorn on port 8000

## Directory Structure

```
vv_catalog/
├── main.py                # Uvicorn entry: runs src.api:app on port 8000
├── Dockerfile
├── requirements.txt
├── static/                # Cached product images, index.html (catalog viewer)
├── src/
│   ├── api.py             # FastAPI app, lifespan (starts crawler), all endpoints
│   ├── config.py          # Pydantic Settings + PAGES/FAMILY_PAGES/MANUAL_SUBTYPES constants
│   ├── crawler.py         # Background catalog crawler (INIT + CONTINUOUS modes)
│   ├── db.py              # PostgreSQL engine + SessionLocal
│   ├── models.py          # SQLAlchemy models: Product, Type, SubType
│   ├── schemas.py         # Pydantic schemas for products
│   ├── seed.py            # Initial reference data seeding (types, subtypes)
│   ├── logger.py
│   └── rest/
│       ├── fetcher.py     # CatalogFetcher — HTTP client to vkusvill.ru with rate limiting
│       ├── parser.py      # ProductParser — HTML/JSON parser for VkusVill catalog pages
│       └── classifier.py  # Product classification logic
```

## API Endpoints (`src/api.py`)

No `/api` prefix — endpoints are at root level.

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Static index.html (catalog viewer) |
| GET | /products | All products with type/subtype info |
| GET | /types | Product types with counts |
| GET | /subtypes | Product subtypes with counts and URLs |
| POST | /products/{id}/rescan | Re-fetch single product details |
| POST | /subtypes/{id}/scan | Scan all products in a subtype |
| POST | /scan | Force full catalog rescan |

## Crawler (`src/crawler.py`)

Background task started in FastAPI lifespan. Two modes:

1. **INIT mode**: If DB is empty, crawl all sections without pauses
2. **CONTINUOUS mode**: Infinite loop, crawl all sections with 30-min pauses between sections

**Crawl cycle**: For each section in `PAGES`:
1. Paginate through catalog pages (`?PAGEN_1=N`)
2. Parse products from HTML
3. Upsert into PostgreSQL (ON CONFLICT DO UPDATE)
4. Remove stale products not found in current crawl
5. Crawl family-format sections (`FAMILY_PAGES`) — updates `count=2`
6. Fetch product details (nutrition, weight, etc.) for products with links

**Rate limiting**: `request_delay=2s` between HTTP requests, `section_pause=1800s` (30 min) between sections.

**Force scan** (`POST /scan`): Cancels continuous crawler, runs full cycle without pauses, restarts continuous crawler.

## Product Categories (`src/config.py`)

13 sections configured in `PAGES` tuple:
- Завтраки (омлеты, сырники, каши, блины)
- Вторые блюда, Супы, Салаты
- Роллы и сеты, Сендвичи/шаурма/бургеры
- Пироги, Десерты, Круассаны, Онигири

2 family-format sections in `FAMILY_PAGES`.

4 manual subtypes in `MANUAL_SUBTYPES` (паста, пицца, драники, онигири).

## Database

**PostgreSQL** (shared across all users):
- `Product`: id, name, type_id, subtype_id, count, image, link, ccals, prots, fats, carbs, rate, weight, last_updated
- `Type`: id, name, enabled
- `SubType`: id, name, breakfast/soup/lunch/snack/dinner/dessert flags

Connection: `postgresql+psycopg2://vv:vv@postgres:5432/vv_catalog` (configurable via `DB_URL`).

## Inter-Service Communication

```
vv_api  -->  vv_catalog (reads catalog via shared PostgreSQL)
vv_catalog  -->  vkusvill.ru (crawls catalog pages via HTTP)
```

- **Inbound**: vv_api reads from the same PostgreSQL database (via `catalog_db_url` in vv_api config)
- **Outbound**: Crawls vkusvill.ru catalog pages for product data
- **No direct HTTP API calls from other services** — data shared via PostgreSQL

## Environment Variables (via Pydantic Settings)

| Variable | Default | Description |
|----------|---------|-------------|
| LOGGING_LEVEL | INFO | Log level |
| BASE_URL | https://vkusvill.ru | VkusVill website URL |
| BOT_PROXY | None | SOCKS5 proxy for VkusVill requests |
| DB_URL | postgresql+psycopg2://vv:vv@postgres:5432/vv_catalog | PostgreSQL connection |
| REQUEST_DELAY | 2.0 | Seconds between HTTP requests |
| SECTION_PAUSE | 1800.0 | Seconds between sections in CONTINUOUS mode |
| RETRY_BASE_DELAY | 5.0 | Base delay on 502 retry |
| RETRY_MAX_DELAY | 60.0 | Max delay on 502 retry |

## Common Issues

- **502 from vkusvill.ru**: Transient errors during crawling. Fetcher has retry with exponential backoff.
- **Stale products**: Crawler removes products not found in current crawl cycle per subtype.
- **Long initial load**: INIT mode crawls all 13+ sections sequentially. Can take 10+ minutes.
