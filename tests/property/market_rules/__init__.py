from datetime import date
from typing import Final

MARKET_OPTIONS: Final = ("A_SHARE", "HONG_KONG", "UNITED_STATES")
EXPIRY_DATES: Final = {
    "A_SHARE": date(2024, 1, 1),
    "HONG_KONG": date(2024, 1, 2),
    "UNITED_STATES": date(2024, 1, 3),
}
