# 開発タスク用 Makefile（ADR-015）。
# すべての Python ツール（uv / pytest / ruff / pyright）はホストではなく
# Docker コンテナ内で実行する。ホスト要件は Docker Engine と GNU Make のみ。

.DEFAULT_GOAL := help
SHELL := /bin/bash

# uv 公式イメージ（python 3.12 入り）。`make lock` で uv.lock 生成に使う。
UV_IMAGE ?= ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# テスト・lint・typecheck の実行コンテナ（dev extras を持つ worker）。
DEV_SVC ?= worker

.PHONY: help
help:  ## 利用可能なターゲット一覧を表示する
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ─────────── 依存・ロック ───────────
.PHONY: lock
lock:  ## shared/uv.lock を最新化する（ホスト uv 不要、コンテナで実行）
	docker run --rm -v "$(CURDIR)/shared:/work" -w /work $(UV_IMAGE) uv lock

.PHONY: build
build:  ## 全 Python コンテナイメージを再ビルド（依存変更時）
	docker compose build api worker

# ─────────── テスト ───────────
.PHONY: test
test:  ## pytest を worker コンテナで実行する（横断＋全サービスのテスト）
	docker compose run --rm $(DEV_SVC) pytest

.PHONY: test-shared
test-shared:  ## kakeibo_shared / Settings / logging のテストのみ
	docker compose run --rm $(DEV_SVC) pytest ../worker/tests/test_environment.py ../worker/tests/unit/

.PHONY: test-api
test-api:  ## api サービスのテストのみ
	docker compose run --rm $(DEV_SVC) pytest ../api/tests/

.PHONY: test-worker
test-worker:  ## worker サービスのテストのみ
	docker compose run --rm $(DEV_SVC) pytest ../worker/tests/

.PHONY: test-structure
test-structure:  ## ルート横断構造テストのみ（compose / docs / 構造）
	docker compose run --rm $(DEV_SVC) pytest ../tests/

# ─────────── 品質ゲート ───────────
.PHONY: lint
lint:  ## ruff で lint チェック（worker コンテナ）
	docker compose run --rm $(DEV_SVC) ruff check .

.PHONY: format
format:  ## ruff で整形（worker コンテナ）
	docker compose run --rm $(DEV_SVC) ruff format .

.PHONY: format-check
format-check:  ## ruff の整形差分チェック（worker コンテナ）
	docker compose run --rm $(DEV_SVC) ruff format --check .

.PHONY: typecheck
typecheck:  ## pyright で型チェック（worker コンテナ）
	docker compose run --rm $(DEV_SVC) pyright

.PHONY: check
check: lint format-check typecheck test  ## lint / format / typecheck / test を一括実行

# ─────────── compose 操作 ───────────
.PHONY: compose-config
compose-config:  ## docker compose 構成の妥当性を検証する
	docker compose -f compose.yml config

.PHONY: up
up:  ## 開発用に Docker Compose を起動する（compose.override.yml 込み）
	docker compose up -d

.PHONY: down
down:  ## Docker Compose を停止する
	docker compose down

.PHONY: health
health:  ## Docker Compose 全コンテナの healthy 状態を確認する
	docker compose ps

# ─────────── 後処理 ───────────
.PHONY: clean
clean:  ## ビルドキャッシュを削除する
	rm -rf .pytest_cache .ruff_cache .pyright .mypy_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
