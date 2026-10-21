"""スターテクノロジー https://startechnology.jp/

中古計測器専門(EC-CUBE)。カテゴリ別一覧 products/list.php?category_id=N を
orderby=date(新着順)で取得し、各カテゴリの新しい順ぶんを集める。
1商品は div.vlistp。型番(vlistname)/メーカー(vlistmaker)/価格税別(vlistprice)/
説明(vlistcomment)/画像/状態(vliststatus)。新着判定は product_id のスナップショット差分。
"""
from __future__ import annotations

import re
import warnings
from typing import List, Optional

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .base import Listing, Scraper

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# category_id -> 表示名
CATEGORIES = {
    "10001": "スペクトラムアナライザ/FFT", "10002": "ネットワークアナライザ",
    "10003": "発振器・信号発生器", "10004": "LCR/インピーダンス/半導体",
    "10005": "オーディオ/TV/ビデオ", "10006": "無線機テスタ",
    "10007": "オシロスコープ", "10008": "パワーメータ/センサ",
    "10009": "マルチメータ/カウンタ", "10010": "光測定器",
    "10011": "電源関連機器", "10012": "ロジック/プロトコル",
    "10013": "記録計", "10014": "パーツ/アクセサリ", "10015": "その他測定器",
}
LIST_URL = "https://startechnology.jp/products/list.php"


class StarTechnologyScraper(Scraper):
    site = "startechnology"
    name = "スターテクノロジー"
    base_url = "https://startechnology.jp"

    def __init__(self, categories=None, pages_per_cat: Optional[int] = None,
                 new_pages_per_cat: int = 2, request_interval: float = 1.0):
        """pages_per_cat=None で各カテゴリを全ページ巡回(フォロー・全在庫用)。
        新着判定は各カテゴリの新しい順の先頭 new_pages_per_cat ページだけで行う。"""
        super().__init__(request_interval=request_interval)
        self.categories = list(categories) if categories else list(CATEGORIES)
        self.pages_per_cat = pages_per_cat
        self.new_pages_per_cat = new_pages_per_cat

    def fetch_listings(self) -> List[Listing]:
        by_uid = {}
        self.new_window_uids = set()
        for cat in self.categories:
            page = 1
            seen_cat = set()
            while self.pages_per_cat is None or page <= self.pages_per_cat:
                params = {"category_id": cat, "orderby": "date", "pageno": page}
                soup = self.get_soup(LIST_URL, params=params)
                items = self._parse_list_page(soup)
                if not items:
                    break
                added = 0
                for it in items:
                    if it.uid not in seen_cat:
                        seen_cat.add(it.uid)
                        added += 1
                    by_uid.setdefault(it.uid, it)
                    if page <= self.new_pages_per_cat:
                        self.new_window_uids.add(it.uid)
                if added == 0:      # このカテゴリはこれ以上ページが無い
                    break
                page += 1
        return list(by_uid.values())

    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        for vp in soup.select("div.vlistp"):
            name_a = vp.select_one(".vlistname a")
            if not name_a:
                continue
            href = name_a.get("href", "")
            m = re.search(r"product_id=(\d+)", href)
            uid = m.group(1) if m else href
            url = href if href.startswith("http") else self.base_url + href

            model = name_a.get_text(" ", strip=True)

            maker_a = vp.select_one(".vlistmaker a")
            maker = maker_a.get_text(" ", strip=True) if maker_a else ""

            comment = vp.select_one(".vlistcomment")
            name = comment.get_text(" ", strip=True) if comment else ""

            price_el = vp.select_one(f"#price02_default_{uid}") or vp.select_one(".vlistprice")
            price_text = price_el.get_text(" ", strip=True) if price_el else ""
            price_value = self._parse_price(price_text)
            price = f"{price_value:,}円(税別)" if price_value is not None else ""

            img = vp.select_one(".vlistphoto img")
            image_url = ""
            if img and img.get("src"):
                src = img["src"]
                image_url = src if src.startswith("http") else self.base_url + src

            status = vp.select_one(".vliststatus")
            condition = status.get_text(" ", strip=True) if status else ""

            items.append(Listing(
                site=self.site,
                uid=uid,
                url=url,
                maker=maker,
                model=model,
                name=name,
                spec="",
                price=price,
                price_value=price_value,
                condition=condition,
                image_url=image_url,
                is_new_badge=True,
            ))
        return items

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        # "販売価格(税別)：690,000 円" → 690000 / お問い合わせ等 → None
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else None
