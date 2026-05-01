---
title: worker/Ph2/05 楽天市場 注文確認メールパーサ
service: worker
phase_task_id: 2.5
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.5（行 259-269）
branch: feature/parser-rakuten-mail
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/05 楽天市場 注文確認メールパーサ（Phase 2.5）

## このファイルの位置付け

原典 §4.2 Phase 2.5 を `worker` 担当の指示書として展開。Phase 2.4（Amazon）/ 2.6（Yahoo）と独立並列可能。

## 担当サービス

`worker` コンテナ。楽天市場の注文確認メールを `Transaction` に正規化する `RakutenMailAdapter`。Gmail MCP（`worker/Ph2/03`）から取得した `RawMail` を入力とする。**楽天ポイント利用額を別フィールドで保持する**点が特徴。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph2/03`（Gmail MCP）, `worker/Ph1/02`（IngestAdapter ABC） |
| 下流 | `worker/Ph2/08`（cron） |

## 入力

1. **原典**: §4.2 Phase 2.5（行 259-269）
2. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
3. **ADR**: `docs/adr/001-hybrid-ingestion-strategy.md`, `docs/adr/003-no-scraping.md`, `docs/adr/007-adapter-pattern.md`
4. **既存資産**: `Transaction`, `compute_hash`, `RawMail`, `IngestAdapter` ABC
5. **依存**: `mail-parser`, `beautifulsoup4`, `lxml`（既宣言）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `src/kakeibo/adapters/mail/rakuten.py` | `RakutenMailAdapter` 実装 |
| `tests/fixtures/mail/rakuten/normal.eml` | ポイント利用なし合成メール |
| `tests/fixtures/mail/rakuten/with_points.eml` | ポイント利用あり |
| `tests/fixtures/mail/rakuten/expected.json` | 期待 Transaction 配列 |
| `tests/unit/adapters/mail/test_rakuten.py` | ゴールデンマスタ + ポイント利用 + ハッシュ決定性 |

## 実装方針

1. **クラス**: `RakutenMailAdapter(IngestAdapter)`、`source: ClassVar[str] = "rakuten_mail"`。
2. **`parse(payload: RawMail | bytes) -> Iterable[Transaction]`**:
   - `body_html` 優先、なければ `body_text`
   - `BeautifulSoup(html, "lxml")` で抽出
3. **抽出フィールド**:
   - 注文番号（`注文番号: <ID>` 正規表現）
   - 注文日
   - 商品合計（`商品合計: ¥<amount>`）
   - **楽天ポイント利用**（`楽天ポイント: -<amount>` のような表記）
   - 支払金額（`お支払金額: ¥<amount>` = 商品合計 − ポイント）
4. **金額符号**: 支払金額（実際に決済された額）を `Transaction.amount` の **負値**として採用。
5. **`raw_payload`**: 注文番号 / 商品合計 / ポイント利用額 / 支払金額を JSON で保持。**ポイント利用額は別フィールドで明示**（原典「楽天ポイント利用額が別フィールドで保持される」）。
6. **ハッシュ**: 注文番号を description に含める（Phase 2.4 と同じ規約）。
7. **`extract_holdings`**: 空イテラブル。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/mail/rakuten/{normal,with_points}.eml` を合成。
- `tests/fixtures/mail/rakuten/expected.json` に期待値（ポイント利用額を含む）。
- `tests/unit/adapters/mail/test_rakuten.py`：
  - ポイント利用なし: `raw_payload["points_used"] == "0"` / `amount == -商品合計`
  - ポイント利用あり: `raw_payload["points_used"] == "<利用額>"` / `amount == -支払金額`
  - 注文番号別で別ハッシュ
  - 同一メール 2 回パースでハッシュ一致

### 2. Green

- `src/kakeibo/adapters/mail/rakuten.py` で `RakutenMailAdapter` を最小実装。
- 楽天独自の HTML 構造に合わせた正規表現を順に追加。

### 3. Refactor

- 共通定数（楽天ポイント表記のバリエーション）をモジュールトップレベル化。
- Amazon との共通化は **しない**（メール構造差が大きい）。

## 受入条件

- 通常 / ポイント利用ありの 2 パターンで `expected.json` と完全一致
- 楽天ポイント利用額が `raw_payload["points_used"]` で別フィールド保持
- 注文番号で冪等性が成立（同注文 2 回投入で行数増えず）
- 金額が `Decimal`、支払金額が負値で `amount` に格納
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/adapters/mail/test_rakuten.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/parser-rakuten-mail`
- コミット粒度（最低 3 件）：
  1. `テスト: 楽天メールゴールデンマスタ（通常/ポイント利用）テストを先行作成`
  2. `機能: RakutenMailAdapter本体（注文番号・金額・ポイント抽出）を実装`
  3. `機能: 楽天ポイント利用額のraw_payload保持と支払金額算出を追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.5 楽天市場 注文確認メールパーサを実装。

## 成果物
- src/kakeibo/adapters/mail/rakuten.py
- tests/fixtures/mail/rakuten/{normal,with_points}.eml
- tests/fixtures/mail/rakuten/expected.json
- tests/unit/adapters/mail/test_rakuten.py

## 検証結果
- 全件緑（2 パターン）
- ポイント利用額の別フィールド保持を確認
- pyright / ruff: クリーン

## 次のアクション提案
worker/Ph2/04, 06 完了を待って worker/Ph2/08 へ。
```

## 注意事項

- **ポイント利用額を支払金額に二重計上しない**：商品合計 − ポイント = 支払金額の関係を fixture で固定し、テストで保証。
- **スクレイピング禁止**（ADR-003）: メール本文以外（楽天サイトのマイページ）から取得しない。
- **実注文情報を fixture に含めない**: 注文番号・氏名・住所・商品名は合成。
- 楽天証券（投信・国内株・米国株）の CSV は **本タスクの対象外**（リスク R-02、Phase 1 拡張時に別 ADR）。
