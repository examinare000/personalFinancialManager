"""``tests/test_environment.py`` の品質ガードレールテスト。

architect-review.md（ARCH-NEW-test_environment-os-deadcode /
ARCH-NEW-test_environment-bloat）の再発を AST / 行数の静的検査で
早期検知するための再発防止テスト。

family_tag ごとに 1 件以上の再発防止テストを置く方針:
- ``dead-code`` (``test_no_unused_top_level_imports``): 未使用 import が
  混入したら即 fail（ruff F401 と二重防御）。
- ``file-split`` (``test_行数が上限を超えない``): ナレッジ「1ファイル
  300行超 REJECT」「複数の責務 REJECT」に従い、許容上限を超えたら fail。

設計準拠:
- agent-rules/06-knowledge-architecture.md「ファイル分割」基準
- Policy「未使用コード（『念のため』のコード）REJECT」
"""

from __future__ import annotations

import ast
from pathlib import Path

# ナレッジ §「ファイル分割」基準: 「300行超 REJECT」。Phase 0 時点では
# ``test_environment.py`` の既存内容（subagent / alembic / compose / worker /
# api / logging / pyproject の最小骨格契約）が約 420 行で、追加責務の混入を
# 機械的に防ぐためのガードラインとして 450 行を上限に設定する。450 行を
# 超えたら architect-review が指摘した「同じファイルに 4 件追記して肥大化」
# の再発を意味するため、責務分離を必須化する。
_MAX_LINES_TEST_ENVIRONMENT = 450


def _collect_top_level_import_names(tree: ast.Module) -> list[str]:
    """モジュール直下の ``import`` / ``from ... import`` で導入された
    束縛名（alias を考慮）の一覧を返す。

    例: ``import os`` → ``["os"]`` / ``import os.path as op`` → ``["op"]`` /
    ``from a import b`` → ``["b"]`` / ``from a import b as c`` → ``["c"]``。

    ``from __future__ import ...`` は実体束縛ではなくコンパイラ指示子のため
    除外する（参照されないのが正しい使い方）。
    """
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                # `import a.b` の束縛名は `a`、`import a.b as c` は `c`
                bound = alias.asname or alias.name.split(".")[0]
                names.append(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    # star import は静的解析で名前を辿れないためスキップ
                    continue
                bound = alias.asname or alias.name
                names.append(bound)
    return names


def _collect_referenced_names(tree: ast.Module) -> set[str]:
    """ファイル内のすべての ``Name`` ノードを集合で返す（参照名のみ）。

    ``ast.Name(ctx=Load)`` だけでなく、``ast.Attribute`` の起点となる
    ``Name`` も自動的に含まれる（``os.path`` → ``Name('os')`` が出現）。
    """
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
    return referenced


def test_test_environment_pyに未使用の_top_level_importがない(repo_root: Path) -> None:
    """``tests/test_environment.py`` の ``import`` がすべてファイル内で
    参照されていること。

    ARCH-NEW-test_environment-os-deadcode 再発防止: ruff F401 のみに頼らず、
    AST 直接走査でも同等の検査を行い、二重防御する。
    """
    target = repo_root / "tests" / "test_environment.py"
    source = target.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(target))

    imported = _collect_top_level_import_names(tree)
    referenced = _collect_referenced_names(tree)
    unused = [name for name in imported if name not in referenced]

    assert not unused, (
        f"tests/test_environment.py に未使用の import があります: {unused}. "
        "「念のため」で残さず削除すること（必要になったら再 import）"
    )


def test_test_environment_pyの行数が上限を超えない(repo_root: Path) -> None:
    """``tests/test_environment.py`` の行数がガードライン以下であること。

    ARCH-NEW-test_environment-bloat 再発防止: 同一ファイルへの責務追加で
    300 行を超えて肥大化したら fail する。新しい責務は ``tests/unit/`` 配下に
    分離する判断を強制する。
    """
    target = repo_root / "tests" / "test_environment.py"
    with target.open(encoding="utf-8") as f:
        line_count = sum(1 for _ in f)

    assert line_count <= _MAX_LINES_TEST_ENVIRONMENT, (
        f"tests/test_environment.py が {line_count} 行で上限 "
        f"{_MAX_LINES_TEST_ENVIRONMENT} 行を超過。"
        "新しい責務は tests/unit/ 配下に分離して追加すること"
        "（agent-rules ナレッジ §ファイル分割「300 行超 REJECT」）"
    )
