"""EHI株式会社 https://ehi.co.jp/  中古科学機器(分析・理化学)専門。

WordPress。在庫一覧 /category/item/ が新しい順。1商品は <article>:
h3.item-name(管理番号【メーカー】名称 型番)/div.field-model-number/div.field-maker/
div.item-price(¥xxx 税込)。詳細は https://ehi.co.jp/<投稿ID>/ 。
新着判定は投稿IDのスナップショット差分。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper

LIST_URL = "https://ehi.co.jp/category/item"


class EhiScraper(Scraper):
    site = "ehi"
    name = "EHI(中古科学機器)"
    base_url = "https://ehi.co.jp"

    def __init__(self, max_pages: int = 3, request_interval: float = 1.0):
        super().__init__(request_interval=request_interval)
        self.max_pages = max_pages

    def fetch_listings(self) -> List[Listing]:
        by_uid = {}
        for page in range(1, self.max_pages + 1):
            url = LIST_URL + ("/" if page == 1 else f"/page/{page}/")
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
        for art in soup.find_all("article"):
            link = art.find("a", href=re.compile(r"ehi\.co\.jp/\d+/"))
            if not link:
                continue
            m = re.search(r"ehi\.co\.jp/(\d+)/", link["href"])
            uid = m.group(1) if m else link["href"]
            url = link["href"]

            title_el = art.select_one(".item-name")
            title = title_el.get_text(" ", strip=True) if title_el else ""

            maker_el = art.select_one(".field-maker")
            maker = re.sub(r"^メーカー[:：]\s*", "",
                           maker_el.get_text(" ", strip=True)) if maker_el else ""
            model_el = art.select_one(".field-model-number")
            model = re.sub(r"^型番[:：]\s*", "",
                           model_el.get_text(" ", strip=True)) if model_el else ""

            price_el = art.select_one(".item-price")
            price_value = self._parse_price(price_el.get_text() if price_el else "")
            price = f"{price_value:,}円(税込)" if price_value is not None else ""

            name = self._clean_name(title, maker)

            img = art.find("img")
            image_url = ""
            if img:
                src = img.get("src") or img.get("data-src") or ""
                image_url = src if src.startswith("http") else (self.base_url + src if src else "")

            items.append(Listing(
                site=self.site, uid=uid, url=url,
                maker=maker, model=model, name=name, spec="",
                price=price, price_value=price_value,
                condition="中古", image_url=image_url, is_new_badge=True,
            ))
        return items

    @staticmethod
    def _clean_name(title: str, maker: str) -> str:
        # "4520【KUBOTA】アングルローター　型番：RA-5" -> "アングルローター"
        s = re.sub(r"^\d+\s*", "", title)
        s = re.sub(r"【[^】]*】", "", s)
        s = re.sub(r"[　\s]*型番[:：].*$", "", s)
        return s.strip("　 ")

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        m = re.search(r"([\d,]+)", text or "")
        if not m:
            return None
        digits = m.group(1).replace(",", "")
        return int(digits) if digits.isdigit() else None
