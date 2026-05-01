---
title: ui サービス Phase3 タスク指示書
service: ui
phase: 3
status: Ready
parent_index: docs/plans/13-phase3-service-assignments.md
last_updated: 2026-05-01
---

# ui サービス Phase3 タスク指示書

`compose.yml` `ui` サービス（Next.js 14 App Router、Phase 0 で雛形配備済み）を **本格的な React Dashboard** に拡張する。Phase 3 の主担当はこの ui サービス（5 タスク + e2e 横断 1 タスク）。

## サービス境界（Phase3 で本ディレクトリが扱うもの）

| 範囲 | パス |
|---|---|
| Next.js App Router 配下のページ | `ui/app/{balances,categories,portfolio,rules}/page.tsx` 等 |
| 共通レイアウト・状態コンポーネント | `ui/components/{layout,feedback,charts,tables,rules,portfolio}/` |
| API クライアント・型生成 | `ui/lib/api/`, `ui/lib/query/` |
| ロジック（構成比計算など） | `ui/lib/portfolio/` |
| グローバル CSS・デザイントークン | `ui/styles/` |
| テスト基盤 | `ui/test/`, `ui/vitest.config.ts` |
| package.json 依存追加 | `ui/package.json`, `ui/tsconfig.json`, `ui/next.config.mjs` |
| Playwright e2e | `tests/e2e/`（リポジトリルート、pytest 系と並列） |

### このディレクトリでは扱わないもの

| 対象 | 帰属 |
|---|---|
| Flask REST API / OpenAPI | `api/Ph3/01` |
| 集計エンドポイント（`/api/balances/monthly` 等） | `api/Ph3/02` |
| ルール dry-run エンドポイント | `api/Ph3/03` |
| DB スキーマ・取込パイプライン | `postgres/Ph3/`, `worker/Ph3/`（いずれもタスクなし） |

## タスク一覧

| 連番 | 担当タスク | 指示書 | 原典 | ブランチ | 優先度 |
|---|---|---|---|---|---|
| 01 | Phase 3.2 React Dashboard 雛形 | [`01-react-dashboard-scaffold.md`](./01-react-dashboard-scaffold.md) | §4.3 L321-331 | `feature/react-dashboard-scaffold` | 🔴 高 |
| 02 | Phase 3.3 月次推移グラフ | [`02-monthly-trend-chart.md`](./02-monthly-trend-chart.md) | §4.3 L333-343 | `feature/monthly-trend-chart` | 🟡 中 |
| 03 | Phase 3.4 カテゴリ別支出ビュー | [`03-category-spending-view.md`](./03-category-spending-view.md) | §4.3 L345-355 | `feature/category-spending-view` | 🟡 中 |
| 04 | Phase 3.5 ポートフォリオ構成ビュー | [`04-portfolio-view.md`](./04-portfolio-view.md) | §4.3 L357-365 | `feature/portfolio-view` | 🟡 中 |
| 05 | Phase 3.6 ルール編集UI | [`05-rule-editor-ui.md`](./05-rule-editor-ui.md) | §4.3 L367-377 | `feature/rule-editor-ui` | 🔴 高 |
| 06 | Phase 3 完了条件 (d) Playwright e2e | [`06-e2e-playwright.md`](./06-e2e-playwright.md) | §3.3 完了条件 (d) | `feature/playwright-e2e` | 🟡 中 |

## 実行順序（推奨）

```
[Phase 1 / 2 完了] + api/Ph3/01 完了
   ↓
ui/Ph3/01 (React 雛形)
   ├─→ ui/Ph3/02 (月次推移)     ← api/Ph3/02 必要
   ├─→ ui/Ph3/03 (カテゴリ別)   ← api/Ph3/02 必要
   ├─→ ui/Ph3/04 (ポートフォリオ) ← api/Ph3/02 必要
   └─→ ui/Ph3/05 (ルール編集UI)  ← api/Ph3/03 必要
                                  ↓
                          ui/Ph3/06 (Playwright e2e)
```

並列の機会：
- `ui/Ph3/02 / 03 / 04` は `ui/Ph3/01 + api/Ph3/02` 完了後に **3 並列** 可（異なるページ・コンポーネント）
- `ui/Ph3/05` は `api/Ph3/03` のみが直接依存、`02-04` と完全並列可

## 共通の前提

- **Phase 1 / 2 完了 + `api/Ph3/01` 完了が必須**
- `api/Ph3/02` 完了が `ui/Ph3/02-04` の前提
- `api/Ph3/03` 完了が `ui/Ph3/05` の dry-run プレビューの前提
- **Next.js 14 App Router 維持**（Vite 移行しない、Phase 0 の Dockerfile / standalone build / healthcheck 互換性確保）
- 状態管理は `@tanstack/react-query` v5、グラフは `recharts`
- API 型は OpenAPI から `openapi-typescript` で機械生成
- フォントは `Noto Sans JP` + 日本語ディスプレイフォント、**Inter / Roboto / system-ui を使用しない**（`agent-rules/15-frontend-design.md`）

## 担当 Worker サブエージェント

`agent-rules/91-claude-subagent-coding.md` に従う。

| Worker | 主な責務 |
|---|---|
| Planner | デザイントークン設計、コンポーネント分割、状態管理境界の設計 |
| Coder | テスト先行（Testing Library / MSW）→ コンポーネント実装。Server / Client Component の使い分け |
| Reviewer | `agent-rules/15-frontend-design.md` の禁止事項（フォント・配色）チェック、accessibility（キーボード操作・aria-label）、Server Component 制約 |
| Git-composer | アトミックコミット、`feature/*` ブランチ運用 |

並列ポリシー: `02 / 03 / 04` は同一メッセージで Coder 3体並列起動可。`05` も独立並列可。

## 共通の品質ゲート

```bash
cd ui
npm run lint                  # next lint
npm run test                  # vitest
npm run build                 # standalone 出力（既存 Dockerfile 互換性確認）
npx tsc --strict --noEmit     # 型チェック
```

統合確認（`ui/Ph3/06` 完了後）：
- Playwright e2e 主要 4 シナリオ（残高 / カテゴリ / ポートフォリオ / ルール）が緑
- 既存の Python テスト（`tests/unit/test_ui_nextjs.py`）も緑のまま

## Phase3 完了条件カバレッジ（ui 担当範囲）

| 完了条件 | 主担当タスク |
|---|---|
| (b) 月次推移 / カテゴリ / ポートフォリオ表示 | `02` + `03` + `04` |
| (c) UI からルール CRUD | `05` |
| (d) Playwright e2e 主要シナリオ緑 | `06` |
| (e) `tsc --strict` クリーン | 全タスク横断 |
