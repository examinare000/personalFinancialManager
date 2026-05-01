---
title: worker/Ph2/06 Yahoo!ショッピング 注文確認メールパーサ
service: worker
phase_task_id: 2.6
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.6（行 271-281）
branch: feature/parser-yahoo-mail
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/06 Yahoo!ショッピング 注文確認メールパーサ（Phase 2.6）

## このファイルの位置付け

原典 §4.2 Phase 2.6 を `worker` 担当の指示書として展開。Phase 2.4 (Amazon) / 2.5 (楽天) と独立並列可能。

## 担当サービス

`worker` コンテナ。Yahoo!ショッピングの注文確認メールを `Transaction` に正規化する `YahooMailAdapter`。**PayPay ポイント利用額を別フィールドで保持する**点が特徴（楽天ポイントと同じ思想だが別 EC）。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph2/03`（Gmail MCP）, `worker/Ph1/02`（IngestAdapter ABC） |
| 下流 | `worker/Ph2/08`（cron） |

## 入力

1. **原典**: §4.2 Phase 2.6（行 271-281）
2. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
3. **ADR**: `docs/adr/001-hybrid-ingestion-strategy.md`, `docs/adr/003-no-scraping.md`, `docs/adr/007-adapter-pattern.md`
4. **既存資産**: `Transaction`, `compute_hash`, `RawMail`, `IngestAdapter` ABC
5. **依存**: `mail-parser`, `beautifulsoup4`, `lxml`（既宣言）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `worker/src/kakeibo_worker/adapters/mail/yahoo.py` | `YahooMailAdapter` 実装 |
| `tests/fixtures/mail/yahoo/normal.eml` | PayPay ポイントなし合成メール |
| `tests/fixtures/mail/yahoo/with_paypay_points.eml` | PayPay ポイント利用あり |
| `tests/fixtures/mail/yahoo/expected.json` | 期待 Transaction 配列 |
| `worker/tests/unit/adapters/mail/test_yahoo.py` | ゴールデンマスタ + PayPay ポイント + ハッシュ決定性 |

## 実装方針

1. **クラス**: `YahooMailAdapter(IngestAdapter)`、`source: ClassVar[str] = "yahoo_mail"`。
2. **`parse(payload: RawMail | bytes) -> Iterable[Transaction]`**:
   - `body_html` 優先、なければ `body_text`
   - `BeautifulSoup(html, "lxml")` で抽出
3. **抽出フィールド**:
   - 注文番号（Yahoo!ショッピング独自フォーマット）
   - 注文日
   - 商品合計
   - **PayPay ポイント利用額**
   - 支払金額（= 商品合計 − ポイント）
4. **金額符号**: 支払金額を `Transaction.amount` の **負値**として採用。
5. **`raw_payload`**: 注文番号 / 商品合計 / PayPay ポイント利用額 / 支払金額を JSON で保持。
6. **ハッシュ**: 注文番号を description に含める（Phase 2.4 / 2.5 と同じ規約）。
7. **`extract_holdings`**: 空イテラブル。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/mail/yahoo/{normal,with_paypay_points}.eml` を合成。
- `tests/fixtures/mail/yahoo/expected.json` に期待値。
- `worker/tests/unit/adapters/mail/test_yahoo.py`：
  - ポイントなし: `raw_payload["paypay_points_used"] == "0"`
  - ポイントあり: `raw_payload["paypay_points_used"] == "<利用額>"`
  - 同一メール 2 回でハッシュ一致
  - 注文番号別で別ハッシュ

### 2. Green

- `worker/src/kakeibo_worker/adapters/mail/yahoo.py` で `YahooMailAdapter` を最小実装。

### 3. Refactor

- Yahoo 独自の HTML 構造定数をモジュールトップレベル化。
- Amazon / 楽天 との共通化は **しない**。

## 受入条件

- 通常 / PayPay ポイント利用ありの 2 パターンで `expected.json` と完全一致
- PayPay ポイント利用額が `raw_payload["paypay_points_used"]` で別フィールド保持
- 注文番号で冪等性が成立
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
docker compose run --rm worker pytest worker/tests/unit/adapters/mail/test_yahoo.py
docker compose run --rm worker ruff check .
docker compose run --rm worker pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/parser-yahoo-mail`
- コミット粒度（最低 3 件）：
  1. `テスト: Yahooメールゴールデンマスタ（通常/PayPayポイント）テストを先行作成`
  2. `機能: YahooMailAdapter本体（注文番号・金額・PayPayポイント抽出）を実装`
  3. `機能: 支払金額算出とraw_payloadへのポイント情報保持を追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.6 Yahoo!ショッピング 注文確認メールパーサを実装。

## 成果物
- worker/src/kakeibo_worker/adapters/mail/yahoo.py
- tests/fixtures/mail/yahoo/{normal,with_paypay_points}.eml
- tests/fixtures/mail/yahoo/expected.json
- worker/tests/unit/adapters/mail/test_yahoo.py

## 検証結果
- 全件緑（2 パターン）
- pyright / ruff: クリーン

## 次のアクション提案
worker/Ph2/04, 05 完了を待って worker/Ph2/08 へ。
```

## 注意事項

- **スクレイピング禁止**（ADR-003）: メール本文以外（Yahoo!ショッピングのマイページ）から取得しない。
- **実注文情報を fixture に含めない**: 注文番号・氏名・住所・商品名は合成。
- PayPay ポイントと PayPay 残高は別物。本タスクは **ポイント利用** のみ扱い、PayPay 残高決済は Phase 2.7 PayPal API とも別レーン（PayPay 残高は `compose.yml` に未準備のため Phase 4 以降で評価）。
- 3 EC（Amazon / 楽天 / Yahoo）でメール構造が大きく異なる。共通化リファクタは Phase 4 以降で評価。
