---
title: Phase 1.3 IngestAdapter ABC（取込アダプタ抽象基底）
phase: 1
task_id: 1.3
status: Draft
priority: 高
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.3 IngestAdapter ABC（取込アダプタ抽象基底）

## タスク概要

ADR-007（アダプタパターン）に従い、機関別取込実装の共通契約を定義する **抽象基底クラス `IngestAdapter`** を実装する。Phase 1.4 / 1.5 の MUFG / SMBC CSV アダプタ、および Phase 2 のメールパーサ・PayPal クライアントがすべて本契約を満たす。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.3, `docs/plans/00-initial-design.md` §5.2, `worker/docs/design/02-ingest-adapters.md`。

## 目的・背景

### 目的

- すべてのアダプタが守るインターフェースを 1 箇所に固定する（`parse(payload) -> Iterable[Transaction]`、`extract_holdings(payload) -> Iterable[Holding]`）。
- アダプタが返す `Transaction` のソース識別子 `source` 属性を強制し、後段のパイプラインで「どの機関由来の取引か」を区別できるようにする。
- `account_id` の渡し方を **コンストラクタ注入** で確定する。`parse` / `extract_holdings` の引数は `payload` のみとし、アダプタ単位で `account_id` を保持する設計を本タスクで契約として固定する（Phase 1.4 / 1.5 はこれに従う）。
- ダミーアダプタ（テスト専用）で契約を検証可能にし、後続タスクのテスト工数を削減する。

### 背景

- `01-development-plan.md` §5 のクリティカルパス上で、Phase 1.4 / 1.5 / Phase 2.x のアダプタはすべて本タスクの ABC を継承する。ABC 未確定のままアダプタを書き始めると、機関ごとに独自インターフェースが乱立する。
- `IngestAdapter` のみ早めに固めれば、MUFG と SMBC を並行作業に分割できる（`01-development-plan.md` §4.1 Phase 1.5 「Phase 1.4 と並行可」）。
- Phase 2 の `RawMail` 取得（メールパーサ系）も `parse(payload)` 経由で取り込むため、`payload` 型は `bytes | str | dict[str, Any]` のような Union として柔軟性を持たせる。

## スコープ

### 含む

- `IngestAdapter` ABC の定義（`abc.ABC` 継承、`@abstractmethod` 注釈）。
- `source: str` クラス属性の強制（未設定サブクラスは初期化時にエラー）。
- `__init__(self, *, account_id: int)` を ABC 側で固定し、`account_id: int` インスタンス属性として保持する契約。
- `parse(payload) -> Iterable[Transaction]` および `extract_holdings(payload) -> Iterable[Holding]` 抽象メソッド宣言（`account_id` はインスタンス属性経由で参照、`parse` 引数には含めない）。
- ダミーアダプタ（テスト fixture 専用）の実装と、契約検証用ユニットテスト。

### 含まない

- 実機関アダプタ（MUFG / SMBC）の実装は Phase 1.4 / 1.5。
- アダプタ → DB 永続化のパイプライン（Phase 1.6）。
- 認証情報の扱い（Phase 2.3 / 2.7 で個別に整備）。

## 依存タスク

- `postgres/docs/plans/Ph1/03-domain-types.md`（Phase 1.2）。`Transaction` / `Holding` 型がないと抽象メソッドの戻り値型が書けない。

## 後続タスク

- `worker/docs/plans/Ph1/05-mufg-csv-adapter.md`（Phase 1.4 MUFG CSV アダプタ）。
- `worker/docs/plans/Ph1/06-smbc-csv-adapter.md`（Phase 1.5 SMBC CSV アダプタ）。
- Phase 2 系のメール・API アダプタ（本プラン群の対象外、`01-development-plan.md` §4.2 で扱う）。

## 対象ファイル/モジュール

| パス | 役割 |
|---|---|
| `worker/src/kakeibo_worker/adapters/__init__.py` | パッケージ初期化 |
| `worker/src/kakeibo_worker/adapters/base.py` | `IngestAdapter` ABC 本体 + `source` 属性検証メタクラス（or `__init_subclass__`） |
| `worker/tests/unit/adapters/__init__.py` | テストパッケージ初期化 |
| `worker/tests/unit/adapters/test_base.py` | 契約検証（抽象メソッド未実装サブクラスのインスタンス化失敗、`source` 必須） |
| `worker/tests/unit/adapters/_dummy_adapter.py` | テスト用ダミーアダプタ |

