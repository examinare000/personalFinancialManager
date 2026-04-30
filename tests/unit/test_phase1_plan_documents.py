"""``docs/plans/`` Phase1 タスクプラン文書群の構造検証テスト。

このテストは、Phase1 タスク分解プランファイル群
(``docs/plans/02-*.md`` 〜 ``docs/plans/09-*.md``) と、それらを俯瞰する
インデックスファイル (``docs/plans/10-*.md``) が、指示書および計画レポートで
定めた以下の契約を満たすことを構造的に検証する。

検証対象（指示書「成果物」と計画レポート §2.1 タスク要素一覧）:

1. 02〜09 の連番でタスクプランファイル 8 本が漏れなく存在する
2. インデックスファイルが 10 番台で 1 本だけ存在する
3. 各プランファイルが必須 10 セクションを含む
   - タスク概要 / 目的・背景 / スコープ / 依存タスク / 後続タスク /
     対象ファイル/モジュール / 実装方針 / 受入条件 / テスト計画 /
     想定 issue タイトル・ブランチ名
4. 各プランファイルが原典 ``01-development-plan.md`` §6 のブランチ名を
   本文に保持する（タスク識別の正本との不整合を即時検出するため）
5. インデックスファイルが Phase1 全体ゴール / タスク一覧表 /
   実装順序 / 依存関係図 の必須要素を含み、8 つのプランファイル名を
   いずれも参照している

設計準拠:
- 指示書「タスク指示書: Phase1 のタスク分解と実装プラン作成」
- 計画レポート §2 要件棚卸し / §6 連番割当
- ``01-development-plan.md`` §4.1 / §5 / §6（タスク粒度・依存・ブランチ名の正本）
- ``agent-rules/11-testing-strategy.md``（振る舞い駆動 TDD）
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

# 原典 ``01-development-plan.md`` §4.1 / §6 から導出した、各タスクプラン
# ファイルが満たすべき正本情報。プランナがスラッグ部分を変更しても、
# 連番プレフィックスとブランチ名の整合は固定であるべきという立場で固定する。
#
# (連番プレフィックス, 原典タスクID, 原典ブランチ名)
PHASE1_TASK_SPEC: list[tuple[str, str, str]] = [
    ("02", "1.1", "feature/db-schema-initial"),
    ("03", "1.2", "feature/domain-types"),
    ("04", "1.3", "feature/ingest-adapter-base"),
    ("05", "1.4", "feature/adapter-mufg-csv"),
    ("06", "1.5", "feature/adapter-smbc-csv"),
    ("07", "1.6", "feature/ingest-cli"),
    ("08", "1.7", "feature/hash-idempotency-tests"),
    ("09", "1.8", "feature/monthly-summary-sql"),
]

# 各プランファイルに必須の 10 セクション。
# 値は「いずれかの組み合わせがいずれかの見出し行に含まれていればOK」という
# 代替指定リスト。例えば「受入条件」は ``Acceptance Criteria`` の英語表記も許容する。
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


@pytest.fixture
def plans_dir(repo_root: Path) -> Path:
    """``docs/plans/`` ディレクトリの絶対パスを返す。

    ``repo_root`` (conftest.py) が function スコープのため、本フィクスチャも
    function スコープに合わせる（pytest の ScopeMismatch を回避するため）。
    """
    return repo_root / "docs" / "plans"


def _iter_heading_texts(content: str) -> Iterable[str]:
    """Markdown 見出し行の見出しテキスト部分のみを順に返す。"""
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        # 連続する '#' を取り除き、見出しテキスト部のみ残す。
        yield stripped.lstrip("#").strip()


def _has_section(content: str, alternatives: list[tuple[str, ...]]) -> bool:
    """``alternatives`` のいずれかの組（AND 条件）に合致する見出しが存在するか。

    ``alternatives`` は OR、各タプル内のキーワードは AND として扱う。
    例: ``[("目的", "背景")]`` は「目的」と「背景」の両方を含む見出しを要求。
    例: ``[("受入条件",), ("Acceptance Criteria",)]`` は片方でも見出しに
        含まれていれば成立。
    """
    headings = list(_iter_heading_texts(content))
    for keyword_set in alternatives:
        for heading in headings:
            if all(kw in heading for kw in keyword_set):
                return True
    return False


def test_docs_plansディレクトリが存在する(plans_dir: Path) -> None:
    """前提条件: 出力先ディレクトリ ``docs/plans/`` が存在すること。"""
    assert plans_dir.is_dir(), (
        f"Phase1 プラン出力先ディレクトリが存在しません: {plans_dir}"
    )


def test_phase1のタスクプランが02から09の連番で8本そろう(plans_dir: Path) -> None:
    """指示書「実装順序に従って連番を付与」の契約を検証する。

    既存ファイル ``00-initial-design.md`` / ``01-development-plan.md`` を
    避けて 02 から開始することを必須とし、抜け番・重複番がないことを確認する。
    """
    found = sorted(plans_dir.glob("0[2-9]-*.md"))
    found_prefixes = {p.name[:2] for p in found}
    expected_prefixes = {f"0{i}" for i in range(2, 10)}

    assert found_prefixes == expected_prefixes, (
        f"02〜09 の連番プランファイルに過不足があります。\n"
        f"  期待: {sorted(expected_prefixes)}\n"
        f"  実在: {sorted(found_prefixes)}\n"
        f"  発見ファイル: {[p.name for p in found]}"
    )


def test_phase1インデックスファイルが10番台で1本のみ存在する(plans_dir: Path) -> None:
    """指示書「タスクプランの最終番号の次の番号」の契約を検証する。

    インデックスファイルは Phase1 を俯瞰する唯一の入口になるため、
    複数本生成されると到達経路が分散して指示書の意図に反する。
    """
    index_files = sorted(plans_dir.glob("1[0-9]-*.md"))
    assert len(index_files) == 1, (
        f"Phase1 インデックスファイルは 10 番台で 1 本のみ想定。\n"
        f"  発見数: {len(index_files)}\n"
        f"  発見ファイル: {[p.name for p in index_files]}"
    )


@pytest.mark.parametrize(
    ("number_prefix", "task_id", "branch"),
    PHASE1_TASK_SPEC,
    ids=[f"{prefix}={task_id}" for prefix, task_id, _ in PHASE1_TASK_SPEC],
)
def test_各プランファイルが原典のブランチ名を保持する(
    plans_dir: Path, number_prefix: str, task_id: str, branch: str
) -> None:
    """原典 ``01-development-plan.md`` §6 のブランチ名と完全一致すること。

    ブランチ名は 1 issue / 1 PR の識別子であり、原典との不整合は
    トレーサビリティ崩壊を意味するため、文字列一致で厳密に検証する。
    """
    matches = list(plans_dir.glob(f"{number_prefix}-*.md"))
    assert len(matches) == 1, (
        f"連番 {number_prefix} のプランファイルが一意に特定できません: {matches}"
    )
    plan_file = matches[0]
    content = plan_file.read_text(encoding="utf-8")
    assert branch in content, (
        f"プランファイル {plan_file.name} (Phase {task_id}) に原典ブランチ名 "
        f"'{branch}' が含まれていません"
    )


@pytest.mark.parametrize(
    ("number_prefix", "task_id", "branch"),
    PHASE1_TASK_SPEC,
    ids=[f"{prefix}={task_id}" for prefix, task_id, _ in PHASE1_TASK_SPEC],
)
def test_各プランファイルが必須10セクションを含む(
    plans_dir: Path, number_prefix: str, task_id: str, branch: str
) -> None:
    """指示書「各プランファイルに含める内容（必須セクション）」を網羅検証する。

    Markdown 見出し行（``#`` から始まる行）にセクション名が現れることを必須とし、
    本文中の単なる言及だけでは合格としない（構造としての見出し化を要求）。
    """
    del task_id, branch  # この検証ではセクション名のみ評価する
    matches = list(plans_dir.glob(f"{number_prefix}-*.md"))
    assert len(matches) == 1, (
        f"連番 {number_prefix} のプランファイルが一意に特定できません: {matches}"
    )
    plan_file = matches[0]
    content = plan_file.read_text(encoding="utf-8")

    missing: list[str] = []
    for section_label, alternatives in REQUIRED_PLAN_SECTIONS:
        if not _has_section(content, alternatives):
            missing.append(section_label)

    assert not missing, (
        f"{plan_file.name} に必須セクションが見出しとして存在しません: {missing}"
    )


def test_インデックスファイルが必須セクションを含む(plans_dir: Path) -> None:
    """指示書「インデックスファイルに含める内容」を網羅検証する。"""
    index_files = sorted(plans_dir.glob("1[0-9]-*.md"))
    assert len(index_files) == 1, (
        f"インデックスファイルが一意に特定できません: "
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


def test_インデックスファイルが8つのプランファイルすべてを参照する(
    plans_dir: Path,
) -> None:
    """インデックスから各プランへの到達経路（Markdown リンク）を検証する。

    指示書「全タスクの一覧、依存関係、実装順序を俯瞰できる構成」かつ
    「依存関係はプランファイル名で参照」の契約に基づき、すべての連番プラン
    ファイル名がインデックス本文に登場することを必須とする。
    """
    index_files = sorted(plans_dir.glob("1[0-9]-*.md"))
    assert len(index_files) == 1, (
        f"インデックスファイルが一意に特定できません: "
        f"{[p.name for p in index_files]}"
    )
    index_content = index_files[0].read_text(encoding="utf-8")

    plan_files = sorted(plans_dir.glob("0[2-9]-*.md"))
    assert len(plan_files) == 8, "プランファイル本数が 8 ではないため前提崩壊"

    missing_refs: list[str] = []
    for plan_file in plan_files:
        if plan_file.name not in index_content:
            missing_refs.append(plan_file.name)

    assert not missing_refs, (
        f"インデックスファイル {index_files[0].name} から参照されていない "
        f"プランファイルがあります: {missing_refs}"
    )


@pytest.mark.parametrize(
    ("number_prefix", "task_id", "branch"),
    PHASE1_TASK_SPEC,
    ids=[f"{prefix}={task_id}" for prefix, task_id, _ in PHASE1_TASK_SPEC],
)
def test_各プランファイルの依存タスク参照がプランファイル名形式に統一されている(
    plans_dir: Path, number_prefix: str, task_id: str, branch: str
) -> None:
    """計画レポート「アンチパターン」の禁則を検証する。

    依存タスクの記述が原典タスク番号 (例: 1.1) のままだと、本タスクで
    導入したプランファイル名による相互参照が崩れる。各プランの「依存タスク」
    セクション以降に少なくとも 1 件のプランファイル名 (``0X-*.md``) または
    「なし」「無し」の明示があることを要求する。
    """
    del task_id, branch
    matches = list(plans_dir.glob(f"{number_prefix}-*.md"))
    assert len(matches) == 1
    content = matches[0].read_text(encoding="utf-8")

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
        f"{matches[0].name} に「依存タスク」セクションの本文がありません"
    )

    # 依存があれば 0X-*.md 形式で示すか、なければその旨が明示されていること。
    has_plan_ref = any(
        f"0{i}-" in body_text for i in range(2, 10)
    )
    declares_none = any(token in body_text for token in ("なし", "無し", "None"))
    assert has_plan_ref or declares_none, (
        f"{matches[0].name} の「依存タスク」セクションに、依存先プランファイル名 "
        f"(0X-*.md) も「なし」表明もありません。本文:\n{body_text}"
    )
