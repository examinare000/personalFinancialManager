---
adr: 015
title: Python ツールチェーン（uv / pyproject / lockfile）をコンテナ内に閉じ込める
status: 採用済み
date: 2026-05-01
author: 池田遼介
related:
  - ADR-009
  - ADR-014
extends:
  - ADR-014
---

# ADR-015: Python ツールチェーン（uv / pyproject / lockfile）をコンテナ内に閉じ込める

## ステータス
採用済み

## 背景

ADR-014 でコード・テスト・運用設定をサービス境界に分離したが、Python の依存マニフェスト（`pyproject.toml` / `uv.lock`）と uv ランタイムはまだリポジトリルートと開発者ホストに残っていた:

- ルート `pyproject.toml` に api / worker / shared 全パッケージを `[tool.hatch.build.targets.wheel].packages` でまとめ、ルート `uv.lock` 1 つで全依存をロックする方式
- 開発者は **ホスト OS に uv をインストール** し（`brew install uv` 等）、`uv sync` でルート `.venv` を生成して使う運用
- `Makefile` の `sync` `test` `lint` 等のターゲットは `uv run ...` をホストから直接呼ぶ

この構成は以下の摩擦を生んでいた:

- ホスト Python と Docker コンテナ Python のバージョン乖離（asdf / pyenv 経由の 3.10/3.11 系が混入する事故）
- 開発者ごとに uv のバージョンが揃わず、`uv.lock` の差分がレビューでノイズになる
- ADR-009 が定める「Docker Compose スタックですべて完結する運用」（→ ADR-014 が拡張した「サービス境界＝コンテナ境界」）に対して、Python ツールチェーンだけがホスト依存の例外として残る
- pyproject.toml がルートにあるため、サービスが Python を採用していること自体がディレクトリ最上位から見えてしまい、サービス内部の関心事が外部へ漏れる

ADR-014 で確立した「`<service>/{Dockerfile, src, tests, docs}` の自明な型」に Python ツールチェーンを整合させるため、本 ADR は uv の存在範囲をコンテナ内に閉じる。

## 検討した選択肢

### 選択肢A. 現状維持（ルート pyproject.toml + ホスト uv 実行）
- メリット: 既存の `Makefile` ターゲットが `uv run` で完結、IDE の Python 解釈もホスト venv で簡単
- デメリット: ホスト Python 依存・uv バージョン揺れ・サービス境界違反

### 選択肢B. 各 Python サービス配下に独立した pyproject.toml + uv.lock（採用候補だった案）
- 構造: `api/pyproject.toml` `api/uv.lock` と `worker/pyproject.toml` `worker/uv.lock` を別個に配置し、共有コードは path 依存で参照
- メリット: 形式上の独立性が最も高い
- デメリット: 共有依存（pydantic-settings / structlog / sqlalchemy 等）の重複宣言が常時発生し、版ずれリスクと PR レビューコストが増える。Phase 0 のコード規模ではオーバースペック

### 選択肢C. 単一 pyproject.toml + 単一 uv.lock を `shared/` に集約、各 Python コンテナの Dockerfile 内で uv を導入してビルド時 sync（採用）
- 構造: `shared/pyproject.toml` で全依存を `[project.optional-dependencies]` の extras（`api` / `worker` / `mail` / `pdf` / `llm` / `dev`）に分けて宣言。`shared/uv.lock` 1 本で全 extras をロック。各サービスの Dockerfile が `COPY --from=ghcr.io/astral-sh/uv:0.5 ...` で uv バイナリだけ取得し、`uv sync --frozen --extra <該当>` でサービスに必要な部分集合だけをインストール
- メリット:
  - 共有依存の宣言は 1 箇所（`shared/pyproject.toml`）で完結し、版ずれリスクが消える
  - uv のホストインストールが不要、開発者は Docker さえあればよい
  - ADR-014 の構造（shared/ は共有モジュール群）と整合：「依存マニフェストも shared が所有する共通資産」
  - サービス専有依存は extras（`api` / `worker` / `mail` 等）として明示的に分離され、PR で容易に追跡できる
- デメリット:
  - shared が「Python パッケージ」ではなくても pyproject.toml を持つ、という非典型な配置（`[tool.uv].package = false` で「仮想プロジェクト」として明示）
  - IDE での Python 解釈が docker compose 経由の遠隔 venv 参照になり、初回設定の手数が増える

## 決定

選択肢 C を採用する。

### shared/pyproject.toml の役割

- 名前: `kakeibo`（プロジェクト全体の依存マニフェストとしての名義）
- `[tool.uv].package = false` で「仮想プロジェクト」と宣言し、shared 自体をビルド可能パッケージにはしない
- 依存は以下の構造:

