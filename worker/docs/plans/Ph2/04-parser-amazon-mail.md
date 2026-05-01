---
title: worker/Ph2/04 Amazon 注文確認メールパーサ
service: worker
phase_task_id: 2.4
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.4（行 247-257）
branch: feature/parser-amazon-mail
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/04 Amazon 注文確認メールパーサ（Phase 2.4）

## このファイルの位置付け

原典 `docs/plans/01-development-plan.md` §4.2 Phase 2.4 を `worker` サービス担当の指示書として展開。Phase 2.5 / 2.6（楽天 / Yahoo）と独立並行可能。

## 担当サービス

`worker` コンテナ。Amazon の注文確認メール（HTML / Plain）を `Transaction` に正規化する `AmazonMailAdapter`。Gmail MCP（`worker/Ph2/03`）から取得した `RawMail` を入力とする。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph2/03`（Gmail MCP）, `worker/Ph1/02`（IngestAdapter ABC） |
| 下流 | `worker/Ph2/08`（cron バッチ） |

`worker/Ph2/05`, `worker/Ph2/06` と独立並列可能。

## 入力

1. **原典**: §4.2 Phase 2.4（行 247-257）
2. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
3. **ADR**: `docs/adr/001-hybrid-ingestion-strategy.md`, `docs/adr/003-no-scraping.md`, `docs/adr/007-adapter-pattern.md`
4. **既存資産**:
   - `worker/src/kakeibo_worker/adapters/base.py`（IngestAdapter ABC）
   - `shared/kakeibo_shared/domain/transaction.py`（`Transaction`, `compute_hash`）
   - `shared/kakeibo_shared/domain/raw_mail.py`（`worker/Ph2/03` で実装される）
5. **依存**: `mail-parser`, `beautifulsoup4`, `lxml`（`pyproject.toml` `[project.optional-dependencies].mail` に既宣言）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `worker/src/kakeibo_worker/adapters/mail/__init__.py` | 新規パッケージ |
| `worker/src/kakeibo_worker/adapters/mail/amazon.py` | `AmazonMailAdapter` 実装 |
| `tests/fixtures/mail/amazon/normal.eml` | 通常購入の合成メール |
| `tests/fixtures/mail/amazon/multiple_items.eml` | 複数商品 |
| `tests/fixtures/mail/amazon/gift_card.eml` | ギフト券利用 |
| `tests/fixtures/mail/amazon/expected.json` | 期待 Transaction 配列 |
| `tests/unit/adapters/mail/test_amazon.py` | ゴールデンマスタ + エッジケース |

## 実装方針

1. **クラス**: `AmazonMailAdapter(IngestAdapter)`、`source: ClassVar[str] = "amazon_mail"`。
2. **`parse(payload: RawMail | bytes) -> Iterable[Transaction]`**:
   - `payload` が `bytes` なら `email.message_from_bytes` でパース → `RawMail` に変換 → 統一処理
   - `RawMail.body_html` 優先、なければ `body_text`
   - HTML から `BeautifulSoup(html, "lxml")` で抽出
3. **抽出フィールド**:
   - 注文番号（`注文番号: <ID>` の正規表現）
   - 注文日（メール件名 or 本文の日付。なければ `received_at.date()`）
   - 合計金額（`合計: ¥<amount>` 正規表現、カンマ除去 → `Decimal`）
   - 主商品名（先頭商品の名称、複数商品時は最初の 1 件 + `…他N件`）
4. **金額符号**: 購入は **負値**（出費）。
5. **`raw_payload`**: 注文番号・全商品名・元 HTML 抜粋を JSON で保持。
6. **ハッシュ**: 共通 `compute_hash(self.account_id, occurred_on, amount, description)`。description に **注文番号を含める** ことで、同日同額の別注文を一意に区別する（原典「ハッシュは『注文番号 + 金額』で重複検出」と整合）。
7. **ギフト券利用**: `ギフト券残高利用: -¥<amount>` のような表記を読み、合計金額に既に反映されているか確認 → 二重計上防止。
8. **`extract_holdings`**: 空イテラブル `return ()`。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/mail/amazon/{normal,multiple_items,gift_card}.eml` を合成データで作成（実注文情報禁止）。
- `tests/fixtures/mail/amazon/expected.json` に期待 Transaction を記述。
- `tests/unit/adapters/mail/test_amazon.py`：
  - 3 パターン全てでゴールデンマスタ完全一致
  - 金額が `Decimal`、購入は負値
  - 注文番号が `raw_payload["order_id"]` に保持される
  - 同一メール 2 回パースでハッシュ一致
  - 注文番号が異なれば同額同日でも別ハッシュ
  - HTML が壊れている場合に `AdapterError`

### 2. Green

- `worker/src/kakeibo_worker/adapters/mail/amazon.py` で `AmazonMailAdapter` を最小実装。
- `BeautifulSoup` での抽出 → 正規表現での金額抽出 → `Transaction` 生成。
- 各テスト順に通す。

### 3. Refactor

- 共通正規表現（`_AMOUNT_RE`, `_ORDER_ID_RE`）をモジュールトップレベル化。
- HTML / Plain の振り分けを `_extract_text(raw: RawMail) -> str` に抽出（楽天・Yahoo パーサと共通化検討は **しない**：早すぎる抽象化）。

## 受入条件

- 通常 / 複数商品 / ギフト券の 3 パターンで `expected.json` と完全一致
- 金額が `Decimal` で生成される
- 注文番号が `raw_payload["order_id"]` に保持される
- ハッシュが「注文番号 + 金額」で重複検出可能（description に order_id 含む）
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/adapters/mail/test_amazon.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/parser-amazon-mail`
- コミット粒度（最低 4 件）：
  1. `テスト: Amazon メールゴールデンマスタ（通常/複数商品/ギフト券）テストを先行作成`
  2. `機能: AmazonMailAdapter本体（HTMLから注文番号・金額・日付抽出）を実装`
  3. `機能: ギフト券残高利用の検出と二重計上回避を追加`
  4. `テスト: ハッシュ決定性と注文番号別の独立性を検証`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.4 Amazon 注文確認メールパーサを実装。

## 成果物
- worker/src/kakeibo_worker/adapters/mail/amazon.py
- tests/fixtures/mail/amazon/{normal,multiple_items,gift_card}.eml
- tests/fixtures/mail/amazon/expected.json
- tests/unit/adapters/mail/test_amazon.py

## 検証結果
- 3 パターン全件緑
- pyright / ruff: クリーン

## 次のアクション提案
worker/Ph2/05, 06 と並行で進行可能。
```

## 注意事項

- **スクレイピング不採用**（ADR-003）: メール本文以外（Amazon サイトの注文履歴 HTML）を取得しない。
- **実注文情報を fixture に含めない**: 注文番号・氏名・住所・購入商品名は合成データのみ。テンプレートとして「`商品名サンプル_001`」のような placeholder を使う。
- **楽天 / Yahoo との共通化を急がない**: 3 EC でメール構造が異なるため、Phase 2.4〜2.6 は独立実装で進める。共通基盤は Phase 4 以降で評価。
- **HTML 構造変化リスク**: Amazon が HTML レイアウトを変える可能性がある。fixtures で固定化し、運用で破綻したらすぐ ADR を起票。
- ハッシュ衝突の境界条件は `worker/Ph1/06`（PBT）と整合させる。description に order_id を含める方針はここで確定。
