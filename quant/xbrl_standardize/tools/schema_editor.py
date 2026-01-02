"""
XBRL Schema Editor - Streamlit Application

A comprehensive tool for viewing, searching, editing, and validating
XBRL mapping schemas for SEC 10-K filings.

Run with: streamlit run tools/schema_editor.py
"""

import difflib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st

# =============================================================================
# Configuration
# =============================================================================

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
SCHEMA_FILES = {
    "Income Statement": "income-statement.json",
    "Balance Sheet": "balance-sheet.json",
    "Cash Flow": "cash-flow.json"
}

# Industry hints used across schemas
INDUSTRY_HINTS = [
    "Bank", "Banks", "Diversified Banks", "Regional Banks",
    "Insurance", "Insurer", "Reinsurance",
    "Utilities", "Electric Utilities", "Gas Utilities", "Water Utilities",
    "Oil", "Gas", "Energy", "E&P", "Refining", "Midstream",
    "REIT", "Real Estate", "Property", "Realty",
    "BrokerDealers", "Capital Markets", "Consumer Finance", "Credit Services",
    "Thrifts", "Savings", "Independent Power Producers"
]

# =============================================================================
# Data Loading & Saving
# =============================================================================

@st.cache_data
def load_schema(schema_name: str) -> Dict:
    """Load a schema file from disk."""
    file_path = SCHEMAS_DIR / SCHEMA_FILES[schema_name]
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_schemas() -> Dict[str, Dict]:
    """Load all schemas into memory."""
    schemas = {}
    for name in SCHEMA_FILES:
        try:
            schemas[name] = load_schema(name)
        except Exception as e:
            st.error(f"Failed to load {name}: {e}")
    return schemas


def save_schema(schema_name: str, schema_data: Dict, backup: bool = True) -> bool:
    """Save a schema to disk with optional backup."""
    file_path = SCHEMAS_DIR / SCHEMA_FILES[schema_name]

    try:
        # Create backup
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            with open(file_path, 'r', encoding='utf-8') as f:
                original = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original)

        # Save new version
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(schema_data, f, indent='\t', ensure_ascii=False)

        return True
    except Exception as e:
        st.error(f"Failed to save: {e}")
        return False


# =============================================================================
# Search Functions
# =============================================================================

def search_fields(schemas: Dict[str, Dict], query: str) -> List[Tuple[str, str, Dict]]:
    """Search for fields by name across all schemas."""
    results = []
    query_lower = query.lower()

    for schema_name, schema in schemas.items():
        for field_name, field_data in schema.get("fields", {}).items():
            if query_lower in field_name.lower():
                results.append((schema_name, field_name, field_data))

    return results


def search_concepts(schemas: Dict[str, Dict], concept: str) -> List[Dict]:
    """Find all fields that use a specific XBRL concept."""
    results = []
    concept_lower = concept.lower()

    for schema_name, schema in schemas.items():
        for field_name, field_data in schema.get("fields", {}).items():
            for rule_idx, rule in enumerate(field_data.get("rules", [])):
                # Check selectAny
                for concept_item in rule.get("selectAny", []):
                    if concept_lower in concept_item.lower():
                        results.append({
                            "schema": schema_name,
                            "field": field_name,
                            "rule_index": rule_idx,
                            "rule_name": rule.get("name", ""),
                            "location": "selectAny",
                            "concept": concept_item
                        })

                # Check computeAny (nested)
                for compute in rule.get("computeAny", []):
                    for term in compute.get("terms", []):
                        if isinstance(term, dict) and "conceptAny" in term:
                            for c in term["conceptAny"]:
                                if concept_lower in c.lower():
                                    results.append({
                                        "schema": schema_name,
                                        "field": field_name,
                                        "rule_index": rule_idx,
                                        "rule_name": rule.get("name", ""),
                                        "location": "computeAny",
                                        "concept": c
                                    })

    return results


def filter_by_industry(schemas: Dict[str, Dict], industry: str) -> List[Tuple[str, str, Dict, int]]:
    """Find rules with specific industry hints."""
    results = []

    for schema_name, schema in schemas.items():
        for field_name, field_data in schema.get("fields", {}).items():
            for rule_idx, rule in enumerate(field_data.get("rules", [])):
                hints = rule.get("industryHints", [])
                if industry in hints:
                    results.append((schema_name, field_name, rule, rule_idx))

    return results


