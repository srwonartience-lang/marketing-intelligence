from typing import Optional

from collectors.site_parsers.base import SiteParser
from collectors.site_parsers.shopee_ads import ShopeeAdsParser
from collectors.site_parsers.tiktok_ads import TikTokAdsParser

# 새 사이트는 파서 클래스를 만들어 여기에 등록하면 된다.
_PARSERS: list[SiteParser] = [TikTokAdsParser(), ShopeeAdsParser()]


def find_parser(url: str) -> Optional[SiteParser]:
    """url을 처리할 수 있는 파서를 반환한다. 없으면 None."""
    for parser in _PARSERS:
        if parser.matches(url or ""):
            return parser
    return None
