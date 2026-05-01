---
title: Phase 1.2 共通型（Transaction / Holding / BalanceSnapshot）
phase: 1
task_id: 1.2
status: Draft
priority: 高
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.2 共通型（Transaction / Holding / BalanceSnapshot）

## タスク概要

各取込アダプタが返す**正規化済みドメインオブジェクト**を `dataclass` (or pydantic) でアプリ層に定義し、Phase 1.1 で確立した DB スキーマと型レベルで対応付ける。`compute_hash(account_id, occurred_on, amount, description)` を決定的な SHA256 として実装し、ADR-006 の冪等性戦略をコードで担保する。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.2, `postgres/docs/design/01-data-model.md`, `worker/docs/design/02-ingest-adapters.md`。

## 目的・背景

### 目的

- アダプタ層の出力契約を `Transaction` / `Holding` / `BalanceSnapshot` ドメイン型として固定し、Phase 1.3 以降のアダプタ実装が同じ型を返すことで型エラーが検出されるようにする。
- `Decimal` 型による金額表現（ADR-005）を Python 層で徹底し、`float` 混入を型レベルで防ぐ。
- ハッシュ生成関数を 1 箇所に集約し、機関ごとのアダプタ実装で再発明されないようにする（ADR-006）。

### 背景

- DB スキーマ（Phase 1.1）が確定しても、アプリ層の型がバラバラだと各アダプタが独自に dict を返してしまい、CLI 永続化層で重複正規化コードが発生する。
- 共通型は「アダプタの戻り値 → CLI / Watcher の入力」という契約点であり、Phase 2 以降のメールパーサ・API クライアントも同じ型を再利用する。
- `Decimal` の通貨コード（ISO 4217 3 文字）バリデーションを最初から強制しないと、Phase 4 の集計で「JPY と USD を合算」のような誤りが入り込む余地が残る。

## スコープ

### 含む

- `Transaction` / `Holding` / `BalanceSnapshot` の dataclass（または pydantic v2 モデル）定義。
- `Transaction.amount` を `Decimal`、`occurred_on` を `date`、`occurred_at` を `Optional[datetime]` として定義。
- 通貨コードのバリデーション（3 文字英大文字）。
- `compute_hash(account_id, occurred_on, amount, description) -> str`（SHA256 hex）。
- 不正値（`amount=None`、通貨コード長違反、`occurred_on` 型違反）でのバリデーションエラー発生。
- `Holding.symbol_kind` の許容値（`'stock' | 'fund' | 'etf' | 'crypto' | 'cash'` 等、design/01 と整合）の Enum 定義。

### 含まない

- DB との永続化ロジック（CLI / repository は Phase 1.6）。
- アダプタ実装（Phase 1.3 以降）。
- LLM / カテゴリ推論の入力としての特殊フィールド（Phase 4.1）。

## 依存タスク

- `02-phase1-db-schema-and-migrations.md`（Phase 1.1）。共通型は DB スキーマと一対一対応で定義するため、スキーマが先に確定している必要がある。

## 後続タスク

- `04-phase1-ingest-adapter-base.md`（Phase 1.3 IngestAdapter ABC: `parse(payload) -> Iterable[Transaction]` の戻り値型として参照）。
- `08-phase1-hash-idempotency-tests.md`（Phase 1.7 ハッシュ冪等性: `compute_hash` の境界条件を property-based test で網羅）。

## 対象ファイル/モジュール

| パス | 役割 |
|---|---|
| `src/kakeibo/domain/__init__.py` | パッケージ初期化、公開 API の集約 |
| `src/kakeibo/domain/transaction.py` | `Transaction` dataclass + `compute_hash` |
| `src/kakeibo/domain/holding.py` | `Holding` dataclass + `SymbolKind` Enum |
| `src/kakeibo/domain/balance_snapshot.py` | `BalanceSnapshot` dataclass |
| `src/kakeibo/domain/currency.py` | 通貨コードバリデータ |
| `tests/unit/domain/test_transaction.py` | `Transaction` バリデーション + `compute_hash` 決定性 |
| `tests/unit/domain/test_holding.py` | `Holding` バリデーション + `SymbolKind` 範囲 |
| `tests/unit/domain/test_balance_snapshot.py` | `BalanceSnapshot` バリデーション |

