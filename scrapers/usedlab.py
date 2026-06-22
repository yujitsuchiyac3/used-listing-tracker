"""中古研究機器.com https://used-lab.com/

WordPress。商品は /news/<slug>/ 投稿で、トップの「新着ニュース」一覧に
日付・カテゴリ・タイトル付きで並ぶ。商品はカテゴリ「新着製品」「仕入情報」で
判別できる(空カテゴリはカテゴリメニューなので除外)。
価格(税抜)・保証は詳細ページにある。商品画像は基本的に無い。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper

TOP_URL = "https://used-lab.com/"
PRODUCT_CATEGORIES = {"新着製品", "仕入情報"}


class UsedLabScraper(Scraper):
    site = "usedlab"
    name = "中古研究機器.com"
    base_url = "https://used-lab.com"

    def fetch_listings(self, enrich: bool = False) -> List[Listing]:
        soup = self.get_soup(TOP_URL)
        listings = self._parse_top(soup)
        if enrich:
            for it in listings:
                try:
                    self._enrich_detail(it)
                except Exception:
                    pass
        return listings

    def _parse_top(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        sec = soup.find("section", class_="top_news")
        if not sec:
            return items
        seen = set()
        for li in sec.select("li"):
            cat_el = li.select_one(".category")
            cat = cat_el.get_text(strip=True) if cat_el else ""
            if cat not in PRODUCT_CATEGORIES:
                continue
            link = li.find("a", href=True)
            if not link:
                continue
            url = link["href"]
            uid = self._slug(url)
            if uid in seen:
                continue
            seen.add(uid)

            title = link.get_text(" ", strip=True)
            date_el = li.select_one(".date")
            date = date_el.get_text(strip=True) if date_el else ""
            maker, _name, model = self._parse_title(title)

            items.append(Listing(
                site=self.site,
                uid=uid,
                url=url,
                maker=maker,
                model=model,
                name=title,           # 書式が一定でないためタイトル全文を保持
                spec="",
                price="",
                price_value=None,
                condition=cat,        # 新着製品 / 仕入情報
                listed_date=date,
                image_url="",
                is_new_badge=True,
            ))
        return items

    def _enrich_detail(self, item: Listing) -> None:
        soup = self.get_soup(item.url)
        text = soup.get_text("\n", strip=True)
        m_price = re.search(r"価格[：:]\s*([\d,]+)\s*円", text)
        if m_price:
            item.price_value = int(m_price.group(1).replace(",", ""))
            item.price = f"{item.price_value:,}円(税抜)"
        m_warranty = re.search(r"保証[：:]\s*([^\n]+)", text)
        parts = []
        if m_warranty:
            parts.append("保証:" + m_warranty.group(1).strip()[:40])
        if parts:
            item.condition = " / ".join([item.condition] + parts) if item.condition else " / ".join(parts)
        h1 = soup.find("h1")
        if h1:
            mk, _nm, md = self._parse_title(h1.get_text(" ", strip=True))
            item.maker = item.maker or mk
            item.model = item.model or md

    @staticmethod
    def _slug(url: str) -> str:
        m = re.search(r"/news/([^/?#]+)", url)
        return m.group(1) if m else url

    @staticmethod
    def _parse_title(title: str):
        # "MODEL NAME　メーカー　SERIAL" / "MODEL NAME メーカー（…）"
        title = re.sub(r"【[^】]*】", "", title).strip()
        segs = [s for s in re.split(r"　", title) if s.strip()]
        head = segs[0] if segs else title
        maker = segs[1] if len(segs) >= 2 else ""
        maker = re.sub(r"[（(].*?[）)]", "", maker).strip()
        if " " in head:
            model, name = head.split(" ", 1)
        else:
            model, name = head, ""
        return maker, name.strip(), model.strip()
