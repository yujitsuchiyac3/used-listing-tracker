"""ZAI 理化学機器のリユースマーケット https://zai.zaico.co.jp/

zaico製。トップが在庫一覧(新しい順)。1商品は a.d-block > div.item_block:
span.item_status(問合せあり/商談中/売却済 等)/span.item_title(名称)。
詳細は /inventories/<id> 。価格・メーカーは一覧に出ないことが多く名称中心。
新着判定は inventory id のスナップショット差分。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper

BASE = "https://zai.zaico.co.jp"


class ZaiScraper(Scraper):
    site = "zai"
    name = "ZAI(理化学リユース)"
    base_url = BASE

    def __init__(self, max_pages: int = 3, request_interval: float = 1.0):
        super().__init__(request_interval=request_interval)
        self.max_pages = max_pages

    def fetch_listings(self) -> List[Listing]:
        by_uid = {}
        for page in range(1, self.max_pages + 1):
            url = f"{BASE}/?page={page}"
            soup = self.get_soup(url)
            items = self._parse_list_page(soup)
            if not items:
                break
            added = 0
            for it in items:
                if it.uid not in by_uid:
                    by_uid[it.uid] = it
                    added += 1
            if added == 0:
                break
        return list(by_uid.values())

    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        for a in soup.select("a.d-block[href*='/inventories/']"):
            m = re.search(r"/inventories/(\d+)", a["href"])
            uid = m.group(1) if m else a["href"]
            url = a["href"] if a["href"].startswith("http") else BASE + a["href"]

            title_el = a.select_one(".item_title")
            name = title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)

            status_el = a.select_one(".item_status")
            condition = status_el.get_text(" ", strip=True) if status_el else ""

            price_value = self._parse_price(a.get_text(" ", strip=True))
            price = f"{price_value:,}円" if price_value is not None else ""

            img = a.find("img")
            image_url = ""
            if img and (img.get("src") or img.get("data-src")):
                image_url = img.get("src") or img.get("data-src")

            items.append(Listing(
                site=self.site, uid=uid, url=url,
                maker="", model="", name=name, spec="",
                price=price, price_value=price_value,
                condition=condition, image_url=image_url, is_new_badge=True,
            ))
        return items

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        m = re.search(r"[¥￥]\s*([\d,]+)", text or "")
        if not m:
            return None
        digits = m.group(1).replace(",", "")
        return int(digits) if digits.isdigit() else None
