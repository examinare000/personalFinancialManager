---
title: api/Ph3/03 ルール dry-run エンドポイント
service: api
phase_task_id: 3.6-aux
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.6（行 367-377）
branch: feature/api-rule-dry-run
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# api/Ph3/03 ルール dry-run エンドポイント（Phase 3.6 補助）

## このファイルの位置付け

原典 §4.3 Phase 3.6 の **API 側補助タスク**。受入基準 (c)「既存取引へのプレビュー（このルールならN件マッチ）が表示される」を実現するための `POST /api/rules/dry-run` エンドポイントと、Categorizer の Rule マッチロジックを実装する。リスク R-09（ReDoS）対応も本タスクの範囲。

## 担当サービス

`compose.yml` `api` サービス。`api/Ph3/01` のルール CRUD を拡張する形で dry-run を追加し、`design/03-categorization-engine.md` の Rule マッチロジックを `api/src/kakeibo_api/categorizer/` 配下に実装ファイル化する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `api/Ph3/01`（Rule CRUD と認証）+ Phase 1 の `transactions` 投入 |
| 下流 | `ui/Ph3/05`（ルール編集UI のプレビュー機能） |

`api/Ph3/02` と並列着手可能。

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.6（行 367-377）
2. **ADR**: `docs/adr/008-three-tier-categorization.md`
3. **分類エンジン設計**: `worker/docs/design/03-categorization-engine.md` §3
4. **Phase 1.7 ハッシュ境界条件**: `worker/Ph1/06-hash-idempotency-tests.md`（description 正規化方針）
5. **リスク**: `docs/plans/01-development-plan.md` §9 R-09（ReDoS）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `api/src/kakeibo_api/categorizer/__init__.py` | 新規パッケージ |
| `api/src/kakeibo_api/categorizer/rules.py` | `match_rule(rule, transaction) -> bool` の実装 |
| `api/src/kakeibo_api/categorizer/safe_regex.py` | regex タイムアウト保護 |
| `api/src/kakeibo_api/blueprints/rules.py` | 既存に `POST /api/rules/dry-run` を追加 |
| `api/src/kakeibo_api/schemas/rule.py` | `DryRunRequest`, `DryRunResponse` を追加（既存に追記） |
| `shared/kakeibo_shared/db/repositories/rules.py` | 既存に `match_transactions(...)` を追加 |
| `api/tests/unit/categorizer/__init__.py` | 新規 |
| `api/tests/unit/categorizer/test_rules.py` | match_type 別の単体テスト（regex / contains / exact） |
| `api/tests/unit/categorizer/test_safe_regex.py` | ReDoS パターンでのタイムアウト検証 |
| `api/tests/unit/test_rule_dry_run.py` | エンドポイント契約 + 件数算出 |

## 実装方針

### 1. ReDoS 対策: SIGALRM タイムアウト + パターン長制限

- **`re2` 採用しない**：Python バインディング（`google-re2`）はビルド負荷が NAS 上で重い、メンテナンス活発さも限定的
- 代わりに **`signal.SIGALRM` ベースのタイムアウト 500ms** + **パターン長 500 文字制限** で防御
- パターン長超過は 422 で即時拒否
- SIGALRM はメインスレッドからの呼び出しが必要だが、Flask + Werkzeug 単一スレッド構成では問題なし（`gevent`/`gunicorn worker_class` を使う場合は別途 ADR で再評価）

### 2. dry-run リクエスト/レスポンス

```
POST /api/rules/dry-run
Content-Type: application/json

{
  "match_field": "description",   # 現状 description のみ、将来 amount / source も
  "match_type": "regex",          # regex | contains | exact
  "pattern": "コンビニ"
}

→ 200 OK
{
  "matched_count": 12,
  "sample": [
    {"transaction_id": 123, "description": "コンビニATM 引出", "occurred_on": "2026-04-15"},
    ... (最大10件)
  ]
}
```

### 3. マッチ対象の絞り込み

- `category_source IN ('rule', NULL)` のみ対象（`design/03-categorization-engine.md` §6 と整合：`manual` / `llm` を上書きしない）
- 現行 `category_id IS NULL` の取引も含む（未分類のうちこのルールでマッチするものをプレビュー）

### 4. 本番 INSERT を伴わない（dry-run）

- DB 書き込みなし（読み取り専用）
- 認証は通常通り必須（ルール構造を漏らさない）

### 5. Phase 4 への布石

- `match_rule()` の API は Phase 4.1 LLM 分類サービス、Phase 4.2 半自動学習でも再利用される設計
- 純粋関数（副作用なし）で実装し、テスト容易性を最優先

## 実装手順（TDD）

### 1. Red

- `api/tests/unit/categorizer/test_safe_regex.py`：
  - `test_safe_regex_match_normal_pattern_succeeds()`
  - `test_safe_regex_redos_pattern_times_out()`：`(a+)+$` + 30 文字超の `a` 列で `TimeoutError`、テスト全体は 1 秒以内に完了
  - `test_safe_regex_pattern_length_exceeded()`：500 文字超で `ValueError`
- `api/tests/unit/categorizer/test_rules.py`：
  - `test_match_type_regex_matches_pattern()`
  - `test_match_type_contains_substring()`
  - `test_match_type_exact_full_match()`
  - `test_match_type_invalid_raises_value_error()`
