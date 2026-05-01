"""開発用 ``compose.override.yml`` の bind mount 検証テスト。

Issue #1 DoD5「ホスト側のコード変更がコンテナに反映」を満たすため、
開発時に api / worker のコンテナ ``/app/src`` および ``/app/shared`` に
ホスト側ソースツリーが bind mount されることを契約として固定する。

ADR-014 によりサービス専有コードは ``<service>/src`` 配下、共有コードは
``shared/`` 配下に分離されたため、それぞれを別マウントとして検証する。

設計準拠:
- 計画レポート §4.2 / §5.1（write_tests 仕様）
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


def test_compose_overrideがapiにsrcとsharedをbind_mount(repo_root: Path) -> None:
    """開発 override マージ後の ``api`` サービス定義に、host ``./api/src`` →
    コンテナ ``/app/src`` および host ``./shared`` → コンテナ ``/app/shared``
    の bind mount が両方存在すること。

    docker compose config の出力では bind mount が
    ``- /abs/path/to/api/src:/app/src`` あるいは ``type: bind`` 形式で展開される
    ため、いずれの表現でも検出できるよう ``/app/src`` と ``/app/shared``
    をマーカーに使う。
    """
    config_text = _compose_config(repo_root)
    api_block = extract_service_block(config_text, "api")
    assert api_block is not None, "merged compose 設定に api サービスが存在しません"

    assert "/app/src" in api_block, (
        "api サービスに /app/src への bind mount が必要です（dev での hot reload 用）"
    )
    assert "/app/shared" in api_block, (
        "api サービスに /app/shared への bind mount が必要です"
        "（ADR-014: 共有コードは shared/ をマウント）"
    )
    api_src_abs = str((repo_root / "api" / "src").resolve())
    shared_abs = str((repo_root / "shared").resolve())
    assert api_src_abs in api_block or "./api/src" in api_block, (
        f"api サービスの bind mount source は {api_src_abs} もしくは ./api/src である必要があります"
    )
    assert shared_abs in api_block or "./shared" in api_block, (
        f"api サービスの shared bind mount source は {shared_abs} もしくは ./shared である必要があります"
    )


def test_compose_overrideがworkerにsrcとsharedをbind_mount(repo_root: Path) -> None:
    """開発 override マージ後の ``worker`` サービス定義に、host ``./worker/src`` →
    コンテナ ``/app/src`` および host ``./shared`` → コンテナ ``/app/shared``
    の bind mount が両方存在すること。

    worker は ``profiles: [worker]`` を持つため、``--profile worker`` で
    activated 状態にしてから config を取得する。
    """
    config_text = _compose_config(repo_root, profiles=("worker",))
    worker_block = extract_service_block(config_text, "worker")
    assert worker_block is not None, "merged compose 設定に worker サービスが存在しません"

    assert "/app/src" in worker_block, (
        "worker サービスに /app/src への bind mount が必要です（dev での hot reload 用）"
    )
    assert "/app/shared" in worker_block, (
        "worker サービスに /app/shared への bind mount が必要です"
        "（ADR-014: 共有コードは shared/ をマウント）"
    )
    worker_src_abs = str((repo_root / "worker" / "src").resolve())
    shared_abs = str((repo_root / "shared").resolve())
    assert worker_src_abs in worker_block or "./worker/src" in worker_block, (
        f"worker サービスの bind mount source は {worker_src_abs} もしくは ./worker/src である必要があります"
    )
    assert shared_abs in worker_block or "./shared" in worker_block, (
        f"worker サービスの shared bind mount source は {shared_abs} もしくは ./shared である必要があります"
    )
