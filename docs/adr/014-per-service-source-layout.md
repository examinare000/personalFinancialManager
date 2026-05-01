---
adr: 014
title: コード・テスト・運用設定もサービス境界へ完全分離する
status: 採用済み
date: 2026-05-01
author: 池田遼介
related:
  - ADR-007
  - ADR-009
  - ADR-013
supersedes: []
extends:
  - ADR-013
---

# ADR-014: コード・テスト・運用設定もサービス境界へ完全分離する

## ステータス
採用済み

## 背景

ADR-013 で設計・計画ドキュメントをサービス境界に同梱する方針を確定した。Phase 1 着手準備としてコードベースを点検したところ、以下の不一致が残っていた。

- `src/kakeibo/` 単一パッケージに api / worker のエントリ、共通設定、共通 DB セッション、ドメイン型、取込アダプタ、取込ユースケースが同居している（ADR-007 で定めた worker 専有のはずの `adapters/` `ingest/` も `src/kakeibo/` 配下に置かれている）
- `tests/` がリポジトリルートにあり、サービス横断テストとサービス専有テストが同居
- `alembic/` `alembic.ini` `sql/queries/` が postgres スキーマに属する資産でありながらルートに置かれている
- `Caddyfile` `caddy_data/` `caddy_config/` がルートに散在し、サービスとしての所有が不明瞭
- `pyproject.toml` がルート1枚で全コンポーネントの依存を抱えている（pdf/mail/llm extras による分離はあるが、サービス単位ではない）
- ルート直下にトップレベル名前空間（`api/` `worker/` `ui/` `postgres/`）と非サービス資産（`alembic/` `tests/` `src/` `sql/`）が混在し、ディレクトリ一覧から「このプロジェクトは何個のサービスで構成されるか」が一読で分からない

ADR-013 はドキュメントのみを境界に揃えたが、コードと運用設定はルート集約のままだった。Phase 1 でコード本体の実装が始まると、`src/kakeibo/` 配下に worker 専有・api 専有のコードがさらに積み上がり、後からの分離コストは指数的に増える。Phase 0（コード実体がスタブのみ ≒ 500 行）の今が、構造を整える最後のタイミングである。

## 検討した選択肢

### 選択肢A. ADR-013 維持（docs のみ分離、コードは `src/kakeibo/` 単一）
- メリット: 現状のまま。Python 単一パッケージの import が短い
- デメリット: サービス間の責務境界がコードに反映されず、Phase 1 以降に分離コストが急増する。コンテナ単位での独立開発（CI/CD 分離・依存差替え）が困難

### 選択肢B. コードもサービス境界に分離、共有モジュールはルート `shared/` に集約しコンテナへランタイムマウント（採用）
- メリット: ディレクトリ最上位がサービス一覧そのものになる。各サービスは `<service>/{Dockerfile, src, tests, docs}` の自明な型を持つ。共有コード（設定・ロギング・DB セッション・ドメイン型）は `shared/` 1 箇所に集約され、複数サービスから読まれる現実を構造で表現できる
- デメリット: 「完全独立」の語感に反して `shared/` を介した結合が残る。compose で `shared/` を両コンテナにマウントする規約と、Dockerfile での COPY 規約の二重管理が必要

### 選択肢C. 共有コードを各サービスへ複製（真の独立、shared なし）
- メリット: コンテナ間の依存ゼロ。任意のサービスを単独で別レポへ切り出せる
- デメリット: ドメイン型・設定スキーマが構造的に乖離しうる。同じバグ修正を複数箇所に反映する運用負荷。Phase 0 の時点ではコードの大半が共有部分（config / logging / db / domain）であり、複製は実害が大きい

### 選択肢D. uv workspace + サービスごと独立 pyproject
- メリット: 依存解決をサービス単位に閉じられる
- デメリット: Phase 0 で導入するには道具立てが過剰。ロックファイルの整合運用も別途必要。本 ADR の範囲ではなく、必要時に別 ADR で起票する余地として残す

## 決定

選択肢 B を採用する。リポジトリ最終形を以下とする。

```
.
├── compose.yml / compose.override.yml      # サービス横断の合成記述のみ
├── pyproject.toml / uv.lock / Makefile     # 当面はルート1枚で運用（Dへの拡張余地）
├── README.md / CLAUDE.md / AGENT.md / GEMINI.md
├── agent-rules/                             # 全エージェント横断ルール
├── secrets/ data/ archive/ inbox/ dead_letter/ backup/   # 実行時マウント先（ホスト資産）
├── shared/                                  # ★ 複数サービスから読まれる共有コード
│   └── kakeibo_shared/{config, logging, db, domain}
├── docs/
│   ├── adr/                                  # 全 ADR
│   ├── design/                               # 横断設計のみ（00, 04, 05）
│   └── plans/
│       ├── 00-initial-design.md / 01-development-plan.md
│       └── 1N-phaseN-service-assignments.md  # サービス振り分け索引
│
├── postgres/
│   ├── Dockerfile                            # 必要時のみ（基本は postgres:16-alpine）
│   ├── src/{alembic, alembic.ini, sql}       # ★ マイグレーション・SQL の本籍
│   ├── tests/                                # 冪等性・スキーマ契約テスト
│   └── docs/{design, plans/Ph1..Ph3}
│
├── worker/
│   ├── Dockerfile
│   ├── src/kakeibo_worker/{main, ingest, adapters, reconciler, ...}
│   ├── tests/
│   └── docs/{design, plans/Ph1..Ph3}
│
├── api/
│   ├── Dockerfile
│   ├── src/kakeibo_api/{app, __main__, ...}
│   ├── tests/
│   └── docs/{design, plans/Ph2..Ph3}
│
├── ui/
│   ├── Dockerfile / package.json / next.config.mjs / tsconfig.json
│   ├── src/app/...                           # Next.js App Router 配下を src/ に内包
│   ├── tests/
│   └── docs/{design, plans/Ph3..Ph4}
│
└── caddy/
    ├── Caddyfile                             # リバースプロキシ設定
    ├── data/ config/                         # 永続ボリューム
    └── docs/                                 # 必要に応じて
```

