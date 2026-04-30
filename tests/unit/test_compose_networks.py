"""``compose.yml`` のネットワーク分離契約テスト。

Issue #1 のチェックボックス 5.2b に対応。
docs/design/04-deployment-stack.md §3 のネットワーク分離方針が実構成と
整合することを ``docker compose config`` 出力で検証する。

分離方針:
- postgres / backup: internal のみ（外部到達不可）
- ui / caddy: external のみ（DB 直結なし）
- api / worker: internal + external 両方（DB 接続 + 外部 API 利用）

設計準拠:
- 計画レポート §4.5 / §5.1（write_tests 仕様）
- architect-review.md（ARCH-NEW-test_environment-bloat の責務分離）
- ``tests/_compose_utils.py:extract_service_block`` を流用
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from tests._compose_utils import extract_service_block


def test_compose設定でnetwork分離が正しい(repo_root: Path) -> None:
    """compose 構成のネットワーク分離が design/04-deployment-stack.md §3 と整合すること。"""
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

    postgres_block = extract_service_block(config_text, "postgres")
    assert postgres_block is not None, "postgres サービスが見つかりません"
    assert "internal" in postgres_block, "postgres は internal ネットワークに所属する必要があります"
    assert "external" not in postgres_block, (
        "postgres は external ネットワークに所属してはいけません"
    )

    ui_block = extract_service_block(config_text, "ui")
    assert ui_block is not None, "ui サービスが見つかりません"
    assert "external" in ui_block, "ui は external ネットワークに所属する必要があります"
    assert "internal" not in ui_block, (
        "ui は internal ネットワークに所属してはいけません（DB 直結禁止）"
    )

    for svc in ("api", "worker"):
        block = extract_service_block(config_text, svc)
        assert block is not None, f"{svc} サービスが見つかりません"
        assert "internal" in block, f"{svc} は internal ネットワークに所属する必要があります"
        assert "external" in block, f"{svc} は external ネットワークに所属する必要があります"
