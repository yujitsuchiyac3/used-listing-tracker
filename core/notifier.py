"""日次まとめの HTML / テキスト生成。

Web ページ(githack で閲覧)としても、メール本文としても使える HTML を生成する。
- ページ全体は共通の見出し・ナビ・スタイル(page_head / page_foot)で統一
- 商品はカード型。ライト/ダーク両対応、レスポンシブ
- カード内は email でも崩れにくいようインラインスタイルを併用
"""
from __future__ import annotations

import html
from datetime import date
from typing import Dict, List

from scrapers.base import Listing

FONT = "-apple-system,BlinkMacSystemFont,'Hiragino Sans','Noto Sans JP',Meiryo,sans-serif"


def _yen(item: Listing) -> str:
    if item.price_value is not None:
        return f"¥{item.price_value:,}"
    return item.price or ""


# ---- 共通スタイル / ヘッダ / フッタ ----------------------------------------

def page_css() -> str:
    return """
<style>
:root{
  --bg:#f4f6f9; --card:#ffffff; --ink:#1a2230; --sub:#6b7684; --line:#e3e8ef;
  --accent:#2b6cb0; --accent-weak:#eaf1fb; --price:#c05621; --chip:#eef2f7;
}
@media (prefers-color-scheme:dark){
  :root{ --bg:#11151b; --card:#1a2029; --ink:#e6eaf0; --sub:#9aa5b3; --line:#2a323d;
    --accent:#6ba7e6; --accent-weak:#1e2a3a; --price:#f0a878; --chip:#232b36; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:FONTSTACK;line-height:1.6;
  -webkit-font-smoothing:antialiased;}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:900px;margin:0 auto;padding:0 16px 48px}
.top{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--line);
  margin:0 -16px 20px;padding:14px 16px;z-index:5}
.top-in{max-width:900px;margin:0 auto;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{font-weight:700;font-size:16px;letter-spacing:.02em}
.brand small{color:var(--sub);font-weight:400;margin-left:8px;font-size:12px}
.nav{margin-left:auto;display:flex;gap:6px}
.nav a{padding:6px 12px;border-radius:999px;font-size:13px;color:var(--sub)}
.nav a.on{background:var(--accent-weak);color:var(--accent);font-weight:600}
.hero{padding:8px 0 4px}
.hero h1{margin:0;font-size:22px}
.hero .meta{color:var(--sub);font-size:13px;margin-top:4px}
.pill{display:inline-block;background:var(--accent);color:#fff;border-radius:999px;
  padding:2px 12px;font-size:13px;font-weight:700}
.empty{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:28px;text-align:center;color:var(--sub)}
.sec{margin:26px 0 10px;display:flex;align-items:center;gap:10px}
.sec h2{margin:0;font-size:16px}
.sec .cnt{background:var(--accent-weak);color:var(--accent);border-radius:999px;
  padding:1px 10px;font-size:12px;font-weight:700}
.sec .rule{flex:1;height:1px;background:var(--line)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.card{display:flex;gap:12px;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:10px;transition:box-shadow .15s,transform .15s}
.card:hover{box-shadow:0 6px 18px rgba(20,40,80,.10);transform:translateY(-1px)}
.thumb{width:96px;height:96px;flex:0 0 96px;border-radius:8px;overflow:hidden;
  background:var(--chip);display:flex;align-items:center;justify-content:center}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb.ph{color:var(--sub);font-size:11px}
.body{min-width:0;flex:1}
.maker{color:var(--sub);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.model{font-weight:700;font-size:15px;margin:1px 0 2px;word-break:break-word}
.nm{font-size:12.5px;color:var(--ink);opacity:.85;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.price{color:var(--price);font-weight:700;font-size:16px;margin-top:4px}
.chip{display:inline-block;background:var(--chip);color:var(--sub);border-radius:6px;
  padding:1px 7px;font-size:11px;margin-top:5px}
.pdf .thumb{background:var(--accent-weak);color:var(--accent);font-size:28px}
.sitechip{display:inline-block;background:var(--chip);color:var(--sub);border-radius:6px;
  padding:0 6px;font-size:10px;margin-right:4px;vertical-align:middle}
.newbadge{display:inline-block;background:var(--price);color:#fff;border-radius:6px;
  padding:0 6px;font-size:10px;font-weight:700;margin-right:4px;vertical-align:middle}
.card.isnew{border-color:var(--price);box-shadow:0 0 0 1px var(--price) inset}
table.tb{border-collapse:collapse;width:100%;background:var(--card);
  border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13px}
table.tb th,table.tb td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left}
table.tb th{background:var(--accent-weak);color:var(--ink);font-weight:700}
table.tb tr:last-child td{border-bottom:none}
.hot{background:var(--accent-weak);font-weight:700}
.muted{color:var(--sub)}
.foot{margin-top:34px;color:var(--sub);font-size:11px;text-align:center}
.scroll{overflow-x:auto}
</style>
""".replace("FONTSTACK", FONT)


