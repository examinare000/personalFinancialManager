---
title: ui/Ph3/06 Playwright e2e（Phase 3 完了条件 (d) 横断）
service: ui
phase_task_id: 3-completion
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §3.3 完了条件 (d)
branch: feature/playwright-e2e
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# ui/Ph3/06 Playwright e2e（Phase 3 完了条件 (d) 横断）

## このファイルの位置付け

原典 §3.3 完了条件 (d)「Playwright e2e で主要シナリオが緑」を満たす **横断タスク**。`ui/Ph3/02〜05` 完了後の Phase 3 最終検証。

## 担当サービス

`ui` サービスをエンドツーエンドで叩く e2e テスト。配置はリポジトリルート `tests/e2e/`（既存 `tests/unit/`, `tests/integration/` と並列、`agent-rules/11-testing-strategy.md` のテスト階層と整合）。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `ui/Ph3/02 / 03 / 04 / 05` 全完了 |
| 下流 | なし（Phase 3 完了の最終検証） |

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §3.3 完了条件 (d)
2. **テスト戦略**: `agent-rules/11-testing-strategy.md` §テスト階層
3. **デプロイ**: `docs/design/04-deployment-stack.md`
4. **既存資産**:
   - Phase 1.6 の取込CLI（`python -m kakeibo_worker.ingest`）でフィクスチャ投入
   - Phase 1.4 / 1.5 の MUFG / SMBC ゴールデンマスタ CSV
   - `compose.yml` の api / ui / postgres スタック
   - `ui/Ph3/01〜05` で実装された画面群

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `playwright.config.ts` | Playwright 設定（webServer / projects / use） |
| `package.json` または `Makefile` | `make e2e` / `npm run e2e` ターゲット |
| `tests/e2e/fixtures/seed.py` | 既知データ投入スクリプト |
| `tests/e2e/fixtures/mufg_known.csv` | 既知の MUFG CSV（合成データ） |
| `tests/e2e/fixtures/smbc_known.csv` | 既知の SMBC CSV |
| `tests/e2e/balances.spec.ts` | 月次推移グラフが描画される |
| `tests/e2e/categories.spec.ts` | カテゴリ別支出のドリルダウン |
| `tests/e2e/portfolio.spec.ts` | ポートフォリオ表示 |
| `tests/e2e/rules.spec.ts` | ルール作成 → dry-run → 保存 → 並び替え |
| `tests/e2e/.gitignore` | `results/`, `report/`, `test-results/` |

## 実装方針

### 1. テスト配置

- **リポジトリルート `tests/e2e/`**（`ui/` ディレクトリ内に置かない）
- 理由: `ui/Dockerfile` の COPY 範囲を不必要に拡大しない、Python 系テスト（`tests/unit/`, `tests/integration/`）と階層整合

### 2. ブラウザ

- **Chromium のみ**（家庭内 NAS 用途で複数ブラウザ検証の必要性低）
- バイナリは開発時 `npx playwright install chromium`、CI は Phase 4.6 で考慮

### 3. 環境

- **`docker compose up -d`** で api / ui / postgres を起動した状態で実行
- 認証は **`KAKEIBO_API_AUTH_BYPASS=1`** で無効化（`api/Ph3/01` の dev バイパス）
- 本番想定の Caddy 経路は **Phase 3 では検証しない**（Phase 4.6 リリース時に手動検証）

### 4. データ投入: `tests/e2e/fixtures/seed.py`

- pytest 系から既存の取込CLIを呼び出し、既知データを decisive に投入
- 各 spec の `beforeAll` で `python -m kakeibo_worker.ingest mufg tests/e2e/fixtures/mufg_known.csv` を実行
- DB 状態をリセットするクリーンアップは Playwright `globalTeardown` で `TRUNCATE` 実行

### 5. webServer 設定

`playwright.config.ts` で：
- `webServer.command`: `docker compose up -d`（CI/local 共通）
- `webServer.url`: `http://localhost:3000`（ui 直）または Caddy 経由 `https://localhost:8443`（自己署名で skipTLS）

開発時の簡易実行は `npm run dev`（ui 単独）も許容。

### 6. 主要 4 シナリオ

#### `balances.spec.ts`
- 残高ページに遷移 → 月次推移チャートが描画 → 期間フィルタ「直近6か月」に変更 → URL 更新確認

#### `categories.spec.ts`
- カテゴリページに遷移 → 月選択 → 親カテゴリクリックで子展開 → 子カテゴリ合計が親と一致

#### `portfolio.spec.ts`
- ポートフォリオページに遷移 → 円グラフ + スナップショット日付表示確認 → NULL 警告の有無

#### `rules.spec.ts`（最も複雑）
1. ルール一覧ページに遷移
2. 「新規作成」→ フォーム入力（`match_type=contains`, `pattern=コンビニ`）
3. dry-run プレビューで「N件マッチ」表示確認
4. 「保存」→ 一覧に表示
5. 「既存取引に適用？」モーダルで Yes
6. 一覧でドラッグ並び替え（最初のルールを最後へ）
7. ページリロード後も順序維持

### 7. CI 連携

