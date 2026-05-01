"""リポジトリ全体の構造（コードを import せず観測可能なもの）の検証テスト。

agent-rules/00-core-principles.md の TDD 原則に従い、Phase 0 の開発環境
整備で「インフラとして整っているべきもの」を振る舞いベースで検証する。

ADR-015 により Python 依存マニフェストは ``shared/pyproject.toml`` に集約され、
``kakeibo_*`` パッケージを import する振る舞い検証は所属サービスの
``<service>/tests/`` へ移管された。本ファイルは Python パッケージを import
せずに済む構造テスト（pyproject 妥当性 / compose 構文 / secrets 雛形 /
必須ディレクトリ / .gitignore / subagent 定義）に限定する。
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests._compose_utils import extract_service_block as _extract_service_block


def test_shared_pyprojectが妥当なTOMLでパースできる(repo_root: Path) -> None:
    """shared/pyproject.toml が TOML として解釈でき、必須メタデータが揃うこと。

    ADR-015 により Python 依存マニフェストは shared/ に集約された。
    name は kakeibo、Python 要件は 3.12 以上、``[tool.uv].package = false``
    で仮想プロジェクト宣言されていることを契約として固定する。
    """
    pyproject_path = repo_root / "shared" / "pyproject.toml"
    assert pyproject_path.exists(), "shared/pyproject.toml が存在しません"

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    assert "project" in data, "[project] セクションが存在しません"
    project = data["project"]
    assert project.get("name") == "kakeibo", (
        f"shared/pyproject.toml の project.name は 'kakeibo' を要求します: {project.get('name')!r}"
    )
    requires_python = project.get("requires-python", "")
    assert ">=3.12" in requires_python, (
        f"requires-python は >=3.12 を含む必要があります: {requires_python!r}"
    )

    # ADR-015 §決定 の「shared 自体は Python パッケージではない」契約。
    tool_uv = data.get("tool", {}).get("uv", {})
    assert tool_uv.get("package") is False, (
        "shared/pyproject.toml は ``[tool.uv].package = false`` で"
        "仮想プロジェクトを宣言する必要があります（ADR-015）"
    )


def test_root_pyprojectが存在しない(repo_root: Path) -> None:
    """ADR-015 によりルートの pyproject.toml / uv.lock は廃止されている。

    ホストに uv を導入させない方針のため、ルートに pyproject が残っていると
    `uv sync` を誤ってホストで実行してしまう事故が起きうる。これを防ぐ
    契約として、ルート pyproject.toml と uv.lock の不在を固定する。
    """
    forbidden = [
        repo_root / "pyproject.toml",
        repo_root / "uv.lock",
    ]
    for path in forbidden:
        assert not path.exists(), (
            f"{path.name} がルートに残存しています（ADR-015 違反）。"
            f"shared/ 配下へ集約してください"
        )


def test_compose設定が構文的に妥当(repo_root: Path) -> None:
    """`docker compose -f compose.yml config` が成功すること。

    Docker daemon が稼働していなくても compose ファイルの構文検証は可能。
    docker CLI 自体が無い環境では skip する。
    """
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI が利用不可のためスキップ")

    compose_path = repo_root / "compose.yml"
    assert compose_path.exists(), "compose.yml が存在しません"

    result = subprocess.run(
        [docker, "compose", "-f", str(compose_path), "config"],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
        timeout=30,
    )
    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        if "cannot connect" in stderr_lower or "daemon" in stderr_lower:
            pytest.skip(f"Docker daemon が利用不可のためスキップ: {result.stderr}")
        pytest.fail(f"compose config が失敗: {result.stderr}")


def test_必須シークレットExampleファイルが存在する(repo_root: Path) -> None:
    """secrets/*.example が4種類すべて揃っていること。

    実体ファイルは git 追跡対象外だが、example だけは雛形として共有する。
    design/05-security-model §5.1 の要件。
    """
    secrets_dir = repo_root / "secrets"
    expected = [
        "pg_password.txt.example",
        "anthropic_key.txt.example",
        "gmail_oauth_token.json.example",
        "paypal_api_secret.txt.example",
    ]
    for name in expected:
        path = secrets_dir / name
        assert path.exists(), f"{path} が存在しません"
        # example でもサイズが 0 だと運用上ヒントにならないため、最低限の中身を要求
        assert path.stat().st_size > 0, f"{path} が空です（雛形には説明を入れること）"


def test_必須ディレクトリが存在する(repo_root: Path) -> None:
    """取込パイプラインが想定する作業ディレクトリが揃っていること。

    Docker volume の host 側マウントポイントになる。.gitkeep でディレクトリ
    自体は git 追跡し、中身は gitignore する。
    """
    expected_dirs = [
        "inbox",
        "archive",
        "dead_letter",
        "backup",
        "data",
        "postgres/src/alembic/versions",
    ]
    for rel in expected_dirs:
        path = repo_root / rel
        assert path.is_dir(), f"{path} が存在しません"


def test_gitignoreがsecretsとenvを除外する(repo_root: Path) -> None:
    """.gitignore に必須エントリが含まれること。

    シークレット漏洩防止のため、secrets/*.txt と *.env と data/ と inbox/**
    は必ず除外する。secrets/*.example は例外として追跡する。
    """
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    required_lines = [
        "secrets/*.txt",
        "secrets/*.json",
        "*.env",
        "data/",
        "inbox/",
        "!secrets/*.example",
    ]
    for line in required_lines:
        assert line in gitignore, f".gitignore に '{line}' が含まれていません"


def test_compose設定にuiサービスが含まれる(repo_root: Path) -> None:
    """`docker compose -f compose.yml config` の出力に ui サービスが含まれ、
    networks に external が含まれること。

    docs/design/04-deployment-stack.md §3 の構成（ui は external のみ）に整合。
    """
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI が利用不可のためスキップ")

    result = subprocess.run(
        [docker, "compose", "-f", str(repo_root / "compose.yml"), "config"],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
        timeout=30,
    )
    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        if "cannot connect" in stderr_lower or "daemon" in stderr_lower:
            pytest.skip(f"Docker daemon が利用不可のためスキップ: {result.stderr}")
        pytest.fail(f"compose config が失敗: {result.stderr}")

    config_text = result.stdout
    ui_block = _extract_service_block(config_text, "ui")
    assert ui_block is not None, "compose 設定に ui サービスが含まれていません"
    assert "external" in ui_block, "ui サービスは external ネットワークに所属する必要があります"


def test_compose設定の主要サービスにhealthcheckが定義されている(repo_root: Path) -> None:
    """postgres / api / worker / ui / caddy の各サービスに healthcheck が定義されていること。

    `docker compose up -d` で全コンテナの起動完了を確実に検知するため、
    Phase 0 の段階で healthcheck を必須化する。backup は sleep ループの常駐
    プロセスで判定が冗長になるため任意。
    """
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI が利用不可のためスキップ")

    result = subprocess.run(
        [docker, "compose", "-f", str(repo_root / "compose.yml"), "config"],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
        timeout=30,
    )
    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        if "cannot connect" in stderr_lower or "daemon" in stderr_lower:
            pytest.skip(f"Docker daemon が利用不可のためスキップ: {result.stderr}")
        pytest.fail(f"compose config が失敗: {result.stderr}")

    config_text = result.stdout
    required_services = ["postgres", "api", "worker", "ui", "caddy"]
    for service in required_services:
        block = _extract_service_block(config_text, service)
        assert block is not None, f"compose 設定に {service} サービスが見つかりません"
        assert "healthcheck:" in block, f"{service} サービスに healthcheck が定義されていません"


def test_subagent定義ファイルが揃っている(repo_root: Path) -> None:
    """.claude/agents 配下に4ロール分の定義ファイルが揃い、frontmatter が妥当なこと。

    agent-rules/91-claude-subagent-coding.md §サブエージェント定義ファイル の要件。
    YAML frontmatter（name / description / tools）が必須。
    """
    agents_dir = repo_root / ".claude" / "agents"
    expected = ["planner.md", "coder.md", "reviewer.md", "git-composer.md"]
    for name in expected:
        path = agents_dir / name
        assert path.exists(), f"{path} が存在しません"
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n"), (
            f"{path} は YAML frontmatter で開始する必要があります"
        )
        for required_key in ("name:", "description:", "tools:"):
            assert required_key in content, (
                f"{path} の frontmatter に '{required_key}' が必要です"
            )
