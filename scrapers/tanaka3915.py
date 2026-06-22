"""タナカ・トレーディング https://www.3915.jp/

新着一覧 /hp01/new_items/N.html (50件/ページ, 新着順)。価格は非表示(問い合わせ型)。
商品ブロックは #news_ititle_area 内の .wrapp_nib。タイトルは
「【中古品】メーカー 機器名 型番 管理番号NNNNN」形式で、管理番号を uid に使う。
新着順なので先頭数ページ取得 + 差分判定で十分。
"""
from __future__ import annotations

import re
import warnings
from typing import List

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .base import Listing, Scraper

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

NEW_URL = "https://www.3915.jp/hp01/new_items/{page}.html"


class Tanaka3915Scraper(Scraper):
    site = "tanaka3915"
    name = "タナカ・トレーディング"
    base_url = "https://www.3915.jp"

    def __init__(self, pages: int = 2, request_interval: float = 1.0):
        super().__init__(request_interval=request_interval)
        self.pages = pages

    def fetch_listings(self) -> List[Listing]:
        by_uid = {}
        for page in range(1, self.pages + 1):
            soup = self.get_soup(NEW_URL.format(page=page))
            page_items = self._parse_list_page(soup)
            if not page_items:
                break
            for it in page_items:
                by_uid.setdefault(it.uid, it)
        return list(by_uid.values())

    def _parse_list_page(self, soup: BeautifulSoup) -> List[Listing]:
        # 表示エリア(画像/タイトル/両方)で構成が変わるため、ページ全体から
        # 「管理番号」付きの商品リンクを集めて uid で重複排除する。
        items: List[Listing] = []
        seen = set()
        image_map = self._build_image_map(soup)
        for link in soup.find_all("a", href=re.compile(r"/hp\d+/\d+\.html")):
            title = link.get_text(" ", strip=True)
            m = re.search(r"管理番号\s*([0-9A-Za-z\-]+)", title)
            if not m:
                continue
            uid = m.group(1)
            if uid in seen:
                continue
            seen.add(uid)

            href = link.get("href", "")
            url = href if href.startswith("http") else self.base_url + href
            maker, name, model = self._parse_title(title)

            spec = ""
            blk = link.find_parent(class_=re.compile("wrapp"))
            if blk:
                spec_el = blk.select_one("p.txt_box2")
                if spec_el:
                    spec = spec_el.get_text(" ", strip=True)

            items.append(Listing(
                site=self.site,
                uid=uid,
                url=url,
                maker=maker,
                model=model,
                name=name or title,
                spec=spec,
                price="",          # 価格は問い合わせ(非表示)
                price_value=None,
                image_url=image_map.get(uid, ""),
                is_new_badge=True,
            ))
        return items

    @staticmethod
    def _build_image_map(soup: BeautifulSoup) -> dict:
        # 画像ファイル名は {管理番号}-1.JPG。uid → 画像URL の対応表を作る。
        image_map = {}
        for img in soup.find_all("img", src=re.compile(r"img\.3915\.jp/img/")):
            src = img["src"]
            m = re.search(r"/img/([0-9A-Za-z\-]+)-\d+\.\w+", src)
            if m:
                image_map.setdefault(m.group(1), src)
        return image_map

    @staticmethod
    def _parse_title(title: str):
        # "【中古品】メーカー 機器名 型番 管理番号NNNNN" を分解
        t = re.sub(r"管理番号\s*[0-9A-Za-z\-]+", "", title)
        t = re.sub(r"^\s*【[^】]*】\s*", "", t).strip()
        tokens = [x for x in re.split(r"[　\s]+", t) if x]
        if len(tokens) >= 3:
            return tokens[0], " ".join(tokens[1:-1]), tokens[-1]
        if len(tokens) == 2:
            return tokens[0], "", tokens[1]
        return "", t, ""
