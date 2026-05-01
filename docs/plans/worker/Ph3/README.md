---
title: worker サービス Phase3 タスク指示書
service: worker
phase: 3
status: NoTasks
parent_index: docs/plans/13-phase3-service-assignments.md
last_updated: 2026-05-01
---

# worker サービス Phase3 タスク指示書

## 結論：Phase3 では本サービス向けの新規実装タスクなし

`compose.yml` `worker` サービスは Phase 1〜2 で取込パイプライン（CLI / Watcher / メールパーサ / PayPal API / cron バッチ）が完成する設計。Phase 3 は **「すでに DB に蓄積された取引データ」を REST API + UI で可視化する**フェーズのため、worker 側の取込ロジックには手を入れない。

`docs/plans/01-development-plan.md` §4.3 のタスク 3.1〜3.6 をすべて確認しても、worker サービスの実装を変更する項目はない。

## サービス境界（参考）

| 範囲 | パス | Phase 3 での扱い |
|---|---|---|
| 取込CLI | `src/kakeibo/ingest/cli.py` | 変更なし |
| Watcher / Archiver | `src/kakeibo/ingest/{watcher,dispatch,archiver}.py` | 変更なし |
| メールパーサ群 | `src/kakeibo/adapters/mail/` | 変更なし |
| PayPal API クライアント | `src/kakeibo/adapters/paypal.py` | 変更なし |
| Scheduler / Jobs | `src/kakeibo/worker/{scheduler,jobs/}.py` | 変更なし |
| `worker/Dockerfile` | – | 変更なし |

## Phase3 の間に worker サービスへ波及する変更（許容例）

| 変更例 | 受入可否 | 備考 |
|---|---|---|
| `pyproject.toml` `[project.dependencies]` への追加（`flask-smorest`, `marshmallow`） | 可（再ビルド必要） | `api/Ph3/01` で発生。worker イメージにも反映されるが起動時は import されない |
| `src/kakeibo/__init__.py` の `__version__` 更新 | 可 | リリース時の同期 |
| `src/kakeibo/config.py` への認証バイパスフラグ追加 | 慎重に | `api/Ph3/01` で `KAKEIBO_API_AUTH_BYPASS` を Settings に追加する際、worker では参照しないが既存テスト（`tests/unit/test_settings_repr.py`）を壊さないこと |
| `worker/Dockerfile` 変更 | 不要 | – |

`agent-rules/00-core-principles.md` の3原則 §1 デグレッション防止と整合：既存の取込パイプラインの動作・既存テストを壊さないこと。

## Phase 4 への申し送り

Phase 4 で本サービスに変更が必要となる候補：

- **Phase 4.1 LLM 分類サービス**: `api/Ph3/03` で実装される `src/kakeibo/categorizer/rules.py` を再利用しつつ、未マッチ取引を Anthropic API に投げて分類するワーカージョブを `src/kakeibo/worker/jobs/llm_classify.py` として追加
- **Phase 4.2 半自動学習**: ルール提案ジョブを `src/kakeibo/worker/jobs/rule_suggest.py` として追加
- **Phase 4.3 Reconciler**: 連動取引マージのワーカージョブ
- **Phase 4.4 残高整合性レポート**: 日次整合性チェックジョブ
- **Phase 4.5 Obsidian 月次出力**: 月次バッチで Markdown 出力

これらは Phase 4 着手時に `docs/plans/worker/Ph4/` を新設して扱う。

## 担当 Worker サブエージェント

Phase3 期間中の起動は **Reviewer のみ**：

| Worker | 役割 |
|---|---|
| Reviewer | `api/Ph3/01` で `pyproject.toml` に `flask-smorest` / `marshmallow` が追加されたとき、`worker` コンテナのビルド・起動・既存テスト（`tests/unit/`, `tests/integration/`）が壊れないことを Read のみで確認 |
| Reviewer | `api/Ph3/03` で実装される `src/kakeibo/categorizer/rules.py` が、Phase 4.1 LLM 分類との接合点として再利用しやすい設計か（責務分離・依存方向）を確認 |

Coder / Planner / Git-composer の起動は Phase3 では原則不要。
