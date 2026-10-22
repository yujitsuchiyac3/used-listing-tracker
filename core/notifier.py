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


def _price_html(item: Listing) -> str:
    """価格が数値で出ている品だけ強調し、「お問い合わせください」等は控えめに出す。"""
    y = _yen(item)
    if not y:
        return ""
    if item.price_value is not None:
        return f'<div class="price">{html.escape(y)}</div>'
    if "問" in y:
        y = "価格は問合せ"
    return f'<div class="price ask">{html.escape(y)}</div>'


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
  margin:0 0 20px;padding:14px 16px;z-index:5}
.top-in{max-width:900px;margin:0 auto;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{font-weight:700;font-size:16px;letter-spacing:.02em;color:var(--ink);text-decoration:none}
.brand:hover{text-decoration:none}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpi .num{font-size:28px;font-weight:800;line-height:1.1}
.kpi .lbl{color:var(--sub);font-size:12px;margin-top:4px}
.kpi.accent .num{color:var(--accent)} .kpi.warm .num{color:var(--price)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.tile{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px;text-decoration:none;color:var(--ink);transition:box-shadow .15s,transform .15s}
.tile:hover{box-shadow:0 6px 18px rgba(20,40,80,.10);transform:translateY(-1px);text-decoration:none}
.tile .ico{font-size:22px} .tile .tt{font-weight:700;margin-top:6px}
.tile .ds{color:var(--sub);font-size:12px;margin-top:2px}
.more{display:inline-block;margin:10px 0 0;font-size:13px;font-weight:600}
.brand small{color:var(--sub);font-weight:400;margin-left:8px;font-size:12px}
.nav{margin-left:auto;display:flex;gap:6px}
.nav a{padding:6px 12px;border-radius:999px;font-size:13px;color:var(--sub)}
.nav a.on{background:var(--accent-weak);color:var(--accent);font-weight:600}
@media (max-width:600px){
  .top{position:static;padding:10px 16px 8px}
  .top-in{gap:6px}
  .nav{margin-left:-12px;max-width:calc(100% + 12px);overflow-x:auto;white-space:nowrap}
  .nav a{padding:6px 10px;flex:0 0 auto}
}
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
.sec[id]{scroll-margin-top:calc(var(--toph,0px) + var(--jumph,0px) + 12px)}
.jump{display:flex;flex-wrap:wrap;gap:6px;margin:14px -16px 4px;padding:8px 16px;
  position:sticky;top:var(--toph,0px);z-index:4;background:var(--bg);border-bottom:1px solid var(--line)}
@media (max-width:600px){
  .jump{flex-wrap:nowrap;overflow-x:auto;white-space:nowrap}
  .jump a{flex:0 0 auto}
}
.jump a{background:var(--card);border:1px solid var(--line);border-radius:999px;
  padding:3px 10px;font-size:12.5px;color:var(--ink)}
.jump a:hover{border-color:var(--accent);text-decoration:none}
.jump .n{color:var(--accent);font-weight:700;margin-left:4px}
.jump .z{color:var(--sub)}
.jump .nw{color:var(--price);font-weight:700;margin-left:4px}
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
.price.ask{color:var(--sub);font-weight:400;font-size:12px}
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
<a class="brand" href="index.html">🔎 中古計測器トラッカー</a>
<span class="nav">
{nav("index.html","ホーム","home")}
{nav("latest.html","新着","latest")}
{nav("watch.html","フォロー","watch")}
{nav("catalog.html","全在庫","catalog")}
{nav("trends.html","傾向","trends")}
</span></div></div>
<div class="wrap">
""".replace('class="nav-a', 'class="')


def page_foot() -> str:
    # 固定表示するヘッダ/ジャンプリンクの高さを測り、見出しへのジャンプ位置に使う
    script = ("<script>(function(){function f(){var r=document.documentElement.style,"
              "t=document.querySelector('.top'),j=document.querySelector('.jump');"
              "r.setProperty('--toph',(t&&getComputedStyle(t).position==='sticky'?t.offsetHeight:0)+'px');"
              "r.setProperty('--jumph',(j?j.offsetHeight:0)+'px')}"
              "f();addEventListener('resize',f)})()</script>")
    return ('<div class="foot">used-listing-tracker — 自動生成</div>\n'
            f"</div>{script}</body></html>")


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
    parts.append(_price_html(it))
    if it.condition:
        parts.append(f'<div class="chip">{e(it.condition[:60])}</div>')
    parts.append("</div></div>")
    return "".join(parts)


def build_html(new_by_site, site_names, day: date, *, kind: str = "new",
               extra_html: str = "") -> str:
    """kind='new' で新着まとめ、kind='all' で全在庫ページを生成。
    extra_html はセクションの後(フッタ前)に差し込む追加HTML。"""
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

    if extra_html:
        out.append(extra_html)

    out.append(page_foot())
    return "\n".join(out)


# ---- フォロー中(監視対象)ページ -------------------------------------------

def _seen_label(d: str) -> str:
    """"2026-10-21" -> "10/21 発見"。空(記録開始前から在庫)なら空文字。"""
    if not d:
        return ""
    y, m, dd = d.split("-")
    return f"{int(m)}/{int(dd)} 発見"


def _by_first_seen(items, first_seen, new_keys):
    """本日新着 → 見つけた日が新しい順 → 記録開始前から在庫、の順に並べる。"""
    return sorted(items, key=lambda it: (it.key() not in new_keys,
                                         not first_seen.get(it.key()),
                                         _neg(first_seen.get(it.key(), ""))))


def _neg(d: str) -> str:
    # 日付文字列の降順ソート用(数字を 9 の補数にする)
    return "".join(chr(ord("9") - ord(c) + ord("0")) if c.isdigit() else c for c in d)


def _watch_card(it: Listing, site_names, is_new: bool, seen: str = "") -> str:
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
    parts.append(_price_html(it))
    chips = [x for x in (it.condition[:60], _seen_label(seen)) if x]
    if chips:
        parts.append("".join(f'<span class="chip">{e(x)}</span> ' for x in chips))
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
    subtitle = f"{day:%Y年%m月%d日} 時点 ・ {len(site_names)}サイト横断"
    if new_total:
        subtitle += f" ・ <span style=\"color:var(--price);font-weight:700;\">本日 新着{new_total}件</span>"
    out.append(f'<div class="meta">{subtitle}</div>')
    out.append("</div>")

    if not groups:
        out.append('<div class="empty">フォロー登録がありません。</div>')
    else:
        # 各フォローへのジャンプリンク(件数つき)
        links = []
        for i, g in enumerate(groups):
            n = len(g["items"])
            n_new = sum(1 for it in g["items"] if it.key() in g["new_keys"])
            nw = f'<span class="nw">NEW {n_new}</span>' if n_new else ''
            cls = '' if n else ' class="z"'
            links.append(f'<a href="#w{i}"{cls}>{e(g["label"])}'
                         f'<span class="n">{n}件</span>{nw}</a>')
        out.append('<nav class="jump">' + "".join(links) + '</nav>')
    for i, g in enumerate(groups):
        items = g["items"]
        new_keys = g["new_keys"]
        first_seen = g.get("first_seen", {})
        items = _by_first_seen(items, first_seen, new_keys)
        n_new = sum(1 for it in items if it.key() in new_keys)
        cnt = f'{len(items)}' + (f' / NEW {n_new}' if n_new else '')
        out.append(f'<div class="sec" id="w{i}">'
                   f'<h2>★ {e(g["label"])}</h2>'
                   f'<span class="cnt">{cnt}</span><span class="rule"></span></div>')
        if not items:
            out.append('<div class="empty">まだ一致する在庫はありません。'
                       '見つかり次第ここに表示されます。</div>')
            continue
        out.append('<div class="grid">')
        out.extend(_watch_card(it, site_names, it.key() in new_keys,
                               first_seen.get(it.key(), "")) for it in items)
        out.append("</div>")

    out.append(page_foot())
    return "\n".join(out)


# ---- ホーム(ダッシュボード) ------------------------------------------------

def build_home(day: date, *, new_by_site=None, watch_groups=None,
               site_names=None, inventory_total=0, n_sites=0,
               archive_rows_html="", last_updated="", new_total=None) -> str:
    """トップのダッシュボード。主要数値・各ページ導線・プレビューを1枚に。
    new_total を渡すと在庫データ無しでも件数表示だけは正確にできる。"""
    site_names = site_names or {}
    new_by_site = new_by_site or {}
    watch_groups = watch_groups or []
    if new_total is None:
        new_total = sum(len(v) for v in new_by_site.values())
    watch_total = sum(len(g["items"]) for g in watch_groups)
    watch_new = sum(sum(1 for it in g["items"] if it.key() in g.get("new_keys", set()))
                    for g in watch_groups)

    out = [page_head("中古計測器トラッカー — ホーム", active="home")]
    out.append('<div class="hero"><h1>中古計測器トラッカー</h1>'
               '<div class="meta">複数の中古計測器・研究機器サイトの新着を毎日まとめています。'
               f'{("　最終更新 " + last_updated) if last_updated else ""}</div></div>')

    # KPI
    out.append('<div class="kpis">')
    out.append(f'<div class="kpi warm"><div class="num">{new_total}</div>'
               '<div class="lbl">今日の新着</div></div>')
    out.append(f'<div class="kpi accent"><div class="num">{watch_total}</div>'
               '<div class="lbl">フォロー該当</div></div>')
    out.append(f'<div class="kpi"><div class="num">{inventory_total:,}</div>'
               '<div class="lbl">全在庫</div></div>')
    out.append(f'<div class="kpi"><div class="num">{n_sites}</div>'
               '<div class="lbl">巡回サイト</div></div>')
    out.append('</div>')

    # 各ページ導線
    out.append('<div class="tiles">')
    tiles = [
        ("latest.html", "🆕", "新着", f"今日 {new_total}件・過去の記録も"),
        ("watch.html", "★", "フォロー", f"監視キーワードの在庫 {watch_total}件"),
        ("catalog.html", "📦", "全在庫", f"現在の在庫 {inventory_total:,}件"),
        ("trends.html", "📊", "傾向", "サイト別・曜日別の更新傾向"),
    ]
    for href, ico, tt, ds in tiles:
        out.append(f'<a class="tile" href="{href}"><div class="ico">{ico}</div>'
                   f'<div class="tt">{tt}</div><div class="ds">{ds}</div></a>')
    out.append('</div>')

    # 今日の新着プレビュー
    flat_new = [it for items in new_by_site.values() for it in items]
    if flat_new:
        out.append('<div class="sec"><h2>今日の新着</h2>'
                   f'<span class="cnt">{new_total}</span><span class="rule"></span></div>')
        out.append('<div class="grid">')
        out.extend(_card(it) for it in flat_new[:6])
        out.append('</div>')
        if new_total > 6:
            out.append('<a class="more" href="latest.html">すべての新着を見る →</a>')

    # フォロー中プレビュー
    if watch_groups:
        badge = (f'<span class="cnt">{watch_total}'
                 + (f' / NEW {watch_new}' if watch_new else '') + '</span>')
        out.append(f'<div class="sec"><h2>★ フォロー中(最近見つけた順)</h2>{badge}'
                   '<span class="rule"></span></div>')
        new_keys = set()
        first_seen = {}
        picks, seen_keys = [], set()
        for g in watch_groups:
            new_keys |= g.get("new_keys", set())
            first_seen.update(g.get("first_seen", {}))
            for it in g["items"]:
                if it.key() not in seen_keys:   # 複数フォローに該当する品は1回だけ
                    seen_keys.add(it.key())
                    picks.append(it)
        picks = _by_first_seen(picks, first_seen, new_keys)
        if picks:
            out.append('<div class="grid">')
            out.extend(_watch_card(it, site_names, it.key() in new_keys,
                                   first_seen.get(it.key(), "")) for it in picks[:6])
            out.append('</div>')
            out.append('<a class="more" href="watch.html">フォロー一覧へ →</a>')
        else:
            labels = "・".join(g["label"] for g in watch_groups)
            out.append(f'<div class="empty">監視中: {html.escape(labels)}'
                       '<br>一致する在庫が出たらここに表示されます。'
                       ' <a href="watch.html">フォロー設定へ</a></div>')

    # 最近の記録(アーカイブ)
    if archive_rows_html:
        out.append('<div class="sec"><h2>最近の記録</h2><span class="rule"></span></div>')
        out.append('<table class="tb"><tr><th>日付</th>'
                   '<th style="text-align:right;">新着</th></tr>')
        out.append(archive_rows_html)
        out.append('</table>')
        out.append('<a class="more" href="latest.html">過去の新着をすべて見る →</a>')

    out.append(page_foot())
    return "\n".join(out)