- **本指示書では CI 設定までは扱わず、ローカル `make e2e` で完了**
- CI 連携は Phase 4.6 リリース時に再評価

## 依存パッケージ追加

`ui/package.json` dev:
- `@playwright/test@^1.45`

リポジトリルートに `playwright.config.ts` を置くため、`@playwright/test` は ui ディレクトリではなく **リポジトリルート** にも置きたいが、Phase 3 では UI と同居させて `ui/` から実行する形にして簡素化（ファイルパスは `tests/e2e/` 直下、設定は `ui/playwright.config.ts` に置くか root に置くかは Coder 判断、推奨はルート）。

**Planner 推奨**: `playwright.config.ts` をリポジトリルートに置き、`package.json`（`ui/package.json` と並列で root にも `package.json` を置くか、Makefile 経由で `ui/node_modules/.bin/playwright test` を呼ぶ）。本リポジトリにはルート `package.json` がない（`ui/package.json` のみ）ため、Makefile アプローチを採用：

```makefile
e2e:
    cd ui && npx playwright test --config=../playwright.config.ts
```

## 実装手順（TDD: e2e は実装と同時進行）

### 1. Red

- `playwright.config.ts` を最小実装し、`tests/e2e/balances.spec.ts` で `expect(page).toHaveTitle(/家計/)` のような単純テストを書く
- `npx playwright test` で **環境設定起因の失敗**を確認（webServer / DB seed が未実装で落ちる）

### 2. Green

1. `tests/e2e/fixtures/{mufg,smbc}_known.csv` を Phase 1.4 / 1.5 のゴールデンマスタから流用
2. `tests/e2e/fixtures/seed.py` で取込CLIを呼び出すヘルパ実装
3. `playwright.config.ts` で `webServer` + `globalSetup`（seed 実行）+ `globalTeardown`（TRUNCATE）を実装
4. 各 spec を順に実装（balances → categories → portfolio → rules の順）
5. `make e2e` で全件緑にする

### 3. Refactor

- 共通の Page Object（`tests/e2e/pages/{BalancesPage,CategoriesPage,...}.ts`）に抽出
- 認証バイパス設定を `tests/e2e/_setup/auth.ts` に集約

## 受入条件

原典 §3.3 完了条件 (d)：
- Playwright e2e で主要シナリオが緑

詳細：
- 主要 4 シナリオ（残高 / カテゴリ / ポートフォリオ / ルール）が緑
- 実行時間が **5 分以内**（`agent-rules/11-testing-strategy.md` §品質指標 統合 5 分以内に整合）
- 失敗時にスクリーンショット + trace が `tests/e2e/results/` に保存
- `make e2e` で全シナリオ実行可能

## 品質ゲート

```bash
docker compose up -d
make e2e
# または
cd ui && npx playwright test --config=../playwright.config.ts
docker compose down
```

## ブランチ・コミット規約

- ブランチ: `feature/playwright-e2e`
- コミット粒度（最低 5 件）：
  1. `テスト: Playwright設定とfixture投入スクリプトを追加`
  2. `テスト: 残高月次推移のe2eシナリオを追加`
  3. `テスト: カテゴリ別支出ドリルダウンのe2eシナリオを追加`
  4. `テスト: ポートフォリオ表示のe2eシナリオを追加`
  5. `テスト: ルール作成・dry-run・並び替えのe2eシナリオを追加`
  6. `設定: Makefile に e2e ターゲットを追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3 完了条件 (d) Playwright e2e を実装。

## 成果物
- playwright.config.ts
- tests/e2e/{balances,categories,portfolio,rules}.spec.ts
- tests/e2e/fixtures/{seed.py, mufg_known.csv, smbc_known.csv}
- Makefile（e2e ターゲット）

## 検証結果
- make e2e: 全件緑（X 分）
- 失敗時のスクショ・trace 保存確認

## Phase 3 完了状況
完了条件 (a) (b) (c) (d) (e) すべて達成。Phase 4 着手準備が整った。

## 次のアクション提案
docs/plans/{api,ui,worker}/Ph4/ 配下に Phase 4 タスク指示書を生成する。
```

## 注意事項

- **Playwright バイナリ**: `npx playwright install` を docker compose 内ではなくホスト側で実行。テストはホストの Chromium が `localhost:3000` を叩く構成（compose 内でブラウザを動かさない）。
- **`globalSetup` でのデータ投入**: 取込CLIが Phase 1.6 で実装される前提。未完了状態では本タスクは着手不可。
- **TRUNCATE タイミング**: `globalTeardown` で全 transactions / categories / rules を削除。本番 DB と混在しないようテスト用 DATABASE_URL を別途指定。
- **認証バイパス**: 本番ビルドで `KAKEIBO_API_AUTH_BYPASS=1` が誤って有効化されないことを `api/Ph3/01` 側で保証済。本タスクでは設定だけ参照。
- **flaky 対策**: `expect(...).toBeVisible({timeout: 5000})` のような明示タイムアウト + retry を入れる。Playwright の自動 retry は **無効化**（テスト failure を隠さない）。
- **CI 連携は Phase 4.6 で**: `agent-rules/50-production-reliability.md` 範囲外、Phase 3 完了スコープには含めない。
