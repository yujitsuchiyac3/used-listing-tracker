"""オリックス・レンテック https://catalog.orixrentec.jp/measuring_instrument_used/

他サイトと異なり「PDF更新検知型」。更新頻度は低い(月数回)が、
重要な『中古機器販売リスト』PDF(電気/通信/分析)がアップされる。

検知方針:
  1. 新着情報 index から「在庫品販売リスト」トピックを動的に辿る(id変更に追従)
  2. 詳細ページから現在の /file/*.pdf リンクを取得
  3. 各PDF の Last-Modified / Content-Length で更新検知
     (ファイル名 denki6→denki7 でも、同名で内容差し替えでも検知できる)
  4. PDF を開いて 版(○月号)・有効期限・機種数 を抽出しメールに明記

uid に last_modified を含めるため、PDF が差し替わると新しい uid になり、
スナップショット差分で「新着(=更新)」として通知される。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import Listing, Scraper

try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except BaseException:  # pypdf/依存が無い・壊れていても(pyo3 panic 含む)検知自体は動かす
    _HAS_PYPDF = False

NEWS_INDEX = "https://www.orixrentec.jp/new_info/index.html"
NEWS_BASE = "https://www.orixrentec.jp"
TOPIC_KEYWORD = "在庫品販売リスト"
FALLBACK_DETAIL = "https://www.orixrentec.jp/new_info/detail.html?id=529"

# ファイル名 → カテゴリ表示名
FILE_CATEGORY = {"denki": "電気", "tsushin": "通信", "bunseki": "分析"}


class OrixRentecScraper(Scraper):
    site = "orix"
    name = "オリックス・レンテック 中古機器販売リスト"
    base_url = "https://catalog.orixrentec.jp/measuring_instrument_used/"

    def fetch_listings(self) -> List[Listing]:
        detail_url = self._resolve_detail_url()
        pdf_links = self._extract_pdf_links(detail_url)
        listings: List[Listing] = []
        for url, label in pdf_links:
            try:
                listings.append(self._build_listing(url, label))
            except Exception:
                continue
        return listings

    # -- トピック解決 -----------------------------------------------------
    def _resolve_detail_url(self) -> str:
        try:
            soup = BeautifulSoup(self.get(NEWS_INDEX).text, "lxml")
            for a in soup.find_all("a", href=True):
                if TOPIC_KEYWORD in a.get_text():
                    href = a["href"]
                    return href if href.startswith("http") else NEWS_BASE + href
        except Exception:
            pass
        return FALLBACK_DETAIL

    def _extract_pdf_links(self, detail_url: str):
        soup = BeautifulSoup(self.get(detail_url).text, "lxml")
        out = []
        seen = set()
        for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
            href = a["href"]
            url = href if href.startswith("http") else NEWS_BASE + href
            if url in seen:
                continue
            seen.add(url)
            out.append((url, a.get_text(" ", strip=True)))
        return out

    # -- 1 PDF → Listing -------------------------------------------------
    def _build_listing(self, url: str, label: str) -> Listing:
        head = self.session.head(url, timeout=30, allow_redirects=True)
        last_modified = head.headers.get("Last-Modified", "")
        size = head.headers.get("Content-Length", "")

        category = self._category(url, label)
        # uid は last_modified を含め、差し替え時に変化させる
        uid = f"{category}|{last_modified or size or url}"

        edition = expiry = ""
        n_models: Optional[int] = None
        meta = self._read_pdf_meta(url)
        if meta:
            edition, expiry, n_models = meta

        cond_parts = []
        if expiry:
            cond_parts.append(f"有効期限 {expiry}")
        if n_models:
            cond_parts.append(f"約{n_models}機種")
        if size.isdigit():
            cond_parts.append(f"{int(size)//1024}KB")

        return Listing(
            site=self.site,
            uid=uid,
            url=url,
            maker="オリックス・レンテック",
            model=f"中古機器販売リスト（{category}）",
            name=edition or "中古機器販売リスト",
            spec=label,
            price="",
            price_value=None,
            condition=" ・ ".join(cond_parts),
            listed_date=last_modified,
            image_url="",
            is_new_badge=True,
        )

    def _category(self, url: str, label: str) -> str:
        m = re.search(r"/([a-z]+)\d*\.pdf", url, re.I)
        if m and m.group(1).lower() in FILE_CATEGORY:
            return FILE_CATEGORY[m.group(1).lower()]
        m2 = re.search(r"（(電気|通信|分析)）", label)
        return m2.group(1) if m2 else "計測器"

    def _read_pdf_meta(self, url: str):
        """PDF を開いて (版, 有効期限, 機種数) を返す。失敗時 None。"""
        if not _HAS_PYPDF:
            return None
        try:
            import io
            data = self.get(url).content
            reader = PdfReader(io.BytesIO(data))
            head = reader.pages[0].extract_text() or ""
            full = "\n".join((p.extract_text() or "") for p in reader.pages)
            m_ed = re.search(r"(\d{4}年\d{1,2}月号)", head)
            m_exp = re.search(r"有効期限[：:]\s*([\d年月日/]+)", head)
            n = len(re.findall(r"型番コード", full)) or None
            return (m_ed.group(1) if m_ed else "",
                    m_exp.group(1) if m_exp else "",
                    n)
        except Exception:
            return None
