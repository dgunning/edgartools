"""
XBRL Parser Coordinator.

This module provides the main XBRLParser class that coordinates parsing
workflow across all specialized parser components while maintaining
API compatibility with the original monolithic parser.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from edgar.core import log
from edgar.xbrl.models import (
    Axis,
    CalculationTree,
    Context,
    Domain,
    ElementCatalog,
    Fact,
    PresentationTree,
    Table,
    XBRLProcessingError,
)

from .calculation import CalculationParser
from .definition import DefinitionParser
from .instance import InstanceParser
from .labels import LabelsParser
from .presentation import PresentationParser
from .schema import SchemaParser


class XBRLParser:
    """
    Coordinated XBRL parser that delegates to specialized component parsers.

    This class maintains full API compatibility with the original monolithic
    XBRLParser while providing improved maintainability through component separation.
    """

    def __init__(self):
        """Initialize the coordinated XBRL parser with all data structures."""
        # Core data structures
        self.element_catalog: Dict[str, ElementCatalog] = {}
        self.contexts: Dict[str, Context] = {}
        self.facts: Dict[str, Fact] = {}
        self.units: Dict[str, Any] = {}
        self.footnotes: Dict[str, Any] = {}

        # Presentation structures
        self.presentation_roles: Dict[str, Dict[str, Any]] = {}
        self.presentation_trees: Dict[str, PresentationTree] = {}

        # Calculation structures
        self.calculation_roles: Dict[str, Dict[str, Any]] = {}
        self.calculation_trees: Dict[str, CalculationTree] = {}

        # Definition (dimensional) structures
        self.definition_roles: Dict[str, Dict[str, Any]] = {}
        self.tables: Dict[str, List[Table]] = {}
        self.axes: Dict[str, Axis] = {}
        self.domains: Dict[str, Domain] = {}

        # Entity information
        self.entity_info: Dict[str, Any] = {}
        self.dei_facts: Dict[str, Fact] = {}

        # Reporting periods
        self.reporting_periods: List[Dict[str, Any]] = []

        # Mapping of context IDs to period identifiers for easy lookup
        self.context_period_map: Dict[str, str] = {}

        # Initialize component parsers
        self._init_parsers()

    def _init_parsers(self):
        """Initialize all component parsers with shared data structures."""
        # Create component parsers with references to shared data structures
        self.schema_parser = SchemaParser(
            element_catalog=self.element_catalog
        )

        self.labels_parser = LabelsParser(
            element_catalog=self.element_catalog
        )

        self.presentation_parser = PresentationParser(
            presentation_roles=self.presentation_roles,
            presentation_trees=self.presentation_trees,
            element_catalog=self.element_catalog
        )

        self.calculation_parser = CalculationParser(
            calculation_roles=self.calculation_roles,
            calculation_trees=self.calculation_trees,
            element_catalog=self.element_catalog,
            facts=self.facts
        )

        self.definition_parser = DefinitionParser(
            definition_roles=self.definition_roles,
            tables=self.tables,
            axes=self.axes,
            domains=self.domains,
            element_catalog=self.element_catalog
        )

        self.instance_parser = InstanceParser(
            contexts=self.contexts,
            facts=self.facts,
            units=self.units,
            footnotes=self.footnotes,
            calculation_trees=self.calculation_trees,
            entity_info=self.entity_info,
            reporting_periods=self.reporting_periods,
            context_period_map=self.context_period_map
        )

        # Set up cross-references for embedded linkbase processing
        self.schema_parser.set_linkbase_parsers(
            labels_parser=self.labels_parser,
            presentation_parser=self.presentation_parser,
            calculation_parser=self.calculation_parser,
            definition_parser=self.definition_parser
        )

    def _create_normalized_fact_key(self, element_id: str, context_ref: str, instance_id: Optional[int] = None) -> str:
        """
        Create a normalized fact key using underscore format.

        Args:
            element_id: The element ID
            context_ref: The context reference
            instance_id: Optional instance ID for duplicate facts

        Returns:
            Normalized key in format: element_id_context_ref[_instance_id]
        """
        return self.instance_parser._create_normalized_fact_key(element_id, context_ref, instance_id)

    def get_facts_by_key(self, element_id: str, context_ref: str) -> List[Fact]:
        """Get all facts matching the given element ID and context reference.

        This method handles both single facts and duplicate facts using the hybrid storage approach.
        For single facts, it returns a list with one fact. For duplicates, it returns all instances.

        Args:
            element_id: The element ID to look up
            context_ref: The context reference

        Returns:
            List of matching facts
        """
        # Create base key for lookup
        base_key = self._create_normalized_fact_key(element_id, context_ref)

        # Check if single fact exists
        if base_key in self.facts:
            return [self.facts[base_key]]

        # Check for duplicate facts (with instance IDs)
        matching_facts = []
        instance_id = 0
        while True:
            instance_key = self._create_normalized_fact_key(element_id, context_ref, instance_id)
            if instance_key in self.facts:
                matching_facts.append(self.facts[instance_key])
                instance_id += 1
            else:
                break

        return matching_facts

    def get_fact(self, element_id: str, context_ref: str) -> Optional[Fact]:
        """Get a single fact by element ID and context reference.

        Returns the first fact if multiple instances exist.

        Args:
            element_id: The element ID to look up
            context_ref: The context reference

        Returns:
            The fact if found, None otherwise
        """
        facts = self.get_facts_by_key(element_id, context_ref)
        return facts[0] if facts else None

    def parse_directory(self, directory_path: Union[str, Path]) -> None:
        """
        Parse all XBRL files in a directory.

        Args:
            directory_path: Path to directory containing XBRL files
        """
        try:
            directory = Path(directory_path)
            if not directory.is_dir():
                raise XBRLProcessingError(f"Directory not found: {directory_path}")

            log.debug(f"Parsing XBRL directory: {directory}")

            # Parse schema files first to build element catalog
            schema_files = list(directory.glob('*.xsd'))
            for schema_file in schema_files:
                log.debug(f"Parsing schema: {schema_file}")
                self.schema_parser.parse_schema(schema_file)

            # Parse linkbase files
            linkbase_patterns = [
                ('*_lab.xml', self.labels_parser.parse_labels),
                ('*_pre.xml', self.presentation_parser.parse_presentation),
                ('*_cal.xml', self.calculation_parser.parse_calculation),
                ('*_def.xml', self.definition_parser.parse_definition),
            ]

            for pattern, parser_method in linkbase_patterns:
                linkbase_files = list(directory.glob(pattern))
                for linkbase_file in linkbase_files:
                    log.debug(f"Parsing linkbase: {linkbase_file}")
                    parser_method(linkbase_file)

            # Parse instance files last (they depend on schemas and linkbases)
            instance_files = list(directory.glob('*.xml'))
            # Filter out linkbase files
            instance_files = [f for f in instance_files if not any(
                f.name.endswith(suffix) for suffix in ['_lab.xml', '_pre.xml', '_cal.xml', '_def.xml']
            )]

            for instance_file in instance_files:
                log.debug(f"Parsing instance: {instance_file}")
                self.instance_parser.parse_instance(instance_file)

            log.info(f"Successfully parsed XBRL directory with {len(self.facts)} facts")

        except Exception as e:
            raise XBRLProcessingError(f"Error parsing directory {directory_path}: {str(e)}") from e

    # Delegate methods to component parsers for API compatibility
    def parse_schema(self, file_path: Union[str, Path]) -> None:
        """Parse schema file and extract element information."""
        return self.schema_parser.parse_schema(file_path)

    def parse_schema_content(self, content: str) -> None:
        """Parse schema content and extract element information."""
        return self.schema_parser.parse_schema_content(content)

    def parse_labels(self, file_path: Union[str, Path]) -> None:
        """Parse label linkbase file and extract label information."""
        return self.labels_parser.parse_labels(file_path)

    def parse_labels_content(self, content: str) -> None:
        """Parse label linkbase content and extract label information."""
        return self.labels_parser.parse_labels_content(content)

    def parse_presentation(self, file_path: Union[str, Path]) -> None:
        """Parse presentation linkbase file and build presentation trees."""
        return self.presentation_parser.parse_presentation(file_path)

    def parse_presentation_content(self, content: str) -> None:
        """Parse presentation linkbase content and build presentation trees."""
        return self.presentation_parser.parse_presentation_content(content)

    def parse_calculation(self, file_path: Union[str, Path]) -> None:
        """Parse calculation linkbase file and build calculation trees."""
        return self.calculation_parser.parse_calculation(file_path)

    def parse_calculation_content(self, content: str) -> None:
        """Parse calculation linkbase content and build calculation trees."""
        return self.calculation_parser.parse_calculation_content(content)

    def parse_definition(self, file_path: Union[str, Path]) -> None:
        """Parse definition linkbase file and build dimensional structures."""
        return self.definition_parser.parse_definition(file_path)

    def parse_definition_content(self, content: str) -> None:
        """Parse definition linkbase content and build dimensional structures."""
        return self.definition_parser.parse_definition_content(content)

    def parse_instance(self, file_path: Union[str, Path]) -> None:
        """Parse instance document file and extract contexts, facts, and units."""
        return self.instance_parser.parse_instance(file_path)

    def parse_instance_content(self, content: str) -> None:
        """Parse instance document content and extract contexts, facts, and units."""
        return self.instance_parser.parse_instance_content(content)

    def count_facts(self, content: str) -> tuple:
        """Count the number of facts in the instance document."""
        return self.instance_parser.count_facts(content)
