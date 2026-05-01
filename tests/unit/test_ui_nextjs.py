"""UI コンテナ（Next.js）の構造検証テスト。

Phase 0 では、ui コンテナを nginx + 静的 HTML から Next.js 14+ の standalone
ビルドへ置換する。Issue #1（Phase 0）のチェックボックス 2.1 / 2.2 / 2.3 と
DoD2 / DoD5 を満たすため、リポジトリ上の静的構造（package.json・Dockerfile・
App Router レイアウト）を振る舞いベースで検証する。

設計準拠:
- 計画レポート §4.1 / §4.2 / §5.1（write_tests 仕様）
- 既存パターン: api/Dockerfile:14-73（builder→runtime / 非 root / urllib HEALTHCHECK）
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def test_ui_packagejsonがNextjsプロジェクトとして妥当(repo_root: Path) -> None:
    """``ui/package.json`` が Next.js プロジェクトの体裁を持つこと。

    - ``dependencies`` に ``next`` と ``react`` が宣言されている。
    - ``engines.node`` で Node.js 20 系以上を要求している
      （Issue 本文「UI: Next.js (Node.js 20 LTS)」要件）。
    """
    package_json_path = repo_root / "ui" / "package.json"
    assert package_json_path.exists(), "ui/package.json が存在しません"

    data = json.loads(package_json_path.read_text(encoding="utf-8"))

    deps = data.get("dependencies", {})
    assert "next" in deps, "dependencies に 'next' が宣言されていません"
    assert "react" in deps, "dependencies に 'react' が宣言されていません"

    engines = data.get("engines", {})
    node_version = str(engines.get("node", ""))
    # 例: ">=20", ">=20.0.0", "20.x" 等を許容する。
    assert re.search(r"(>=\s*20|\b20(\.|\b))", node_version), (
        f"engines.node は Node 20 LTS 以上を要求すること: {node_version!r}"
    )
    assert not re.search(r"<\s*20\b", node_version), (
        f"engines.node に Node 20 未満を許容する範囲は指定できません: {node_version!r}"
    )


def test_ui_appディレクトリにルートレイアウトとページが存在(repo_root: Path) -> None:
    """Next.js App Router の最小構成として ``src/app/layout.tsx`` と ``src/app/page.tsx``
    が存在し、空でないこと。

    ADR-014 によりサービス専有コードは ``ui/src/`` 配下に集約され、
    App Router は ``ui/src/app/`` を起点とする。Next.js は src/app と
    プロジェクトルート app の両方を自動検出するため設定変更は不要。

    Phase 0 はダッシュボードの placeholder 1 ページを返せれば DoD2 を満たす。
    """
    app_dir = repo_root / "ui" / "src" / "app"
    layout = app_dir / "layout.tsx"
    page = app_dir / "page.tsx"

    assert layout.exists(), f"{layout} が存在しません"
    assert page.exists(), f"{page} が存在しません"
    assert layout.stat().st_size > 0, f"{layout} が空です"
    assert page.stat().st_size > 0, f"{page} が空です"


def test_ui_dockerfileがマルチステージビルド構成(repo_root: Path) -> None:
    """``ui/Dockerfile`` が builder→runtime のマルチステージで、
    必要なディレクティブ（``EXPOSE 3000`` / ``HEALTHCHECK`` / ``USER``）を備えること。

    api/Dockerfile:14-73 の構造に揃えることで、運用上の認知負荷を下げる。
    """
    dockerfile_path = repo_root / "ui" / "Dockerfile"
    assert dockerfile_path.exists(), "ui/Dockerfile が存在しません"

    content = dockerfile_path.read_text(encoding="utf-8")

    # マルチステージ: builder と runtime（あるいは同等の最終ステージ）の 2 段が必須。
    # api/Dockerfile に倣い `AS builder` と `AS runtime` を要求する。
    assert re.search(r"FROM\s+\S+\s+AS\s+builder", content, re.IGNORECASE), (
        "ui/Dockerfile に builder ステージ（FROM ... AS builder）が必要です"
    )
    assert re.search(r"FROM\s+\S+\s+AS\s+runtime", content, re.IGNORECASE), (
        "ui/Dockerfile に runtime ステージ（FROM ... AS runtime）が必要です"
    )

    # コンテナポート: 3000 番（compose.yml と Caddyfile 両方の前提）。
    assert re.search(r"^\s*EXPOSE\s+3000\b", content, re.MULTILINE), (
        "ui/Dockerfile は EXPOSE 3000 を宣言する必要があります"
    )

    # HEALTHCHECK ディレクティブ（compose 側ではなく Dockerfile 側にも置く）。
    assert re.search(r"^\s*HEALTHCHECK\b", content, re.MULTILINE), (
        "ui/Dockerfile に HEALTHCHECK ディレクティブが必要です"
    )

    # 非 root 実行（agent-rules/70-docker-environments.md 必須要件）。
    assert re.search(r"^\s*USER\s+\S+", content, re.MULTILINE), (
        "ui/Dockerfile は USER ディレクティブで非 root 実行を指定する必要があります"
    )


def test_ui_dockerfileがnode20ベースイメージを使う(repo_root: Path) -> None:
    """``ui/Dockerfile`` が Node.js 20 LTS 系のベースイメージを使うこと。

    Issue 本文「UI: Next.js (Node.js 20 LTS)」要件。alpine / slim 等の
    タグ修飾は許容するが、メジャーバージョンは ``node:20`` で固定する。
    """
    dockerfile_path = repo_root / "ui" / "Dockerfile"
    assert dockerfile_path.exists(), "ui/Dockerfile が存在しません"

    content = dockerfile_path.read_text(encoding="utf-8")
    # 例: FROM node:20-alpine AS builder, FROM node:20.11-slim AS runtime
    assert re.search(r"FROM\s+node:20(\.|-|\s)", content), (
        "ui/Dockerfile は node:20 系のベースイメージを使う必要があります"
    )
