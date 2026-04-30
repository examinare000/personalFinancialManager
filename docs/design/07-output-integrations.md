---
title: 外部出力連携 詳細設計
version: 1.0
status: Draft
last_updated: 2026-04-30
related_adrs: []
---

# 外部出力連携 詳細設計

## 1. 概要

本ドキュメントは、本アプリケーションのデータを外部ツール（Obsidian / 表計算ソフト / カレンダー）へ書き出す出力モジュールの詳細設計を示す。概要設計 §3.1 の出力レイヤを実装可能なレベルで定義する。

設計方針:
- 出力は **読み取り専用**（外部システムを書き換えない、自分のNAS外には出ない）
- 出力フォーマットは人間が直接読める形式を優先（Markdown / CSV / iCal）
- バッチ起動（cron）と手動起動（CLIサブコマンド）の両方に対応

## 2. 出力モジュール一覧

| 出力先 | 形式 | 用途 | フェーズ |
|---|---|---|---|
| Obsidian Vault | Markdown | 月次サマリの個人メモ統合 | Phase 4 |
| CSV export | CSV (UTF-8 BOM付き) | 確定申告・家族との共有 | Phase 3 |
| iCal export | ics | 大型支出のカレンダー反映 | 将来 |

## 3. Obsidian 月次サマリ出力

### 3.1 出力先

- パス: `/volume1/obsidian/Vault/Finance/YYYY/YYYY-MM.md`
- 各月1ファイル。同一ファイルへの再書き込みは前回内容を上書き
- 既存ファイルがあった場合の取扱: フロントマター `auto_generated: true` のものは上書き、そうでなければスキップしてログに記録

### 3.2 フォーマット

```markdown
---
title: 2026年4月の家計サマリ
auto_generated: true
generated_at: 2026-05-01T03:00:00+09:00
month: 2026-04
total_income: 450000
total_expense: 320000
net: 130000
---

# 2026年4月の家計サマリ

## 月次サマリ

- 収入合計: ¥450,000
- 支出合計: ¥320,000
- 差引: **¥130,000**

## カテゴリ別支出

| カテゴリ | 金額 | 件数 | 構成比 |
|---|---:|---:|---:|
| 食費/外食 | ¥45,000 | 18 | 14.1% |
| 食費/食材 | ¥38,000 | 22 | 11.9% |
| 固定費/家賃 | ¥120,000 | 1 | 37.5% |
| 公共料金/電気 | ¥12,000 | 1 | 3.8% |
| 通信費/携帯 | ¥8,500 | 1 | 2.7% |
| ... | ... | ... | ... |

## 残高推移

| 口座 | 月初 | 月末 | 変動 |
|---|---:|---:|---:|
| MUFG ****1234 | ¥800,000 | ¥780,000 | -¥20,000 |
| SMBC ****5678 | ¥250,000 | ¥320,000 | +¥70,000 |
| 楽天証券 | ¥1,500,000 | ¥1,580,000 | +¥80,000 |

## ポートフォリオ構成（月末時点）

| 種別 | 評価額 | 構成比 |
|---|---:|---:|
| 現金 | ¥1,100,000 | 41.0% |
| 投資信託 | ¥980,000 | 36.6% |
| 国内株式 | ¥600,000 | 22.4% |

## 主要な支出（金額上位5件）

1. 2026-04-01 家賃 ¥120,000
2. 2026-04-15 電化製品購入（Amazon） ¥35,000
3. 2026-04-10 SMBC日興証券 投信買付 ¥30,000
4. 2026-04-22 旅行 新幹線 ¥18,000
5. 2026-04-05 公共料金（電気・ガス・水道合計） ¥17,500

## 未分類取引

- 2026-04-12 ¥-3,500 「PAYMENT*XXXX」（要分類）

## 自動分類率

- ルール: 82% (245件)
- LLM: 14% (42件)
- 未分類: 4% (13件)
```

### 3.3 生成スクリプト