- `api/tests/unit/test_rule_dry_run.py`：
  - `test_dry_run_returns_zero_for_no_match_pattern()`
  - `test_dry_run_returns_sample_with_at_most_10_transactions()`
  - `test_dry_run_rejects_invalid_match_type()`（422）
  - `test_dry_run_redos_pattern_times_out_safely()`（API が 1 秒以内に 422 で応答）
  - `test_dry_run_pattern_too_long_returns_422()`
  - `test_dry_run_excludes_manual_categorized_transactions()`
  - `test_dry_run_requires_auth()`

### 2. Green

1. `api/src/kakeibo_api/categorizer/safe_regex.py` を実装：
   ```python
   def safe_regex_match(pattern: str, text: str, *, timeout_ms: int = 500) -> bool:
       if len(pattern) > 500:
           raise ValueError("pattern too long")
       def handler(signum, frame):
           raise TimeoutError("regex timeout")
       signal.signal(signal.SIGALRM, handler)
       signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000)
       try:
           return bool(re.search(pattern, text))
       finally:
           signal.setitimer(signal.ITIMER_REAL, 0)
   ```
2. `api/src/kakeibo_api/categorizer/rules.py` で `match_rule(rule, transaction) -> bool` を実装
3. `shared/kakeibo_shared/db/repositories/rules.py` に `match_transactions(conn, *, match_field, match_type, pattern, limit=10)` を追加
4. `api/src/kakeibo_api/schemas/rule.py` に `DryRunRequest`, `DryRunResponse` を追加
5. `api/src/kakeibo_api/blueprints/rules.py` に `POST /api/rules/dry-run` を追加

### 3. Refactor

- `safe_regex.py` のタイムアウトロジックを context manager `_alarm_timeout(ms)` に抽出
- `rules.py` の match_type ディスパッチを辞書ベースに（早すぎる抽象化は避ける、3 種なら if/elif でも可）

## 受入条件

原典 §4.3 Phase 3.6 受入基準のうち API 側に関するもの：

- バックエンドの dry-run エンドポイントを利用して **既存取引へのプレビュー（N件マッチ）** が取得できる
- regex / contains / exact のいずれかの match_type に対応

加えて：
- ReDoS パターンで API がハングしない（pytest で 1 秒以内に 422 が返る）
- パターン長 500 文字超は 422
- dry-run の集計結果と、実ルール保存後のマッチング結果が一致（`match_rule` が両方で使われる）
- 認可なしで 401（dry-run も書き込みは無いがルール構造を漏らさない）
- OpenAPI スキーマに dry-run エンドポイントが反映される
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
docker compose run --rm worker pytest api/tests/unit/categorizer/ api/tests/unit/test_rule_dry_run.py
docker compose run --rm worker ruff check api/ shared/
docker compose run --rm worker pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/api-rule-dry-run`
- コミット粒度（最低 4 件）：
  1. `テスト: ルールdry-run・マッチング・ReDoS耐性のテストを先行作成`
  2. `機能: 正規表現のタイムアウト保護helperを実装`
  3. `機能: design/03準拠のRuleマッチロジックを実装`
  4. `機能: POST /api/rules/dry-runエンドポイントとリポジトリ拡張を追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.6 ルール dry-run エンドポイントとCategorizerコアを実装。

## 成果物
- api/src/kakeibo_api/categorizer/{__init__,rules,safe_regex}.py
- api/src/kakeibo_api/blueprints/rules.py（dry-run 追加）
- api/src/kakeibo_api/schemas/rule.py（DryRunRequest/Response 追加）
- shared/kakeibo_shared/db/repositories/rules.py（match_transactions 追加）
- api/tests/unit/categorizer/* / api/tests/unit/test_rule_dry_run.py

## 検証結果
- pytest 全件緑（< 1 秒で完了、ReDoS テスト含む）
- pyright / ruff: クリーン

## 既知の課題・申し送り
- gevent / gunicorn worker_class 採用時は SIGALRM が機能しない可能性あり、ADR で再評価。
- match_field は description のみ。amount / source 等は Phase 4 で拡張可能。

## 次のアクション提案
ui/Ph3/05 (ルール編集UI) の dry-run プレビュー機能で本エンドポイントを使用。
```

## 注意事項

- **`signal.SIGALRM` は Unix 専用**。本プロジェクトは Linux コンテナ前提（Phase 0 の Dockerfile）のため許容、Windows 開発時の動作は保証しない。
- **`re.search` のタイムアウト解像度** は OS の `setitimer` 解像度に依存（通常 10ms 単位）、500ms タイムアウトの実測ばらつきは許容。
- **マルチスレッド/マルチプロセス Flask** に変更する場合は `signal` ではなく `multiprocessing.Process` ベースの隔離タイムアウトに変更が必要。Phase 3 の Werkzeug 単一スレッド前提で本実装は妥当、設定変更時は再評価。
- **パターン長 500 文字** は経験的閾値。運用で短すぎ / 長すぎが顕在化したら ADR で再評価。
- **`description` 正規化との整合**: `worker/Ph1/06`（ハッシュ境界条件 PBT）で確定された description 正規化方針（前後空白を strip しない）と本タスクの match ロジックが整合していること。
- **Phase 4.2 半自動学習** で本ロジックを再利用するため、`match_rule(rule, transaction) -> bool` のシグネチャを安易に変えない。