```
[project.dependencies]               # api / worker 双方が常に必要
  pydantic, pydantic-settings, structlog, sqlalchemy, psycopg, click, httpx

[project.optional-dependencies]
  api    = [flask, ...]              # api コンテナのみ
  worker = [alembic, ...]            # worker コンテナのみ
  mail   = [mail-parser, beautifulsoup4, lxml, ...]  # Phase 2 メール取込
  pdf    = [pypdf, ...]              # Phase 1 拡張 / Phase 4 PDF パース
  llm    = [anthropic, ...]          # Phase 4 LLM 分類
  dev    = [pytest, hypothesis, testcontainers, ruff, pyright, ...]
```

### shared/kakeibo_shared/ の配信方法

shared 自体は **Python パッケージではなく素のモジュール群**（ADR-014 Q1=案B）。各コンテナで以下のように配信する:

- Dockerfile が `COPY shared /app/shared` で `/app/shared/kakeibo_shared/` 配下にモジュールを配置
- `ENV PYTHONPATH="/app/shared:/app/src"` でモジュール解決パスに加える
- サービス専有コード（`kakeibo_api` / `kakeibo_worker`）は同様に `/app/src/<package>/` で配置し PYTHONPATH に含める

### 各 Dockerfile の規約

```Dockerfile
# uv バイナリのみ取得（ホスト uv 不要）
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# 依存解決のキャッシュ層: pyproject + lock のみ COPY
COPY shared/pyproject.toml shared/uv.lock /app/shared/
WORKDIR /app/shared
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra <api|worker> [...]

# ソース配信: shared モジュールとサービス専有 src を別レイヤで COPY
COPY shared/kakeibo_shared /app/shared/kakeibo_shared
COPY <service>/src /app/src
ENV PYTHONPATH="/app/shared:/app/src"
```

`uv.lock` 生成・更新もコンテナ内で行う:

```sh
docker run --rm -v "$(pwd)/shared:/app/shared" -w /app/shared \
  ghcr.io/astral-sh/uv:python3.12-bookworm-slim \
  uv lock
```

### tests の所在

ADR-014 で示した「`<service>/tests/` のサービス専有テスト」を本 ADR で具体化する:

- `worker/tests/` — `kakeibo_shared` / `kakeibo_worker` / alembic env を import するテスト群（worker は dev extras を持つため pytest 実行基盤として機能）
- `api/tests/` — `kakeibo_api` （Flask アプリ）固有のテスト
- `tests/`（ルート残置）— `kakeibo_*` を import せずファイル構造のみ検証する横断テスト（compose / gitignore / README / docs / ui 構造）。実行は `worker` コンテナで `pytest tests/ worker/tests/` として一括起動する

### 開発者ワークフロー（ホスト無 Python）

- `make test` → `docker compose run --rm worker pytest tests/ worker/tests/`
- `make api-test` → `docker compose run --rm api pytest tests/ api/tests/`
- `make lint` / `make typecheck` → `docker compose run --rm worker ruff check .` / `pyright`
- `make lock` → 上記 `docker run ... uv lock` を Makefile 経由で叩く
- ホスト側に必要なのは Docker Engine と GNU Make のみ（uv / Python は不要）

## 理由

- shared/ に pyproject + lock を集約することで、版ずれを構造的に予防しつつ、サービス境界（ADR-014）も維持できる
- 「shared は Python の意味でのパッケージではない」という事実を `[tool.uv].package = false` で明示し、PYTHONPATH 配信という単純な仕組みに合わせる
- uv の存在範囲をコンテナ内に閉じることで ADR-009 の「Docker Compose スタックで完結する運用」を Python レイヤまで拡張する
- 開発者の初期セットアップ（asdf / pyenv / uv の手動インストール）が消え、Docker さえあれば Phase 0 が再現できる
- CI も同じ `docker compose run --rm worker pytest ...` を呼ぶだけになり、ホスト・CI・本番の Python 実行環境が完全に同一化する

## 結果

- ルート `pyproject.toml` / `uv.lock` / `.python-version` / `.venv/` を削除する
- `Makefile` のターゲットはすべて `docker compose run --rm <service>` 経由に書き換える
- `tests/test_environment.py` 内の root pyproject 検証テストは `shared/pyproject.toml` を見るよう更新する
- `tests/test_environment.py` の Python import 系テスト（`kakeibo_shared` `kakeibo_api` `kakeibo_worker`）は所属サービスの `tests/` へ分割移動する
- compose.override.yml の `./shared:/app/shared:ro` マウントは維持（dev 時の hot reload）。ただし image にも shared/ を COPY 済みのため、本番（override 不適用）でも自己完結する
- pyright / ruff の解釈ルートは `shared/pyproject.toml` 1 本に集約。IDE 連携で Python 解釈がうまく動かないケースは、コンテナ内 venv を IDE が参照する設定（VS Code の Dev Containers 等）の導入を別途検討する余地として残す
- 将来 api / worker 間で依存差分が顕著に拡大した場合（例: api が機械学習ライブラリ、worker が独自バイナリ依存を持つ等）、選択肢 B（per-service pyproject）への移行を新 ADR で起票する