```python
# tools/export_obsidian.py
import argparse
from datetime import date
from pathlib import Path

from app.db import session
from app.exporters.obsidian import build_monthly_markdown


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--vault", default="/volume1/obsidian/Vault/Finance")
    args = parser.parse_args()

    year, month = map(int, args.month.split("-"))
    target_month = date(year, month, 1)

    md = build_monthly_markdown(session(), target_month)
    out = Path(args.vault) / f"{year}" / f"{args.month}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
```

### 3.4 cron スケジュール

毎月1日午前3時に前月分を生成:

```cron
0 3 1 * * docker compose run --rm worker python -m tools.export_obsidian --month $(date -d 'last month' +\%Y-\%m)
```

## 4. CSV export

### 4.1 仕様

| 項目 | 値 |
|---|---|
| 文字コード | UTF-8 BOM付き（Excel互換） |
| 区切り | カンマ |
| 引用 | RFC 4180準拠（フィールドにカンマ・改行・ダブルクォートを含む場合のみ） |
| ヘッダ | 1行目に列名 |
| 改行 | CRLF |

### 4.2 export種類

| 種類 | 内容 | 用途 |
|---|---|---|
| `transactions.csv` | 取引明細（指定期間） | 確定申告の帳票準備 |
| `holdings.csv` | 保有資産スナップショット | 資産棚卸 |
| `monthly_summary.csv` | 月次集計（カテゴリ別） | 表計算ソフトでのグラフ作成 |

### 4.3 列定義例（transactions.csv）

```csv
"id","occurred_on","occurred_at","institution","account_no_masked","amount","currency","description","counterparty","category","category_source"
12345,"2026-04-15","2026-04-15T12:34:56+09:00","mufg","****1234",-1280,"JPY","コンビニ","セブン-イレブン渋谷","食費/コンビニ","rule"
```

### 4.4 CLI

```bash
docker compose run --rm worker python -m tools.export_csv \
  --type transactions \
  --since 2026-01-01 \
  --until 2026-12-31 \
  --output /export/transactions_2026.csv
```

`/export/` は NAS共有フォルダに mount されたディレクトリ。

## 5. iCal export（将来）

### 5.1 想定ユースケース

- 大型支出（10万円超）の発生日をカレンダーで可視化
- 固定費（家賃・サブスク）の引落予定日アラート

### 5.2 仕様（暫定）

- RFC 5545 準拠の `.ics` ファイル
- イベント形式: 終日イベント、サマリは「カテゴリ + 金額」、説明欄に詳細
- 1ファイル = 1ユーザ年（2026.ics）

```ics
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//kakeibo//ical-export//JP
BEGIN:VEVENT
UID:kakeibo-tx-12345@local
DTSTART;VALUE=DATE:20260401
SUMMARY:[家賃] ¥120,000
DESCRIPTION:三菱UFJ銀行 ****1234 から引落
END:VEVENT
END:VCALENDAR
```

### 5.3 配信方法

- `/export/calendar.ics` をWeb公開せず、ファイル配信
- ユーザはiPhone/Macで「URLからカレンダー購読」でTailscale URL を指定

## 6. 起動方法まとめ

| 用途 | 起動 |
|---|---|
| 月次Obsidianサマリ | cron 月初3時 |
| 任意期間CSV | 手動CLI |
| 年次iCal | cron 年初 or 手動 |

すべてのツールは `docker compose run --rm worker python -m tools.<name>` で起動可能。

## 7. エラーハンドリング

| エラー | 対応 |
|---|---|
| 出力先ディレクトリが存在しない | `mkdir -p` で自動作成 |
| 出力先ファイルが既存（auto_generated=false） | スキップしてログに記録 |
| データ0件 | 空ファイルではなく「該当データなし」プレースホルダ生成 |
| 出力中の例外 | 一時ファイル（.tmp）に書き込み、成功時にrename。中途半端なファイルを残さない |

## 8. 既知の課題・申し送り

- Obsidianリンク化（カテゴリ名を `[[食費/外食]]` リンクにする）はユーザのVault構成に依存するため設定可能にする。
- グラフ画像生成（matplotlib）は当面未対応。Obsidianプラグイン（dataview等）で代替できるならそちらを推奨。
- 確定申告用CSVフォーマットは税理士・国税庁書式に合わせて将来拡張。
- iCal export はユーザ需要を見て Phase 5 以降で実装。
