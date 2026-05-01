"""``docs/plans/`` Phase1 タスクプラン文書群の構造検証テスト。

このテストは、Phase1 タスク分解プランファイル群
(``docs/plans/02-*.md`` 〜 ``docs/plans/09-*.md``) と、それらを俯瞰する
**インデックスファイル** (``docs/plans/10-*.md``)、および各 Phase の
**サービス別タスク振り分け文書** (``docs/plans/11-*.md`` /
``docs/plans/12-*.md`` / ``docs/plans/13-*.md``) が、指示書および
計画レポートで定めた契約を満たすことを構造的に検証する。

「俯瞰インデックス」と「サービス別タスク振り分け」は別概念として明示的に
区別する立場を取る。両者を同一の glob (``1[0-9]-*.md``) で同一視すると、
振り分け文書の追加で俯瞰インデックスの一意性が崩れる脆弱なテストになるため、
俯瞰インデックスは ``10-*.md`` のみで識別する。サービス別振り分け文書
(11/12/13) は Phase 番号別に別個のファイル名規約 (``NN-phaseN-service-
assignments.md``) を持ち、本文構造の検証は最低限の「存在性」と「Phase
連番との整合」に限定する（過度に厳密化して将来の節構成変更を縛らない）。

検証対象（指示書「成果物」と計画レポート §2.1 タスク要素一覧）:

1. 02〜09 の連番でタスクプランファイル 8 本が漏れなく存在する
2. **俯瞰**インデックスファイルが ``10-*.md`` で 1 本だけ存在する
3. 各プランファイルが必須 10 セクションを含む
   - タスク概要 / 目的・背景 / スコープ / 依存タスク / 後続タスク /
     対象ファイル/モジュール / 実装方針 / 受入条件 / テスト計画 /
     想定 issue タイトル・ブランチ名
4. 各プランファイルが原典 ``01-development-plan.md`` §6 のブランチ名を
   本文に保持する（タスク識別の正本との不整合を即時検出するため）
5. 俯瞰インデックスが Phase1 全体ゴール / タスク一覧表 /
   実装順序 / 依存関係図 の必須要素を含み、8 つのプランファイル名を
   いずれも参照している
6. サービス別タスク振り分け文書が Phase 1/2/3 ごとに 1 本ずつ存在し、
   frontmatter で対応 Phase 番号を宣言している

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

# サービス別タスク振り分け文書の連番プレフィックスと、対応する Phase 番号。
# (number_prefix, phase) で「``NN-phaseN-service-assignments.md`` が一意に
# 存在し、frontmatter ``phase: N`` を保持する」契約を表現する。Phase 別の
# 内部節構成は Planner の裁量に委ね、本テストでは検証しない。
SERVICE_ASSIGNMENTS_SPEC: list[tuple[str, int]] = [
    ("11", 1),
    ("12", 2),
    ("13", 3),
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
    assert plans_dir.is_dir(), f"Phase1 プラン出力先ディレクトリが存在しません: {plans_dir}"


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


def test_phase1俯瞰インデックスファイルが10番のみで1本だけ存在する(
    plans_dir: Path,
) -> None:
    """指示書「タスクプランの最終番号の次の番号」の契約を検証する。

    俯瞰インデックスは Phase1 を俯瞰する唯一の入口になるため、複数本生成
    されると到達経路が分散して指示書の意図に反する。サービス別タスク振り分け
    文書 (11/12/13) は別概念であり、本テストの一意性条件には含めない。
    """
    index_files = sorted(plans_dir.glob("10-*.md"))
    assert len(index_files) == 1, (
        f"Phase1 俯瞰インデックスファイルは 10-*.md で 1 本のみ想定。\n"
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

    assert not missing, f"{plan_file.name} に必須セクションが見出しとして存在しません: {missing}"


def test_俯瞰インデックスファイルが必須セクションを含む(plans_dir: Path) -> None:
    """指示書「インデックスファイルに含める内容」を網羅検証する。

    対象は 10-*.md の俯瞰インデックスのみ。サービス別タスク振り分け文書
    (11/12/13) は内部節構成を Planner 裁量とするため、本テストでは
    必須セクション検証の対象外とする。
    """
    index_files = sorted(plans_dir.glob("10-*.md"))
    assert len(index_files) == 1, (
        f"俯瞰インデックスファイルが一意に特定できません: {[p.name for p in index_files]}"
    )
    index_file = index_files[0]
    content = index_file.read_text(encoding="utf-8")

    missing: list[str] = []
    for section_label, alternatives in INDEX_REQUIRED_SECTIONS:
        if not _has_section(content, alternatives):
            missing.append(section_label)

    assert not missing, f"{index_file.name} に必須セクションが見出しとして存在しません: {missing}"


def test_俯瞰インデックスファイルが8つのプランファイルすべてを参照する(
    plans_dir: Path,
) -> None:
    """俯瞰インデックスから各プランへの到達経路（Markdown リンク）を検証する。

    指示書「全タスクの一覧、依存関係、実装順序を俯瞰できる構成」かつ
    「依存関係はプランファイル名で参照」の契約に基づき、すべての連番プラン
    ファイル名が俯瞰インデックス本文に登場することを必須とする。サービス別
    タスク振り分け文書 (11/12/13) はサブディレクトリへのディスパッチが主
    責務であり、原典プラン全 8 本の網羅参照は要求しない（責務分離）。
    """
    index_files = sorted(plans_dir.glob("10-*.md"))
    assert len(index_files) == 1, (
        f"俯瞰インデックスファイルが一意に特定できません: {[p.name for p in index_files]}"
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
    assert body_text, f"{matches[0].name} に「依存タスク」セクションの本文がありません"

    # 依存があれば 0X-*.md 形式で示すか、なければその旨が明示されていること。
    has_plan_ref = any(f"0{i}-" in body_text for i in range(2, 10))
    declares_none = any(token in body_text for token in ("なし", "無し", "None"))
    assert has_plan_ref or declares_none, (
        f"{matches[0].name} の「依存タスク」セクションに、依存先プランファイル名 "
        f"(0X-*.md) も「なし」表明もありません。本文:\n{body_text}"
    )


def _extract_frontmatter(content: str) -> dict[str, str]:
    """Markdown ファイル先頭の YAML frontmatter を素朴な ``key: value`` で
    辞書化する。``yaml`` 依存を持ち込まずに ``phase`` 値だけ確認するため、
    入れ子・リスト・複数行値は対象外（本テストでは登場しない）。
    """
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
    plans_dir: Path, number_prefix: str, phase: int
) -> None:
    """サービス別タスク振り分け文書 (11/12/13) が Phase 1/2/3 ごとに 1 本ずつ
    存在し、frontmatter の ``phase`` 値が連番と整合することを検証する。

    俯瞰インデックス (10-*.md) と振り分け文書 (11/12/13) を別概念として
    扱う設計判断（モジュールdocstring 参照）に基づき、振り分け文書側にも
    最低限の存在性検証を置く。Phase 番号と連番プレフィックスの食い違いは
    インデックス全体の信頼を失わせるため、frontmatter で固定する。
    """
    matches = sorted(plans_dir.glob(f"{number_prefix}-phase{phase}-service-assignments.md"))
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
