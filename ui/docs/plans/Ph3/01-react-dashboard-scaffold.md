---
title: ui/Ph3/01 React Dashboard 雛形
service: ui
phase_task_id: 3.2
priority: 高
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.2（行 321-331）
branch: feature/react-dashboard-scaffold
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# ui/Ph3/01 React Dashboard 雛形（Phase 3.2）

## このファイルの位置付け

原典 `docs/plans/01-development-plan.md` §4.3 Phase 3.2 を `ui` サービス担当の指示書として展開。Phase 3 ui タスク群（02〜06）すべての **基盤**となるクリティカルパス上のタスク。

**原典との重要な差分**: 原典は「Vite + TypeScript + React」を指定しているが、本指示書は **Next.js 14 App Router を維持**する方針を採用する（Phase 0 の Dockerfile / standalone build / healthcheck / 既存テストを保護するため、`agent-rules/00-core-principles.md` §1 デグレッション防止）。原典の本質である「TypeScript + React」は採用、ビルド基盤のみ Next.js に固定。原典は不変扱い（Phase 1〜2 と同じ慣習）。

## 担当サービス

`compose.yml` `ui` サービス（Next.js 14、Node.js 20 LTS）。`ui/Dockerfile` の standalone build と healthcheck 互換性を維持しつつ、ライブラリ・コンポーネント・テスト基盤を整備する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `api/Ph3/01`（OpenAPI スキーマが取得できる） |
| 下流 | `ui/Ph3/02`〜`05`（共通レイアウト・APIクライアント前提）, `ui/Ph3/06`（Playwright） |

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.2（行 321-331）
2. **デプロイ**: `docs/design/04-deployment-stack.md` §3 / §6（Caddy `/` → ui:3000、`/api/*` → api:8000）
3. **フロントエンド規約**: `agent-rules/15-frontend-design.md`（**必読**）
4. **テスト戦略**: `agent-rules/11-testing-strategy.md`
5. **既存資産**: `ui/{app/{layout,page}.tsx, Dockerfile, next.config.mjs, tsconfig.json, package.json, package-lock.json}`
6. **既存テスト**: `tests/unit/test_ui_nextjs.py`（Python 側、UI 設定の構造検証 — 破壊しないこと）
7. **API 基盤**: `api/Ph3/01-flask-rest-api.md` で実装される OpenAPI 仕様（`/api/openapi.json`）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `ui/package.json` | 依存追加（後述） |
| `ui/tsconfig.json` | `paths` 拡張（`@/lib/*`, `@/components/*`） |
| `ui/next.config.mjs` | `/api/*` を `process.env.API_BASE_URL`（既定 `http://api:8000`）にプロキシ |
| `ui/postcss.config.js` | Tailwind / autoprefixer |
| `ui/tailwind.config.ts` | カスタムフォント・カラートークン |
| `ui/styles/globals.css` | Tailwind ディレクティブ + デザイントークン CSS 変数 |
| `ui/lib/api/client.ts` | `fetch` ラッパ（タイムアウト / エラー正規化） |
| `ui/lib/api/types.gen.ts` | OpenAPI から自動生成（`openapi-typescript`） |
| `ui/lib/api/{transactions,categories,rules,balances,aggregations}.ts` | エンドポイント別 thin client |
| `ui/lib/query/provider.tsx` | `QueryClientProvider` |
| `ui/components/layout/AppShell.tsx` | サイドバー + ヘッダ + コンテンツ |
| `ui/components/feedback/{EmptyState,ErrorState,LoadingState}.tsx` | 共通状態コンポーネント |
| `ui/app/layout.tsx` | App Router ルート（既存拡張、`AppShell` 組込） |
| `ui/app/page.tsx` | ダッシュボードトップ（プレースホルダ → 02〜05 で内容追加） |
| `ui/test/setup.ts` | vitest + Testing Library セットアップ |
| `ui/test/msw/{server,handlers}.ts` | MSW モックサーバ |
| `ui/vitest.config.ts` | jsdom 環境、`@/` paths |
| `ui/lib/api/__tests__/client.test.ts` | `fetch` ラッパのテスト |
| `ui/components/__tests__/AppShell.test.tsx` | レイアウト Render テスト |
| `ui/components/__tests__/feedback.test.tsx` | 状態コンポーネントテスト |

`npm run generate:api` スクリプトで `/api/openapi.json` から型再生成可能にする（`package.json` の `scripts` に追加）。

## 実装方針

### 1. Next.js 14 App Router 維持

- Phase 0 の `ui/Dockerfile`（standalone build）/ healthcheck / `tests/unit/test_ui_nextjs.py` を **絶対に壊さない**
- 原典の「Vite」は採用しない（理由は本ファイル冒頭参照）
- React Server Components を活用：データ取得は Server Component、インタラクティブ UI は `"use client"`

### 2. 状態管理: `@tanstack/react-query` v5

