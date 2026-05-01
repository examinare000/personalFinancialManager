"""開発用 ``compose.override.yml`` の bind mount 検証テスト。

Issue #1 DoD5「ホスト側のコード変更がコンテナに反映」を満たすため、
開発時に api / worker のコンテナにリポジトリ全体が ``/workspace`` として
bind mount されることを契約として固定する。

ADR-015 によりホストには uv / Python を置かず、テスト・lint・typecheck は
すべてコンテナ内で行うため、ホスト編集の即時反映と、コンテナ内テスト走行
（pytest が ``shared/pyproject.toml`` の testpaths から横断的にテスト群を
収集できる）の両方を ``./:/workspace`` マウントで成立させる。

設計準拠:
- ADR-015 §開発者ワークフロー
- 既存パターン: tests/test_environment.py の `extract_service_block` を再利用
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from tests._compose_utils import extract_service_block


def _compose_config(
    repo_root: Path,
    *,
    profiles: tuple[str, ...] = (),
) -> str:
    """``docker compose -f compose.yml -f compose.override.yml config`` を実行し、
    標準出力を返す。

    docker CLI 不在 / docker daemon 未起動はスキップ扱いに分岐する。
    profile 起動が必要なサービスは ``profiles`` 引数で活性化する。
    """
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI が利用不可のためスキップ")

    cmd: list[str] = [docker, "compose"]
    for profile in profiles:
        cmd.extend(["--profile", profile])
    cmd.extend(
        [
            "-f",
            str(repo_root / "compose.yml"),
            "-f",
            str(repo_root / "compose.override.yml"),
            "config",
        ]
    )

    result = subprocess.run(
        cmd,
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
    return result.stdout


def test_compose_overrideがapiにworkspaceマウントとPYTHONPATH切替を持つ(
    repo_root: Path,
) -> None:
    """開発 override マージ後の ``api`` サービス定義が、host リポジトリ全体を
    コンテナ ``/workspace`` に bind mount し、PYTHONPATH を /workspace 配下に
    切り替えていること。

    docker compose config の出力では bind mount は
    ``- /abs/path/to/repo:/workspace`` あるいは ``type: bind`` の long-form
    で展開される。``/workspace`` をマーカーに使い、いずれの表現でも検出できる。
    """
    config_text = _compose_config(repo_root)
    api_block = extract_service_block(config_text, "api")
    assert api_block is not None, "merged compose 設定に api サービスが存在しません"

    assert "/workspace" in api_block, (
        "api サービスに /workspace への bind mount が必要です（ADR-015: 全リポジトリマウント）"
    )
    repo_abs = str(repo_root.resolve())
    assert repo_abs in api_block or "source: ." in api_block or "- ." in api_block, (
        f"api サービスの bind mount source は {repo_abs} （リポジトリルート）である必要があります"
    )
    # PYTHONPATH が /workspace/shared と /workspace/api/src を含むこと。
    assert "/workspace/shared" in api_block, (
        "api サービスの PYTHONPATH に /workspace/shared が必要です（ADR-015）"
    )
    assert "/workspace/api/src" in api_block, (
        "api サービスの PYTHONPATH に /workspace/api/src が必要です（ADR-015）"
    )


def test_compose_overrideがworkerにworkspaceマウントとPYTHONPATH切替を持つ(
    repo_root: Path,
) -> None:
    """開発 override マージ後の ``worker`` サービス定義が、host リポジトリ全体を
    コンテナ ``/workspace`` に bind mount し、PYTHONPATH を /workspace 配下に
    切り替えていること。

    worker は dev/test 基盤も兼ねるため、PYTHONPATH には api/src も含めて
    クロスサービステストを許可する（ADR-015）。

    worker は ``profiles: [worker]`` を持つため、``--profile worker`` で
    activated 状態にしてから config を取得する。
    """
    config_text = _compose_config(repo_root, profiles=("worker",))
    worker_block = extract_service_block(config_text, "worker")
    assert worker_block is not None, "merged compose 設定に worker サービスが存在しません"

    assert "/workspace" in worker_block, (
        "worker サービスに /workspace への bind mount が必要です（ADR-015: 全リポジトリマウント）"
    )
    repo_abs = str(repo_root.resolve())
    assert repo_abs in worker_block or "source: ." in worker_block or "- ." in worker_block, (
        f"worker サービスの bind mount source は {repo_abs} （リポジトリルート）である必要があります"
    )
    # PYTHONPATH が shared / worker/src / api/src を含むこと（横断テストのため）。
    for required_path in (
        "/workspace/shared",
        "/workspace/worker/src",
        "/workspace/api/src",
    ):
        assert required_path in worker_block, (
            f"worker サービスの PYTHONPATH に {required_path} が必要です（ADR-015）"
        )

    # pytest が shared/pyproject.toml を起点に動作するため、working_dir が
    # /workspace/shared に設定されていること。
    assert "/workspace/shared" in worker_block, (
        "worker サービスの working_dir が /workspace/shared であること（ADR-015）"
    )
