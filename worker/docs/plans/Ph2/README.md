---
title: worker サービス Phase2 タスク指示書
service: worker
phase: 2
status: Ready
parent_index: docs/plans/12-phase2-service-assignments.md
last_updated: 2026-05-01
---

# worker サービス Phase2 タスク指示書

`compose.yml` `worker` サービス（Phase1 で取込パイプラインのコア層を実装した上に、Phase2 では **自動取込基盤**を積み上げる）。Phase2 の 8 タスクすべてが本サービスに帰属する。

## サービス境界（Phase2 で本ディレクトリが扱うもの）

| 範囲 | パス |
|---|---|
| watchdog Watcher（inbox 監視） | `worker/src/kakeibo_worker/ingest/watcher.py` |
| アーカイブ移動 / dead letter ロジック | `worker/src/kakeibo_worker/ingest/archiver.py` |
| Gmail MCP クライアント + `RawMail` 共通型 | `worker/src/kakeibo_worker/adapters/gmail/`, `shared/kakeibo_shared/domain/raw_mail.py` |
| メールパーサ群（Amazon / 楽天 / Yahoo） | `worker/src/kakeibo_worker/adapters/mail/{amazon,rakuten,yahoo}.py` |
| PayPal API クライアント | `worker/src/kakeibo_worker/adapters/paypal.py` |
| cron バッチランナー / scheduler | `worker/src/kakeibo_worker/scheduler.py`, `worker/Dockerfile`（cron 関連改修） |
| Phase2 統合テスト | `tests/integration/{watcher,archiver,mail,paypal,scheduler}/` |
| メール fixture（合成 .eml） | `tests/fixtures/mail/{amazon,rakuten,yahoo}/*.eml` |

### このディレクトリでは扱わないもの

| 対象 | 帰属 |
|---|---|
| DB スキーマの追加変更 | `postgres/`（Phase2 ではスキーマ変更なし） |
| REST API / UI | `api/Ph3/`, `ui/Ph3/`（Phase 3 で着手） |
| LLM 分類 / Reconciler | Phase 4（`docs/plans/01-development-plan.md` §4.4） |

## タスク一覧

| 連番 | 担当タスク | 指示書 | 原典（行） | ブランチ | 優先度 |
|---|---|---|---|---|---|
| 01 | Phase 2.1 watchdog Watcher サービス | [`01-watcher-service.md`](./01-watcher-service.md) | §4.2 L211-221 | `feature/watcher-service` | 🔴 高 |
| 02 | Phase 2.2 アーカイブ + dead letter | [`02-archive-and-dead-letter.md`](./02-archive-and-dead-letter.md) | §4.2 L223-233 | `feature/archive-and-dead-letter` | 🟠 中 |
| 03 | Phase 2.3 Gmail MCP 接続 | [`03-gmail-mcp-client.md`](./03-gmail-mcp-client.md) | §4.2 L235-245 | `feature/gmail-mcp-client` | 🔴 高 |
| 04 | Phase 2.4 Amazon メールパーサ | [`04-parser-amazon-mail.md`](./04-parser-amazon-mail.md) | §4.2 L247-257 | `feature/parser-amazon-mail` | 🟡 中 |
| 05 | Phase 2.5 楽天市場 メールパーサ | [`05-parser-rakuten-mail.md`](./05-parser-rakuten-mail.md) | §4.2 L259-269 | `feature/parser-rakuten-mail` | 🟡 中 |
| 06 | Phase 2.6 Yahoo!ショッピング メールパーサ | [`06-parser-yahoo-mail.md`](./06-parser-yahoo-mail.md) | §4.2 L271-281 | `feature/parser-yahoo-mail` | 🟡 中 |
| 07 | Phase 2.7 PayPal API クライアント | [`07-adapter-paypal-api.md`](./07-adapter-paypal-api.md) | §4.2 L283-293 | `feature/adapter-paypal-api` | 🔴 高 |
| 08 | Phase 2.8 cron バッチ運用化 | [`08-cron-batch-runner.md`](./08-cron-batch-runner.md) | §4.2 L295-305 | `feature/cron-batch-runner` | 🟠 中 |

## 実行順序（推奨直列 + 並列）

```
[Phase1 完了] ←必須前提
   ↓
worker/Ph2/01 (Watcher) ─→ worker/Ph2/02 (Archive/DLQ)
worker/Ph2/03 (Gmail) ─┬─→ worker/Ph2/04 (Amazon)
                       ├─→ worker/Ph2/05 (Rakuten)
                       └─→ worker/Ph2/06 (Yahoo)
worker/Ph2/07 (PayPal)
                                         ↓
                           worker/Ph2/08 (cron; 04/05/06/07 完了後)
```

並列の機会：
- `01 (Watcher)` と `03 (Gmail)` は独立 → 別 Coder で並列可
- `04 / 05 / 06` は Gmail MCP 完了後に 3 並列可
- `07 (PayPal)` は他レーンと完全独立

## 共通の前提

- **Phase1 完了が必須**（`worker/Ph1/01〜07` と `postgres/Ph1/01` が緑）
- `pyproject.toml` の dependencies / dev / mail extras は宣言済み（追加は最小限）
- secrets ファイルは `secrets/*.example` を参考にローカル開発用にコピーして使用（実値は git に絶対コミットしない）
- `compose.yml` の `worker` 環境変数（`INBOX_PATH`, `GMAIL_OAUTH_TOKEN_FILE` など）は変更不要（既宣言）

## 担当 Worker サブエージェント（モードB前提）

`agent-rules/91-claude-subagent-coding.md` に従う。

| Worker | 主な責務 |
|---|---|
| Planner | Watcher の責務分割、メールパーサの fixture 設計、cron スケジュール設計 |
| Coder | テスト先行 → 実装。Watcher/Archiver は統合テスト中心、メールパーサはゴールデンマスタ |
| Reviewer | OAuth スコープが `gmail.readonly` 限定か、トークン・シークレットがログに漏れないか、冪等性、レート制限ハンドリング |
| Git-composer | アトミックコミット、`feature/*` ブランチ運用 |

並列ポリシー: `04/05/06` は同一メッセージ内に 3 体の Coder Task を並列起動可（同一ファイルへの競合なし）。

## 共通の品質ゲート

```bash
pytest tests/unit/ tests/integration/   # 該当範囲緑（統合は 5 分以内）
ruff check .
pyright
```

統合確認（`08-cron-batch-runner.md` 完了後）：
- `/inbox` への CSV 投下から 5 分以内に DB 反映
- 模擬メール 3 EC で取引抽出
- PayPal Sandbox 取引取得
- 失敗ファイルが dead_letter へ移動
- cron 連続実行で重複取引なし

## Phase2 完了条件カバレッジ

| 完了条件 | 主担当タスク |
|---|---|
| (a) Watcher 5 分以内 DB 反映 | `01` + `02` |
| (b) EC メール取引抽出 | `04` + `05` + `06`（基盤: `03`） |
| (c) PayPal Sandbox 取引取得 | `07` |
| (d) 失敗ファイル → dead_letter | `02` |
| (e) 統合テスト緑 | 全タスク横断 |
