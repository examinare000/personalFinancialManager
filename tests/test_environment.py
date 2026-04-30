"""開発環境ブートストラップの検証テスト。

agent-rules/00-core-principles.md の TDD 原則に従い、
Phase 0 の開発環境整備で「インフラとして整っているべきもの」を
振る舞いベースで検証する。各テストは独立して実行可能で、
詳細な実装は問わず、外部から観測可能な性質のみを確認する。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests._compose_utils import extract_service_block as _extract_service_block

# テスト #2 / #3 で kakeibo パッケージを動的に import するため、
# src レイアウトを sys.path に追加する。プロジェクト同梱テストでは
# 一般的な手法（pip install -e なしでも動く）。
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def test_pyprojectが妥当なTOMLでパースできる(repo_root: Path) -> None:
    """pyproject.toml が TOML として解釈でき、必須メタデータが揃うこと。

    name は kakeibo、Python 要件は 3.12 以上を指定していることを確認する。
    requirements.txt を採用しないため、依存関係は本ファイルが正本となる。
    """
    pyproject_path = repo_root / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml が存在しません"

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    assert "project" in data, "[project] セクションが存在しません"
    project = data["project"]
    assert project.get("name") == "kakeibo"
    requires_python = project.get("requires-python", "")
    assert ">=3.12" in requires_python, (
        f"requires-python は >=3.12 を含む必要があります: {requires_python!r}"
    )


def test_kakeiboパッケージがimportできる() -> None:
    """src/kakeibo がパッケージとして import 可能で、バージョン文字列を持つこと。

    最小骨格でも __version__ を公開する慣習に従い、公開 API の起点を
    明示的に確認する。
    """
    import kakeibo

    assert hasattr(kakeibo, "__version__")
    assert isinstance(kakeibo.__version__, str)
    assert kakeibo.__version__  # 空文字でない


def test_設定クラスが環境変数からDATABASE_URLを読める(monkeypatch: pytest.MonkeyPatch) -> None:
    """pydantic-settings の Settings が環境変数から DATABASE_URL を取得できること。

    Docker Compose の environment 経由で渡される URL を、Settings で
    一貫して読み取れることを確認する。
    """
    test_url = "postgresql://kakeibo:secret@postgres:5432/kakeibo"
    monkeypatch.setenv("DATABASE_URL", test_url)
    # 他の必須項目を仮で埋める（Docker secret 経由の値は本テストでは未検証）
    monkeypatch.delenv("PG_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)

    from kakeibo.config import Settings

    # pydantic-settings は環境変数からフィールドを充填するため、
    # 引数なし生成は意図された使い方だが pyright は Field(...) を必須と判断する。
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

    monkeypatch.setenv("DATABASE_URL", "postgresql://x@y:5432/z")
    monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))

    from kakeibo.config import Settings

    settings = Settings()  # pyright: ignore[reportCallIssue]
    # ファイル末尾の改行は除去される（trim）
    assert settings.pg_password == "secret_value"


def test_logging設定でpasswordキーが自動マスクされる() -> None:
    """structlog processor が機密キーを [REDACTED] に置換すること。

    agent-rules/12-security-guidelines.md §4 の要件を満たすため、
    password / token / secret / key / authorization を含むキーは
    値に関わらずログ出力前にマスクされる必要がある。
    """
    from kakeibo.logging import redact_sensitive_processor

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

    依存パッケージとして alembic がインストール済みであることを確認する。
    uv の仮想環境がアクティブであるか、`uv run` 経由で実行されることを想定。
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
    """alembic/env.py が環境変数 DATABASE_URL を sqlalchemy.url に解決すること。

    alembic.ini に固定 URL を書かず、ランタイムで環境変数から取得する設計。
    env.py を import して `_resolve_database_url()` を直接呼ぶ。
    """
    test_url = "postgresql://kakeibo:pw@postgres:5432/kakeibo"
    monkeypatch.setenv("DATABASE_URL", test_url)

    # alembic/ ディレクトリを sys.path に追加して env をモジュールとして読む
    alembic_dir = repo_root / "alembic"
    if str(alembic_dir) not in sys.path:
        sys.path.insert(0, str(alembic_dir))

    # env.py を import するとオフラインモードの判定で副作用が走るため、
    # ヘルパ関数のみを切り出して評価する設計とする。
    import importlib.util

    env_path = alembic_dir / "env.py"
    spec = importlib.util.spec_from_file_location("kakeibo_alembic_env", env_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "resolve_database_url"), (
        "alembic/env.py に resolve_database_url() を公開する必要があります"
    )
    resolved = module.resolve_database_url()
    assert resolved == test_url


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

    # secret ファイルが実体として存在しないと config が失敗するので、
    # *.example をコピーした一時ファイルを Compose の secrets が参照できるよう
    # 環境変数で差し替える発想もあるが、ここでは config コマンドが
    # secret ファイルの実在を要求しない（参照のみで OK）ことを利用する。
    result = subprocess.run(
        [docker, "compose", "-f", str(compose_path), "config"],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
        timeout=30,
    )
    if result.returncode != 0:
        # Docker daemon 未起動などの環境要因はスキップ扱いに分岐する
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
        "alembic/versions",
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


def test_api_create_appが200でhealthを返す() -> None:
    """``kakeibo.api.create_app()`` が Flask アプリを返し、``GET /health`` が
    ``{"status": "ok"}`` を 200 で応答すること。

    ヘルスチェックは Docker / Caddy / 監視系すべての疎通基盤になるため、
    レスポンス形式（status キーが ok）と HTTP ステータス（200）を契約として
    固定する。互換性破壊が発生したらここで早期検出する。
    """
    from kakeibo.api import create_app

    app = create_app()
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.is_json, "ヘルスチェックは JSON を返すこと"
    payload = response.get_json()
    assert payload == {"status": "ok"}


def test_worker_runが短時間でheartbeatを書き込む(tmp_path: Path) -> None:
    """``kakeibo.worker.run()`` が短時間で heartbeat ファイルを生成すること。

    Docker の HEALTHCHECK は heartbeat ファイルの mtime で生存判定するため、
    起動直後に最低 1 回 heartbeat が書かれることを契約として固定する。

    - 子スレッドで run を起動し、heartbeat 出現を最大 5 秒待つ
    - 終了は ``stop_event`` で graceful shutdown を要求
    - 本番では SIGTERM ハンドラ経由で同じイベントが立つ
    """
    import threading

    from kakeibo.worker import run

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

    # 最大 5 秒だけ heartbeat の出現を待つ（CI の貧弱な環境を考慮）。
    deadline = 5.0
    waited = 0.0
    step = 0.05
    while waited < deadline and not heartbeat_path.exists():
        import time as _time

        _time.sleep(step)
        waited += step

    stop_event.set()
    thread.join(timeout=2.0)

    assert heartbeat_path.exists(), "heartbeat ファイルが生成されていません"
    assert heartbeat_path.stat().st_size >= 0  # 0 バイトでも touch されていれば OK


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

    # PyYAML を使わず軽量な正規表現でサービス境界を抜き出す（依存追加を避ける）。
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
        assert content.startswith("---\n"), f"{name} が YAML frontmatter で始まっていません"
        # 簡易パース: 2 つ目の '---' までを frontmatter とする
        end = content.find("\n---", 4)
        assert end != -1, f"{name} の frontmatter 終端 '---' が見つかりません"
        frontmatter = content[4:end]
        for key in ("name:", "description:", "tools:"):
            assert key in frontmatter, f"{name} の frontmatter に '{key}' がありません"
