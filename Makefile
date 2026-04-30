# 開発タスク用 Makefile。
# 主要操作を 1 行で実行可能にする。CI / Docker 内でも同じターゲットを呼ぶ。

.DEFAULT_GOAL := help
SHELL := /bin/bash

# 既定で uv 経由ですべてのツールを実行する（仮想環境の有無に依存しない）。
UV ?= uv

.PHONY: help
help:  ## 利用可能なターゲット一覧を表示する
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: sync
sync:  ## uv で依存をインストールする（dev extras 含む）
	$(UV) sync --extra dev

.PHONY: sync-all
sync-all:  ## 全 extras（dev / pdf / mail / llm）を含めて依存をインストールする
	$(UV) sync --extra dev --extra pdf --extra mail --extra llm

.PHONY: lock
lock:  ## uv.lock を最新化する
	$(UV) lock

.PHONY: test
test:  ## pytest を実行する
	$(UV) run pytest

.PHONY: test-env
test-env:  ## 開発環境ブートストラップテストのみ実行する
	$(UV) run pytest tests/test_environment.py -v

.PHONY: lint
lint:  ## ruff で lint チェックする
	$(UV) run ruff check .

.PHONY: format
format:  ## ruff で整形する
	$(UV) run ruff format .

.PHONY: format-check
format-check:  ## ruff の整形差分が無いかチェックする
	$(UV) run ruff format --check .

.PHONY: typecheck
typecheck:  ## pyright で型チェックする
	$(UV) run pyright

.PHONY: check
check: lint format-check typecheck test  ## lint / format / typecheck / test を一気に実行する

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

.PHONY: clean
clean:  ## キャッシュを削除する
	rm -rf .pytest_cache .ruff_cache .pyright .mypy_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
