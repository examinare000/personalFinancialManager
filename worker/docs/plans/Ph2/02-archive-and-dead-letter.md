---
title: worker/Ph2/02 アーカイブ移動 + dead letter
service: worker
phase_task_id: 2.2
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.2（行 223-233）
branch: feature/archive-and-dead-letter
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/02 アーカイブ移動 + dead letter（Phase 2.2）

## このファイルの位置付け

原典 `docs/plans/01-development-plan.md` §4.2 Phase 2.2 を `worker` サービス担当の指示書として展開。Phase2 完了条件 (d)「失敗ファイルが dead_letter へ移動」を直接満たす。

## 担当サービス

`worker` コンテナ。取込成功/失敗の **後処理**（archive 移動・dead letter 隔離・エラーログ書き出し）を `worker/Ph2/01` Watcher の中から呼び出す。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph2/01`（Watcher） |
| 下流 | `worker/Ph2/08`（cron バッチでも archive ロジックを再利用） |

## 入力

1. **原典**: §4.2 Phase 2.2（行 223-233）
2. **取込フロー**: `worker/docs/design/08-ingest-flow.md`
3. **ADR**: `docs/adr/009-nas-docker-compose.md`, `docs/adr/012-three-tier-backup.md`
4. **既存資産**:
   - `compose.yml` `worker` の volume `./archive:/archive:rw`, `./dead_letter:/dead_letter:rw`
   - `shared/kakeibo_shared/config.py` の `archive_path`, `dead_letter_path`（環境変数 `ARCHIVE_PATH`, `DEAD_LETTER_PATH` から）
5. **依存**: 標準ライブラリ `shutil`, `datetime`, `pathlib`（追加依存なし）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `worker/src/kakeibo_worker/ingest/archiver.py` | `archive_success(path)`, `archive_failure(path, error)` の純関数 |
| `worker/src/kakeibo_worker/ingest/watcher.py` | （既存）archiver 呼び出しを統合 |
| `worker/tests/unit/ingest/test_archiver.py` | 成功 / 失敗 / 衝突 / エラーログ併置テスト |
| `worker/tests/integration/archiver/test_archiver_e2e.py` | tmp_path で実ファイル移動を検証 |

## 実装方針

1. **成功時の移動先**: `archive_path / institution / occurred_year_month / filename`。`occurred_year_month` は `YYYY-MM`（取込日ではなく **取込実行時刻**を採用、原典と整合）。
2. **失敗時の移動先**: `dead_letter_path / filename` 直下。`<filename>.error.log` を併置（例外クラス名 / メッセージ / トレースバック）。
3. **同名ファイル衝突**: `<stem>_<YYYYMMDDhhmmss>.<suffix>` でリネーム。タイムスタンプは UTC ベース。
4. **inbox からの除去**: `shutil.move(src, dst)` で原子的に。途中失敗時はリトライではなく例外を伝播（Watcher 側で再試行）。
5. **エラーログのフォーマット**: 1 行目に例外クラス名 + メッセージ、空行、`traceback.format_exc()` 全文。トークン・シークレットを含むメッセージは絶対に書き込まない（`agent-rules/12-security-guidelines.md`）。
6. **権限**: `worker` コンテナの非 root ユーザ（`kakeibo`、UID 1000）が読み書きできる必要がある。volume の所有権は事前に揃えておく前提。

## 実装手順（TDD）

### 1. Red

- `worker/tests/unit/ingest/test_archiver.py`：
  - 成功時に `archive_path / mufg / 2026-05 / sample.csv` に移動、inbox から消滅
  - 失敗時に `dead_letter_path / sample.csv` + `sample.csv.error.log`
  - 同名衝突時にタイムスタンプ付きリネーム
  - `error.log` にトークン文字列が含まれていないこと（pytest fixture でログを inspect）
- `worker/tests/integration/archiver/test_archiver_e2e.py` で実ファイル移動。

### 2. Green

- `worker/src/kakeibo_worker/ingest/archiver.py` に `archive_success(path: Path, *, institution: str, archive_root: Path) -> Path` と `archive_failure(path: Path, *, error: Exception, dead_letter_root: Path) -> Path` を実装。
- `watcher.py` から取込結果に応じて呼び分ける。

### 3. Refactor

- 衝突回避のリネームロジックを `_resolve_collision(target: Path) -> Path` に抽出。
- `_format_error_log(error: Exception) -> str` を独立関数にしてテストしやすくする。

## 受入条件

- 成功時にファイルが `archive_path/<institution>/<YYYY-MM>/` へ移動し inbox から消える
- パース例外時に dead_letter へ移動し `<file>.error.log` が併置される
- 同名ファイル衝突時にタイムスタンプが付与される
- error.log に **トークン・シークレット文字列が含まれない** ことをテストで保証
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
docker compose run --rm worker pytest worker/tests/unit/ingest/test_archiver.py worker/tests/integration/archiver/
docker compose run --rm worker ruff check .
docker compose run --rm worker pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/archive-and-dead-letter`
- コミット粒度（最低 4 件）：
  1. `テスト: archive成功/失敗/衝突/エラーログ機微情報除外のテストを先行作成`
  2. `機能: archive_success / archive_failure 純関数を実装`
  3. `機能: error.log書き出しと衝突時タイムスタンプリネームを追加`
  4. `機能: WatcherにArchiver呼び出しを統合`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.2 アーカイブ移動 + dead letter を実装。

## 成果物
- worker/src/kakeibo_worker/ingest/archiver.py
- worker/tests/unit/ingest/test_archiver.py
- worker/tests/integration/archiver/test_archiver_e2e.py

## 検証結果
- 全件緑（unit + integration）
- error.log にトークン非混入を確認
- pyright / ruff: クリーン

## 次のアクション提案
worker/Ph2/03 (Gmail MCP) と並行 / worker/Ph2/08 (cron) で再利用可能。
```

## 注意事項

- error.log への書き込み時、**例外メッセージにトークン値が含まれる可能性**がある（HTTP クライアントのエラーメッセージ等）。`agent-rules/12-security-guidelines.md` に従い、シークレット候補文字列をマスクするフィルタを通す（`re.sub(r'(token|secret|key)=\S+', r'\1=***', msg, flags=re.IGNORECASE)`）。
- `shutil.move` は **異なるファイルシステム間で fall back コピー＋削除**になる。Docker volume が同一 FS にある前提で `os.rename` 同等の原子性を期待してよい。
- `archive_path` / `dead_letter_path` が存在しない場合は **作成しない**（運用時に明示的に作成する volume なので）。`FileNotFoundError` を伝播させて運用ミスを早期検出。
- 取込日・実行時刻は `datetime.now(timezone.utc)` で UTC 取得。タイムゾーン揺れを避ける（`compose.yml` の TZ=Asia/Tokyo はログ表示用、ファイル系処理は UTC）。