- データ取得・キャッシュ・mutate の業界標準
- エラー時のリトライは既定で **無効化**（fetch ラッパ側で正規化したエラーをそのまま伝播）
- `staleTime: 30s`, `gcTime: 5min` 既定

### 3. API クライアント型: `openapi-typescript` で機械生成

- `ui/lib/api/types.gen.ts` を `npm run generate:api` で再生成
- 手書き型は禁止（DRY、API 仕様との乖離防止）
- 生成スクリプト例: `openapi-typescript http://api:8000/api/openapi.json -o ui/lib/api/types.gen.ts`

### 4. グラフライブラリ: `recharts`

- React ファースト・MIT・Server Component 互換性あり（Client Component で利用）
- `Chart.js` / `visx` は採用しない（後者は学習コスト、前者は命令的）

### 5. CSS: Tailwind + デザイントークン

- `tailwindcss` で utility-first
- デザイントークン（フォント・カラー・スペーシング）は `tailwind.config.ts` の `theme.extend` に集約
- **フォント**: `Noto Sans JP` + 日本語ディスプレイフォント（`Zen Kaku Gothic Antique` / `Reggae One` 等の選定は Coder/Reviewer 判断）
- **禁止フォント**: `Inter`, `Roboto`, `Helvetica`, system-ui defaults（`agent-rules/15-frontend-design.md`）

### 6. 認証

- 本番 Caddy が `Tailscale-User-Login` ヘッダを後段に伝播する前提
- UI 側はそのヘッダを意識しない（API 呼出時はそのまま fetch、ヘッダは Caddy が追加）
- ログイン UI は **実装しない**（Tailscale 認証で代替）

### 7. dev サーバ起動と環境変数

- `npm run dev` で `next dev` を起動（既存挙動を維持）
- `API_BASE_URL` 環境変数で API 接続先を切替（compose では `http://api:8000`、ローカル `http://localhost:8000`）
- `next.config.mjs` の `rewrites()` で `/api/*` → `${API_BASE_URL}/api/*` に変換

### 8. テスト基盤

- `vitest` + `@testing-library/react` + `@testing-library/jest-dom`
- `msw`（Mock Service Worker）で API モック
- jsdom 環境
- Playwright は別タスク（`ui/Ph3/06`）

### 9. AppShell レイアウト

- サイドバー: 残高 / 取引 / カテゴリ / ポートフォリオ / ルール の 5 リンク
- ヘッダ: アプリ名 + 現在の Tailscale ユーザ表示（`/api/me` で取得、Phase 3.1 で実装）
- メインコンテンツ領域: `children` を渡す
- レスポンシブ: 家庭内 PC / iPad で利用想定、モバイルは Phase 4 以降で評価

## 依存パッケージ追加（`ui/package.json`）

### runtime

- `@tanstack/react-query@^5`
- `recharts@^2`
- `zod@^3`
- `clsx@^2`

### dev

- `vitest@^2`
- `@vitest/ui`
- `@testing-library/react@^16`
- `@testing-library/jest-dom@^6`
- `@testing-library/user-event@^14`
- `jsdom@^24`
- `msw@^2`
- `tailwindcss@^3`
- `postcss@^8`
- `autoprefixer@^10`
- `openapi-typescript@^7`

`eslint-config-next` は Next.js 14 既定で同梱。

## 実装手順（TDD）

### 0. ブランチ作成

```bash
git checkout develop && git pull origin develop
git checkout -b feature/react-dashboard-scaffold
```

### 1. Red

`ui/lib/api/__tests__/client.test.ts`：
- `fetch` 失敗時に `ApiError` を throw
- タイムアウト時に `TimeoutError`
- エラーレスポンスの `error.code` をパース

`ui/components/__tests__/AppShell.test.tsx`：
- ナビゲーションリンク 5 項目が描画
- 現在ユーザ名がヘッダに表示（MSW で `/api/me` モック）
- アクティブなナビ項目がスタイル反映

`ui/components/__tests__/feedback.test.tsx`：
- `EmptyState` が `description` プロパティを表示
- `ErrorState` が `error.code` を表示
- `LoadingState` が `aria-busy="true"` を持つ

`pyproject` 系既存テストも引き続き緑（`tests/unit/test_ui_nextjs.py`）。

`npm run test` で全件赤を確認。

### 2. Green

1. `ui/package.json` に依存追加 → `npm install`
2. `ui/tailwind.config.ts`, `ui/postcss.config.js`, `ui/styles/globals.css` を実装
3. `ui/tsconfig.json` の `paths` 設定
4. `ui/next.config.mjs` の `rewrites()` 設定
5. `ui/vitest.config.ts`, `ui/test/setup.ts`, `ui/test/msw/{server,handlers}.ts` を実装
6. `ui/lib/api/client.ts`, `types.gen.ts`（生成）, `{transactions,...}.ts` を実装
7. `ui/lib/query/provider.tsx` を実装
8. `ui/components/feedback/{EmptyState,ErrorState,LoadingState}.tsx` を実装
9. `ui/components/layout/AppShell.tsx` を実装
10. `ui/app/layout.tsx` で `AppShell` + `QueryClientProvider` 統合
11. `ui/app/page.tsx` をダッシュボードトップ（プレースホルダ）に

