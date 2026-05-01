---
title: ui/Ph3/02 月次推移グラフ
service: ui
phase_task_id: 3.3
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.3（行 333-343）
branch: feature/monthly-trend-chart
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# ui/Ph3/02 月次推移グラフ（Phase 3.3）

## このファイルの位置付け

原典 §4.3 Phase 3.3 を `ui` サービス担当の指示書として展開。`ui/Ph3/01` の基盤と `api/Ph3/02` の集計エンドポイントを利用して、全口座合計残高の月次推移を `recharts` の `LineChart` で表示する。

## 担当サービス

`compose.yml` `ui` サービス。`ui/app/balances/` に残高ページを追加し、期間フィルタ + 折れ線グラフ + 空状態 UI を実装する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `ui/Ph3/01`（雛形）+ `api/Ph3/02`（`/api/balances/monthly`） |
| 下流 | `ui/Ph3/06`（Playwright e2e） |

`ui/Ph3/03` / `04` / `05` と並列着手可能。

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.3（行 333-343）
2. **デプロイ**: `docs/design/04-deployment-stack.md`
3. **API 仕様**: `api/Ph3/02-aggregation-endpoints.md` の `/api/balances/monthly`
4. **デザイン**: `agent-rules/15-frontend-design.md`
5. **既存資産**: `ui/lib/api/client.ts`, `ui/components/feedback/*`（`ui/Ph3/01` で実装済み）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `ui/lib/api/balances.ts` | `useMonthlyBalances({from, to})` フック（react-query） |
| `ui/components/charts/MonthlyTrendChart.tsx` | recharts `LineChart`（Client Component） |
| `ui/components/charts/PeriodFilter.tsx` | 直近12か月 / 全期間 / カスタム |
| `ui/app/balances/page.tsx` | 残高ページ（ヘッダ + フィルタ + チャート） |
| `ui/components/charts/__tests__/MonthlyTrendChart.test.tsx` | Render + 空状態 + データ反映 |
| `ui/app/balances/__tests__/page.test.tsx` | MSW モックでの統合 Render |

## 実装方針

1. **空状態 UI**: 原典 (c)「データ無し時に空状態 UI」を `ui/Ph3/01` の `EmptyState` で実装。
2. **期間フィルタの URL 同期**: `?from=YYYY-MM&to=YYYY-MM` を Next.js `searchParams` で同期、ブックマーク可能に。
3. **アクセシビリティ**: チャートに `aria-label` / `role="img"` + 数値テーブル併設（スクリーンリーダ対応）。
4. **凡例**: 全口座合計のみ。口座別の重ね描画は Phase 4 以降。
5. **Server / Client Component**: `page.tsx` は Server、データ取得は `useMonthlyBalances` フック → `"use client"` のチャートコンポーネントに渡す。
6. **金額整形**: `Intl.NumberFormat('ja-JP', {style: 'currency', currency: 'JPY'})` で軸ラベル整形。

## 実装手順（TDD）

### 1. Red

- `MonthlyTrendChart.test.tsx`：
  - `test_renders_line_chart_with_data()`：期待データで折れ線が描画
  - `test_shows_empty_state_when_no_data()`：データ空で `EmptyState` 表示
  - `test_chart_has_accessible_label()`：`aria-label` を持つ
  - `test_y_axis_formats_currency_jpy()`
- `page.test.tsx`（MSW）：
  - `test_renders_12_months_default()`
  - `test_period_filter_updates_url_search_params()`：フィルタ変更で URL に反映

### 2. Green

1. `ui/lib/api/balances.ts` で `useMonthlyBalances` フック実装（react-query + fetch ラッパ）
2. `ui/components/charts/MonthlyTrendChart.tsx` で recharts `LineChart` 実装、`"use client"`
3. `ui/components/charts/PeriodFilter.tsx` で期間選択 UI
4. `ui/app/balances/page.tsx` でフィルタ + チャート統合、`searchParams` 連携

### 3. Refactor

- 通貨整形を `ui/lib/format/currency.ts` に共通化（`03 / 04` でも再利用予定）
- 期間プリセット（直近 6 か月 / 12 か月 / 全期間）を定数化

## 受入条件

原典 §4.3 Phase 3.3 受入基準：
- `GET /api/balances/monthly` の結果を折れ線で描画
- 期間フィルタ（直近12か月 / 全期間）が動作
- データ無し時に空状態 UI

加えて：
- recharts の SSR/CSR 互換性確認（`"use client"` 配下で正常）
- 月数 1〜120 で正常描画
- 巨大データ（120 か月）で描画 1 秒以内
- `aria-label` で「YYYY年MM月の全口座合計残高: ¥XXX」の要約が読める
- `tsc --strict` クリーン

## 品質ゲート

```bash
cd ui
npm run test -- balances MonthlyTrendChart
npm run typecheck
npm run lint
```

## ブランチ・コミット規約

- ブランチ: `feature/monthly-trend-chart`
- コミット粒度（最低 4 件）：
  1. `テスト: 月次推移チャート・期間フィルタ・空状態のテストを先行作成`
  2. `機能: useMonthlyBalances フックとAPIラッパを実装`
  3. `機能: MonthlyTrendChart コンポーネントとアクセシビリティ対応を実装`
  4. `機能: balances ページに期間フィルタとチャートを統合`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.3 月次推移グラフを実装。

## 成果物
- ui/lib/api/balances.ts
- ui/components/charts/{MonthlyTrendChart,PeriodFilter}.tsx
- ui/app/balances/page.tsx
- 各 __tests__/

## 検証結果
- npm run test / typecheck / lint: 全件緑
- 描画パフォーマンス: 120ヶ月データで < 1秒

## 次のアクション提案
ui/Ph3/03 (カテゴリ別) / 04 (ポートフォリオ) と並行で進行可能。
```

## 注意事項

- **recharts は Client Component 必須**（`"use client"` ディレクティブを忘れない）。
- **searchParams の hydration mismatch** に注意：Server Component で読んだ searchParams を Client に渡すパターンを踏襲。
- **空配列レスポンス**は API 側（`api/Ph3/02`）で `200 + {data: []}` を返す前提。
- **凡例・色**: `agent-rules/15-frontend-design.md` のアクセント色に合わせる。`recharts` の既定パステルは使わない。