def filter_by_priority(schemas: Dict[str, Dict], min_p: int, max_p: int) -> List[Tuple[str, str, Dict, int]]:
    """Find rules within a priority range."""
    results = []

    for schema_name, schema in schemas.items():
        for field_name, field_data in schema.get("fields", {}).items():
            for rule_idx, rule in enumerate(field_data.get("rules", [])):
                priority = rule.get("priority", 0)
                if min_p <= priority <= max_p:
                    results.append((schema_name, field_name, rule, priority))

    return results


# =============================================================================
# Validation Functions
# =============================================================================

def validate_schema(schema_name: str, schema: Dict) -> List[Dict]:
    """Run comprehensive validation on a schema."""
    issues = []

    # Track all concepts used
    concept_usage = defaultdict(list)

    for field_name, field_data in schema.get("fields", {}).items():
        rules = field_data.get("rules", [])

        # Check for missing rules
        if not rules:
            issues.append({
                "severity": "error",
                "field": field_name,
                "message": "Field has no rules defined",
                "category": "structure"
            })
            continue

        has_ifrs = False
        has_usgaap = False
        priorities = []

        for rule_idx, rule in enumerate(rules):
            priority = rule.get("priority", 0)
            priorities.append(priority)
            name = rule.get("name", "")

            # Check for IFRS/US GAAP coverage
            if "ifrs" in name.lower():
                has_ifrs = True
            if "us gaap" in name.lower() or "us-gaap" in name.lower():
                has_usgaap = True

            # Check selectAny concepts
            for concept in rule.get("selectAny", []):
                concept_usage[concept].append((field_name, rule_idx, "selectAny"))

                # Check for common concept name issues
                if not concept.startswith(("us-gaap:", "ifrs-full:")):
                    issues.append({
                        "severity": "warning",
                        "field": field_name,
                        "rule_index": rule_idx,
                        "message": f"Non-standard concept prefix: {concept}",
                        "category": "concept"
                    })

            # Check for mixed selectAny + computeAny
            if rule.get("selectAny") and rule.get("computeAny"):
                issues.append({
                    "severity": "warning",
                    "field": field_name,
                    "rule_index": rule_idx,
                    "message": f"Rule '{name}' has both selectAny and computeAny - precedence unclear",
                    "category": "structure"
                })

        # Check for missing IFRS
        if not has_ifrs and has_usgaap:
            issues.append({
                "severity": "warning",
                "field": field_name,
                "message": "Field has US GAAP rules but no IFRS rules",
                "category": "coverage"
            })

        # Check for duplicate priorities with same industryHints
        priority_hints = defaultdict(list)
        for rule_idx, rule in enumerate(rules):
            p = rule.get("priority", 0)
            hints = tuple(sorted(rule.get("industryHints", [])))
            priority_hints[(p, hints)].append(rule_idx)

        for (p, hints), indices in priority_hints.items():
            if len(indices) > 1 and hints:
                issues.append({
                    "severity": "warning",
                    "field": field_name,
                    "message": f"Multiple rules with priority {p} and same industryHints",
                    "category": "priority"
                })

    # Check for duplicate concepts across fields (potential double-counting)
    for concept, usages in concept_usage.items():
        if len(usages) > 1:
            fields = set(u[0] for u in usages)
            if len(fields) > 1:
                issues.append({
                    "severity": "info",
                    "field": ", ".join(fields),
                    "message": f"Concept '{concept}' used in multiple fields",
                    "category": "overlap"
                })

    return issues


def find_unused_computed_fields(schema: Dict) -> List[str]:
    """Find fields defined but never referenced in computeAny."""
    defined_fields = set(schema.get("fields", {}).keys())
    referenced_fields = set()

    for field_data in schema.get("fields", {}).values():
        for rule in field_data.get("rules", []):
            for compute in rule.get("computeAny", []):
                _extract_field_refs(compute, referenced_fields)

    return list(defined_fields - referenced_fields)


