"""日次まとめの HTML / テキスト生成。

GitHub Pages で閲覧するページと、メール・アーカイブ用の HTML を生成する。
- 写真を主役にしたカード(_photo_card)を全ページで共通に使う
- 配色は OS の昼/夜設定に合わせて自動で切り替える
- フォロー該当品は「前回見たとき以降に見つかった品」をブラウザ側で判定して先頭に出す
  (前回の閲覧日はブラウザの localStorage に保存。サーバ側には何も残さない)
"""
from __future__ import annotations

import html
from datetime import date, timedelta
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
    if item.price_value is not None:
        return f'<span class="pr">{html.escape(y)}</span>'
    if not y or "問" in y:
        y = "問合せ"
    return f'<span class="pr ask">{html.escape(y)}</span>'


def _md(d: str) -> str:
    """"2026-10-21" -> "10/21"。"""
    if not d:
        return ""
    _, m, dd = d.split("-")
    return f"{int(m)}/{int(dd)}"


# ---- 共通スタイル / ヘッダ / フッタ ----------------------------------------

def page_css() -> str:
    return """
<style>
:root{
  --bg:#fff; --ink:#1c1c1c; --sub:#767676; --line:#e6e6e6; --well:#f1f1ef;
  --hot:#d9480f; --link:#1f4e79; --head:#f6f6f4;
}
@media (prefers-color-scheme:dark){
  :root{ --bg:#16171a; --ink:#ececec; --sub:#9b9da3; --line:#2c2e33; --well:#22242a;
    --hot:#ff7a3d; --link:#8db8e8; --head:#1d1f23; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 FONTSTACK;
  -webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:1240px;margin:0 auto;padding:0 28px 48px}
.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.top-in{max-width:1240px;margin:0 auto;padding:14px 28px;display:flex;flex-wrap:wrap;
  align-items:baseline;gap:6px 28px}
.brand{font-weight:700;font-size:16px;letter-spacing:.03em}
.nav{display:flex;gap:20px;font-size:13px;color:var(--sub);overflow-x:auto;white-space:nowrap}
.nav a.on{color:var(--ink);font-weight:700}
.nav a:hover{color:var(--ink)}
.hero{margin:24px 0 14px;display:flex;align-items:flex-end;justify-content:space-between;gap:12px}
.hero h1{margin:0;font-size:22px;line-height:1.35}
.hero h1 em{font-style:normal;color:var(--hot)}
.meta{color:var(--sub);font-size:12.5px;margin-top:2px}
.btn{border:1px solid var(--ink);background:none;color:var(--ink);padding:6px 14px;font:inherit;
  font-size:13px;border-radius:2px;cursor:pointer;white-space:nowrap}
.btn:hover{background:var(--ink);color:var(--bg)}
.sec{margin:40px 0 12px;padding-top:14px;border-top:1px solid var(--line);
  display:flex;align-items:baseline;gap:10px}
.sec h2{margin:0;font-size:15px}
.sec .cnt{color:var(--sub);font-size:12px}
.sec .cnt b{color:var(--hot)}
.sec .rule{display:none}
.sec[id]{scroll-margin-top:calc(var(--toph,0px) + var(--jumph,0px) + 8px)}
.jump{position:sticky;top:var(--toph,0px);z-index:4;background:var(--bg);
  display:flex;flex-wrap:wrap;gap:4px 18px;margin:8px -28px 0;padding:8px 28px;
  border-bottom:1px solid var(--line);font-size:12.5px}
.jump a{white-space:nowrap}
.jump a:hover{text-decoration:underline}
.jump .n{color:var(--sub);margin-left:3px}
.jump .nw{color:var(--hot);font-weight:700;margin-left:3px}
.jump a.z{color:var(--sub)}
.g4,.g5{display:grid;gap:24px 20px}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.g5{grid-template-columns:repeat(5,minmax(0,1fr));gap:20px 16px}
.pc{display:block;min-width:0}
.ph{position:relative;display:block;aspect-ratio:4/3;background:var(--well);overflow:hidden}
.ph img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}
.pc:hover .ph img{transform:scale(1.03)}
.noimg{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
  justify-content:center;text-align:center;padding:10px;color:var(--sub);font-size:11px;letter-spacing:.08em}
.noimg b{font-size:22px;color:var(--ink);letter-spacing:0;margin-bottom:4px;word-break:break-all;line-height:1.15}
.g5 .noimg b{font-size:17px}
.new{display:none;position:absolute;left:0;top:0;background:var(--hot);color:#fff;
  font-size:12px;font-weight:700;padding:3px 9px}
.pc.unread .new{display:block}
.tag{position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.62);color:#fff;
  font-size:11px;padding:2px 8px;max-width:calc(100% - 16px);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tag.dt{right:auto;left:8px;background:rgba(0,0,0,.5)}
.pc.unread .tag.dt{display:none}
.cap{padding:8px 1px 0}
.mdl{font-weight:700;font-size:15px;line-height:1.3;word-break:break-word}
.g5 .mdl{font-size:13.5px}
.pc:hover .mdl{color:var(--link);text-decoration:underline}
.sub{color:var(--sub);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-top:2px}
.row .sub{flex:0 1 auto;text-align:right}
.pr{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.pr.ask{font-weight:400;color:var(--sub);font-size:12.5px}
#fresh.has .pc:not(.unread){display:none}
#fresh:not(.has) .g4 .pc:nth-child(n+9){display:none}
.empty{border:1px dashed var(--line);padding:24px;text-align:center;color:var(--sub)}
.more{display:inline-block;margin:12px 0 0;font-size:13px;color:var(--link)}
.more:hover{text-decoration:underline}
.summary{color:var(--sub);font-size:12.5px;margin:-6px 0 0}
.summary b{color:var(--ink);font-weight:600}
table.tb{border-collapse:collapse;width:100%;font-size:13px}
table.tb th,table.tb td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left}
table.tb th{background:var(--head);font-weight:700}
table.tb a{color:var(--link)}
.hot{background:var(--head);font-weight:700}
.muted{color:var(--sub)}
.scroll{overflow-x:auto}
.foot{margin-top:40px;color:var(--sub);font-size:11px;text-align:center}
@media (max-width:1000px){.g4{grid-template-columns:repeat(3,minmax(0,1fr))}
  .g5{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (max-width:700px){
  .wrap{padding:0 14px 40px}.top{position:static}.top-in{padding:10px 14px}
  .g4,.g5{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 12px}
  .hero{flex-direction:column;align-items:flex-start}.hero h1{font-size:19px}
  .jump{margin:8px -14px 0;padding:8px 14px;flex-wrap:nowrap;overflow-x:auto}
  .row{flex-direction:column;align-items:flex-start;gap:0}.row .sub{text-align:left;max-width:100%}
}
</style>
""".replace("FONTSTACK", FONT)


