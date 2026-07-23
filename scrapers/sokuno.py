"""速納.com / TechEyesOnline https://www.techeyes-sokuno.com/

MakeShop製(文字コード EUC-JP)。中古在庫は ct-CHU_ALL に全件集約されており、
/shopbrand/ct-CHU_ALL/pageN/ で新しい順に並ぶ。1商品は div.section:
p.name(【中古】メーカー 型番 名称)/p.price(税抜・税込)/div.else(メーカー 管理番号)。
新着判定は shopdetail の商品コードのスナップショット差分。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper

CHU_ALL = "https://www.techeyes-sokuno.com/shopbrand/ct-CHU_ALL"


class SokunoScraper(Scraper):
    site = "sokuno"
    name = "速納.com(TechEyes)"
    base_url = "https://www.techeyes-sokuno.com"

    def __init__(self, max_pages: int = 4, request_interval: float = 1.0):
        super().__init__(request_interval=request_interval)
        self.max_pages = max_pages

    def fetch_listings(self) -> List[Listing]:
        by_uid = {}
        for page in range(1, self.max_pages + 1):
            url = f"{CHU_ALL}/page{page}/"
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
        for name_el in soup.select("p.name"):
            sec = name_el.find_parent("li") or name_el.parent
            link = sec.find("a", href=re.compile(r"/shopdetail/"))
            if not link:
                continue
            m = re.search(r"/shopdetail/(\d+)", link["href"])
            uid = m.group(1) if m else link["href"]
            url = self._abs(link["href"])

            name_el = sec.select_one("p.name")
            name_raw = name_el.get_text(" ", strip=True) if name_el else ""

            else_el = sec.select_one("div.else")
            else_txt = else_el.get_text(" ", strip=True) if else_el else ""
            # 末尾の管理番号(例 1220051 / 1011029-F)を除去
            maker = re.sub(r"\s*\d[\w\-/]*\s*$", "", else_txt).strip()

            price_el = sec.select_one("p.price")
            price_value = self._parse_price(price_el.get_text() if price_el else "")
            price = f"{price_value:,}円(税抜)" if price_value is not None else ""

            model, disp_name = self._split_name(name_raw, maker)
            warn = "訳あり品" if "訳あり" in name_raw else ""
            condition = " ".join(x for x in [warn, "中古(再生品)"] if x)

            img = sec.find("img")
            image_url = ""
            if img and (img.get("src") or img.get("data-src")):
                src = img.get("src") or img.get("data-src")
                image_url = src if src.startswith("http") else self._abs(src)

            items.append(Listing(
                site=self.site, uid=uid, url=url,
                maker=maker, model=model, name=disp_name, spec="",
                price=price, price_value=price_value,
                condition=condition, image_url=image_url, is_new_badge=True,
            ))
        return items

    @staticmethod
    def _split_name(name_raw: str, maker: str):
        # "訳あり品【中古】アンリツ　MF76A　マイクロ波周波数カウンタ" -> (型番, 名称)
        s = re.sub(r"^(訳あり品)?\s*【中古】\s*", "", name_raw)
        if maker and s.startswith(maker):
            s = s[len(maker):]
        s = s.strip("　 ")
        parts = re.split(r"[　\s]+", s, maxsplit=1)
        model = parts[0] if parts else ""
        return model, s

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        # 先頭の「◯◯円（税抜）」を採用
        m = re.search(r"([\d,]+)\s*円", text or "")
        if not m:
            return None
        digits = m.group(1).replace(",", "")
        return int(digits) if digits.isdigit() else None

    def _abs(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{self.base_url}/{href.lstrip('/')}"
