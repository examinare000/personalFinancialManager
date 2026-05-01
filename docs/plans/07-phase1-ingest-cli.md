---
title: Phase 1.6 取込CLI
phase: 1
task_id: 1.6
status: Draft
priority: 高
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.6 取込CLI

## タスク概要

`python -m kakeibo.ingest <institution> <path>` 相当のコマンドを提供し、**アダプタ起動 → DB 永続化 → 原本退避**までを一気通貫で実行する CLI を実装する。Phase1 完了条件 (b)「同一 CSV を 2 回投入しても `transactions` 行数が増えない」を直接満たす。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.6, §3.1 完了条件 (b), `docs/design/02-ingest-adapters.md`, `docs/design/08-ingest-flow.md`。

## 目的・背景

### 目的

- 機関コードとファイルパスを引数に取り、対応するアダプタを起動して `Transaction` を抽出し、DB に永続化する。
- `transactions.hash` の UNIQUE 制約を活用して、同じファイルを再投入しても行数が増えない冪等性を実現する（ADR-006）。
- `--dry-run` で DB に書き込まずに抽出結果のみ表示できるようにし、運用での確認用途を支える。
- 終了コードを成功 0 / 失敗 非0 で正しく返し、Phase 2.1 の Watcher サービスからスクリプト経由で起動できるようにする。

### 背景

- Phase1 完了条件のうち (b) と、間接的に (c)（月次サマリ SQL の前提となるデータ投入）を本タスクで満たす。
- Phase 2.1 の Watcher は CLI を `subprocess` 経由で呼ぶ前提のため、CLI が安定した終了コード規約を持つことが必須。
- 機関コード判定は CLI 引数で行い、Watcher 段階ではディレクトリ名から自動判定する（責務を分離）。

## スコープ

### 含む

- CLI エントリポイント `src/kakeibo/ingest/cli.py`。`click` または `argparse` ベース。
- 機関コード → アダプタクラスのレジストリ（`{"mufg": MufgCsvAdapter, "smbc": SmbcCsvAdapter}`）。
- DB へのバルク INSERT（`INSERT ... ON CONFLICT (hash) DO NOTHING` で冪等化）。
- `--dry-run` オプション（DB 書き込みをスキップし、抽出件数 + サンプル数件を標準出力）。
- 終了コード規約（成功 = 0、引数不正 = 2、パース失敗 = 3、DB エラー = 4）。
- 取込結果のサマリログ（取込件数 / 重複でスキップした件数）。

### 含まない

- ファイル監視（Phase 2.1）。
- 取込済みファイルの自動アーカイブ移動（Phase 2.2）。
- メール / API 取込（Phase 2.3〜2.7）。
- Web UI 経由の取込（Phase 3）。

## 依存タスク

- `05-phase1-mufg-csv-adapter.md`（Phase 1.4 MUFG CSV アダプタ）。
- `06-phase1-smbc-csv-adapter.md`（Phase 1.5 SMBC CSV アダプタ）。

## 後続タスク

- `08-phase1-hash-idempotency-tests.md`（Phase 1.7 ハッシュ冪等性ユニットテスト強化）。
- `09-phase1-monthly-summary-sql.md`（Phase 1.8 月次サマリ SQL: 本 CLI で投入したデータを集計）。
- Phase 2.1 Watcher（本プラン群の対象外、`01-development-plan.md` §4.2 で扱う）。

## 対象ファイル/モジュール

| パス | 役割 |
|---|---|
| `src/kakeibo/ingest/__init__.py` | パッケージ初期化 |
| `src/kakeibo/ingest/cli.py` | CLI エントリ。`if __name__ == "__main__": ...` を含む |
| `src/kakeibo/ingest/registry.py` | 機関 → アダプタクラスのレジストリ |
| `src/kakeibo/ingest/persister.py` | DB 永続化（`ON CONFLICT (hash) DO NOTHING`） |
| `tests/unit/ingest/test_cli.py` | CLI 引数 / 終了コード / dry-run テスト |
| `tests/unit/ingest/test_persister.py` | 冪等 INSERT 検証（実 Postgres or テスト用 DB） |