def page_head(title: str, subtitle: str = "", active: str = "") -> str:
    def nav(href, label, key):
        on = ' class="on"' if key == active else ""
        return f'<a{on} href="{href}">{label}</a>'
    e = html.escape
    return f"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>{page_css()}</head><body>
<div class="top"><div class="top-in">
<a class="brand" href="index.html">中古計測器トラッカー</a>
<nav class="nav">
{nav("index.html","ホーム","home")}
{nav("watch.html","フォロー","watch")}
{nav("latest.html","新着","latest")}
{nav("catalog.html","全在庫","catalog")}
{nav("trends.html","傾向","trends")}
</nav></div></div>
<div class="wrap">
"""


# 前回の閲覧日(ブラウザに保存)と各カードの data-seen(見つけた日)を比べ、未読に印を付ける。
# 同じタブで再読み込みしても未読表示が消えないよう、セッション中は最初に読んだ「前回」を使う。
_UNREAD_JS = r"""
(function(){
  var s=document.getElementById('fresh'); if(!s) return;
  var today=s.getAttribute('data-today'), K='ult-last-visit', prev='';
  try{ prev=sessionStorage.getItem(K);
       if(prev===null){ prev=localStorage.getItem(K)||''; sessionStorage.setItem(K,prev); }
       localStorage.setItem(K,today); }catch(e){ prev=''; }
  function md(d){ var p=d.split('-'); return (+p[1])+'/'+(+p[2]); }
  function apply(){
    var n=0, seenKey={};
    document.querySelectorAll('.pc[data-seen]').forEach(function(c){
      var d=c.getAttribute('data-seen');
      var u=prev ? (d>prev) : (c.getAttribute('data-recent')==='1');
      c.classList.toggle('unread',u);
      if(u && s.contains(c)) n++;
    });
    var h=document.getElementById('fresh-h');
    if(prev){
      h.innerHTML = n ? '前回('+md(prev)+')から <em>'+n+'件</em> 新しく見つかりました'
                      : '前回('+md(prev)+')以降、フォローの新着はありません';
    }else{
      h.innerHTML = n ? '最近7日間に <em>'+n+'件</em> 見つかりました' : '最近7日間の新着はありません';
    }
    s.classList.toggle('has', n>0);
    var b=document.getElementById('markread'); if(b) b.style.display = n ? '' : 'none';
    var sub=document.getElementById('fresh-sub'); if(sub) sub.style.display = n ? 'none' : '';
  }
  var b=document.getElementById('markread');
  if(b) b.onclick=function(){ prev=today; try{ sessionStorage.setItem(K,prev); }catch(e){} apply(); };
  apply();
})();
"""

_LAYOUT_JS = (
    "(function(){function f(){var r=document.documentElement.style,"
    "t=document.querySelector('.top'),j=document.querySelector('.jump');"
    "r.setProperty('--toph',(t&&getComputedStyle(t).position==='sticky'?t.offsetHeight:0)+'px');"
    "r.setProperty('--jumph',(j?j.offsetHeight:0)+'px')}"
    "f();addEventListener('resize',f)})();"
)


def page_foot() -> str:
    return ('<div class="foot">used-listing-tracker — 自動生成</div>\n'
            f"</div><script>{_LAYOUT_JS}{_UNREAD_JS}</script></body></html>")


# ---- 写真カード(全ページ共通) ----------------------------------------------

def _photo_card(it: Listing, *, site_label: str = "", seen: str = "",
                recent: bool = False, tag: str = "") -> str:
    """写真を主役にしたカード。

    seen: フォローに初めて載った日(YYYY-MM-DD)。指定すると未読判定の対象になる。
    recent: 前回の閲覧日が無い(初めて開いた)ときに未読扱いにするか。
    tag: 写真の右下に出す札(フォロー名など)。
    """
    e = html.escape
    title = it.model or it.name
    if it.image_url:
        img = f'<img src="{e(it.image_url)}" alt="" loading="lazy">'
    else:
        kind = "PDF掲載" if it.site == "orix" else "写真なし"
        img = f'<span class="noimg"><b>{e(title)}</b>{kind}</span>'
    attrs = ""
    if seen:
        attrs = f' data-seen="{e(seen)}"' + (' data-recent="1"' if recent else "")
    new = f'<span class="new">{_md(seen)} 新着</span>' if seen else ""
    if tag:
        tg = f'<span class="tag">{e(tag)}</span>'
    elif seen:
        tg = f'<span class="tag dt">{_md(seen)} 発見</span>'
    else:
        tg = ""
    desc = " ".join(x for x in (it.maker, it.name if it.name != title else "") if x)
    right = site_label
    return (f'<a class="pc" href="{e(it.url)}" target="_blank" rel="noopener"{attrs}>'
            f'<span class="ph">{img}{new}{tg}</span><div class="cap">'
            f'<div class="mdl">{e(title)}</div><div class="sub">{e(desc)}</div>'
            f'<div class="row">{_price_html(it)}<span class="sub">{e(right)}</span></div>'
            "</div></a>")


def _card(it: Listing) -> str:
    """新着・全在庫ページ用(サイト別に並べるのでサイト名は出さない)。"""
    return _photo_card(it)


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




# ---- 新着まとめ / 全在庫 HTML ------------------------------------------------

def build_html(new_by_site, site_names, day: date, *, kind: str = "new",
               extra_html: str = "") -> str:
    """kind='new' で新着まとめ、kind='all' で全在庫ページを生成。
    extra_html はセクションの後(フッタ前)に差し込む追加HTML。"""
    total = sum(len(v) for v in new_by_site.values())
    n_sites = sum(1 for v in new_by_site.values() if v)
    e = html.escape
    if kind == "all":
        title = "全在庫 — 中古計測器トラッカー"
        active, hero = "catalog", f"全在庫 {total:,}件"
        meta = f"{day:%Y年%m月%d日} 時点 ・ {n_sites}サイト"
        empty_msg = "在庫を取得できませんでした。"
    else:
        title = "最新の新着 — 中古計測器トラッカー"
        active, hero = "latest", f"新着 {total}件"
        meta = f"{day:%Y年%m月%d日} ・ {n_sites}サイトで新着"
        empty_msg = "本日の新着はありませんでした。"

    out = [page_head(title, active=active)]
    out.append(f'<div class="hero"><div><h1>{hero}</h1><div class="meta">{meta}</div></div></div>')

    if total == 0:
        out.append(f'<div class="empty">{empty_msg}</div>')
    else:
        for site, items in new_by_site.items():
            if not items:
                continue
            out.append(f'<div class="sec"><h2>{e(site_names.get(site, site))}</h2>'
                       f'<span class="cnt">{len(items):,}件</span></div>')
            out.append('<div class="g5">')
            out.extend(_card(it) for it in items)
            out.append("</div>")

    if extra_html:
        out.append(extra_html)

    out.append(page_foot())
    return "\n".join(out)


# ---- フォロー(監視対象) ------------------------------------------------------

def _seen_label(d: str) -> str:
    """"2026-10-21" -> "10/21 発見"。空(記録開始前から在庫)なら空文字。"""
    return f"{_md(d)} 発見" if d else ""


def _by_first_seen(items, first_seen, new_keys):
    """本日新着 → 見つけた日が新しい順 → 記録開始前から在庫、の順に並べる。"""
    return sorted(items, key=lambda it: (it.key() not in new_keys,
                                         not first_seen.get(it.key()),
                                         _neg(first_seen.get(it.key(), ""))))


def _neg(d: str) -> str:
    # 日付文字列の降順ソート用(数字を 9 の補数にする)
    return "".join(chr(ord("9") - ord(c) + ord("0")) if c.isdigit() else c for c in d)


def _short_label(label: str) -> str:
    # 写真の札用に短くする: "クライオスタット・温度コントローラ(Lakeshore系)" -> "クライオスタット"
    return label.split("(")[0].split("・")[0].split("/")[0]


def _flatten_watch(watch_groups):
    """複数フォローに該当する品を1回にまとめる。戻り値: (items, first_seen, new_keys, label_of)"""
    items, first_seen, new_keys, label_of = [], {}, set(), {}
    for g in watch_groups:
        new_keys |= g.get("new_keys", set())
        first_seen.update(g.get("first_seen", {}))
        for it in g["items"]:
            if it.key() not in label_of:
                label_of[it.key()] = g["label"]
                items.append(it)
    return items, first_seen, new_keys, label_of


# 「前回から N件」枠に載せる候補: 見つけた日が新しい品(最大件数・遡る日数)
FRESH_MAX = 24
FRESH_DAYS = 60
RECENT_DAYS = 7     # 初めて開いたときに未読扱いにする日数


def _fresh_block(watch_groups, site_names, day: date, meta: str) -> str:
    """フォロー該当のうち最近見つかった品を写真で並べる枠。

    どれを「新着」として出すかはブラウザ側(_UNREAD_JS)が前回の閲覧日と比べて決める。
    JavaScript が使えない環境では、最近見つかった品がそのまま全部見える。
    """
    e = html.escape
    items, first_seen, new_keys, label_of = _flatten_watch(watch_groups)
    since = (day - timedelta(days=FRESH_DAYS)).isoformat()
    recent_since = (day - timedelta(days=RECENT_DAYS)).isoformat()
    picks = [it for it in _by_first_seen(items, first_seen, new_keys)
             if first_seen.get(it.key(), "") >= since][:FRESH_MAX]
    out = [f'<section id="fresh" data-today="{day.isoformat()}">',
           '<div class="hero"><div><h1 id="fresh-h">最近見つかったフォロー該当</h1>'
           f'<div class="meta">{meta}</div></div>'
           '<button class="btn" id="markread" type="button">すべて既読にする</button></div>']
    if picks:
        out.append('<div id="fresh-sub" class="meta" style="margin:-6px 0 10px">最近見つかった品</div>')
        out.append('<div class="g4">')
        for it in picks:
            seen = first_seen.get(it.key(), "")
            out.append(_photo_card(it, site_label=site_names.get(it.site, it.site), seen=seen,
                                   recent=seen >= recent_since,
                                   tag=_short_label(label_of[it.key()])))
        out.append("</div>")
    else:
        out.append('<div class="empty">最近見つかったフォロー該当はありません。</div>')
    out.append("</section>")
    return "\n".join(out)


def build_watch(groups, site_names, day: date) -> str:
    """groups: [{"label", "items": [Listing], "new_keys": set, "first_seen": {key: date}}]"""
    e = html.escape
    items, _, _, _ = _flatten_watch(groups)
    meta = (f"フォロー中 {len(items)}件 ・ {day:%Y年%m月%d日} 時点 ・ "
            f"{len(site_names)}サイト横断")
    out = [page_head("フォロー — 中古計測器トラッカー", active="watch")]
    out.append(_fresh_block(groups, site_names, day, meta))

    if not groups:
        out.append('<div class="empty">フォロー登録がありません。</div>')
    else:
        links = []
        for i, g in enumerate(groups):
            n = len(g["items"])
            cls = '' if n else ' class="z"'
            links.append(f'<a href="#w{i}"{cls}>{e(g["label"])}<span class="n">{n}</span></a>')
        out.append('<nav class="jump">' + "".join(links) + '</nav>')
    for i, g in enumerate(groups):
        first_seen = g.get("first_seen", {})
        its = _by_first_seen(g["items"], first_seen, g["new_keys"])
        out.append(f'<div class="sec" id="w{i}"><h2>{e(g["label"])}</h2>'
                   f'<span class="cnt">{len(its)}件</span></div>')
        if not its:
            out.append('<div class="empty">まだ一致する在庫はありません。'
                       '見つかり次第ここに表示されます。</div>')
            continue
        out.append('<div class="g5">')
        out.extend(_photo_card(it, site_label=site_names.get(it.site, it.site),
                               seen=first_seen.get(it.key(), "")) for it in its)
        out.append("</div>")

    out.append(page_foot())
    return "\n".join(out)


# ---- ホーム ------------------------------------------------------------------

def build_home(day: date, *, new_by_site=None, watch_groups=None,
               site_names=None, inventory_total=0, n_sites=0,
               archive_rows_html="", last_updated="", new_total=None) -> str:
    """トップページ。フォローの新着を最上段に写真で出し、その下に全サイトの新着と記録。
    new_total を渡すと在庫データ無しでも件数表示だけは正確にできる。"""
    site_names = site_names or {}
    new_by_site = new_by_site or {}
    watch_groups = watch_groups or []
    if new_total is None:
        new_total = sum(len(v) for v in new_by_site.values())
    items, _, _, _ = _flatten_watch(watch_groups)

    out = [page_head("中古計測器トラッカー", active="home")]
    meta = (f"フォロー中 {len(items)}件 ・ 今日の新着 {new_total}件 ・ 全在庫 {inventory_total:,}件"
            f" ・ {n_sites}サイト{(' ・ 最終更新 ' + last_updated) if last_updated else ''}")
    if watch_groups:
        out.append(_fresh_block(watch_groups, site_names, day, meta))
        out.append('<a class="more" href="watch.html">フォロー一覧へ →</a>')
    else:
        out.append(f'<div class="hero"><div><h1>中古計測器トラッカー</h1>'
                   f'<div class="meta">{meta}</div></div></div>')

    flat_new = [it for its in new_by_site.values() for it in its]
    if flat_new:
        out.append('<div class="sec"><h2>今日の新着(全サイト)</h2>'
                   f'<span class="cnt">{new_total}件</span></div>')
        out.append('<div class="g5">')
        out.extend(_photo_card(it, site_label=site_names.get(it.site, it.site))
                   for it in flat_new[:10])
        out.append('</div>')
        if new_total > 10:
            out.append('<a class="more" href="latest.html">すべての新着を見る →</a>')

    if archive_rows_html:
        out.append('<div class="sec"><h2>最近の記録</h2></div>')
        out.append('<table class="tb"><tr><th>日付</th>'
                   '<th style="text-align:right;">新着</th></tr>')
        out.append(archive_rows_html)
        out.append('</table>')
        out.append('<a class="more" href="latest.html">過去の新着をすべて見る →</a>')

    out.append(page_foot())
    return "\n".join(out)
