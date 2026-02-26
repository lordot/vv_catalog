import logging
import sys

from src.config import settings

logger = logging.getLogger("vv_catalog")
logger.setLevel(settings.logging_level)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)
