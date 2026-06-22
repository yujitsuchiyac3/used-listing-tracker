"""オルティカ (OrutiKA) https://orutika.com/

WordPress ベース。新着商品は /product/?status=new に表形式で並ぶ。
一覧テーブルの列: 画像 / 型番 / メーカー / 主スペック(名称+スペック) / 管理番号 / 価格(税込)
コンディション(外観ランク)・付属品・備考は商品詳細ページにある。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper


class OrutikaScraper(Scraper):
    site = "orutika"
    name = "オルティカ (OrutiKA)"
    base_url = "https://orutika.com"

    LIST_URL = "https://orutika.com/product/?status=new"

    def fetch_listings(self, enrich: bool = True) -> List[Listing]:
        # 新着ページ (?status=new) は単一ページ完結。
        # /product/page/2/?status=new は 0 件を返すためページ送りはしない。
        # 確実な新着判定は本一覧の前回スナップショットとの差分で行う。
        html = self.get(self.LIST_URL).text
        soup = BeautifulSoup(html, "lxml")
        listings = self._parse_list_page(soup)
        if enrich:
            for item in listings:
                try:
                    self._enrich_detail(item)
                except Exception:
                    pass  # 詳細取得に失敗しても一覧情報は残す
        return listings

    # -- 一覧ページの解析 -------------------------------------------------
    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        items: List[Listing] = []
        table = soup.select_one("table")
        if not table:
            return items
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 6:
                continue
            img_td, model_td, maker_td, spec_td, ctrl_td, price_td = tds[:6]

            link = model_td.find("a", href=True)
            if not link:
                continue
            url = link["href"]
            m = re.search(r"/product/(\d+)/", url)
            uid = m.group(1) if m else url

            img = img_td.find("img")
            image_url = (img.get("src") or "") if img else ""

            dt = spec_td.find("dt")
            dd = spec_td.find("dd")
            name = dt.get_text(" ", strip=True) if dt else ""
            spec = dd.get_text(" ", strip=True) if dd else ""

            price_text = price_td.get_text(" ", strip=True)
            price_value = self._parse_price(price_text)

            items.append(Listing(
                site=self.site,
                uid=uid,
                url=url,
                maker=maker_td.get_text(" ", strip=True),
                model=link.get_text(" ", strip=True),
                name=name,
                spec=spec,
                price=price_text,
                price_value=price_value,
                image_url=image_url,
                is_new_badge=bool(tr.find(string=re.compile("NEW"))),
            ))
        return items

    # -- 詳細ページの解析 -------------------------------------------------
    def _enrich_detail(self, item: Listing) -> None:
        html = self.get(item.url).text
        soup = BeautifulSoup(html, "lxml")
        fields = {}
        for row in soup.select("th"):
            td = row.find_next_sibling("td")
            if td is None:
                continue
            key = row.get_text(" ", strip=True)
            val = td.get_text(" ", strip=True)
            if key:
                fields[key] = val
        appearance = fields.get("外観", "")
        note = fields.get("備考", "")
        accessory = fields.get("付属品", "")
        parts = []
        if appearance:
            parts.append(f"外観{appearance}")
        if accessory and accessory not in ("無", "なし", "-"):
            parts.append(f"付属:{accessory}")
        if note and note not in ("無", "なし", "特になし", "-"):
            parts.append(note)
        item.condition = " / ".join(parts)

    # -- ユーティリティ ---------------------------------------------------
    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None