## 実装方針

1. **dataclass vs pydantic**: 第一選択は `dataclass(frozen=True, slots=True)` + 手書きバリデータ。pydantic を入れると依存が増えるため、Phase1 では避ける。Phase 3（Flask API）で必要になったら導入を検討。
2. **`Transaction` 必須フィールド**: `account_id: int`, `occurred_on: date`, `occurred_at: Optional[datetime]`, `amount: Decimal`, `currency: str`, `description: str`, `category_id: Optional[int]`, `category_source: Literal['rule','llm','manual'] | None`, `raw_payload: dict[str, Any]`, `hash: str`。
3. **`__post_init__` でバリデーション**: `amount is None` → `ValueError`、`len(currency) != 3 or not currency.isalpha() or not currency.isupper()` → `ValueError`、`occurred_on` が `date` でない → `TypeError`。
4. **`compute_hash`**: `f"{account_id}|{occurred_on.isoformat()}|{amount}|{description}"` を UTF-8 エンコードして `hashlib.sha256(...).hexdigest()` を返す。区切り文字 `|` で衝突を低減。description の正規化（前後空白の扱い）は ADR-006 と整合させ、Phase 1.7 の境界条件テストで詳細を確定する（ここではトリミング**しない**を初期方針とする）。
5. **`SymbolKind`**: `enum.StrEnum` で定義し、`Holding.symbol_kind` は型ヒントを `SymbolKind` に固定。
6. **`BalanceSnapshot`**: `account_id`, `as_of_date: date`, `balance: Decimal`, `currency: str`。同日同口座の重複は DB 側 UNIQUE で防ぐ。

## 受入条件

- `Transaction.amount` が `Decimal` 型である（`isinstance(tx.amount, Decimal) is True`）。
- `Transaction.occurred_on` が `date`、`occurred_at` が `Optional[datetime]` である。
- `amount=None` / 通貨コード `"JP"` / 通貨コード `"jpy"` / `occurred_on=None` のいずれかでインスタンス化すると `ValueError` または `TypeError` が発生する。
- `compute_hash(1, date(2026,4,30), Decimal("1234.56"), "コンビニ")` が複数回呼んでも同じ SHA256 hex 文字列を返す（決定性）。
- `Holding.symbol_kind` に `SymbolKind` 以外の値を渡すと型エラー（pyright）または実行時エラー。
- `pyright` クリーン、`ruff` 違反なし。

## テスト計画

### ユニットテスト（テスト先行）

1. **`Transaction` バリデーション**: 正常系 / 異常系の表駆動テスト。`amount=None`, `currency="JP"`, `currency="jpy"`, `currency="JPYY"`, `occurred_on="2026-04-30"`（文字列）など 8 件以上。
2. **`compute_hash` 決定性**: 同一引数で 100 回呼んでも同じ hex 値。引数 1 つでも変わると別の hex（`account_id`, `occurred_on`, `amount`, `description` を 1 件ずつ変える）。
3. **`Holding` `SymbolKind`**: 列挙値ごとに正常生成、未定義値で例外。
4. **`BalanceSnapshot`**: `balance` の `Decimal` 型強制、`as_of_date` の `date` 型強制。

### TDD アプローチ

- Red: ドメイン型ファイルを空のまま、テストファイルを先に書いて落とす。
- Green: dataclass を最小限で定義し、テストを 1 件ずつ通す。
- Refactor: バリデーションロジックを `currency.py` 等に抽出して重複を解消。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.2: 共通ドメイン型（Transaction / Holding / BalanceSnapshot）の定義`
- ブランチ名: `feature/domain-types`
- ベースブランチ: `develop`
