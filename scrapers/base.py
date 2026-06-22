"""共通インターフェース。

各サイトのスクレイパーは Scraper を継承し、fetch_listings() で
Listing のリストを返す。サイト固有の癖はここに閉じ込める。
"""
from __future__ import annotations

import dataclasses
import hashlib
import time
from typing import Iterable, List, Optional

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


@dataclasses.dataclass
class Listing:
    """1つの中古商品リスティングを表す正規化済みデータ。"""

    site: str                      # サイト識別子 (例: "orutika")
    uid: str                       # サイト内で一意なキー (管理番号など)
    url: str                       # 商品個別ページURL
    maker: str = ""                # メーカー
    model: str = ""                # 型番・機種名
    name: str = ""                 # 名称・カテゴリ
    spec: str = ""                 # 主スペック
    price: str = ""                # 価格 (表示文字列)
    price_value: Optional[int] = None  # 価格 (数値, 円)
    condition: str = ""            # 状態・コンディション
    listed_date: str = ""          # 掲載日 (取れる場合)
    image_url: str = ""            # 代表画像URL
    is_new_badge: bool = False     # サイト上の「NEW」表示の有無

    def key(self) -> str:
        """新着判定に使う安定キー。site + uid。"""
        return f"{self.site}:{self.uid}"

    def fingerprint(self) -> str:
        """主要フィールドのハッシュ。価格変更などの検知に使える。"""
        raw = "|".join([
            self.model, self.name, self.price, self.condition,
        ])
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


class Scraper:
    """サイトスクレイパーの基底クラス。"""

    site: str = ""
    name: str = ""          # 表示用サイト名
    base_url: str = ""

    def __init__(self, request_interval: float = 1.0):
        self.request_interval = request_interval
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get(self, url: str, **kwargs) -> requests.Response:
        resp = self.session.get(url, timeout=30, **kwargs)
        resp.raise_for_status()
        time.sleep(self.request_interval)  # サイトに負荷をかけない
        return resp

    def get_soup(self, url: str, **kwargs):
        """バイト列から BeautifulSoup を生成する。

        HTTP ヘッダに charset が無いサイト(requests が ISO-8859-1 と誤判定)でも
        HTML の meta charset / BOM から bs4 が正しくデコードできるようにする。
        """
        from bs4 import BeautifulSoup
        resp = self.get(url, **kwargs)
        return BeautifulSoup(resp.content, "lxml")

    def fetch_listings(self) -> List[Listing]:
        """新着相当のリスティング一覧を取得して返す。サブクラスで実装。"""
        raise NotImplementedError
