---
title: worker/Ph2/01 watchdog Watcher サービス
service: worker
phase_task_id: 2.1
priority: 高
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.1（行 211-221）
branch: feature/watcher-service
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/01 watchdog Watcher サービス（Phase 2.1）

## このファイルの位置付け

原典 `docs/plans/01-development-plan.md` §4.2 Phase 2.1 を `worker` サービス担当の実装指示書として展開。Phase2 完了条件 (a)「CSV 投下 5 分以内に DB 反映」を直接満たす。原典との乖離時は原典優先。

## 担当サービス

`worker` コンテナ。Phase 0 で実装した heartbeat ループ（`src/kakeibo/worker/main.py`）を **取込スケジューラのディスパッチャに発展させる**（`src/kakeibo/worker/__init__.py` のコメント参照）。`/inbox/<institution>/` 配下の新規ファイルを監視し、Phase 1.6 で実装した取込CLIを subprocess（or in-process 関数）で起動する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph1/05`（取込CLI、Phase 1.6） |
| 下流 | `worker/Ph2/02`（archive/dead_letter）, `worker/Ph2/08`（cron） |

`worker/Ph2/03` (Gmail MCP) と独立並列可能。

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.2 Phase 2.1
2. **取込フロー**: `worker/docs/design/08-ingest-flow.md`
3. **デプロイ**: `docs/design/04-deployment-stack.md`
4. **ADR**: `docs/adr/007-adapter-pattern.md`, `docs/adr/009-nas-docker-compose.md`
5. **既存資産**:
   - `src/kakeibo/worker/main.py`（Phase 0 heartbeat ループ。本タスクで内容拡張）
   - `src/kakeibo/ingest/cli.py`（Phase 1.6 で実装される取込CLI）
   - `src/kakeibo/ingest/registry.py`（機関 → アダプタ）
   - `compose.yml` `worker` の volume `./inbox:/inbox:rw`
6. **依存パッケージ**: `pyproject.toml` に **`watchdog` を追加** が必要（dev ではなく runtime 依存。`[project.dependencies]` に `"watchdog>=4,<5"` を追記）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `pyproject.toml` | `watchdog>=4,<5` を `[project.dependencies]` に追加 |
| `src/kakeibo/ingest/watcher.py` | watchdog `Observer` ベースの Watcher 本体 |
| `src/kakeibo/ingest/dispatch.py` | ディレクトリ名 → 機関コード判定 + 取込CLI 起動 |
| `src/kakeibo/worker/main.py` | heartbeat ループに Watcher 起動を統合（既存の API は維持） |
| `tests/unit/ingest/test_watcher.py` | watchdog をモックしてイベント発火検証 |
| `tests/unit/ingest/test_dispatch.py` | 機関コード判定とリトライ |
| `tests/integration/watcher/test_watcher_e2e.py` | `tmp_path` で実ファイル投下 → DB 反映の統合テスト |

## 実装方針

1. **watchdog 採用**: `watchdog.observers.Observer` + `FileSystemEventHandler`。デバウンス（同一ファイルの複数イベント抑制）は 1 秒の windowed dispatch で実装。
2. **機関コード自動判定**: `/inbox/<institution>/<filename>` のディレクトリ階層から `institution` を取り出す。`registry.get(institution)` が `KeyError` なら **dead_letter へ即移動**（`worker/Ph2/02` と連携）。
3. **取込起動方式**: 当面は **in-process 関数呼び出し**（`from kakeibo.ingest.cli import ingest_file; ingest_file(institution, path)`）を採用。subprocess は cron バッチ（`worker/Ph2/08`）と Phase 2.1 のリトライで利用検討。
4. **ファイルロック競合リトライ**: パース対象ファイルが書き込み中の可能性に対し、サイズ安定確認（`os.stat(path).st_size` を 500ms 間隔で 2 回チェックして同値）→ 失敗時は最大 3 回リトライ。
5. **graceful shutdown**: Phase 0 の `stop_event: threading.Event` パターンを継承し、SIGTERM / SIGINT で `Observer.stop()` + `join(timeout=5)`。
6. **heartbeat 維持**: 既存の heartbeat 更新は維持（HEALTHCHECK 互換性）。Watcher 起動後も周期的に touch する。
7. **ログ**: `structlog` で `event=watcher_started`, `event=file_detected`, `event=ingest_completed`, `event=ingest_failed`。

## 実装手順（TDD）

### 1. Red

- `tests/unit/ingest/test_watcher.py` で `watchdog.events.FileSystemEvent` を直接ハンドラに渡し、ディスパッチが期待通り呼ばれることを `unittest.mock.MagicMock` で検証。
- `tests/unit/ingest/test_dispatch.py` で機関コード判定 / 未対応機関で dead_letter 行き / リトライ挙動を検証。
- `tests/integration/watcher/test_watcher_e2e.py` で `tmp_path` 配下に `mufg/sample.csv` を配置 → 5 秒以内に testcontainers Postgres へ取引が INSERT されることを確認（前提: `worker/Ph1/05` 完了で取込CLI が動く）。
- 全件赤になることを確認。

### 2. Green

- `pyproject.toml` に `watchdog` を追加し `uv sync`。
- `src/kakeibo/ingest/dispatch.py` を最小実装（機関コード判定 + `ingest_file` 呼び出し）。
- `src/kakeibo/ingest/watcher.py` で `Observer` を初期化し、`FileSystemEventHandler` のサブクラスを登録。
- `src/kakeibo/worker/main.py` の `run()` を改修し、`heartbeat_path` ループと並行して Watcher を起動。

### 3. Refactor

- ファイルサイズ安定確認を `_wait_file_stable(path, attempts=3, interval=0.5)` に抽出。
- リトライポリシーを `_retry_with_backoff(...)` に抽出（PayPal の指数バックオフと共通化可能性は Phase 2.7 で評価）。

## 受入条件

- サービス起動状態で `/inbox/mufg/sample.csv` 投下から **5 分以内**（実測は 5 秒以内）に DB に反映
- 機関コードがディレクトリ名（`/inbox/<institution>/...`）から自動判定される
- ファイルロック競合時のリトライが実装されている（最大 3 回）
- SIGTERM / SIGINT で graceful shutdown（`Observer.stop()` + `join(timeout=5)`）
- HEALTHCHECK の heartbeat ファイルが Watcher 起動中も更新される
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/ingest/test_watcher.py tests/unit/ingest/test_dispatch.py
pytest tests/integration/watcher/      # testcontainers 起動含む
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/watcher-service`
- コミット粒度（最低 5 件）：
  1. `テスト: watchdogイベントハンドラとディスパッチ・統合E2Eのテストを先行作成`
  2. `設定: watchdog依存パッケージをpyproject.tomlに追加`
  3. `機能: 機関コード判定とリトライ付き取込ディスパッチを実装`
  4. `機能: watchdog Observerベースのファイル監視Watcherを実装`
  5. `機能: workerメインループにWatcher起動とgraceful shutdownを統合`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.1 watchdog Watcher サービスを実装。

