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
