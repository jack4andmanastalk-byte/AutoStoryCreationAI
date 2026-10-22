"""Source specific acquisition logic."""

from .aozora import (  # noqa: F401
    AozoraSource,
    CardList,
    load_ndc_map,
    parse_japanese_year,
    parse_legacy_card_csv,
    parse_nuxt_payload,
    parse_official_card_csv,
    parse_pages_mirror,
    sample_works,
)
from .narou import (  # noqa: F401
    BIG_GENRES,
    GENRES,
    NarouApiClient,
    NarouSource,
    NovelText,
    normalize_novel,
)
