"""アスカインデックス https://stocks.askindex.co.jp/

WordPress(Cocoon)ベース。掲載日フィルタ create_from=YYYY/MM/DD を持つ。
新着は /search/?create_from=<date>&cat_cd=<cat>&page_no=<n> で取得。
1ページ40件、page_no でページ送り。価格は常に「お問合せください」で
金額非表示。状態ランクは無い。カテゴリで対象を絞れる(cat_cd)。
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import List

from bs4 import BeautifulSoup

from .base import Listing, Scraper

# cat_cd → 表示名(参考)
CATEGORY_NAMES = {
    "bt": "測定器・計測器",
    "bg": "理化学機器・研究開発",
    "bx": "半導体(前工程)",
    "by": "半導体(後工程)",
}

PER_PAGE = 40


class AskindexScraper(Scraper):
    site = "askindex"
    name = "アスカインデックス"
    base_url = "https://stocks.askindex.co.jp"

    SEARCH_URL = "https://stocks.askindex.co.jp/search/"

    def __init__(self, categories=("bg", "bx", "by"), lookback_days: int = 7,
                 request_interval: float = 1.0):
        super().__init__(request_interval=request_interval)
        self.categories = list(categories)
        self.lookback_days = lookback_days

    def fetch_listings(self) -> List[Listing]:
        create_from = (date.today() - timedelta(days=self.lookback_days)).strftime("%Y/%m/%d")
        by_uid = {}
        for cat in self.categories:
            for item in self._fetch_category(cat, create_from):
                by_uid[item.uid] = item  # uid で重複排除
        return list(by_uid.values())

    def _fetch_category(self, cat: str, create_from: str) -> List[Listing]:
        items: List[Listing] = []
        page = 1
        while True:
            params = {"create_from": create_from, "cat_cd": cat, "page_no": page}
            soup = BeautifulSoup(self.get(self.SEARCH_URL, params=params).text, "lxml")
            page_items = self._parse_list_page(soup)
            items.extend(page_items)
            if len(page_items) < PER_PAGE:
                break  # 最終ページ
            page += 1
            if page > 50:
                break  # 安全弁
        return items

    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        for li in soup.select("li.result_list_item"):
            link = li.find("a", href=True)
            if not link:
                continue
            url = link["href"]
            m = re.search(r"code=(\w+)", url)
            uid = m.group(1) if m else url

            code_el = li.select_one(".result_code")
            if code_el:
                # "ASK管理No：Q60577" → "Q60577"
                uid = code_el.get_text(strip=True).split("：")[-1].strip() or uid

            img = li.select_one(".result_img img, .result_img source")
            image_url = (img.get("src") or img.get("srcset") or "") if img else ""

            name_el = li.select_one(".result_name")
            name = name_el.get_text(" ", strip=True) if name_el else ""

            maker = model = ""
            for tag in li.select(".result_tag"):
                label_el = tag.find("span")
                label = label_el.get_text(strip=True) if label_el else ""
                value = tag.get_text(" ", strip=True).replace(label, "", 1).strip()
                if "メーカー" in label:
                    maker = value
                elif "モデル" in label or "型式" in label:
                    model = value

            price_el = li.select_one(".result_price")
            price = ""
            if price_el:
                ps = price_el.find("span")
                price = price_el.get_text(" ", strip=True).replace(
                    ps.get_text(strip=True) if ps else "", "", 1).strip()

            items.append(Listing(
                site=self.site,
                uid=uid,
                url=url,
                maker=maker,
                model=model,
                name=name,
                price=price,            # 多くは「お問合せください」、一部実価格
                price_value=self._parse_price(price),
                image_url=image_url,
                is_new_badge=True,      # create_from で絞った新着相当
            ))
        return items

    @staticmethod
    def _parse_price(text: str):
        # 「お問合せください」等は数値なし。「550,000円(税込)」→ 550000
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else None
