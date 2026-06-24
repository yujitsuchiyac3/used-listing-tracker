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

## ローカル実行

```bash
pip install -r requirements.txt

python3 main.py --dry-run            # 送信せず data/latest_email.html に出力
python3 main.py --dry-run --force-all# 差分でなく現在の全件を出力(動作確認用)
python3 main.py                      # 収集して送信(下記SMTP環境変数が必要)
```

メールのプレビューは `data/latest_email.html` をブラウザで開くか、
raw.githack 経由で確認できます。

## 自動実行(GitHub Actions)

`.github/workflows/daily.yml` が毎日 JST 8:00 に実行します。
リポジトリの **Settings → Secrets and variables → Actions** に以下を登録してください。

| Secret | 例 | 説明 |
|--------|-----|------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTPサーバ |
| `SMTP_PORT` | `465` | ポート(465=SSL) |
| `SMTP_USER` | `you@gmail.com` | 認証ユーザ |
| `SMTP_PASS` | `xxxx xxxx ...` | アプリパスワード等 |
| `MAIL_FROM` | `you@gmail.com` | 差出人(省略時 SMTP_USER) |
| `MAIL_TO` | `you@example.com` | 宛先(カンマ区切りで複数可) |

Gmail を使う場合は 2 段階認証を有効化し「アプリパスワード」を発行して `SMTP_PASS` に設定します。

## 新着判定の仕様

- サイトごとに `uid`(管理番号等)を `data/state.json` に記録し、**前回に無かった uid のみ**を新着とします。
- 初回実行はベースライン作成のみ(大量通知を防ぐため新着0扱い)。翌日以降から差分を通知します。
- オリックスは PDF の更新(差し替え/新版)を Last-Modified ベースで検知します。
