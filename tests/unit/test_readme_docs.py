"""``README.md`` の運用手順記載検証テスト。

Issue #1 のチェックボックス 1.3 / 5.1 に対応:
- 1.3 secrets 4 種実体化手順 + ``chmod 600``
- 5.1 ``alembic upgrade head`` の DB 初期化手順

設計準拠:
- 計画レポート §4.3 / §5.1（write_tests 仕様）
- architect-review.md（ARCH-NEW-test_environment-bloat の責務分離）
"""

from __future__ import annotations

from pathlib import Path


def test_readmeにsecret実体化手順が4種類すべて記載されている(repo_root: Path) -> None:
    """``README.md`` に Docker secrets 4 種類すべての ``cp <example> <実体>``
    手順と ``chmod 600`` 行が記載されていること。

    pg_password / anthropic_key / paypal_api_secret / gmail_oauth_token の
    4 種類すべてについて、``*.example`` から実体への複製コマンドが必要。
    """
    readme_path = repo_root / "README.md"
    assert readme_path.exists(), "README.md が存在しません"

    content = readme_path.read_text(encoding="utf-8")
    required_cp_patterns = [
        "cp secrets/pg_password.txt.example",
        "cp secrets/anthropic_key.txt.example",
        "cp secrets/paypal_api_secret.txt.example",
        "cp secrets/gmail_oauth_token.json.example",
    ]
    for pattern in required_cp_patterns:
        assert pattern in content, (
            f"README.md に secret 実体化手順 '{pattern}' が記載されていません"
        )

    # 権限を 600 に絞る運用が design/05-security-model §5.1 で必須。
    assert "chmod 600" in content, (
        "README.md に secret ファイルの 'chmod 600' 手順が記載されていません"
    )


def test_readmeにalembic_upgrade_head手順が記載されている(repo_root: Path) -> None:
    """``README.md`` に ``alembic upgrade head`` 手順が記載されていること。

    Phase 0 では初期マイグレーション SQL は未作成（Phase 1.1 範囲）の
    ため、運用手順として README に記載することで「手順確立」を満たす。
    """
    readme_path = repo_root / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    assert "alembic upgrade head" in content, (
        "README.md に 'alembic upgrade head' の DB 初期化手順が記載されていません"
    )
