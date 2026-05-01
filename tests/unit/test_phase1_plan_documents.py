"""Phase1 タスクプラン文書群の構造検証テスト（ADR-014 後の per-service レイアウト）。

ADR-013 と ADR-014 により、サービス専有のタスクプランは
``<service>/docs/plans/PhN/`` に同梱される構造となった。本テストは:

1. 連番 02〜09 の Phase1 タスクプランファイル 8 本が **per-service** な
   位置（postgres / worker のいずれか）に存在する
2. 横断俯瞰インデックスが ``docs/plans/10-*.md`` に 1 本だけ存在する
3. Phase 別サービス振り分け文書 (11/12/13) がルート ``docs/plans/`` に
   1 本ずつ存在する
4. 各タスクプランファイルが必須 10 セクションと原典ブランチ名を保持する
5. 俯瞰インデックスがすべてのタスクプランファイルを参照する
6. 依存タスク参照がプランファイル名形式（``NN-...md``）に統一されている

設計準拠:
- ADR-013 / ADR-014（サービス境界へのプラン配置）
- 計画レポート §2 / §6（連番割当・タスク要素）
- ``docs/plans/01-development-plan.md`` §6（ブランチ名の正本）
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

# ADR-014 に基づき、各タスクの新所属サービスを宣言する。
# (連番プレフィックス, 原典タスクID, 原典ブランチ名, 所属サービス)
PHASE1_TASK_SPEC: list[tuple[str, str, str, str]] = [
    ("02", "1.1", "feature/db-schema-initial",       "postgres"),
    ("03", "1.2", "feature/domain-types",            "postgres"),
    ("04", "1.3", "feature/ingest-adapter-base",     "worker"),
    ("05", "1.4", "feature/adapter-mufg-csv",        "worker"),
    ("06", "1.5", "feature/adapter-smbc-csv",        "worker"),
    ("07", "1.6", "feature/ingest-cli",              "worker"),
    ("08", "1.7", "feature/hash-idempotency-tests",  "worker"),
    ("09", "1.8", "feature/monthly-summary-sql",     "postgres"),
]

# 各プランファイルに必須の 10 セクション。
# 値は「いずれかの組み合わせがいずれかの見出し行に含まれていればOK」という
# 代替指定リスト。
REQUIRED_PLAN_SECTIONS: list[tuple[str, list[tuple[str, ...]]]] = [
    ("タスク概要", [("タスク概要",)]),
    ("目的・背景", [("目的", "背景")]),
    ("スコープ", [("スコープ",)]),
    ("依存タスク", [("依存タスク",)]),
    ("後続タスク", [("後続タスク",)]),
    ("対象ファイル/モジュール", [("対象ファイル",), ("対象モジュール",)]),
    ("実装方針", [("実装方針",)]),
    ("受入条件", [("受入条件",), ("Acceptance Criteria",)]),
    ("テスト計画", [("テスト計画",)]),
    ("想定issueタイトル/ブランチ名", [("ブランチ名",)]),
]

# インデックスファイルに必須のセクション要素。
INDEX_REQUIRED_SECTIONS: list[tuple[str, list[tuple[str, ...]]]] = [
    ("Phase1 全体ゴール", [("Phase1", "ゴール"), ("Phase 1", "ゴール")]),
    ("タスク一覧表", [("タスク一覧",)]),
    ("実装順序", [("実装順序",), ("実装順",)]),
    ("依存関係図", [("依存関係",)]),
]

# サービス別タスク振り分け文書の連番プレフィックスと、対応する Phase 番号。
SERVICE_ASSIGNMENTS_SPEC: list[tuple[str, int]] = [
    ("11", 1),
    ("12", 2),
    ("13", 3),
]


@pytest.fixture
def root_plans_dir(repo_root: Path) -> Path:
    """ルート横断 ``docs/plans/`` ディレクトリの絶対パスを返す。"""
    return repo_root / "docs" / "plans"


def _service_ph1_dir(repo_root: Path, service: str) -> Path:
    """指定サービスの Phase1 タスクディレクトリを返す。"""
    return repo_root / service / "docs" / "plans" / "Ph1"


def _resolve_plan_file(repo_root: Path, number_prefix: str, service: str) -> Path:
    """連番プレフィックスとサービス名から、所属するタスクプランファイルを一意特定する。"""
    matches = list(_service_ph1_dir(repo_root, service).glob(f"{number_prefix}-*.md"))
    assert len(matches) == 1, (
        f"連番 {number_prefix} のタスクプランファイルが {service}/docs/plans/Ph1/ で"
        f"一意に特定できません: {matches}"
    )
    return matches[0]


def _iter_heading_texts(content: str) -> Iterable[str]:
    """Markdown 見出し行の見出しテキスト部分のみを順に返す。"""
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        yield stripped.lstrip("#").strip()


def _has_section(content: str, alternatives: list[tuple[str, ...]]) -> bool:
    """``alternatives`` のいずれかの組（AND 条件）に合致する見出しが存在するか。"""
    headings = list(_iter_heading_texts(content))
    for keyword_set in alternatives:
        for heading in headings:
            if all(kw in heading for kw in keyword_set):
                return True
    return False


def test_root_docs_plansディレクトリが存在する(root_plans_dir: Path) -> None:
    """前提条件: 横断 ``docs/plans/`` ディレクトリが存在すること。"""
    assert root_plans_dir.is_dir(), (
        f"横断プランディレクトリが存在しません: {root_plans_dir}"
    )


def test_root_docs_plans直下に02から09のタスクプランファイルが残存しない(
    root_plans_dir: Path,
) -> None:
    """ADR-014 によりタスクプランは per-service へ移動済みであり、ルートに
    残ってはいけない。残存している場合は二重管理になるため早期検出する。
    """
    leftover = sorted(root_plans_dir.glob("0[2-9]-*.md"))
    assert leftover == [], (
        f"docs/plans/ 直下に Phase1 タスクプランが残存しています（ADR-014 違反）: "
        f"{[p.name for p in leftover]}"
    )


@pytest.mark.parametrize(
    ("number_prefix", "task_id", "branch", "service"),
    PHASE1_TASK_SPEC,
    ids=[
        f"{prefix}={task_id}@{service}"
        for prefix, task_id, _, service in PHASE1_TASK_SPEC
    ],
)
def test_phase1タスクプランが所属サービスのPh1配下に存在する(
    repo_root: Path,
    number_prefix: str,
    task_id: str,
    branch: str,
    service: str,
) -> None:
    """ADR-014 で定めた配置（postgres or worker の Ph1 配下）に各タスクプラン
    ファイルが一意に存在すること。
    """
    del task_id, branch  # この検証では存在性のみ評価する
    plan_file = _resolve_plan_file(repo_root, number_prefix, service)
    assert plan_file.is_file(), f"{plan_file} が存在しません"


def test_phase1俯瞰インデックスファイルが10番のみで1本だけ存在する(
    root_plans_dir: Path,
) -> None:
    """俯瞰インデックスは Phase1 を俯瞰する唯一の入口になるため、複数本生成
    されると到達経路が分散する。サービス別タスク振り分け文書 (11/12/13) は
    別概念であり、本テストの一意性条件には含めない。
    """
    index_files = sorted(root_plans_dir.glob("10-*.md"))
    assert len(index_files) == 1, (
        f"Phase1 俯瞰インデックスファイルは 10-*.md で 1 本のみ想定。\n"
        f"  発見数: {len(index_files)}\n"
        f"  発見ファイル: {[p.name for p in index_files]}"
    )


@pytest.mark.parametrize(
    ("number_prefix", "task_id", "branch", "service"),
    PHASE1_TASK_SPEC,
    ids=[
        f"{prefix}={task_id}@{service}"
        for prefix, task_id, _, service in PHASE1_TASK_SPEC
    ],
)
def test_各プランファイルが原典のブランチ名を保持する(
    repo_root: Path,
    number_prefix: str,
    task_id: str,
    branch: str,
    service: str,
) -> None:
    """原典 ``01-development-plan.md`` §6 のブランチ名と完全一致すること。

    ブランチ名は 1 issue / 1 PR の識別子であり、原典との不整合は
    トレーサビリティ崩壊を意味するため、文字列一致で厳密に検証する。
    """
    del task_id  # ブランチ名検証ではタスクID は使わない
    plan_file = _resolve_plan_file(repo_root, number_prefix, service)
    content = plan_file.read_text(encoding="utf-8")
    assert branch in content, (
        f"プランファイル {plan_file.relative_to(repo_root)} に原典ブランチ名 "
        f"'{branch}' が含まれていません"
    )


@pytest.mark.parametrize(
    ("number_prefix", "task_id", "branch", "service"),
    PHASE1_TASK_SPEC,
    ids=[
        f"{prefix}={task_id}@{service}"
        for prefix, task_id, _, service in PHASE1_TASK_SPEC
    ],
)
def test_各プランファイルが必須10セクションを含む(
    repo_root: Path,
    number_prefix: str,
    task_id: str,
    branch: str,
    service: str,
) -> None:
    """指示書「各プランファイルに含める内容（必須セクション）」を網羅検証する。"""
    del task_id, branch  # この検証ではセクション名のみ評価する
    plan_file = _resolve_plan_file(repo_root, number_prefix, service)
    content = plan_file.read_text(encoding="utf-8")

    missing: list[str] = []
    for section_label, alternatives in REQUIRED_PLAN_SECTIONS:
        if not _has_section(content, alternatives):
            missing.append(section_label)

    assert not missing, (
        f"{plan_file.relative_to(repo_root)} に必須セクションが見出しとして存在しません: "
        f"{missing}"
    )


def test_俯瞰インデックスファイルが必須セクションを含む(root_plans_dir: Path) -> None:
    """俯瞰インデックス (10-*.md) が必須要素（全体ゴール / タスク一覧 /
    実装順序 / 依存関係図）をすべて見出しとして保持すること。
    """
    index_files = sorted(root_plans_dir.glob("10-*.md"))
    assert len(index_files) == 1, (
        f"俯瞰インデックスファイルが一意に特定できません: "
        f"{[p.name for p in index_files]}"
    )
    index_file = index_files[0]
    content = index_file.read_text(encoding="utf-8")

    missing: list[str] = []
    for section_label, alternatives in INDEX_REQUIRED_SECTIONS:
        if not _has_section(content, alternatives):
            missing.append(section_label)

    assert not missing, (
        f"{index_file.name} に必須セクションが見出しとして存在しません: {missing}"
    )


def test_俯瞰インデックスファイルが8つのプランファイルすべてを参照する(
    repo_root: Path,
    root_plans_dir: Path,
) -> None:
    """俯瞰インデックスから各タスクプランファイル名（連番付きベース名）が
    本文中に登場すること。配置先（per-service Ph1）はベース名で一意になる
    ため、フルパスではなくファイル名のみで検証する。
    """
    index_files = sorted(root_plans_dir.glob("10-*.md"))
    assert len(index_files) == 1, (
        f"俯瞰インデックスファイルが一意に特定できません: "
        f"{[p.name for p in index_files]}"
    )
    index_content = index_files[0].read_text(encoding="utf-8")

    missing_refs: list[str] = []
    for number_prefix, _task_id, _branch, service in PHASE1_TASK_SPEC:
        plan_file = _resolve_plan_file(repo_root, number_prefix, service)
        if plan_file.name not in index_content:
            missing_refs.append(plan_file.name)

    assert not missing_refs, (
        f"インデックスファイル {index_files[0].name} から参照されていない "
        f"プランファイルがあります: {missing_refs}"
    )


@pytest.mark.parametrize(
    ("number_prefix", "task_id", "branch", "service"),
    PHASE1_TASK_SPEC,
    ids=[
        f"{prefix}={task_id}@{service}"
        for prefix, task_id, _, service in PHASE1_TASK_SPEC
    ],
)
def test_各プランファイルの依存タスク参照がプランファイル名形式に統一されている(
    repo_root: Path,
    number_prefix: str,
    task_id: str,
    branch: str,
    service: str,
) -> None:
    """各プランの「依存タスク」セクションに、依存先プランファイル名
    (``NN-...md``) または「なし」「無し」の明示があること。
    """
    del task_id, branch
    plan_file = _resolve_plan_file(repo_root, number_prefix, service)
    content = plan_file.read_text(encoding="utf-8")

    # 「依存タスク」見出しから次の見出しまでの本文ブロックを切り出す。
    lines = content.splitlines()
    in_section = False
    section_body: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if "依存タスク" in heading:
                in_section = True
                continue
            if in_section:
                # 次の見出しに到達したらブロック終了
                break
        if in_section:
            section_body.append(line)

    body_text = "\n".join(section_body).strip()
    assert body_text, (
        f"{plan_file.relative_to(repo_root)} に「依存タスク」セクションの本文がありません"
    )

    # 依存があれば 0X-*.md 形式で示すか、なければその旨が明示されていること。
    has_plan_ref = any(f"0{i}-" in body_text for i in range(2, 10))
    declares_none = any(token in body_text for token in ("なし", "無し", "None"))
    assert has_plan_ref or declares_none, (
        f"{plan_file.relative_to(repo_root)} の「依存タスク」セクションに、"
        f"依存先プランファイル名 (0X-*.md) も「なし」表明もありません。本文:\n{body_text}"
    )


def _extract_frontmatter(content: str) -> dict[str, str]:
    """Markdown ファイル先頭の YAML frontmatter を素朴に key:value で辞書化する。"""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


@pytest.mark.parametrize(
    ("number_prefix", "phase"),
    SERVICE_ASSIGNMENTS_SPEC,
    ids=[f"{prefix}=phase{phase}" for prefix, phase in SERVICE_ASSIGNMENTS_SPEC],
)
def test_サービス別タスク振り分け文書がphase別に1本ずつ存在する(
    root_plans_dir: Path, number_prefix: str, phase: int
) -> None:
    """サービス別タスク振り分け文書 (11/12/13) が Phase 1/2/3 ごとに 1 本ずつ
    ルート ``docs/plans/`` に存在し、frontmatter の ``phase`` 値が連番と整合
    することを検証する。
    """
    matches = sorted(
        root_plans_dir.glob(f"{number_prefix}-phase{phase}-service-assignments.md")
    )
    assert len(matches) == 1, (
        f"サービス別タスク振り分け文書 {number_prefix}-phase{phase}-"
        f"service-assignments.md が一意に存在しません。発見: "
        f"{[p.name for p in matches]}"
    )
    frontmatter = _extract_frontmatter(matches[0].read_text(encoding="utf-8"))
    assert frontmatter.get("phase") == str(phase), (
        f"{matches[0].name} の frontmatter ``phase`` が {phase} と一致しません: "
        f"{frontmatter.get('phase')!r}"
    )
