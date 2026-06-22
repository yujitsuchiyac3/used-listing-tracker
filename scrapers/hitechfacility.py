"""Hitech & Facility https://www.hitechfacility.co.jp/

中古測定機器専門。/cate/20/ が「最新入荷」一覧で、これが新着源。
一覧は ul.resultarea__list > li。1ページ24件程度、/cate/20/page/N でページ送り。
各カードに メーカー/型番/スペック/価格(数値 or お問い合わせ)/在庫数/管理コード/画像 が揃う。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper


class HitechFacilityScraper(Scraper):
    site = "hitechfacility"
    name = "Hitech & Facility"
    base_url = "https://www.hitechfacility.co.jp"

    NEW_PATH = "/cate/20/"  # 最新入荷

    def fetch_listings(self, max_pages: int = 10) -> List[Listing]:
        listings: List[Listing] = []
        page = 1
        while page <= max_pages:
            path = self.NEW_PATH if page == 1 else f"{self.NEW_PATH}page/{page}"
            soup = BeautifulSoup(self.get(self.base_url + path).text, "lxml")
            page_items = self._parse_list_page(soup)
            if not page_items:
                break
            listings.extend(page_items)
            if not self._has_next(soup, page):
                break
            page += 1
        return listings

    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        for li in soup.select("ul.resultarea__list > li"):
            link = li.find("a", href=True)
            if not link:
                continue
            url = self._abs(link["href"])
            m = re.search(r"/item/(\w+)", link["href"])
            uid = m.group(1) if m else url

            prod = li.select_one("dl.product")
            maker = model = ""
            if prod:
                dt = prod.find("dt"); dd = prod.find("dd")
                maker = dt.get_text(" ", strip=True) if dt else ""
                model = dd.get_text(" ", strip=True) if dd else ""

            img = li.find("img")
            image_url = self._abs(img.get("src")) if img and img.get("src") else ""

            spec_el = li.select_one("p.spec")
            name = spec_el.get_text(" ", strip=True) if spec_el else ""

            meta = self._parse_meta(li)
            price_text = meta.get("価格", "")

            items.append(Listing(
                site=self.site,
                uid=uid,
                url=url,
                maker=maker,
                model=model,
                name=name,
                spec=name,
                price=price_text,
                price_value=self._parse_price(price_text),
                condition="",  # このサイトに状態ランクは無い
                image_url=image_url,
                is_new_badge=True,
            ))
        return items

    def _parse_meta(self, li) -> dict:
        meta = {}
        for dl in li.select("div.meta dl"):
            dt = dl.find("dt"); dd = dl.find("dd")
            if dt and dd:
                meta[dt.get_text(strip=True)] = dd.get_text(" ", strip=True)
        return meta

    def _has_next(self, soup: BeautifulSoup, page: int) -> bool:
        return bool(soup.select_one(f'a[href*="/cate/20/page/{page + 1}"]'))

    def _abs(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return self.base_url + href

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        # 「1,760,000 円(税込)」→ 1760000 / 「お問い合わせ」→ None
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else None
