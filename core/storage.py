"""新着判定のためのスナップショット管理。

サイトごとに {uid: fingerprint} を保存し、前回に無かった uid を「新着」とする。
fingerprint は将来の価格変更検知などに使えるよう保持しておく(現状は新規 uid のみ通知)。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from scrapers.base import Listing


class Snapshot:
    def __init__(self, path: str = "data/state.json"):
        self.path = path

    def load(self) -> Dict[str, Dict[str, str]]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, state: Dict[str, Dict[str, str]]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def diff_new(prev: Dict[str, Dict[str, str]], site: str,
             listings: List[Listing]) -> List[Listing]:
    """前回スナップショットに無い uid のリスティングだけ返す。

    前回その site の記録が全く無い(初回)場合は、誤って大量通知しないよう
    「新着なし」とみなす(=今回分を基準スナップショットとして記録するだけ)。
    """
    prev_site = prev.get(site)
    if prev_site is None:
        return []  # 初回はベースライン作成のみ
    return [it for it in listings if it.uid not in prev_site]


def build_state_for_site(listings: List[Listing]) -> Dict[str, str]:
    return {it.uid: it.fingerprint() for it in listings}


# ---- フォロー該当品の「初めて見つけた日」 ------------------------------------

WATCH_SEEN_PATH = "data/watch_seen.json"


def load_watch_seen(path: str = WATCH_SEEN_PATH) -> Dict[str, str]:
    """{Listing.key(): "YYYY-MM-DD"}。日付が空文字の品は記録開始前から在庫にあったもの。"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_watch_seen(seen: Dict[str, str], path: str = WATCH_SEEN_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=1, sort_keys=True)


def archive_first_dates(archive_dir: str = "data/archive") -> Dict[str, str]:
    """日付別アーカイブ(新着ページ)に載った商品URL → 最初に載った日付。
    watch_seen.json を初めて作るときの遡り用。"""
    import glob
    import html as _html
    import re
    first: Dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(archive_dir, "*.html"))):
        day = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for url in re.findall(r'href="(https?://[^"]+)"', text):
            first.setdefault(_html.unescape(url), day)
    return first