### 共有コード運用規約（選択肢 B 補足）

- 物理位置: ルート `shared/kakeibo_shared/`
- ビルド: 各サービスの `Dockerfile` は build context から `shared/` を COPY して image に焼き込む（本番での自己完結を保証）
- 開発時: `compose.yml` で `./shared:/app/shared:ro` を api / worker の双方にマウントし、ホットリロードと開発／本番の構成乖離防止を両立する
- import 規約: 各サービスは `from kakeibo_shared.config import Settings` のように共有名前空間を参照する。サービス専有コードは `kakeibo_api` / `kakeibo_worker` 名前空間で完結させる
- 依存方向: `shared` → どのサービスにも依存しない。`api` `worker` → `shared` に依存可。サービス間の直接 import は禁止（DB 経由 or HTTP 経由のみ）

### alembic / SQL の所属（ADR-013 の補強）

- マイグレーション資産は postgres スキーマの所有物として `postgres/src/{alembic, alembic.ini, sql}` に置く
- 実行は Python ランタイムを持つコンテナ（worker または専用 init コンテナ）が `postgres/src/alembic` を read-only マウントして `alembic upgrade head` を呼ぶ
- スキーマ契約は postgres が保有し、worker は実行責務のみを持つ

### Caddy の所属

- `caddy/Caddyfile` `caddy/data/` `caddy/config/` をサービス配下に集約する
- `compose.yml` から `./caddy/Caddyfile` `./caddy/data` `./caddy/config` を参照する

### Phase 1 計画文書の所属

- 横断（Phase 全体俯瞰、サービス振り分け索引）はルート `docs/plans/` 残留: `00`, `01`, `10`, `11`, `12`, `13`
- サービス専有 Phase 1 タスク文書は所属サービスへ移動:
  - `02-phase1-db-schema-and-migrations` → postgres
  - `03-phase1-domain-types` → postgres（型はスキーマ契約と一体）
  - `04-phase1-ingest-adapter-base` → worker
  - `05-phase1-mufg-csv-adapter` → worker
  - `06-phase1-smbc-csv-adapter` → worker
  - `07-phase1-ingest-cli` → worker
  - `08-phase1-hash-idempotency-tests` → worker
  - `09-phase1-monthly-summary-sql` → postgres

## 理由

- ディレクトリ最上位がサービスと一致することで、新規参加者・新規エージェントは「このプロジェクトは postgres / worker / api / ui / caddy で構成される」を一目で把握できる
- ADR-007 で確定した「アダプタは worker 専有」が物理配置で表現される。`src/kakeibo/adapters/` がルートに見えていた現状の不整合が解消される
- Phase 0 のコード実体は約 500 行のスタブのみであり、移動コストが最小。Phase 1 着手後にこの再編をやると import パス・テスト・Dockerfile・compose・docs の同時改訂が肥大化する
- `shared/` をランタイムマウントで両コンテナに供給する形は、現行の `compose.override.yml` で行っている `./src` バインドマウントの自然な拡張であり、開発フローの破壊が小さい
- alembic を postgres 配下に置くことは「スキーマ所有はデータベースサービス」という直感に一致し、Phase 2 以降にスキーマ周辺のオペレーション資産（ER 図、移行手順書）が増えても所属が揺らがない
- Caddy をサービス化することで「ルート直下にあるものはサービス合成記述・サービス横断ドキュメント・実行時マウント先のみ」というルートの責務が単純化する

## 結果

- 物理移動と同時に発生する変更:
  - `compose.yml`: `<service>/Dockerfile` のビルドコンテキストはルート維持（`shared/` を COPY するため）。`./shared:/app/shared:ro` を api / worker に追加。`./caddy/Caddyfile` 等を caddy サービスに反映。worker に `./postgres/src/alembic:/app/alembic:ro` を追加
  - `pyproject.toml`: `[tool.hatch.build.targets.wheel].packages` を `["shared/kakeibo_shared", "api/src/kakeibo_api", "worker/src/kakeibo_worker"]` に更新。`[tool.ruff].src` `[tool.pyright].include` も同様
  - `alembic.ini`: `script_location` を新パスに更新。env.py の sys.path も更新
  - `tests/`: 横断テスト（compose / docs 構造検証）はルート `tests/` 残留可。サービス専有テストは `<service>/tests/` 配下へ漸次移動
  - `agent-rules/`: 既存ルールはレイアウト言及がないため改訂不要。`30-documentation-management.md` のディレクトリ図に shared/ を追記する余地は次の改訂で対応
- 本 ADR は ADR-013 を上書きせず**拡張**する。ADR-013 はドキュメント分離の決定として有効、本 ADR はコード・運用設定への分離拡張として独立した決定
- per-service `pyproject.toml` 化（選択肢 D）は、Phase 2 以降に依存差分が広がった時点で別 ADR を起票して再検討する
- `shared/` が肥大化（10 ファイル超 / 200 行超のモジュールが複数）した場合は、共有という抽象が破綻している兆候として、shared を更に分割するか各サービスへ複製するかを別 ADR で判断する
