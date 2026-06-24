"""計測器ランド リセール https://www.keisokuki-land.com/

Color Me Shop 系。中古商品一覧 /SHOP/319016/t01/list.html を ITEMLIST フォーム
(POST, PAGE フィールド)でページングする。標準順が新着順とは限らないため、
確実な新着検知のために全ページを巡回して全 UKK-管理番号を集め、差分で判定する。
商品タイトルは「中古 メーカー 機器名 型番 (管理番号：UKK-xxxx)」形式。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper

LIST_POST_URL = "https://www.keisokuki-land.com/SHOP/319016/t01/list.html"
ITEM_URL = "https://www.keisokuki-land.com/SHOP/{uid}.html"


class KeisokukiScraper(Scraper):
    site = "keisokuki"
    name = "計測器ランド リセール"
    base_url = "https://www.keisokuki-land.com"

    LIST_GET_URL = "https://www.keisokuki-land.com/SHOP/319016/list.html"

    def fetch_listings(self, max_pages: int = 30) -> List[Listing]:
        import time as _t
        by_uid = {}
        try:
            for page in range(1, max_pages + 1):
                data = {"PAGE": page, "Type": "01", "Search": "",
                        "m": "319016", "s": "", "g": "", "y": "", "b": ""}
                resp = self.session.post(LIST_POST_URL, data=data, timeout=30)
                resp.raise_for_status()
                _t.sleep(self.request_interval)
                soup = BeautifulSoup(resp.content, "lxml")
                page_items = self._parse_list_page(soup)
                if not page_items:
                    break
                new_here = 0
                for it in page_items:
                    if it.uid not in by_uid:
                        new_here += 1
                    by_uid[it.uid] = it
                if new_here == 0:  # これ以上新しい商品が出てこない
                    break
        except Exception:
            # POST一覧API(t01)が一時的に503等になる場合があるため、
            # 通常のGET一覧(1ページ目=新着40件相当)にフォールバックする。
            if not by_uid:
                soup = BeautifulSoup(self.get(self.LIST_GET_URL).content, "lxml")
                for it in self._parse_list_page(soup):
                    by_uid[it.uid] = it
            if not by_uid:
                raise
        return list(by_uid.values())

    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        for sec in soup.select("section.column4"):
            link = sec.find("a", href=re.compile(r"/SHOP/UKK-\d+\.html"))
            if not link:
                continue
            m = re.search(r"(UKK-\d+)", link["href"])
            uid = m.group(1) if m else link["href"]
            title = link.get("title") or link.get_text(" ", strip=True)

            maker, name, model = self._parse_title(title)

            img = sec.find("img")
            image_url = ""
            if img and img.get("src"):
                image_url = img["src"].split("?")[0]  # キャッシュバスター除去

            price_el = sec.select_one(".selling_price")
            price_text = price_el.get_text(" ", strip=True) if price_el else ""
            price_value = self._parse_price(price_text)
            price = f"{price_value:,}円(税込)" if price_value is not None else price_text

            stock_el = sec.select_one(".sps-itemList-stockDisp")
            stock = stock_el.get_text(" ", strip=True).replace("在庫", "").strip() if stock_el else ""

            items.append(Listing(
                site=self.site,
                uid=uid,
                url=ITEM_URL.format(uid=uid),
                maker=maker,
                model=model,
                name=name or title,
                price=price,
                price_value=price_value,
                condition=stock,
                image_url=image_url,
                is_new_badge=True,
            ))
        return items

    @staticmethod
    def _parse_title(title: str):
        # "中古 メーカー 機器名 型番 (管理番号：UKK-xxxx)" を分解
        t = re.sub(r"[（(]管理番号[^）)]*[）)]", "", title).strip()
        t = re.sub(r"^\s*中古\s*", "", t)
        tokens = [x for x in re.split(r"[　\s]+", t) if x]
        if len(tokens) >= 3:
            return tokens[0], " ".join(tokens[1:-1]), tokens[-1]
        if len(tokens) == 2:
            return tokens[0], "", tokens[1]
        return "", t, ""

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else None