## 成果物
- pyproject.toml（watchdog 追加）
- src/kakeibo/ingest/{watcher,dispatch}.py
- src/kakeibo/worker/main.py（拡張）
- tests/unit/ingest/test_watcher.py / test_dispatch.py
- tests/integration/watcher/test_watcher_e2e.py

## 検証結果
- pytest（unit + integration）: 全件緑
- /inbox 投下 → DB 反映: 平均 X 秒
- SIGTERM graceful shutdown 動作確認
- pyright / ruff: クリーン

## 次のアクション提案
worker/Ph2/02 (Archive/DLQ) 着手可能。
```

## 注意事項

- watchdog は **runtime 依存**として追加（`[project.dependencies]`）。dev のみだと本番イメージで `ImportError`。
- ファイル投下中の競合（書き込み途中）対策で **サイズ安定確認**を入れること（巨大 CSV をスキャンし始めて壊れるパターン防止）。
- 統合テストでは testcontainers を使う（`pytest-postgresql` は dev 依存に未宣言）。
- 機関コード判定の **大文字小文字** は原典で未確定。`institution.lower()` で正規化する暫定ポリシー（CLI 側のレジストリも小文字キーを採用）。
- `RawMail` のような新規ドメイン型は本タスクでは追加しない（メール系は `worker/Ph2/03` で扱う）。
