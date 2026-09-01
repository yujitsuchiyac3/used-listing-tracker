"""中古市場(チューコイチ) https://www.chukoichi.com/

2026年のサイト刷新で URL 体系が変わった(旧 searchd.php?regdate= は廃止)。
現行は検索ページ /search?sort=new が新着順の一覧で、1ページ24件・末尾に
`/search?page=N` のページャがある。商品ページは /item/<id>。

一覧カードから 名称/メーカー・型式/価格/管理番号/画像 が取れるので、巡回は
一覧だけで行い(既定は全ページ)、新着のみ詳細ページ /item/<id> の仕様表から
メーカー・型式・掲載日を正確に補完する。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper


class ChukoichiScraper(Scraper):
    site = "chukoichi"
    name = "中古市場(チューコイチ)"
    base_url = "https://www.chukoichi.com"

    SEARCH = "https://www.chukoichi.com/search?sort=new"
    MAX_PAGES_CAP = 300  # 暴走防止

    def __init__(self, max_pages: Optional[int] = None, request_interval: float = 1.0):
        """max_pages=None で全ページ巡回。数字を渡すと新着順の先頭Nページのみ。"""
        super().__init__(request_interval=request_interval)
        self.max_pages = max_pages

    def fetch_listings(self, enrich: bool = False) -> List[Listing]:
        soup = self.get_soup(self.SEARCH)
        last = self._last_page(soup)
        limit = min(last, self.max_pages or last, self.MAX_PAGES_CAP)

        by_uid = {}
        for item in self._parse_list_page(soup):
            by_uid[item.uid] = item
        for page in range(2, limit + 1):
            soup = self.get_soup(f"{self.SEARCH}&page={page}")
            page_items = self._parse_list_page(soup)
            if not page_items:
                break
            for item in page_items:
                by_uid[item.uid] = item

        items = list(by_uid.values())
        if enrich:
            for item in items:
                self._enrich_detail(item)
        return items

    def _last_page(self, soup: BeautifulSoup) -> int:
        pages = [int(m) for m in re.findall(r"[?&]page=(\d+)", str(soup))]
        return max(pages) if pages else 1

    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        for card in soup.select("a.card"):
            item = self._parse_card(card)
            if item:
                items.append(item)
        return items

    def _parse_card(self, card) -> Optional[Listing]:
        href = card.get("href", "")
        m = re.search(r"/item/(\d+)", href)
        if not m:
            return None
        uid = m.group(1)

        name = self._text(card.select_one(".card-name"))
        maker, model = self._split_maker_model(self._text(card.select_one(".card-sub")))
        price = self._text(card.select_one(".card-price"))
        price_value = self._parse_price(price)
        if price_value is not None:
            price = f"{price_value:,}円(税別)"

        # 管理番号は spec に入れない(番号中の数字が型番キーワードに誤ヒットするため)。
        # フォロー判定の対象外である condition に置いて表示だけ残す。
        control_no = self._text(card.select_one(".card-meta"))

        img = card.select_one("img")
        image_url = self._abs(img.get("src")) if img and img.get("src") else ""

        return Listing(
            site=self.site,
            uid=uid,
            url=self._abs(href),
            maker=maker,
            model=model,
            name=name,
            spec="",
            price=price,
            price_value=price_value,
            condition=control_no,
            listed_date="",
            image_url=image_url,
            is_new_badge=False,
        )

    def _enrich_detail(self, item: Listing) -> None:
        """商品ページの仕様表からメーカー/型式/掲載日を正確に補完する。"""
        try:
            soup = self.get_soup(item.url)
        except Exception:
            return
        table = soup.select_one("table.spec")
        if not table:
            return
        fields = {}
        for tr in table.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                fields[th.get_text(" ", strip=True)] = td.get_text(" ", strip=True)

        item.maker = fields.get("メーカー", item.maker)
        item.model = fields.get("型式", item.model)
        item.name = fields.get("機器名", item.name)
        item.listed_date = fields.get("掲載日", item.listed_date)
        extra = " ".join(v for k, v in fields.items()
                         if k in ("仕様", "備考", "付属品", "状態"))
        if extra:
            item.spec = " ".join(p for p in (item.spec, extra) if p)
        if fields.get("管理番号"):
            item.condition = f"管理番号 {fields['管理番号']}"

    @staticmethod
    def _split_maker_model(sub: str) -> tuple:
        """カードの "メーカー 型式" 表記を分ける。

        型式は末尾1トークンであることが多い(例: "アズワン As one ASU-6")。
        分割を誤ってもフォロー判定は全フィールド連結で行うため影響はなく、
        新着分は詳細ページの仕様表で上書きされる。
        """
        parts = sub.split()
        if len(parts) >= 2:
            return " ".join(parts[:-1]), parts[-1]
        return "", sub

    @staticmethod
    def _text(node) -> str:
        return node.get_text(" ", strip=True) if node else ""

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        # "お問い合わせください" など数字が無いものは None
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else None

    def _abs(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{self.base_url}/{href.lstrip('/')}"
