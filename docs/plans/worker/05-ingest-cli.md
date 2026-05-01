---
title: worker/05 取込CLI
service: worker
phase_task_id: 1.6
priority: 高
source_plan: docs/plans/07-phase1-ingest-cli.md
branch: feature/ingest-cli
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/05 取込CLI（Phase 1.6）

## このファイルの位置付け

原典 `docs/plans/07-phase1-ingest-cli.md` を `worker` サービス担当の指示書として再編。原典との乖離時は原典優先。Phase1 完了条件 (b)「同一 CSV 2 回投入で行数増えず」を直接満たすクリティカルパス上のタスク。

## 担当サービス

`worker` コンテナ。`python -m kakeibo.ingest <institution> <path>` の本体。Phase 2.1 の watchdog Watcher が `subprocess` 経由で叩く前提のため、終了コード規約が固定される。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/03`（MUFG） + `worker/04`（SMBC） |
| 下流 | `worker/06`（ハッシュ冪等性 PBT）、`worker/07`（月次サマリ）、Phase 2.1 Watcher |

## 入力

1. **原典**: `docs/plans/07-phase1-ingest-cli.md`（必読）
2. **取込フロー**: `worker/docs/design/08-ingest-flow.md`
3. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
4. **ADR**: `docs/adr/006-hash-uniqueness.md`, `docs/adr/007-adapter-pattern.md`
5. **依存資産**: `pyproject.toml` `[project.dependencies]` に宣言済みの `click>=8.1,<9` を採用
6. **DB 接続**: `src/kakeibo/db/session.py`（Phase 0 で作成済み engine factory）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `src/kakeibo/ingest/__init__.py` | 既存（公開 API 集約に追記） |
| `src/kakeibo/ingest/cli.py` | CLI エントリ + `main()` |
| `src/kakeibo/ingest/__main__.py` | `python -m kakeibo.ingest` 起動用（`from .cli import main; main()`） |
| `src/kakeibo/ingest/registry.py` | 機関 → アダプタクラスのレジストリ |
| `src/kakeibo/ingest/persister.py` | DB 永続化（`INSERT ... ON CONFLICT (hash) DO NOTHING`） |
| `tests/unit/ingest/__init__.py` | 新規 |
| `tests/unit/ingest/test_cli.py` | CLI 引数・終了コード・dry-run のテスト（`CliRunner`） |
| `tests/unit/ingest/test_persister.py` | 冪等 INSERT 検証（実 Postgres or testcontainers） |
| `tests/unit/ingest/test_registry.py` | レジストリ参照と未対応機関 |

`pyproject.toml` の `[project.scripts]` に既に `kakeibo = "kakeibo.__main__:main"` が宣言されている。本タスクで `kakeibo.ingest` サブコマンドへの委譲を `src/kakeibo/__main__.py` に実装するか、`python -m kakeibo.ingest` 直接呼びを採用するかの方針を決める（**`python -m kakeibo.ingest` 直接呼び** を推奨。`kakeibo` トップ CLI は Phase 4 で導入）。

## 実装方針（原典 §実装方針より要約）

1. **CLI フレームワーク**: `click` を採用（`CliRunner` で in-process テスト可能）。
2. **コマンドシグネチャ**: `python -m kakeibo.ingest <institution> <path> [--dry-run] [--account-id INT]`。
3. **アダプタ呼び出し**: `registry.get(institution)` でクラス取得 → `adapter = cls(account_id=...)` → `adapter.parse(file_bytes)`。
4. **DB 永続化**: SQLAlchemy Core の `insert(transactions).on_conflict_do_nothing(index_elements=["hash"])`（`postgresql.insert`）。トランザクション境界はコマンド全体で 1 つ。
5. **dry-run**: `--dry-run` 指定時は永続化スキップ、件数 + 先頭 3 件を `print`。
6. **終了コード規約**: 成功 = 0、引数不正 = 2、パース失敗 = 3（`EncodingMismatchError` / `ColumnMissingError` / `ValueError`）、DB エラー = 4（`psycopg.Error`）。
7. **ログ**: `logging.getLogger("kakeibo.ingest")`。INFO で件数、WARNING で重複スキップ件数。
8. **テスト DB**: dev 依存の `testcontainers.postgres.PostgresContainer` を session-scope fixture で利用、`postgres/01` の Alembic マイグレーションを適用してから各テストを流す。

## 実装手順（TDD）

### 1. Red

- `tests/unit/ingest/test_cli.py` で `CliRunner().invoke(...)` ベースのテストを書く：
  - 正常系（mufg / smbc それぞれで exit 0、行数増加）
  - 冪等性（同一ファイル 2 回で 2 回目の行数変化なし）
  - dry-run（行数 0 のまま、stdout に件数表示）
  - 壊れた CSV → exit 3、未対応機関 → exit 2
- `tests/unit/ingest/test_persister.py` で `persister.persist(...)` を直接呼び、`ON CONFLICT DO NOTHING` の挙動確認。
- `tests/unit/ingest/test_registry.py` で `registry.get("mufg")` / `registry.get("nonexistent")` の挙動。

### 2. Green

- `registry.py` を最小実装（`{"mufg": MufgCsvAdapter, "smbc": SmbcCsvAdapter}`）。
- `persister.py` で SQLAlchemy Core の bulk `INSERT ... ON CONFLICT DO NOTHING`。
- `cli.py` で click コマンドを定義し、上記を呼び出す。
- 各テストを順に通す。エラーパスは最後にまとめて。

### 3. Refactor

- 永続化ロジックを CLI から完全分離（`persister.persist(transactions)` で受け取る）。
- 例外 → 終了コードマッピングを `_handle_exception(exc) -> int` に集約。

## 受入条件

- CLI で MUFG / SMBC の CSV を取り込み、`transactions` 行数が増える
- 同じファイル 2 回投入で 2 回目に行数増加なし（`ON CONFLICT DO NOTHING`）
- 終了コード: 成功 0 / 引数不正 2 / パース失敗 3 / DB エラー 4
- `--dry-run` で DB 書込みなし、stdout に件数 + 先頭 3 件
- 未対応機関で exit 2 + 適切なエラーメッセージ
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/ingest/      # 全件緑（< 30 秒、testcontainers 起動含む）
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/ingest-cli`
- コミット粒度（最低 6 件）：
  1. `テスト: 取込CLIの正常系・冪等性・dry-run・エラーパスのテストを先行作成`
  2. `機能: 機関→アダプタクラスのレジストリを追加`
  3. `機能: ON CONFLICT DO NOTHINGによる冪等永続化レイヤを実装`
  4. `機能: clickベースの取込CLIエントリを実装`
  5. `機能: 例外→終了コードマッピングを追加`
  6. `機能: --dry-runオプションと件数サマリ出力を追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 1.6 取込CLI を実装。

## 成果物
- src/kakeibo/ingest/{cli,registry,persister,__main__}.py
- tests/unit/ingest/{test_cli,test_registry,test_persister}.py

## 検証結果
- pytest tests/unit/ingest/: 全件緑
- 同一CSV 2回投入で行数変化なし（冪等性）
- 終了コード規約（0/2/3/4）動作確認
- pyright / ruff: クリーン

## 既知の課題・申し送り
（あれば）

## 次のアクション提案
worker/06 (ハッシュ冪等性PBT) と worker/07 (月次サマリ) を並行着手可能。
```

## 注意事項

- `click` は `[project.dependencies]` に既に宣言済み（`click>=8.1,<9`）。新規依存追加は不要。
- **dry-run 時に DB に書き込まない** ことをテストで明示（行数 0 を確認）。
- DB エラー時のロールバック挙動は SQLAlchemy のトランザクション境界で担保（`with engine.begin()`）。
- 機関コード判定は CLI 引数で行い、ディレクトリ名からの自動判定は **Phase 2.1 Watcher の責務**（責務分離）。
- `pytest-postgresql` は dev 依存に未宣言。`testcontainers` を使用。
- `pyproject.toml` の `[project.scripts]` `kakeibo = "kakeibo.__main__:main"` は別タスクで実体化（Phase 4 想定）。Phase 1 では `python -m kakeibo.ingest` 直接呼びを正規ルートとする。