def page_head(title: str, subtitle: str = "", active: str = "") -> str:
    def nav(href, label, key):
        on = " on" if key == active else ""
        return f'<a class="nav-a{on}" href="{href}">{label}</a>'
    e = html.escape
    return f"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>{page_css()}</head><body>
<div class="top"><div class="top-in">
<span class="brand">🔎 中古計測器トラッカー</span>
<span class="nav">
{nav("index.html","履歴","index")}
{nav("latest.html","最新","latest")}
{nav("watch.html","フォロー","watch")}
{nav("catalog.html","全在庫","catalog")}
{nav("trends.html","傾向","trends")}
</span></div></div>
<div class="wrap">
""".replace('class="nav-a', 'class="')


def page_foot() -> str:
    return ('<div class="foot">used-listing-tracker — 自動生成</div>\n'
            "</div></body></html>")


# ---- 件名 / テキスト --------------------------------------------------------

def build_subject(new_by_site: Dict[str, List[Listing]], day: date) -> str:
    total = sum(len(v) for v in new_by_site.values())
    n_sites = sum(1 for v in new_by_site.values() if v)
    return f"【中古計測器 新着】{day:%Y-%m-%d} — 新着 {total}件 ({n_sites}サイト)"


def build_text(new_by_site, site_names, day: date) -> str:
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
            if it.name and it.name != it.model:
                lines.append(f"    {it.name}")
            if it.condition:
                lines.append(f"    状態: {it.condition}")
            lines.append(f"    {it.url}")
        lines.append("")
    if total == 0:
        lines.append("本日の新着はありませんでした。")
    return "\n".join(lines)


# ---- 新着まとめ HTML(最新/アーカイブ共通) --------------------------------

def _card(it: Listing) -> str:
    e = html.escape
    is_pdf = it.site == "orix"
    if it.image_url:
        thumb = (f'<a class="thumb" href="{e(it.url)}">'
                 f'<img src="{e(it.image_url)}" alt="" loading="lazy"></a>')
    elif is_pdf:
        thumb = f'<a class="thumb" href="{e(it.url)}">📄</a>'
    else:
        thumb = '<span class="thumb ph">No Image</span>'

    parts = [f'<div class="card{" pdf" if is_pdf else ""}">', thumb, '<div class="body">']
    if it.maker:
        parts.append(f'<div class="maker">{e(it.maker)}</div>')
    parts.append(f'<div class="model"><a href="{e(it.url)}">{e(it.model or it.name)}</a></div>')
    if it.name and it.name != it.model:
        parts.append(f'<div class="nm">{e(it.name)}</div>')
    y = _yen(it)
    if y:
        parts.append(f'<div class="price">{e(y)}</div>')
    if it.condition:
        parts.append(f'<div class="chip">{e(it.condition[:60])}</div>')
    parts.append("</div></div>")
    return "".join(parts)


def build_html(new_by_site, site_names, day: date, *, kind: str = "new") -> str:
    """kind='new' で新着まとめ、kind='all' で全在庫ページを生成。"""
    total = sum(len(v) for v in new_by_site.values())
    n_sites = sum(1 for v in new_by_site.values() if v)
    e = html.escape
    if kind == "all":
        title = "全在庫 — 中古計測器トラッカー"
        active, hero = "catalog", "全在庫"
        meta = f"{day:%Y年%m月%d日} 時点 ・ {n_sites}サイト"
        empty_msg = "在庫を取得できませんでした。"
    else:
        title = "最新の新着 — 中古計測器トラッカー"
        active, hero = "latest", "最新の新着"
        meta = f"{day:%Y年%m月%d日} ・ {n_sites}サイトで新着"
        empty_msg = "本日の新着はありませんでした。"

    out = [page_head(title, active=active)]
    out.append('<div class="hero">')
    out.append(f'<h1>{hero} <span class="pill">{total}件</span></h1>')
    out.append(f'<div class="meta">{meta}</div>')
    out.append("</div>")

    if total == 0:
        out.append(f'<div class="empty">{empty_msg}</div>')
    else:
        for site, items in new_by_site.items():
            if not items:
                continue
            out.append('<div class="sec">'
                       f'<h2>{e(site_names.get(site, site))}</h2>'
                       f'<span class="cnt">{len(items)}</span><span class="rule"></span></div>')
            out.append('<div class="grid">')
            out.extend(_card(it) for it in items)
            out.append("</div>")

    out.append(page_foot())
    return "\n".join(out)


# ---- フォロー中(監視対象)ページ -------------------------------------------

def _watch_card(it: Listing, site_names, is_new: bool) -> str:
    e = html.escape
    is_pdf = it.site == "orix"
    if it.image_url:
        thumb = (f'<a class="thumb" href="{e(it.url)}">'
                 f'<img src="{e(it.image_url)}" alt="" loading="lazy"></a>')
    elif is_pdf:
        thumb = f'<a class="thumb" href="{e(it.url)}">📄</a>'
    else:
        thumb = '<span class="thumb ph">No Image</span>'

    cls = "card" + (" pdf" if is_pdf else "") + (" isnew" if is_new else "")
    parts = [f'<div class="{cls}">', thumb, '<div class="body">']
    site_label = site_names.get(it.site, it.site)
    badge = '<span class="newbadge">NEW</span>' if is_new else ''
    parts.append(f'<div class="maker"><span class="sitechip">{e(site_label)}</span>{badge}'
                 f'{(" " + e(it.maker)) if it.maker else ""}</div>')
    parts.append(f'<div class="model"><a href="{e(it.url)}">{e(it.model or it.name)}</a></div>')
    if it.name and it.name != it.model:
        parts.append(f'<div class="nm">{e(it.name)}</div>')
    y = _yen(it)
    if y:
        parts.append(f'<div class="price">{e(y)}</div>')
    if it.condition:
        parts.append(f'<div class="chip">{e(it.condition[:60])}</div>')
    parts.append("</div></div>")
    return "".join(parts)


def build_watch(groups, site_names, day: date) -> str:
    """groups: [{"label": str, "items": [Listing], "new_keys": set(...)}] """
    e = html.escape
    total = sum(len(g["items"]) for g in groups)
    new_total = sum(sum(1 for it in g["items"] if it.key() in g["new_keys"]) for g in groups)
    out = [page_head("フォロー中 — 中古計測器トラッカー", active="watch")]
    out.append('<div class="hero">')
    out.append(f'<h1>★ フォロー中 <span class="pill">{total}件</span></h1>')
    subtitle = f"{day:%Y年%m月%d日} 時点 ・ 12サイト横断"
    if new_total:
        subtitle += f" ・ <span style=\"color:var(--price);font-weight:700;\">本日 新着{new_total}件</span>"
    out.append(f'<div class="meta">{subtitle}</div>')
    out.append("</div>")

    if not groups:
        out.append('<div class="empty">フォロー登録がありません。</div>')
    for g in groups:
        items = g["items"]
        new_keys = g["new_keys"]
        # 新着を先頭に
        items = sorted(items, key=lambda it: (it.key() not in new_keys))
        n_new = sum(1 for it in items if it.key() in new_keys)
        cnt = f'{len(items)}' + (f' / NEW {n_new}' if n_new else '')
        out.append('<div class="sec">'
                   f'<h2>★ {e(g["label"])}</h2>'
                   f'<span class="cnt">{cnt}</span><span class="rule"></span></div>')
        if not items:
            out.append('<div class="empty">まだ一致する在庫はありません。'
                       '見つかり次第ここに表示されます。</div>')
            continue
        out.append('<div class="grid">')
        out.extend(_watch_card(it, site_names, it.key() in new_keys) for it in items)
        out.append("</div>")

    out.append(page_foot())
    return "\n".join(out)