def _extract_field_refs(obj: Any, refs: set):
    """Recursively extract field references from computeAny."""
    if isinstance(obj, dict):
        if "field" in obj:
            refs.add(obj["field"])
        for v in obj.values():
            _extract_field_refs(v, refs)
    elif isinstance(obj, list):
        for item in obj:
            _extract_field_refs(item, refs)


# =============================================================================
# Diff Functions
# =============================================================================

def compute_diff(original: str, modified: str) -> str:
    """Compute a unified diff between two JSON strings."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile="original",
        tofile="modified",
        lineterm=""
    )

    return "".join(diff)


# =============================================================================
# UI Components
# =============================================================================

def render_rule_card(rule: Dict, rule_idx: int, editable: bool = False) -> Dict:
    """Render a single rule as an expandable card."""
    name = rule.get("name", f"Rule {rule_idx}")
    priority = rule.get("priority", 0)
    hints = rule.get("industryHints", [])

    with st.expander(f"**{name}** (Priority: {priority})", expanded=False):
        col1, col2 = st.columns([1, 1])

        with col1:
            if editable:
                new_name = st.text_input("Rule Name", value=name, key=f"rule_name_{rule_idx}")
                new_priority = st.number_input("Priority", value=priority, min_value=1, max_value=200, key=f"rule_priority_{rule_idx}")
            else:
                st.write(f"**Name:** {name}")
                st.write(f"**Priority:** {priority}")

        with col2:
            if hints:
                st.write("**Industry Hints:**")
                st.write(", ".join(hints))
            else:
                st.write("**Industry Hints:** None")

        # selectAny
        if "selectAny" in rule:
            st.write("**selectAny:**")
            for i, concept in enumerate(rule["selectAny"]):
                if editable:
                    st.text_input(f"Concept {i+1}", value=concept, key=f"select_{rule_idx}_{i}")
                else:
                    st.code(concept, language=None)

        # computeAny
        if "computeAny" in rule:
            st.write("**computeAny:**")
            st.json(rule["computeAny"])

        if editable:
            return {
                "name": new_name if editable else name,
                "priority": new_priority if editable else priority
            }

    return rule


def render_validation_issue(issue: Dict):
    """Render a validation issue with appropriate styling."""
    severity = issue.get("severity", "info")
    icon = {"error": "🔴", "warning": "🟠", "info": "🔵"}.get(severity, "⚪")

    st.markdown(f"""
    {icon} **{issue.get('category', 'General').upper()}** - {issue.get('field', 'N/A')}
    
    {issue.get('message', '')}
    """)


def render_field_tree(field_name: str, field_data: Dict):
    """Render a field as a tree structure."""
    rules = field_data.get("rules", [])

    st.markdown(f"### 📋 {field_name}")
    st.caption(f"Standard Label: `{field_data.get('standardLabel', field_name)}`")
    st.caption(f"{len(rules)} rule(s)")

    for idx, rule in enumerate(rules):
        render_rule_card(rule, idx)


# =============================================================================
# Page: Search & Browse
# =============================================================================

def page_search(schemas: Dict[str, Dict]):
    """Search and browse page."""
    st.header("🔍 Search & Browse")

    # Search controls
    col1, col2 = st.columns([2, 1])

    with col1:
        search_type = st.radio(
            "Search by:",
            ["Field Name", "XBRL Concept", "Industry"],
            horizontal=True
        )
        query = st.text_input("Search query", placeholder="Enter search term...")

    with col2:
        schema_filter = st.multiselect(
            "Filter by Statement",
            options=list(SCHEMA_FILES.keys()),
            default=list(SCHEMA_FILES.keys())
        )
        priority_range = st.slider("Priority Range", 1, 200, (1, 200))

    # Filter schemas
    filtered_schemas = {k: v for k, v in schemas.items() if k in schema_filter}

    if not query:
        # Show all fields summary
        st.subheader("All Fields Summary")
        for schema_name, schema in filtered_schemas.items():
            with st.expander(f"**{schema_name}** ({len(schema.get('fields', {}))} fields)"):
                for field_name, field_data in schema.get("fields", {}).items():
                    rules = field_data.get("rules", [])
                    priorities = [r.get("priority", 0) for r in rules]
                    if any(priority_range[0] <= p <= priority_range[1] for p in priorities):
                        st.write(f"• **{field_name}** - {len(rules)} rules (priorities: {min(priorities)}-{max(priorities)})")
        return

    # Perform search
    st.subheader("Search Results")

    if search_type == "Field Name":
        results = search_fields(filtered_schemas, query)
        if results:
            for schema_name, field_name, field_data in results:
                with st.expander(f"**{field_name}** ({schema_name})"):
                    render_field_tree(field_name, field_data)
        else:
            st.info("No fields found matching your query.")

    elif search_type == "XBRL Concept":
        results = search_concepts(filtered_schemas, query)
        if results:
            st.write(f"Found {len(results)} occurrence(s)")
            for r in results:
                st.markdown(f"""
                **{r['field']}** ({r['schema']})  
                Rule: {r['rule_name']}  
                Location: `{r['location']}`  
                Concept: `{r['concept']}`
                """)
                st.divider()
        else:
            st.info("No concepts found matching your query.")

    elif search_type == "Industry":
        if query in INDUSTRY_HINTS:
            results = filter_by_industry(filtered_schemas, query)
            if results:
                st.write(f"Found {len(results)} rule(s) with industry hint '{query}'")
                for schema_name, field_name, rule, rule_idx in results:
                    with st.expander(f"**{field_name}** ({schema_name}) - {rule.get('name', '')}"):
                        st.json(rule)
            else:
                st.info("No rules found with that industry hint.")
        else:
            st.warning(f"'{query}' is not a recognized industry hint.")
            st.write("Available hints:", ", ".join(INDUSTRY_HINTS[:10]), "...")


# =============================================================================
# Page: Field Editor
# =============================================================================

def page_editor(schemas: Dict[str, Dict]):
    """Field editor page."""
    st.header("✏️ Field Editor")

    # Initialize session state for modifications
    if "modified_schemas" not in st.session_state:
        st.session_state.modified_schemas = {k: json.loads(json.dumps(v)) for k, v in schemas.items()}

    # Schema and field selection
    col1, col2 = st.columns(2)

    with col1:
        selected_schema = st.selectbox("Select Statement", list(SCHEMA_FILES.keys()))

    schema = st.session_state.modified_schemas[selected_schema]
    field_names = list(schema.get("fields", {}).keys())

    with col2:
        selected_field = st.selectbox("Select Field", field_names)

    if not selected_field:
        st.info("Select a field to edit")
        return

    field_data = schema["fields"][selected_field]

    # Field metadata
    st.subheader(f"📋 {selected_field}")

    new_label = st.text_input(
        "Standard Label",
        value=field_data.get("standardLabel", selected_field),
        key="field_label"
    )

    # Rules editor
    st.subheader("Rules")

    rules = field_data.get("rules", [])

    for idx, rule in enumerate(rules):
        with st.expander(f"Rule {idx + 1}: {rule.get('name', 'Unnamed')}", expanded=idx == 0):
            col1, col2 = st.columns(2)

            with col1:
                new_name = st.text_input("Name", value=rule.get("name", ""), key=f"rule_name_{idx}")
                new_priority = st.number_input(
                    "Priority", 
                    value=rule.get("priority", 100),
                    min_value=1, max_value=200,
                    key=f"rule_priority_{idx}"
                )

            with col2:
                current_hints = rule.get("industryHints", [])
                new_hints = st.multiselect(
                    "Industry Hints",
                    options=INDUSTRY_HINTS,
                    default=current_hints,
                    key=f"rule_hints_{idx}"
                )

            # selectAny editor
            if "selectAny" in rule:
                st.write("**selectAny Concepts:**")
                concepts_text = st.text_area(
                    "One concept per line",
                    value="\n".join(rule["selectAny"]),
                    height=100,
                    key=f"selectany_{idx}"
                )
                new_concepts = [c.strip() for c in concepts_text.split("\n") if c.strip()]
            else:
                new_concepts = None

            # computeAny viewer/editor
            if "computeAny" in rule:
                st.write("**computeAny (JSON):**")
                try:
                    compute_json = st.text_area(
                        "computeAny JSON",
                        value=json.dumps(rule["computeAny"], indent=2),
                        height=150,
                        key=f"computeany_{idx}"
                    )
                    new_compute = json.loads(compute_json)
                except json.JSONDecodeError:
                    st.error("Invalid JSON")
                    new_compute = rule["computeAny"]
            else:
                new_compute = None

            # Update rule in session state
            st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"][idx]["name"] = new_name
            st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"][idx]["priority"] = new_priority

            if new_hints:
                st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"][idx]["industryHints"] = new_hints
            elif "industryHints" in st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"][idx]:
                del st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"][idx]["industryHints"]

            if new_concepts is not None:
                st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"][idx]["selectAny"] = new_concepts

            if new_compute is not None:
                st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"][idx]["computeAny"] = new_compute

            # Delete rule button
            if st.button(f"🗑️ Delete Rule {idx + 1}", key=f"delete_rule_{idx}"):
                st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"].pop(idx)
                st.rerun()

    # Add new rule
    st.divider()
    if st.button("➕ Add New Rule"):
        new_rule = {
            "name": "New Rule",
            "priority": 100,
            "selectAny": []
        }
        st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["rules"].append(new_rule)
        st.rerun()

    # Update standardLabel
    st.session_state.modified_schemas[selected_schema]["fields"][selected_field]["standardLabel"] = new_label


# =============================================================================
# Page: Validation
# =============================================================================

def page_validation(schemas: Dict[str, Dict]):
    """Validation page."""
    st.header("✅ Schema Validation")

    # Use modified schemas if available
    if "modified_schemas" in st.session_state:
        schemas_to_validate = st.session_state.modified_schemas
        st.info("Validating modified schemas from editor.")
    else:
        schemas_to_validate = schemas

    schema_select = st.selectbox(
        "Select schema to validate",
        options=["All Schemas"] + list(SCHEMA_FILES.keys())
    )

    if st.button("🔍 Run Validation"):
        all_issues = []

        if schema_select == "All Schemas":
            for name, schema in schemas_to_validate.items():
                issues = validate_schema(name, schema)
                for issue in issues:
                    issue["schema"] = name
                all_issues.extend(issues)
        else:
            issues = validate_schema(schema_select, schemas_to_validate[schema_select])
            for issue in issues:
                issue["schema"] = schema_select
            all_issues.extend(issues)

        # Store results in session state
        st.session_state.validation_results = all_issues

    # Display results
    if "validation_results" in st.session_state:
        issues = st.session_state.validation_results

        if not issues:
            st.success("✅ No issues found!")
            return

        # Summary
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]
        infos = [i for i in issues if i["severity"] == "info"]

        col1, col2, col3 = st.columns(3)
        col1.metric("🔴 Errors", len(errors))
        col2.metric("🟠 Warnings", len(warnings))
        col3.metric("🔵 Info", len(infos))

        # Filter by category
        categories = list(set(i.get("category", "other") for i in issues))
        selected_cats = st.multiselect("Filter by category", categories, default=categories)

        # Display issues
        st.subheader("Issues")
        for issue in issues:
            if issue.get("category", "other") in selected_cats:
                render_validation_issue(issue)
                st.divider()


# =============================================================================
# Page: Comparison
# =============================================================================

def page_comparison(schemas: Dict[str, Dict]):
    """Schema comparison page."""
    st.header("🔄 Schema Comparison")

    col1, col2 = st.columns(2)

    with col1:
        schema1_name = st.selectbox("Schema 1", list(SCHEMA_FILES.keys()), key="cmp1")
    with col2:
        schema2_name = st.selectbox("Schema 2", list(SCHEMA_FILES.keys()), index=1, key="cmp2")

    schema1 = schemas[schema1_name]
    schema2 = schemas[schema2_name]

    fields1 = set(schema1.get("fields", {}).keys())
    fields2 = set(schema2.get("fields", {}).keys())

    # Field overlap analysis
    st.subheader("Field Analysis")

    common = fields1 & fields2
    only1 = fields1 - fields2
    only2 = fields2 - fields1

    col1, col2, col3 = st.columns(3)
    col1.metric("Common Fields", len(common))
    col2.metric(f"Only in {schema1_name}", len(only1))
    col3.metric(f"Only in {schema2_name}", len(only2))

    # Show details
    if common:
        with st.expander(f"Common Fields ({len(common)})"):
            for f in sorted(common):
                st.write(f"• {f}")

    if only1:
        with st.expander(f"Only in {schema1_name} ({len(only1)})"):
            for f in sorted(only1):
                st.write(f"• {f}")

    if only2:
        with st.expander(f"Only in {schema2_name} ({len(only2)})"):
            for f in sorted(only2):
                st.write(f"• {f}")

    # Concept overlap
    st.subheader("Concept Overlap Analysis")

    concepts1 = set()
    concepts2 = set()

    for field_data in schema1.get("fields", {}).values():
        for rule in field_data.get("rules", []):
            concepts1.update(rule.get("selectAny", []))

    for field_data in schema2.get("fields", {}).values():
        for rule in field_data.get("rules", []):
            concepts2.update(rule.get("selectAny", []))

    common_concepts = concepts1 & concepts2

    if common_concepts:
        st.write(f"**{len(common_concepts)} concepts** are used in both schemas:")
        with st.expander("Show common concepts"):
            for c in sorted(common_concepts):
                st.code(c)


# =============================================================================
# Page: Export
# =============================================================================

def page_export(schemas: Dict[str, Dict]):
    """Export page."""
    st.header("💾 Export & Save")

    if "modified_schemas" not in st.session_state:
        st.info("No modifications made. Edit schemas first in the Field Editor tab.")
        return

    modified = st.session_state.modified_schemas

    for schema_name in SCHEMA_FILES.keys():
        original = schemas[schema_name]
        current = modified[schema_name]

        original_json = json.dumps(original, indent='\t')
        current_json = json.dumps(current, indent='\t')

        if original_json != current_json:
            st.subheader(f"📄 {schema_name}")
            st.warning("Schema has been modified")

            # Show diff
            with st.expander("Show Diff"):
                diff = compute_diff(original_json, current_json)
                if diff:
                    st.code(diff, language="diff")
                else:
                    st.write("No differences")

            # Download button
            st.download_button(
                label=f"⬇️ Download {schema_name}",
                data=current_json,
                file_name=SCHEMA_FILES[schema_name],
                mime="application/json"
            )

            # Save to disk
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save to Disk", key=f"save_{schema_name}"):
                    if save_schema(schema_name, current):
                        st.success(f"Saved {schema_name}!")
                        # Clear cache to reload
                        st.cache_data.clear()
            with col2:
                if st.button("↩️ Revert Changes", key=f"revert_{schema_name}"):
                    st.session_state.modified_schemas[schema_name] = json.loads(json.dumps(original))
                    st.success("Reverted!")
                    st.rerun()

            st.divider()
        else:
            st.success(f"✅ {schema_name} - No changes")


# =============================================================================
# Main App
# =============================================================================

def main():
    st.set_page_config(
        page_title="XBRL Schema Editor",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 XBRL Schema Editor")
    st.caption("View, search, edit, and validate XBRL mapping schemas")

    # Load schemas
    schemas = load_all_schemas()

    if not schemas:
        st.error("Failed to load schemas. Check the schemas directory.")
        return

    # Sidebar - Quick Stats
    with st.sidebar:
        st.header("📈 Schema Stats")
        for name, schema in schemas.items():
            fields = len(schema.get("fields", {}))
            rules = sum(len(f.get("rules", [])) for f in schema.get("fields", {}).values())
            st.metric(name, f"{fields} fields", f"{rules} rules")

        st.divider()

        # Quick actions
        st.header("⚡ Quick Actions")
        if st.button("🔄 Reload Schemas"):
            st.cache_data.clear()
            if "modified_schemas" in st.session_state:
                del st.session_state.modified_schemas
            st.rerun()

        if st.button("🗑️ Clear All Edits"):
            if "modified_schemas" in st.session_state:
                del st.session_state.modified_schemas
            st.success("Cleared!")
            st.rerun()

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Search & Browse",
        "✏️ Field Editor",
        "✅ Validation",
        "🔄 Comparison",
        "💾 Export"
    ])

    with tab1:
        page_search(schemas)

    with tab2:
        page_editor(schemas)

    with tab3:
        page_validation(schemas)

    with tab4:
        page_comparison(schemas)

    with tab5:
        page_export(schemas)


if __name__ == "__main__":
    main()
