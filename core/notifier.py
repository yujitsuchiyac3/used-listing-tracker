"""日次メールの生成。

サイトごとに「新着」リスティングをまとめ、HTML と プレーンテキストの
両方を生成する。HTML はメールクライアントでの表示を想定し、画像サムネイル・
価格・状態・リンクを並べたカード型レイアウト。
"""
from __future__ import annotations

import html
from datetime import date
from typing import Dict, List

from scrapers.base import Listing


def _yen(item: Listing) -> str:
    if item.price_value is not None:
        return f"¥{item.price_value:,}"
    return item.price or "—"


def build_subject(new_by_site: Dict[str, List[Listing]], day: date) -> str:
    total = sum(len(v) for v in new_by_site.values())
    n_sites = sum(1 for v in new_by_site.values() if v)
    return f"【中古計測器 新着】{day:%Y-%m-%d} — 新着 {total}件 ({n_sites}サイト)"


def build_text(new_by_site: Dict[str, List[Listing]], site_names: Dict[str, str], day: date) -> str:
    lines: List[str] = []
    total = sum(len(v) for v in new_by_site.values())
    lines.append(f"中古計測器 新着まとめ  {day:%Y-%m-%d}")
    lines.append(f"新着合計: {total}件")
    lines.append("")
    for site, items in new_by_site.items():
        if not items:
            continue
        lines.append(f"■ {site_names.get(site, site)} ({len(items)}件)")
        for it in items:
            lines.append(f"  ・[{it.maker}] {it.model}  {_yen(it)}")
            if it.name:
                lines.append(f"    {it.name}")
            if it.condition:
                lines.append(f"    状態: {it.condition}")
            lines.append(f"    {it.url}")
        lines.append("")
    if total == 0:
        lines.append("本日の新着はありませんでした。")
    return "\n".join(lines)


def build_html(new_by_site: Dict[str, List[Listing]], site_names: Dict[str, str], day: date) -> str:
    total = sum(len(v) for v in new_by_site.values())
    e = html.escape
    out: List[str] = []
    out.append('<div style="font-family:-apple-system,Segoe UI,Hiragino Sans,Meiryo,sans-serif;'
               'max-width:760px;margin:0 auto;color:#1a1a1a;">')
    out.append(f'<h2 style="margin:0 0 4px;">中古計測器 新着まとめ</h2>')
    out.append(f'<div style="color:#666;font-size:13px;margin-bottom:16px;">'
               f'{day:%Y年%m月%d日} ・ 新着合計 <b>{total}</b>件</div>')

    if total == 0:
        out.append('<p>本日の新着はありませんでした。</p>')

    for site, items in new_by_site.items():
        if not items:
            continue
        out.append(f'<h3 style="border-bottom:2px solid #2b6cb0;padding-bottom:4px;margin:24px 0 12px;">'
                   f'{e(site_names.get(site, site))} '
                   f'<span style="color:#2b6cb0;font-size:13px;">({len(items)}件)</span></h3>')
        for it in items:
            out.append('<table style="width:100%;border-collapse:collapse;margin-bottom:10px;'
                       'border:1px solid #e2e8f0;border-radius:6px;"><tr>')
            # image
            out.append('<td style="width:130px;padding:8px;vertical-align:top;">')
            if it.image_url:
                out.append(f'<a href="{e(it.url)}"><img src="{e(it.image_url)}" '
                           f'alt="" style="width:120px;height:auto;border-radius:4px;display:block;"></a>')
            out.append('</td>')
            # body
            out.append('<td style="padding:8px;vertical-align:top;">')
            out.append(f'<div style="font-size:12px;color:#777;">{e(it.maker)}</div>')
            out.append(f'<div style="font-size:16px;font-weight:bold;margin:2px 0;">'
                       f'<a href="{e(it.url)}" style="color:#2b6cb0;text-decoration:none;">{e(it.model)}</a></div>')
            if it.name:
                out.append(f'<div style="font-size:13px;margin-bottom:2px;">{e(it.name)}</div>')
            out.append(f'<div style="font-size:18px;color:#c05621;font-weight:bold;margin:4px 0;">{e(_yen(it))}</div>')
            if it.condition:
                out.append(f'<div style="font-size:12px;color:#444;">{e(it.condition)}</div>')
            if it.spec:
                out.append(f'<div style="font-size:11px;color:#999;margin-top:2px;">{e(it.spec[:90])}</div>')
            out.append('</td></tr></table>')

    out.append('<div style="color:#aaa;font-size:11px;margin-top:24px;">'
               'used-listing-tracker による自動生成</div>')
    out.append('</div>')
    return "\n".join(out)
