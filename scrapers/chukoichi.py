"""中古市場(チューコイチ) https://www.chukoichi.com/

独自PHPサイト。登録日別の一覧 searchd.php?regdate=YYYY-MM-DD が新着源。
トップに最近の登録日リンクが並ぶので、それを辿って最近の登録日ぶんを集める。
一覧は table.photolist の「2行1組」: 写真(rowspan2)+カテゴリ/機器名称/仕様/メーカー、
2行目に 商品NO(photoid)/モデルNO/税別価格。
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

    INDEX = "https://www.chukoichi.com/index.php"

    def __init__(self, recent_dates: int = 6, request_interval: float = 1.0):
        super().__init__(request_interval=request_interval)
        self.recent_dates = recent_dates

    def fetch_listings(self) -> List[Listing]:
        dates = self._recent_regdates()
        by_uid = {}
        for regdate in dates:
            url = f"{self.base_url}/searchd.php?regdate={regdate}"
            soup = self.get_soup(url)
            for item in self._parse_list_page(soup, regdate):
                by_uid[item.uid] = item
        return list(by_uid.values())

    def _recent_regdates(self) -> List[str]:
        soup = self.get_soup(self.INDEX)
        dates = []
        for a in soup.find_all("a", href=re.compile(r"searchd\.php\?regdate=")):
            m = re.search(r"regdate=(\d{4}-\d{2}-\d{2})", a["href"])
            if m and m.group(1) not in dates:
                dates.append(m.group(1))
        return dates[: self.recent_dates]

    def _parse_list_page(self, soup: BeautifulSoup, regdate: str) -> List[Listing]:
        items: List[Listing] = []
        table = soup.select_one("table.photolist")
        if not table:
            return items
        rows = table.find_all("tr", recursive=False)
        i = 0
        while i < len(rows):
            row1 = rows[i]
            photo_link = row1.find("a", href=re.compile(r"photoid="))
            if not photo_link:
                i += 1
                continue
            row2 = rows[i + 1] if i + 1 < len(rows) else None
            item = self._parse_pair(row1, row2, regdate)
            if item:
                items.append(item)
            i += 2
        return items

    def _parse_pair(self, row1, row2, regdate: str) -> Optional[Listing]:
        tds1 = row1.find_all("td", recursive=False)
        if len(tds1) < 5:
            return None
        # tds1: [写真(rowspan), カテゴリ, 機器名称, 仕様, メーカー]
        category = self._clean_code(tds1[1].get_text(" ", strip=True))
        name = tds1[2].get_text(" ", strip=True)
        spec = tds1[3].get_text(" ", strip=True)
        maker = self._clean_code(tds1[4].get_text(" ", strip=True))

        img = tds1[0].find("img")
        image_url = self._abs(img.get("src")) if img and img.get("src") else ""

        link = row1.find("a", href=re.compile(r"photoid="))
        m = re.search(r"photoid=(\d+)", link["href"])
        uid = m.group(1) if m else link["href"]
        url = self._abs(f"pro_count.php?photoid={uid}")

        model = price = ""
        price_value = None
        if row2:
            tds2 = row2.find_all("td", recursive=False)
            # tds2: [商品NO/年代, (空), モデルNO, 税別価格]
            if len(tds2) >= 4:
                model = tds2[2].get_text(" ", strip=True)
                price = tds2[3].get_text(" ", strip=True)
                price_value = self._parse_price(price)

        if price_value is not None:
            price = f"{price_value:,}円(税別)"

        return Listing(
            site=self.site,
            uid=uid,
            url=url,
            maker=maker,
            model=model,
            name=name,
            spec=spec or category,
            price=price,
            price_value=price_value,
            condition="",
            listed_date=regdate,
            image_url=image_url,
            is_new_badge=True,
        )

    @staticmethod
    def _clean_code(text: str) -> str:
        # "34：アルバック Ulvac" / "2:真空ポンプ" の先頭コードを除去
        return re.sub(r"^\s*\d+\s*[:：]\s*", "", text).strip()

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else None

    def _abs(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{self.base_url}/{href.lstrip('/')}"
