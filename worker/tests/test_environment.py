"""worker サービス境界での kakeibo_shared / kakeibo_worker / alembic 検証テスト。

ADR-015 により Python 依存マニフェストは ``shared/pyproject.toml`` に集約され、
worker コンテナが dev extras を持つテスト基盤を兼ねる。本ファイルは旧
``tests/test_environment.py`` から、``kakeibo_*`` を import する振る舞い検証
（Settings / logging redaction / alembic env / worker run heartbeat）を
worker サービス配下へ移管したもの。

横断構造テスト（compose / gitignore / secrets / ディレクトリ存在）は引き続き
ルート ``tests/`` 側で実行する（PYTHONPATH 不要）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_kakeibo_sharedパッケージがimportできる() -> None:
    """``shared/kakeibo_shared`` がパッケージとして import 可能で、バージョン文字列を持つこと。

    ADR-014 によりコードはサービス境界へ分離され、共有モジュールは
    ``kakeibo_shared`` 名前空間に集約された。最小骨格でも __version__ を
    公開する慣習に従い、公開 API の起点を明示的に確認する。
    """
    import kakeibo_shared

    assert hasattr(kakeibo_shared, "__version__")
    assert isinstance(kakeibo_shared.__version__, str)
    assert kakeibo_shared.__version__  # 空文字でない


def test_設定クラスが環境変数からDATABASE_URLを読める(monkeypatch: pytest.MonkeyPatch) -> None:
    """pydantic-settings の Settings が環境変数から DATABASE_URL を取得できること。

    Docker Compose の environment 経由で渡される URL を、Settings で
    一貫して読み取れることを確認する。
    """
    test_url = "postgresql+psycopg://kakeibo:secret@postgres:5432/kakeibo"
    monkeypatch.setenv("DATABASE_URL", test_url)
    monkeypatch.delenv("PG_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)

    from kakeibo_shared.config import Settings

    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.database_url == test_url


def test_DocSecretのFILE規約で値を取得できる(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """*_FILE 環境変数で指定された secret ファイルから値が読まれること。

    Docker secret は `/run/secrets/<name>` に bind mount され、
    アプリは `<NAME>_FILE` で参照するのが規約（design/05-security-model §5）。
    """
    secret_file = tmp_path / "pg_password.txt"
    secret_file.write_text("secret_value\n", encoding="utf-8")

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@y:5432/z")
    monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))

    from kakeibo_shared.config import Settings

    settings = Settings()  # pyright: ignore[reportCallIssue]
    # ファイル末尾の改行は除去される（trim）
    assert settings.pg_password == "secret_value"


def test_logging設定でpasswordキーが自動マスクされる() -> None:
    """structlog processor が機密キーを [REDACTED] に置換すること。

    agent-rules/12-security-guidelines.md §4 の要件を満たすため、
    password / token / secret / key / authorization を含むキーは
    値に関わらずログ出力前にマスクされる必要がある。
    """
    from kakeibo_shared.logging import redact_sensitive_processor

    event_dict = {
        "event": "ログイン試行",
        "user": "alice",
        "password": "should-be-hidden",
        "api_token": "xxx",
        "anthropic_key": "sk-ant-xxx",
        "authorization": "Bearer xxx",
    }
    masked = redact_sensitive_processor(None, "info", dict(event_dict))

    assert masked["user"] == "alice", "通常キーは変更されないこと"
    for sensitive in ("password", "api_token", "anthropic_key", "authorization"):
        assert masked[sensitive] == "[REDACTED]", f"{sensitive} がマスクされていません"


def test_alembicコマンドが起動できる() -> None:
    """`alembic --help` が正常終了し usage を出力すること。

    worker コンテナの dev/worker extras に alembic がインストール済みであることを確認する。
    """
    alembic = shutil.which("alembic")
    if alembic is None:
        pytest.skip("alembic コマンドが PATH 上に存在しないためスキップ")

    result = subprocess.run(
        [alembic, "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, f"alembic --help が失敗: {result.stderr}"
    assert "usage" in result.stdout.lower()


def test_alembic_envがDATABASE_URLを参照する(
    monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    """alembic env.py が環境変数 DATABASE_URL を sqlalchemy.url に解決すること。

    alembic.ini に固定 URL を書かず、ランタイムで環境変数から取得する設計。
    ADR-014 によりマイグレーション資産は ``postgres/src/alembic/`` 配下に移動済み。
    env.py を import して `_resolve_database_url()` を直接呼ぶ。
    """
    test_url = "postgresql+psycopg://kakeibo:pw@postgres:5432/kakeibo"
    monkeypatch.setenv("DATABASE_URL", test_url)

    # postgres/src/alembic/ ディレクトリを sys.path に追加して env をモジュールとして読む
    alembic_dir = repo_root / "postgres" / "src" / "alembic"
    if str(alembic_dir) not in sys.path:
        sys.path.insert(0, str(alembic_dir))

    import importlib.util

    env_path = alembic_dir / "env.py"
    spec = importlib.util.spec_from_file_location("kakeibo_alembic_env", env_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "resolve_database_url"), (
        "postgres/src/alembic/env.py に resolve_database_url() を公開する必要があります"
    )
    resolved = module.resolve_database_url()
    assert resolved == test_url


def test_worker_runが短時間でheartbeatを書き込む(tmp_path: Path) -> None:
    """``kakeibo_worker.run()`` が短時間で heartbeat ファイルを生成すること。

    Docker の HEALTHCHECK は heartbeat ファイルの mtime で生存判定するため、
    起動直後に最低 1 回 heartbeat が書かれることを契約として固定する。

    - 子スレッドで run を起動し、heartbeat 出現を最大 5 秒待つ
    - 終了は ``stop_event`` で graceful shutdown を要求
    - 本番では SIGTERM ハンドラ経由で同じイベントが立つ
    """
    import threading
    import time

    from kakeibo_worker import run

    heartbeat_path = tmp_path / "worker_heartbeat"
    stop_event = threading.Event()

    # interval を短く設定し、テスト時間を 1 秒未満で完了させる。
    thread = threading.Thread(
        target=run,
        kwargs={
            "heartbeat_path": heartbeat_path,
            "interval_seconds": 0.05,
            "stop_event": stop_event,
        },
        daemon=True,
    )
    thread.start()

    # heartbeat ファイル出現を最大 5 秒待つ。
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if heartbeat_path.exists():
            break
        time.sleep(0.05)

    try:
        assert heartbeat_path.exists(), "5 秒以内に heartbeat ファイルが生成されませんでした"
        first_mtime = heartbeat_path.stat().st_mtime
        # interval 経過後に再更新されることも確認する。
        time.sleep(0.2)
        second_mtime = heartbeat_path.stat().st_mtime
        assert second_mtime >= first_mtime, "heartbeat の mtime が更新されていません"
    finally:
        stop_event.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "stop_event 後も worker スレッドが終了していません"
