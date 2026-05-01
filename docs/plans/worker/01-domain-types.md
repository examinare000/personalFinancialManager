---
title: worker/01 ドメイン共通型（Transaction / Holding / BalanceSnapshot）
service: worker
phase_task_id: 1.2
priority: 高
source_plan: docs/plans/03-phase1-domain-types.md
branch: feature/domain-types
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/01 ドメイン共通型（Phase 1.2）

## このファイルの位置付け

原典 `docs/plans/03-phase1-domain-types.md` を `worker` サービス担当の実装指示書として再編。原典との乖離時は原典優先。

## 担当サービス

`worker` コンテナ。`src/kakeibo/domain/` 配下の dataclass モジュール群。`api` コンテナも `src/kakeibo` を import するが、Phase1 では参照しない。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `postgres/01`（DB スキーマ） |
| 下流 | `worker/02`（IngestAdapter ABC） / `worker/06`（ハッシュ冪等性 PBT）から参照 |

## 入力（Coder が読むべきファイル）

1. **原典**: `docs/plans/03-phase1-domain-types.md`（必読）
2. **データモデル**: `postgres/docs/design/01-data-model.md`
3. **取込アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
4. **ADR**: `docs/adr/005-numeric-money-type.md`, `docs/adr/006-hash-uniqueness.md`
5. **既存スケルトン**: `src/kakeibo/domain/__init__.py`（プレースホルダ。本タスクで中身を実装）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `src/kakeibo/domain/__init__.py` | 公開 API の集約（`Transaction`, `Holding`, `BalanceSnapshot`, `SymbolKind`, `compute_hash`） |
| `src/kakeibo/domain/transaction.py` | `Transaction` dataclass + `compute_hash` |
| `src/kakeibo/domain/holding.py` | `Holding` dataclass + `SymbolKind` (StrEnum) |
| `src/kakeibo/domain/balance_snapshot.py` | `BalanceSnapshot` dataclass |
| `src/kakeibo/domain/currency.py` | 通貨コードバリデータ（ISO 4217 3 文字英大文字） |
| `tests/unit/domain/__init__.py` | 新規（パッケージ初期化） |
| `tests/unit/domain/test_transaction.py` | バリデーション + `compute_hash` 決定性 |
| `tests/unit/domain/test_holding.py` | `SymbolKind` 範囲 + バリデーション |
| `tests/unit/domain/test_balance_snapshot.py` | バリデーション |
| `tests/unit/domain/test_currency.py` | 通貨コードバリデータ |

## 実装方針（原典 §実装方針より要約）

1. **dataclass 第一選択**: `@dataclass(frozen=True, slots=True)` + `__post_init__` で手書きバリデーション。pydantic は使わない（依存縮小）。
2. **Transaction フィールド**: `account_id: int`, `occurred_on: date`, `occurred_at: datetime | None`, `amount: Decimal`, `currency: str`, `description: str`, `category_id: int | None`, `category_source: Literal['rule','llm','manual'] | None`, `raw_payload: dict[str, Any]`, `hash: str`。
3. **バリデーション**: `amount is None` → `ValueError`、`len(currency) != 3 or not currency.isalpha() or not currency.isupper()` → `ValueError`、`occurred_on` が `date` でない → `TypeError`。
4. **`compute_hash`**: `f"{account_id}|{occurred_on.isoformat()}|{amount}|{description}"` を UTF-8 で encode → `hashlib.sha256(...).hexdigest()`。description のトリミングは **行わない**（境界条件は `worker/06` で確定）。
5. **`SymbolKind`**: `enum.StrEnum` で `STOCK / FUND / ETF / CRYPTO / CASH`（`design/01-data-model.md` と整合）。
6. **`BalanceSnapshot`**: `account_id`, `as_of_date: date`, `balance: Decimal`, `currency: str`。

## 実装手順（TDD）

### 0. ブランチ作成

```bash
git checkout develop && git pull origin develop
git checkout -b feature/domain-types
```

### 1. Red

- `tests/unit/domain/test_transaction.py` に正常系 1 件 + 異常系 7 件以上（`amount=None`, `currency="JP"`, `currency="jpy"`, `currency="JPYY"`, `occurred_on="2026-04-30"` など）。
- `compute_hash` 決定性: 同一引数 100 回呼んで同一 hex / 引数 1 つ変えると別 hex（`account_id`/`occurred_on`/`amount`/`description` を 1 件ずつ変える）。
- `tests/unit/domain/test_holding.py` で `SymbolKind` 列挙、未定義値で例外。
- `tests/unit/domain/test_balance_snapshot.py` で `Decimal` / `date` 強制。
- `tests/unit/domain/test_currency.py` で通貨コードバリデータの境界。
- `pytest tests/unit/domain/` で全件落ちることを確認。

### 2. Green

- `currency.py` → `transaction.py` → `holding.py` → `balance_snapshot.py` の順に最小実装。
- 各実装で対応するテストが緑になることを確認。

### 3. Refactor

- バリデーション共通部分（`_ensure_decimal`, `_ensure_date`）を `currency.py` 隣接の `_validators.py` に抽出するか検討。早すぎる抽象化は避ける。

## 受入条件

- `Transaction.amount` が `Decimal`（`isinstance(tx.amount, Decimal) is True`）
- `Transaction.occurred_on` が `date`、`occurred_at` が `datetime | None`
- 異常値で `ValueError` または `TypeError` が発生
- `compute_hash(1, date(2026,4,30), Decimal("1234.56"), "コンビニ")` が複数回呼んで同じ SHA256 hex
- `Holding.symbol_kind` に `SymbolKind` 以外を渡すと型エラー（pyright）または実行時エラー
- `pyright` クリーン、`ruff check` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/domain/    # 全件緑（< 5 秒）
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/domain-types`
- コミット粒度（最低 5 件）：
  1. `テスト: ドメイン共通型のバリデーションとcompute_hash決定性テストを先行作成`
  2. `機能: 通貨コードバリデータとSymbolKind列挙を追加`
  3. `機能: Transaction共通型とcompute_hash関数を実装`
  4. `機能: Holding共通型を実装`
  5. `機能: BalanceSnapshot共通型を実装`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 1.2 ドメイン共通型を実装。

## 成果物
- src/kakeibo/domain/{transaction,holding,balance_snapshot,currency}.py
- tests/unit/domain/test_*.py（4 ファイル）

## 検証結果
- pytest tests/unit/domain/: 全件緑（X 秒）
- pyright / ruff: クリーン

## 既知の課題・申し送り
- description の前後空白の扱いは Phase 1.7（worker/06）で確定する暫定方針。

## 次のアクション提案
worker/02-ingest-adapter-base.md（Phase 1.3）の着手準備が整った。
```

## 注意事項

- pydantic を導入しない。依存膨張を避ける（`docs/plans/03-phase1-domain-types.md` §実装方針 1）。
- `compute_hash` 内で description を strip しない。境界条件は `worker/06` で property-based test として固定する。
- `hash: str` は dataclass のフィールドだが、`__post_init__` で `compute_hash(...)` を計算してフィールドに設定するか、生成側で渡すかの設計選択がある。原典は明示していないが、**呼び出し側で `compute_hash` を呼んで `hash` を渡す** 方式を採用（不変条件が単純で、テストしやすい）。
