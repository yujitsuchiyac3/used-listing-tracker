"""測定器市場 http://sokuteiki-market.com/

中古計測器の販売サイト。/shop/category/all-product.php が全在庫の一覧表で、
1リクエストで全件(管理番号/メーカー/品名/型番/仕様/価格)が取れる。

文字コードは EUC-JP。XHTML の宣言のせいで bs4 の自動判定が外れるため、
明示的に euc_jp でデコードしてから解析する。
"""
from __future__ import annotations

import re
from typing import List, Optional

from .base import Listing, Scraper

ITEM_RE = re.compile(r"item(\d+)\.html")


class SokuteikiMarketScraper(Scraper):
    site = "sokuteikimarket"
    name = "測定器市場"
    base_url = "http://sokuteiki-market.com"

    ALL_PRODUCTS = "http://sokuteiki-market.com/shop/category/all-product.php"

    def fetch_listings(self) -> List[Listing]:
        from bs4 import BeautifulSoup
        resp = self.get(self.ALL_PRODUCTS)
        soup = BeautifulSoup(resp.content.decode("euc_jp", "replace"), "lxml")

        items: List[Listing] = []
        seen = set()
        for tr in soup.find_all("tr"):
            link = tr.find("a", href=ITEM_RE)
            if not link:
                continue
            item = self._parse_row(tr, link)
            if item and item.uid not in seen:
                seen.add(item.uid)
                items.append(item)
        return items

    def _parse_row(self, tr, link) -> Optional[Listing]:
        tds = tr.find_all("td")
        if len(tds) < 6:
            return None
        # [管理番号, メーカー, 品名, 型番, 仕様, 標準価格, 詳細]
        ctrl_no = self._clean(tds[0])
        maker = self._clean(tds[1])
        name = re.sub(r"\s*中古\s*$", "", self._clean(tds[2]))
        model = self._clean(tds[3])
        spec = self._clean(tds[4])
        price_text = self._clean(tds[5])

        m = ITEM_RE.search(link.get("href", ""))
        uid = ctrl_no or (m.group(1) if m else "")
        if not uid:
            return None

        price_value = self._parse_price(price_text)
        price = f"{price_value:,}円(税込)" if price_value is not None else price_text

        return Listing(
            site=self.site,
            uid=uid,
            url=self._abs(link.get("href", "")),
            maker=maker,
            model=model,
            name=name,
            spec=spec[:400],
            price=price,
            price_value=price_value,
            condition="中古",
        )

    @staticmethod
    def _clean(td) -> str:
        return re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        m = re.search(r"([\d,]+)\s*円", text or "")
        if not m:
            return None
        digits = m.group(1).replace(",", "")
        return int(digits) if digits.isdigit() else None

    def _abs(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{self.base_url}/{href.lstrip('/')}"