## 実装方針

1. **CLI フレームワーク**: `click` を採用（テスタビリティが高く、`CliRunner` で in-process 実行可能）。`pyproject.toml` の依存に追加。
2. **コマンドシグネチャ**: `kakeibo.ingest <institution> <path> [--dry-run] [--account-id INT]`。`--account-id` は CSV に口座 ID が含まれない場合の指定用（Phase1 では機関＋口座が 1:1 を仮定）。
3. **アダプタ呼び出し**: `registry.get(institution)` でアダプタクラスを取得 → インスタンス化 → `parse(file_bytes)` で `Iterable[Transaction]` を取得。
4. **DB 永続化**: SQLAlchemy Core の `insert(...).on_conflict_do_nothing(index_elements=["hash"])` で一括 INSERT。トランザクション境界はコマンド全体で 1 つ。
5. **dry-run**: `--dry-run` 指定時は `persister.persist(...)` をスキップし、`len(transactions)` と先頭 3 件を `print` する。
6. **終了コード**: `click` の例外ハンドリングで `EncodingMismatchError` / `ColumnMissingError` → exit 3、`psycopg.Error` → exit 4、その他 `SystemExit(2)` は引数不正。
7. **ログ**: `logging.getLogger("kakeibo.ingest")` を使用し、構造化ログ（INFO で件数、WARNING で重複スキップ件数）。
8. **テストでの DB**: dev 依存に宣言済みの `testcontainers`（pyproject.toml `[project.optional-dependencies].dev`）または既存 `tests/_compose_utils.py` を活用し、テストごとに一時 DB を立ち上げて Phase 1.1 のマイグレーションを適用。`pytest-postgresql` は dev 依存に未宣言のため採用しない。

## 受入条件

- CLI で MUFG / SMBC の CSV を取り込み、`transactions` 行数が増える。
- 同じファイルを 2 回投入しても、2 回目で行数が増えない（`ON CONFLICT DO NOTHING` 確認）。
- 終了コードが成功時 0、CSV パース失敗時 3、DB エラー時 4。
- `--dry-run` 指定時に DB に書き込まれず、件数とサンプルが標準出力に表示される。
- 未対応の機関コード（例: `paypal`）を渡すと exit 2 と適切なエラーメッセージ。
- `pyright` クリーン、`ruff` 違反なし。

## テスト計画

### ユニットテスト（テスト先行）

1. **正常系**: `CliRunner().invoke(cli, ["mufg", str(fixture_path)])` で exit 0、DB 行数が期待と一致。
2. **冪等性**: 同じファイルを 2 回 invoke、2 回目の DB 行数が変化しない。
3. **dry-run**: `--dry-run` 指定で DB に書き込まれない（行数 0 のまま）、stdout に件数表示。
4. **エラーパス**: 壊れた CSV → exit 3、未対応機関 → exit 2。
5. **registry**: `registry.get("mufg")` が `MufgCsvAdapter`、`registry.get("nonexistent")` が `KeyError`。
6. **永続化単体**: `persister.persist(transactions)` を直接呼び、`ON CONFLICT DO NOTHING` の動作を SQL レベルで確認。

### TDD アプローチ

- Red: `tests/unit/ingest/test_cli.py` で `CliRunner` ベースのテストを書き、CLI 未実装で落とす。
- Green: `cli.py` を最小実装（成功パスのみ）→ 冪等性 → エラーパスの順に実装。
- Refactor: 永続化ロジックを `persister.py` に切り出し、CLI は引数解釈に専念。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.6: 取込CLI（アダプタ起動 → DB 永続化）の実装`
- ブランチ名: `feature/ingest-cli`
- ベースブランチ: `develop`
