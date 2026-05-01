---
title: worker/Ph2/08 cron バッチ運用化
service: worker
phase_task_id: 2.8
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.8（行 295-305）
branch: feature/cron-batch-runner
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/08 cron バッチ運用化（Phase 2.8）

## このファイルの位置付け

原典 §4.2 Phase 2.8 を `worker` 担当の指示書として展開。Phase 2.4〜2.7 のすべてが **完了** していることが前提。Gmail 取込（Amazon / 楽天 / Yahoo）と PayPal 取込を **日次バッチ**として運用に組み込む最終タスク。

## 担当サービス

`worker` コンテナ。`worker/Dockerfile` への cron 関連改修と、`worker/src/kakeibo_worker/scheduler.py` バッチ実行エントリポイントを実装する。`compose.yml` の `worker` サービスは引き続き常駐し、内部で cron が日次トリガを発火する形（Phase 0 の heartbeat ループ + Watcher + cron の三層常駐構造）。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph2/04`, `05`, `06`（メールパーサ）, `worker/Ph2/07`（PayPal） |
| 下流 | Phase 4.x（LLM 分類 / Reconciler 等が本バッチに新規ジョブを追加する想定） |

## 入力

1. **原典**: §4.2 Phase 2.8（行 295-305）
2. **デプロイ**: `docs/design/04-deployment-stack.md`
3. **取込フロー**: `worker/docs/design/08-ingest-flow.md`
4. **ADR**: `docs/adr/009-nas-docker-compose.md`
5. **既存資産**:
   - `worker/Dockerfile`（uv マルチステージ、`USER kakeibo` で非 root）
   - `worker/src/kakeibo_worker/main.py`（heartbeat ループ + `worker/Ph2/01` で Watcher 統合済み）
   - 各種 Adapter（`worker/Ph2/03〜07`）
6. **依存追加検討**: `apscheduler>=3.10,<4` を `[project.dependencies]` に追加（cron 起動を **Python プロセス内**で行う方式を推奨。OS の cron デーモンを別途立てる方式より監査・テストが容易）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `pyproject.toml` | `apscheduler>=3.10,<4` 追加 |
| `worker/src/kakeibo_worker/scheduler.py` | APScheduler ベースのジョブ登録 + 起動 |
| `worker/src/kakeibo_worker/jobs/__init__.py` | パッケージ |
| `worker/src/kakeibo_worker/jobs/gmail_ingest.py` | Gmail 取込ジョブ（Amazon / 楽天 / Yahoo を順に実行） |
| `worker/src/kakeibo_worker/jobs/paypal_ingest.py` | PayPal 取込ジョブ |
| `worker/src/kakeibo_worker/main.py` | `run()` の中で Scheduler を起動（既存 API 互換維持） |
| `tests/unit/worker/test_scheduler.py` | ジョブ登録 / トリガ時刻 / 実行ログ |
| `tests/unit/worker/test_gmail_ingest_job.py` | Gmail ジョブが冪等に動く |
| `tests/unit/worker/test_paypal_ingest_job.py` | PayPal ジョブが冪等に動く |
| `tests/integration/scheduler/test_scheduler_e2e.py` | 短い間隔でジョブを発火させて DB 反映を確認 |

## 実装方針

1. **APScheduler 採用理由**: OS の cron デーモンを `worker` コンテナに同居させると、非 root 運用と PID 1 のシグナルハンドリングが複雑化する。Python プロセス内 scheduler ならテストとログが統一できる。
2. **トリガ時刻**:
   - Gmail 取込: 毎日 03:00 JST（`CronTrigger(hour=3, minute=0, timezone="Asia/Tokyo")`）
   - PayPal 取込: 毎日 03:30 JST
3. **ジョブの冪等性**: 各ジョブは `worker/Ph2/04〜07` の Adapter を呼び、`worker/Ph1/05` の `persister.persist(transactions)` で DB に永続化（`ON CONFLICT (hash) DO NOTHING`）。**連続実行で重複取引が発生しない**ことをテストで保証。
4. **失敗時のログ**: `structlog` で構造化ログ。`event=job_failed`, `job_name=...`, `error_class=...`, `traceback=...`。stdout / stderr 経由で Docker のログドライバへ流す。
5. **graceful shutdown**: `BackgroundScheduler.shutdown(wait=True)` を SIGTERM ハンドラから呼ぶ。実行中ジョブの完了待ち（最大 30 秒）→ 強制終了。
6. **`worker/Dockerfile` 改修**: 原則 **不要**（Python プロセス内 scheduler のため）。CMD は `python -m kakeibo.worker` のまま。
7. **テスト戦略**: APScheduler の `BackgroundScheduler` は **同期実行に切替えてテスト**（`scheduler.add_job(..., next_run_time=datetime.now())` + `scheduler.start()` + `scheduler.shutdown(wait=True)`）。

## 実装手順（TDD）

### 1. Red

- `tests/unit/worker/test_scheduler.py`：
  - `register_jobs(scheduler)` が 2 ジョブ登録（gmail / paypal）
  - `CronTrigger` の時刻が期待通り
  - SIGTERM 相当で graceful shutdown
- `tests/unit/worker/test_gmail_ingest_job.py`：
  - モック Gmail クライアント + モック persister で `gmail_ingest_job()` が Amazon / 楽天 / Yahoo の順に呼ばれる
  - 連続 2 回実行で永続化呼び出し回数は同じだが行数増加なし（モック persister の `ON CONFLICT` 模倣）
- `tests/unit/worker/test_paypal_ingest_job.py`：同様に PayPal 単独。
- `tests/integration/scheduler/test_scheduler_e2e.py`：testcontainers Postgres + 短い `next_run_time` で実発火 → DB 反映確認。

### 2. Green

- `pyproject.toml` に `apscheduler` 追加 + `uv sync`。
- `worker/src/kakeibo_worker/jobs/{gmail_ingest,paypal_ingest}.py` を最小実装。
- `worker/src/kakeibo_worker/scheduler.py` で `register_jobs(scheduler) -> None` と `build_scheduler() -> BackgroundScheduler` を実装。
- `worker/src/kakeibo_worker/main.py` の `run()` で Scheduler を起動 + heartbeat ループ + Watcher と並行常駐。

### 3. Refactor

- ジョブ共通の例外ハンドリング（ログ書き出し → 例外を握り潰さない）を `_run_with_logging(job_fn, *, job_name)` に抽出。
- トリガ設定を `_build_triggers(settings: Settings) -> dict[str, CronTrigger]` に集約してテスト容易化。

## 受入条件

- `docker compose up -d` で `worker` コンテナ内で日次 cron が起動状態（`docker compose exec worker python -c "..."` で scheduler 状態確認可能）
- バッチ失敗時に構造化ログが残る（`event=job_failed` を含む）
- 連続実行で重複取引が発生しない（`hash` UNIQUE で吸収）
- SIGTERM で graceful shutdown（実行中ジョブ完了待ち 30 秒以内）
- heartbeat / Watcher と並行して動作する
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/worker/ tests/integration/scheduler/
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/cron-batch-runner`
- コミット粒度（最低 5 件）：
  1. `テスト: scheduler登録・冪等ジョブ実行・graceful shutdownのテストを先行作成`
  2. `設定: apscheduler依存パッケージをpyproject.tomlに追加`
  3. `機能: Gmail取込ジョブ（Amazon/楽天/Yahoo順次起動）を実装`
  4. `機能: PayPal取込ジョブを実装`
  5. `機能: APScheduler起動とworkerメインループ統合・graceful shutdownを追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.8 cron バッチ運用化を実装。

## 成果物
- pyproject.toml（apscheduler 追加）
- worker/src/kakeibo_worker/scheduler.py
- worker/src/kakeibo_worker/jobs/{gmail_ingest,paypal_ingest}.py
- worker/src/kakeibo_worker/main.py（拡張）
- tests/unit/worker/{test_scheduler,test_gmail_ingest_job,test_paypal_ingest_job}.py
- tests/integration/scheduler/test_scheduler_e2e.py

## 検証結果
- 全件緑（unit + integration）
- 連続実行で重複取引なし
- graceful shutdown 動作確認
- pyright / ruff: クリーン

## Phase 2 完了状況
Phase2 完了条件 (a) (b) (c) (d) (e) すべて達成。Phase 3 着手準備が整った。

## 次のアクション提案
docs/plans/{api,ui}/Ph3/ 配下に Phase 3 タスク指示書を生成する。
```

## 注意事項

- **OS cron デーモン併設は採用しない**: 非 root 運用 + PID 1 シグナル処理が複雑になるため、APScheduler in-process 方式で統一。
- **タイムゾーン**: cron トリガは `Asia/Tokyo` 指定だが、内部処理（PayPal の日付範囲など）は **UTC で固定**（タイムゾーン揺れ防止）。
- **ジョブ重複起動禁止**: APScheduler の `max_instances=1` をジョブごとに設定。前回実行が遅延しても多重実行しない。
- **secrets 不在時の挙動**: 開発ホスト等で `gmail_oauth_token` / `paypal_api_secret` が未配置の場合、scheduler 起動は成功するがジョブ実行時に `RuntimeError` を出して停止。**サイレントに失敗させない**。
- **Watcher との競合なし**: Watcher は inbox の CSV 取込、cron は Gmail / PayPal の API 取込で経路が完全分離。同じ `transactions.hash` で UNIQUE 衝突しても `ON CONFLICT DO NOTHING` で吸収される。