## 実装方針

1. **`IngestAdapter(abc.ABC)`**: `__init__(self, *, account_id: int)` を非抽象として ABC 側で実装し `self.account_id = account_id` を保持。`parse` と `extract_holdings` を `@abstractmethod` で定義し、引数は `payload` のみ。戻り値型は `Iterable[Transaction]` / `Iterable[Holding]`。`payload` 型は `bytes | str | dict[str, Any]` の Union（メールも CSV も API レスポンスも受け取れる柔軟性）。
2. **`source` 強制**: `__init_subclass__(cls, **kwargs)` で `cls.source` の存在と非空文字列をチェックし、未設定なら `TypeError` を送出する。クラス属性として `source: ClassVar[str]` を宣言し、サブクラスで必ず上書きさせる。
3. **`account_id` 注入**: コンストラクタ引数 `account_id` をサブクラス共通で受け取り、`Transaction` 生成時に `self.account_id` を参照する。`parse(payload, account_id=...)` のような可変引数注入や `parse(payload, **context)` 拡張は採用しない（契約の単純化のため）。
4. **デフォルト実装**: `extract_holdings` は銀行アダプタには無関係なため、デフォルトで空 `Iterable` を返す具体メソッドにする選択肢もあるが、抽象を保ち各サブクラスで `return ()` を明示する方を採用（明示が型安全）。
5. **エラー型**: パース失敗時はサブクラスが `kakeibo_worker.adapters.errors.AdapterError`（同タスクで定義）を送出する規約とする。型は本タスクで宣言、利用は Phase 1.4 以降。
6. **ダミーアダプタ**: `worker/tests/unit/adapters/_dummy_adapter.py` に `class DummyAdapter(IngestAdapter)` を実装し、`parse` が固定の `Transaction` リストを返す。`source = "dummy"`、コンストラクタは `DummyAdapter(account_id=...)` で受ける。

## 受入条件

- `IngestAdapter` は `__init__(self, *, account_id: int)` を備え、`parse(payload) -> Iterable[Transaction]` と `extract_holdings(payload) -> Iterable[Holding]` を抽象メソッドとして持つ。
- `source` 属性が未設定のサブクラスは初期化（クラス定義時）に `TypeError` で弾かれる。
- `account_id` を渡さずにサブクラスを初期化すると `TypeError`（Python の標準 `__init__` 挙動）で弾かれる。
- ダミーアダプタが契約を満たし、ユニットテストで `DummyAdapter(account_id=...)` 経由の `parse` / `extract_holdings` が呼べる。
- 抽象メソッドを実装していないサブクラスのインスタンス化が `TypeError` で失敗する（Python 標準の `abc` 挙動）。
- `pyright` クリーン、`ruff` 違反なし。

## テスト計画

### ユニットテスト（テスト先行）

1. **抽象メソッド未実装の検出**: `IncompleteAdapter(IngestAdapter)` を `parse` のみ実装する形で書き、インスタンス化が `TypeError` で失敗することを `pytest.raises` で確認。
2. **`source` 属性必須**: `class NoSourceAdapter(IngestAdapter): ...`（`source` 未定義）を試みると `TypeError` が発生（クラス定義時点で）。
3. **`account_id` 注入必須**: `DummyAdapter()` を `account_id` キーワード引数なしで初期化すると `TypeError` が発生し、`DummyAdapter(account_id=42)` は成功して `instance.account_id == 42` であることを確認。
4. **ダミーアダプタの正常動作**: `DummyAdapter(account_id=42).parse(b"")` が `Iterable[Transaction]` を返し、要素が `Transaction` 型かつ `account_id == 42` を持つことを検証。
5. **`extract_holdings` のデフォルト挙動**: ダミーアダプタが `extract_holdings(b"")` を返す（空でも型に従う）。

### TDD アプローチ

- Red: `worker/tests/unit/adapters/test_base.py` を先に書き、`from kakeibo_worker.adapters.base import IngestAdapter` で ImportError を起こす。
- Green: `IngestAdapter` ABC を最小限で実装、各テストを順に通す。
- Refactor: `__init_subclass__` 内のバリデーションを別関数に抽出可能なら抽出。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.3: IngestAdapter 抽象基底クラスの導入`
- ブランチ名: `feature/ingest-adapter-base`
- ベースブランチ: `develop`
