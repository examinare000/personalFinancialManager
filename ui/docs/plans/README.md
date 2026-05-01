---
title: ui サービス Phase1 タスク指示書
service: ui
phase: 1
status: NoTasks
parent_index: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# ui サービス Phase1 タスク指示書

## 結論：Phase1 では本サービス向けの新規実装タスクなし

`compose.yml` `ui` サービス（Next.js / Node.js 20 LTS）は **Phase 0 で雛形が配備済み**。`ui/src/app/{layout.tsx,page.tsx}` の最小ページが起動するのみで、Phase 1 の MVP（CSV → DB → SQL）には UI が必要ない。

Phase 1 のタスク（1.1〜1.8）はすべて `postgres` または `worker` サービスに帰属する。`docs/plans/10-phase1-overview.md` §2 のタスク一覧で UI を変更する項目は存在しない。

## サービス境界（参考）

| 範囲 | パス |
|---|---|
| Next.js アプリ本体 | `ui/src/app/` |
| 設定 | `ui/{next.config.mjs, tsconfig.json, package.json, package-lock.json}` |
| Dockerfile（multi-stage） | `ui/Dockerfile` |
| .gitignore | `ui/.gitignore` |

## Phase1 の間に ui サービスへ波及する変更（許容例）

| 変更例 | 受入可否 | 備考 |
|---|---|---|
| `ui/package.json` の依存追加 | 原則不要 | Phase 1 では追加しない |
| `ui/Dockerfile` 変更 | 原則不要 | – |
| ヘルスチェック挙動の変更 | 不可 | Phase 0 の HEALTHCHECK が他テスト（`tests/unit/test_ui_nextjs.py` 等）と整合していることを維持 |

`agent-rules/00-core-principles.md` の絶対遵守の3原則 §1 デグレッション防止を厳守する。

## Phase 3.2 への申し送り

Phase 3 で本サービスに本格着手するときの起点：

- 原典: `docs/plans/01-development-plan.md` §4.3 Phase 3.2 React Dashboard 雛形
- ブランチ: `feature/react-dashboard-scaffold`
- 関連 ADR: ADR-009（NAS + Docker Compose）
- 関連 design: `docs/design/04-deployment-stack.md`
- 関連 agent-rules: `agent-rules/15-frontend-design.md`
- 着手内容（予定）：
  - Vite + TypeScript + React の構築（Next.js 雛形からの移行 or 併存）
  - API クライアント（`fetch` ラッパ）
  - レイアウト整備
  - vitest + Testing Library 基盤

Phase 3.2 着手時に本ディレクトリへ `01-react-dashboard-scaffold.md` 等の指示書を追加する。

## 担当 Worker サブエージェント

Phase1 期間中は原則不要。

| Worker | 役割 |
|---|---|
| Reviewer | `tests/unit/test_ui_nextjs.py` 等が `worker`/`postgres` 側のタスクで影響を受けないことを Read のみで確認（プロジェクト共通設定の変更時など） |
