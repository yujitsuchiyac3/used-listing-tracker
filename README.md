# used-listing-tracker

複数の中古計測器サイトを毎日巡回し、**前回からの新着のみ**をまとめて1通のメール
(HTML・画像入り)で受け取るためのツール。GitHub Actions の cron で 1 日 1 回自動実行します。

## 対象サイト（8）

| サイト | 新着源 | 備考 |
|--------|--------|------|
| オルティカ | `/product/?status=new` | 外観ランク/付属品を詳細から補完 |
| アスカインデックス | `create_from`＋カテゴリ | 価格は問合せ中心。対象: 理化学/半導体 |
| Hitech & Facility | `/cate/20/`(最新入荷) | 価格まで取得 |
| オリックス・レンテック | PDF更新検知 | 中古機器販売リスト(電気/通信/分析) |
| 中古市場(チューコイチ) | 登録日別一覧 | 文字コード自動判定 |
| 計測器ランド リセール | 全ページ巡回(差分判定) | Color Me Shop |
| タナカ・トレーディング | `/hp01/new_items/` | 価格は問合せ |
| 中古研究機器.com | 新着ニュース(仕入情報/新着製品) | 価格/保証を詳細から補完 |

## 構成

```
scrapers/      サイトごとの実装(1サイト1ファイル)+ 共通基盤 base.py
core/
  notifier.py  メール(件名/HTML/テキスト)生成
  storage.py   スナップショット差分(新着判定)
  mailer.py    画像のインライン埋め込み＋SMTP送信
main.py        統合ランナー
.github/workflows/daily.yml  1日1回の自動実行
data/          スナップショット(state.json)・メールアーカイブ
```

## 実行

```bash
pip install -r requirements.txt

python3 main.py              # 収集して HTML を生成(data/latest.html 等)
python3 main.py --force-all  # 差分でなく現在の全件を出力(動作確認用)
python3 main.py --send       # 上記に加えてメール送信も行う(任意, SMTP環境変数が必要)
```

既定ではメール送信せず、以下の HTML を生成します:

| ファイル | 内容 |
|---------|------|
| `data/latest.html` | 最新の新着まとめ |
| `data/archive/YYYY-MM-DD.html` | 日付別アーカイブ |
| `data/index.html` | 最新版＋アーカイブへのリンク一覧 |

## 閲覧(GitHub上のHTMLをプレビュー)

GitHub はHTMLをソース表示するため、`raw.githack.com` 経由でレンダリング表示します:

```
https://raw.githack.com/yujitsuchiyac3/used-listing-tracker/main/data/index.html
https://raw.githack.com/yujitsuchiyac3/used-listing-tracker/main/data/latest.html
```

## 自動実行

1日1回クロールして HTML を生成・コミットする運用です(メール送信なし)。
`--send` を付ければメール送信も可能ですが、その場合は下記のSMTP環境変数が必要です。

| 環境変数 | 例 |
|--------|-----|
| `SMTP_HOST` / `SMTP_PORT` | `smtp-relay.brevo.com` / `587` |
| `SMTP_USER` / `SMTP_PASS` | SMTPログイン / SMTPキー |
| `MAIL_FROM` / `MAIL_TO` | 差出人 / 宛先 |

## 新着判定の仕様

- サイトごとに `uid`(管理番号等)を `data/state.json` に記録し、**前回に無かった uid のみ**を新着とします。
- 初回実行はベースライン作成のみ(大量通知を防ぐため新着0扱い)。翌日以降から差分を通知します。
- オリックスは PDF の更新(差し替え/新版)を Last-Modified ベースで検知します。
