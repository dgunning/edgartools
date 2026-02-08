"""
Verification of user-facing AI surface added in v5.15.0.

Follows the Verification Constitution:
- Ground-truth assertions (specific values, not just `is not None`)
- Silence checks (bad input produces useful errors)
- Solvability (skills are discoverable and well-formed)
"""

import pytest
import yaml
from pathlib import Path


# ============================================================================
# Skill YAML Validity — all skill files parse and have required fields
# ============================================================================

SKILLS_ROOT = Path(__file__).parent.parent / "edgar" / "ai" / "skills"

# Collect all skill.yaml files
SKILL_YAML_FILES = sorted(SKILLS_ROOT.glob("**/skill.yaml"))
SHARP_EDGES_FILES = sorted(SKILLS_ROOT.glob("**/sharp-edges.yaml"))


@pytest.mark.fast
@pytest.mark.parametrize("yaml_path", SKILL_YAML_FILES, ids=lambda p: str(p.relative_to(SKILLS_ROOT)))
def test_skill_yaml_parses_and_has_required_fields(yaml_path):
    """Every skill.yaml must parse as valid YAML with id, name, and version."""
    content = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert isinstance(data, dict), f"{yaml_path.name} should parse as a YAML mapping"
    assert "id" in data, f"{yaml_path} missing 'id' field"
    assert "name" in data, f"{yaml_path} missing 'name' field"
    assert "version" in data, f"{yaml_path} missing 'version' field"
    assert data["id"].startswith("edgartools-"), f"Skill id should start with 'edgartools-', got '{data['id']}'"


@pytest.mark.fast
@pytest.mark.parametrize("yaml_path", SHARP_EDGES_FILES, ids=lambda p: str(p.relative_to(SKILLS_ROOT)))
def test_sharp_edges_yaml_parses(yaml_path):
    """Every sharp-edges.yaml must parse as valid YAML."""
    content = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict), f"{yaml_path.name} should parse as a YAML mapping"


@pytest.mark.fast
def test_skill_yaml_ids_are_unique():
    """All skill.yaml files must have unique ids."""
    ids = []
    for yaml_path in SKILL_YAML_FILES:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        ids.append(data["id"])

    assert len(ids) == len(set(ids)), f"Duplicate skill ids found: {[x for x in ids if ids.count(x) > 1]}"


@pytest.mark.fast
def test_all_six_skill_domains_present():
    """EdgarTools ships 6 skill domains: core, financials, holdings, ownership, reports, xbrl."""
    expected_domains = {"core", "financials", "holdings", "ownership", "reports", "xbrl"}
    actual_domains = {p.parent.name for p in SKILL_YAML_FILES}
    assert expected_domains == actual_domains, f"Missing domains: {expected_domains - actual_domains}"


@pytest.mark.fast
def test_core_skill_yaml_has_patterns():
    """The core skill.yaml must define patterns (the primary content)."""
    core_yaml = SKILLS_ROOT / "core" / "skill.yaml"
    data = yaml.safe_load(core_yaml.read_text(encoding="utf-8"))

    assert "patterns" in data, "Core skill.yaml must have 'patterns'"
    assert len(data["patterns"]) >= 3, f"Core skill should have at least 3 patterns, got {len(data['patterns'])}"


# ============================================================================
# Skills API — list, get, error paths
# ============================================================================


@pytest.mark.fast
def test_list_skills_returns_edgartools():
    """list_skills() must return the EdgarTools skill."""
    from edgar.ai import list_skills

    skills = list_skills()
    assert len(skills) == 1
    assert skills[0].name == "EdgarTools"


@pytest.mark.fast
def test_get_skill_returns_correct_skill():
    """get_skill('EdgarTools') returns a skill with name, description, and content_dir."""
    from edgar.ai import get_skill

    skill = get_skill("EdgarTools")
    assert skill.name == "EdgarTools"
    assert "SEC" in skill.description
    assert skill.content_dir.exists()
    assert skill.content_dir.is_dir()


@pytest.mark.fast
def test_get_skill_bad_name_raises_with_available_list():
    """get_skill() with invalid name must raise ValueError listing available skills."""
    from edgar.ai import get_skill

    with pytest.raises(ValueError, match="EdgarTools") as exc_info:
        get_skill("NonExistentSkill")

    # The error message should help the user — it must mention what IS available
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.fast
def test_skill_get_documents_returns_known_files():
    """EdgarTools skill must expose documents including SKILL and readme."""
    from edgar.ai.skills.core import edgartools_skill

    docs = edgartools_skill.get_documents()
    assert "SKILL" in docs, f"SKILL should be in documents, got: {docs}"
    assert "readme" in docs, f"readme should be in documents, got: {docs}"


@pytest.mark.fast
def test_skill_get_document_content_bad_name_raises():
    """get_document_content() with bad name must raise FileNotFoundError with helpful message."""
    from edgar.ai.skills.core import edgartools_skill

    with pytest.raises(FileNotFoundError, match="not found"):
        edgartools_skill.get_document_content("nonexistent-document")


@pytest.mark.fast
def test_skill_str_has_concrete_values():
    """str(skill) must include the skill name, document count, and helper count."""
    from edgar.ai.skills.core import edgartools_skill

    text = str(edgartools_skill)
    assert "EdgarTools" in text
    assert "Documents:" in text
    assert "Helper Functions:" in text
    # Ground truth: we know there are 5 helpers
    assert "5" in text


@pytest.mark.fast
def test_skill_repr_includes_class_name():
    """repr(skill) must include the class name."""
    from edgar.ai.skills.core import edgartools_skill

    assert "EdgarToolsSkill" in repr(edgartools_skill)


# ============================================================================
# AI module API surface
# ============================================================================


@pytest.mark.fast
def test_ai_module_public_api():
    """edgar.ai must export the documented public API."""
    import edgar.ai as ai

    # Core classes
    assert hasattr(ai, "AIEnabled")
    assert hasattr(ai, "TokenOptimizer")
    assert hasattr(ai, "SemanticEnricher")

    # Skills
    assert hasattr(ai, "list_skills")
    assert hasattr(ai, "get_skill")
    assert hasattr(ai, "edgartools_skill")
    assert hasattr(ai, "BaseSkill")

    # Convenience functions
    assert hasattr(ai, "install_skill")
    assert hasattr(ai, "package_skill")
    assert hasattr(ai, "export_skill")

    # Status flags
    assert hasattr(ai, "AI_AVAILABLE")


@pytest.mark.fast
def test_get_ai_info_structure():
    """get_ai_info() must return a dict with documented keys."""
    from edgar.ai import get_ai_info

    info = get_ai_info()
    assert isinstance(info, dict)
    assert "ai_available" in info
    assert "mcp_available" in info
    assert "tiktoken_available" in info
    assert "missing_dependencies" in info
    assert isinstance(info["missing_dependencies"], list)
