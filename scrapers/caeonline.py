"""CAE Online (日本語版) https://jp.caeonline.com/

中古半導体・試験装置の国際マーケットプレイス。カテゴリページが
「メーカー×型番」単位のカード一覧で、各カードに現在のオファー数が出る。
新しい機種が在庫に入るとカードが1枚増えるので、それを新着として拾う。

robots.txt の制約:
  - 検索・絞り込み系のクエリ(?q= ?keywords= ?sort= ?skip= ?mfr= 等)は全て Disallow
  - 個別出品ページ /listing/product/* も Disallow
許可されているのは /buy/<カテゴリ> と ?page=N のみなので、そこだけを巡回する。
そのため価格は取得できない(サイト上も一覧では非表示。詳細は問合せ)。

カテゴリは並びがメーカー名のアルファベット順で新着が先頭に来ないため、
対象カテゴリは最後のページまで辿る(MAX_PAGES で上限を設ける)。
"""
from __future__ import annotations

from typing import List, Tuple

from .base import Listing, Scraper


class CaeOnlineScraper(Scraper):
    site = "caeonline"
    name = "CAE Online"
    base_url = "https://jp.caeonline.com"

    # (カテゴリのスラッグ, 表示名) — フォロー対象に効くものだけに絞る
    CATEGORIES: List[Tuple[str, str]] = [
        ("probers", "プローバ・プローブステーション"),
        ("wafer-testing-and-metrology", "ウェーハ検査・計測"),
    ]
    PER_PAGE = 30
    MAX_PAGES = 45

    def __init__(self, request_interval: float = 1.0, max_pages: int = MAX_PAGES):
        super().__init__(request_interval=request_interval)
        self.max_pages = max_pages

    def fetch_listings(self) -> List[Listing]:
        by_uid = {}
        for slug, label in self.CATEGORIES:
            for item in self._fetch_category(slug, label):
                # 同じ機種が複数カテゴリに出る場合は先に取れた方を残す
                by_uid.setdefault(item.uid, item)
        return list(by_uid.values())

    def _fetch_category(self, slug: str, label: str) -> List[Listing]:
        items: List[Listing] = []
        for page in range(1, self.max_pages + 1):
            url = f"{self.base_url}/buy/{slug}"
            if page > 1:
                url += f"?page={page}"
            soup = self.get_soup(url)
            cards = soup.select(".model-card-small")
            if not cards:
                break
            for card in cards:
                item = self._parse_card(card, label)
                if item:
                    items.append(item)
            if len(cards) < self.PER_PAGE:
                break
        return items

    def _parse_card(self, card, label: str):
        link = card.select_one("a[href]")
        if not link:
            return None
        href = link.get("href", "")
        if not href.startswith("/buy/"):
            return None
        maker = self._text(card, ".model-card-small-manufacturer")
        model = self._text(card, ".model-card-small-model")
        offers = self._text(card, ".model-card-small-offers")
        img = card.select_one("img")
        image_url = img.get("src", "") if img else ""
        if image_url.startswith("/"):
            image_url = self.base_url + image_url

        return Listing(
            site=self.site,
            uid=href,                       # 機種ページのパスが一意キー
            url=self.base_url + href,
            maker=maker,
            model=model,
            # カテゴリ名(「プローバ…」等)は name/spec に入れない。
            # フォロー判定が maker/model/name/spec の部分一致なので、
            # カテゴリ名を入れるとそのカテゴリ全件がキーワードに一致してしまう。
            name="",
            spec="",
            price="",                       # 一覧に価格表示なし(要問合せ)
            price_value=None,
            condition=f"{label}・{offers}" if offers else label,
            image_url=image_url if image_url.startswith("http") else "",
        )

    @staticmethod
    def _text(card, selector: str) -> str:
        el = card.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""