`package.json` `scripts`：
```json
{
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "test": "vitest run",
  "test:watch": "vitest",
  "generate:api": "openapi-typescript ${API_BASE_URL:-http://localhost:8000}/api/openapi.json -o lib/api/types.gen.ts",
  "typecheck": "tsc --strict --noEmit"
}
```

### 3. Refactor

- `client.ts` のエラー正規化を `_normalize_error(response)` ヘルパに抽出
- AppShell のナビゲーション項目を `_NAV_ITEMS` 定数化

## 受入条件

原典 §4.3 Phase 3.2 受入基準：
- `npm run dev` で起動
- `tsc --strict` クリーン
- API クライアントと型定義が API スキーマと一致（`openapi-typescript` で機械生成）
- vitest + Testing Library が動作

加えて：
- `npm run build` が standalone 出力で成功（既存 Dockerfile 互換）
- `npm run lint`（next lint）違反ゼロ
- `npm run test` 全件緑
- `npm run typecheck` 全件緑
- MSW で OpenAPI スキーマ準拠のモックレスポンスが返せる
- `agent-rules/15-frontend-design.md` の禁止フォント / 配色を採用していない（Reviewer チェック）
- `npm run generate:api` で型再生成可能
- `tests/unit/test_ui_nextjs.py` が引き続き緑

## 品質ゲート

```bash
cd ui
npm install
npm run lint
npm run test
npm run build
npm run typecheck

# Python 側既存テスト
cd ..
pytest tests/unit/test_ui_nextjs.py
```

## ブランチ・コミット規約

- ブランチ: `feature/react-dashboard-scaffold`
- コミット粒度（最低 7 件）：
  1. `テスト: APIクライアント・AppShell・状態コンポーネントのテストを先行作成`
  2. `設定: vitest / Testing Library / MSW / Tailwind / openapi-typescript を導入`
  3. `機能: APIクライアント（fetchラッパ + 型生成スクリプト）を実装`
  4. `機能: react-query Provider と共通状態コンポーネントを実装`
  5. `機能: AppShell レイアウトとデザイントークン（フォント・配色）を実装`
  6. `設定: Next.js next.config.mjs の API リライトと dev サーバ環境変数を整備`
  7. `機能: app router layout に Provider と AppShell を統合`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.2 React Dashboard 雛形を実装。

## 成果物
- ui/package.json（依存追加 + scripts）
- ui/lib/api/{client,*.ts}
- ui/lib/query/provider.tsx
- ui/components/{layout/AppShell,feedback/*}.tsx
- ui/styles/globals.css + tailwind 設定
- ui/test/{setup.ts, msw/*}
- ui/vitest.config.ts
- ui/app/{layout,page}.tsx（拡張）
- ui/next.config.mjs（rewrites 追加）

## 検証結果
- npm run lint / test / build / typecheck: 全件緑
- tsc --strict クリーン
- tests/unit/test_ui_nextjs.py: 既存挙動維持
- 禁止フォント未使用を Reviewer 確認済み

## 次のアクション提案
ui/Ph3/02-04（残高 / カテゴリ / ポートフォリオ）が 3 並列で着手可能。
ui/Ph3/05（ルール編集UI）も並行可能。
```

## 注意事項

- **`ui/Dockerfile` を絶対に壊さない**（standalone build / healthcheck 互換）。Tailwind の build 時 CSS 確定は standalone と互換。
- **MSW の Service Worker 登録は dev only**（`npm run build` には乗せない、Phase 0 の本番イメージサイズに影響させない）。
- **`tests/unit/test_ui_nextjs.py` 互換性**: `package.json` の構造変更時にこの Python テストが期待する `name` / `scripts` / `dependencies` の存在条件を確認する。破壊する場合は同コミットでテストも更新。
- **Server Component vs Client Component**: グラフ・フォーム・状態管理が必要なコンポーネントは `"use client"` を付ける。データ取得は可能な限り Server Component で。
- **API 型生成のタイミング**: `api/Ph3/01` 完了後、最初に `npm run generate:api` を実行して `types.gen.ts` を取得。CI には組まない（Phase 3 内では手動）。
- **デザイン判断**: `agent-rules/15-frontend-design.md` の方向性（記憶に残るデザイン、禁止フォント・配色）について不明点があればユーザに確認。フォント候補（`Noto Sans JP` + ディスプレイフォント）は仮で、最終決定は Reviewer + ユーザ承認推奨。
