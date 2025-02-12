import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Set, Tuple
from typing import Optional, Union

import pyarrow as pa
import pyarrow.compute as pc
from bs4 import BeautifulSoup
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.core import strtobool, DataPager, PagingState, log
from edgar.files.html import Document
from edgar.richtools import print_rich
from edgar.richtools import repr_rich, rich_to_text
from edgar.xmltools import child_text
from functools import lru_cache

__all__ = ['Report', 'Reports', 'File', 'FilingSummary']

class Reports:

    """
    A collection of reports in a filing summary
    """

    def __init__(self,
                 data:pa.Table,
                 filing_summary: Optional['FilingSummary'] = None,
                 original_state: Optional[PagingState] = None,
                 title: Optional[str] = "Reports"):
        self.data:pa.Table = data
        self.data_pager = DataPager(data)
        self._original_state = original_state or PagingState(0, len(self.data))
        self.n = 0
        self._filing_summary = filing_summary
        self.title = title

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        self.n = 0
        return self

    def __next__(self):
        if self.n < len(self.data):
            report = Report(
                instance=self.data['instance'][self.n].as_py(),
                is_default=self.data['IsDefault'][self.n].as_py(),
                has_embedded_reports=self.data['HasEmbeddedReports'][self.n].as_py(),
                html_file_name=self.data['HtmlFileName'][self.n].as_py(),
                long_name=self.data['LongName'][self.n].as_py(),
                report_type=self.data['ReportType'][self.n].as_py(),
                role=self.data['Role'][self.n].as_py(),
                parent_role=self.data['ParentRole'][self.n].as_py(),
                short_name=self.data['ShortName'][self.n].as_py(),
                menu_category=self.data['MenuCategory'][self.n].as_py(),
                position=self.data['Position'][self.n].as_py(),
                reports = self
            )
            self.n += 1
            return report
        else:
            raise StopIteration

    def current(self):
        """Display the current page ... which is the default for this filings object"""
        return self

    def next(self):
        """Show the next page"""
        data_page = self.data_pager.next()
        if data_page is None:
            log.warning("End of data .. use prev() \u2190 ")
            return None
        start_index, _ = self.data_pager._current_range
        paging_state = PagingState(page_start=start_index, num_records=len(self))
        return Reports(data_page, original_state=paging_state)

    def previous(self):
        """
        Show the previous page of the data
        :return:
        """
        data_page = self.data_pager.previous()
        if data_page is None:
            log.warning(" No previous data .. use next() \u2192 ")
            return None
        start_index, _ = self.data_pager._current_range
        paging_state = PagingState(page_start=start_index, num_records=len(self))
        return Reports(data_page, original_state=paging_state)

    def to_pandas(self):
        return self.data.to_pandas()

    def __getitem__(self, item):
        record = self.filter("Position", str(item))
        if record:
            return record


    def create_from_record(self, data:pa.Table):
        return Report(
                instance=data['instance'][0].as_py(),
                is_default=data['IsDefault'][0].as_py(),
                has_embedded_reports=data['HasEmbeddedReports'][0].as_py(),
                html_file_name=data['HtmlFileName'][0].as_py(),
                long_name=data['LongName'][0].as_py(),
                report_type=data['ReportType'][0].as_py(),
                role=data['Role'][0].as_py(),
                parent_role=data['ParentRole'][0].as_py(),
                short_name=data['ShortName'][0].as_py(),
                menu_category=data['MenuCategory'][0].as_py(),
                position=data['Position'][0].as_py(),
                reports = self
            )

    @property
    def long_names(self) -> List[str]:
        return self.data['LongName'].to_pylist()

    @property
    def short_names(self) -> List[str]:
        return self.data['ShortName'].to_pylist()

    def get_by_category(self, category: str):
        """
        Get a single report by category
        """
        data = self.data.filter(pc.equal(self.data['MenuCategory'], category))
        return Reports(data, filing_summary=self._filing_summary, title=category)

    @property
    def statements(self) -> Optional['Statements']:
        """
        Get all reports in the Statements category
        """
        reports = self.get_by_category('Statements')
        if reports:
            return Statements(reports)

    def get_by_filename(self, file_name: str):
        """
        Get a single report by file name
        """
        data = self.data.filter(pc.equal(self.data['HtmlFileName'], file_name))
        if len(data) ==1:
            return self.create_from_record(data)

    def get_by_short_name(self, short_name: str):
        """
        Get a single report by short name
        """
        data = self.data.filter(pc.equal(self.data['ShortName'], short_name))
        if len(data) == 1:
            return self.create_from_record(data)

    def filter(self, column: Union[str, List[str]], value: Union[str, List[str]]):
        if isinstance(column, str):
            column = [column]
        if isinstance(value, str):
            value = [value]
        # Convert value list to a pyarrow array for proper comparison
        value_set = pa.array(value)
        # Initialize mask using the first column
        mask = pc.is_in(self.data[column[0]], value_set)
        # Combine with subsequent columns using logical AND
        for col in column[1:]:
            mask = pc.and_(mask, pc.is_in(self.data[col], value_set))
        # Apply the mask to filter the data
        data = self.data.filter(mask)
        # Return a single Report or new Reports instance
        if len(data) == 1:
            return self.create_from_record(data)
        return Reports(data)

    def __rich__(self):
        table = Table(
            show_header=True,
            header_style="dim",
            show_lines=True,
            box=box.SIMPLE,
            border_style="bold grey54",
            row_styles=["", "bold"]
        )
        table.add_column("#", style="dim", justify="left")
        table.add_column("Report", style="bold", width=60)
        table.add_column("Category", width=12)
        table.add_column("File", justify="left")

        # Iterate through rows in current page
        for i in range(len(self)):
            position = self.data['Position'][i].as_py()

            row = [
                str(position) if position else "-",
                self.data['ShortName'][i].as_py(),
                self.data['MenuCategory'][i].as_py() or "",
                self.data['HtmlFileName'][i].as_py() or ""
            ]
            table.add_row(*row)

        panel = Panel(table, title=self.title, expand=False)
        return panel

    def __repr__(self):
        return repr_rich(self.__rich__())


class Report:

    def __init__(self,
                 instance: Optional[str],
                 is_default: Optional[bool],
                 has_embedded_reports: Optional[bool],
                 long_name: Optional[str],
                 short_name: Optional[str],
                 menu_category: Optional[str],
                 position: Optional[int],
                 html_file_name: Optional[str],
                 report_type: Optional[str],
                 role: Optional[str],
                 parent_role: Optional[str] = None,
                 reports = None):
        self.instance = instance
        self.is_default = is_default
        self.has_embedded_reports = has_embedded_reports
        self.long_name = long_name
        self.short_name = short_name
        self.menu_category = menu_category
        self.position = position
        self.html_file_name = html_file_name
        self.report_type = report_type
        self.role = role
        self.parent_role = parent_role
        self._reports = reports

    @property
    def content(self):
        """
        Get the content of the report
        """
        sgml = self._reports._filing_summary._filing_sgml
        if sgml:
            return sgml.get_content(self.html_file_name)

    def text(self):
        """
        Get the text content of the report
        """
        table = self._get_report_table()
        if table:
            return rich_to_text(table.render(500))

    @lru_cache
    def _get_report_table(self):
        """
        Get the first table in the document
        """
        document = Document.parse(self.content)
        if len(document.tables) == 0:
            log.warning(f"No tables found in {self.html_file_name}")
            return None
        return document.tables[0]

    def view(self):
        table = self._get_report_table()
        if table:
            print_rich(table.render(500))

    def __str__(self):
        return f"Report(short_name={self.short_name}, category={self.menu_category}, file_name={self.html_file_name})"

    def __rich__(self):
        return Panel(
            Text.assemble(("Report ", "dim"), (self.long_name, "bold")),
            subtitle=Text(self.menu_category, style='dim italic'),
            expand=False,
            width=400,
            height=4
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

@dataclass
class File:
    file_name: str
    doc_type: Optional[str]
    is_definitely_fs: Optional[bool]
    is_usgaap: Optional[bool]
    original: Optional[str]

class FilingSummary:

    def __init__(self,
                    reports: Reports,
                    short_name_map: Dict[str, Report],
                    category_map: Dict[str, List[Report]],
                    input_files: List[File],
                    supplemental_files: List[File],
                    report_format: Optional[str] = None,
                    context_count: Optional[int] = None,
                    element_count: Optional[int] = None,
                    entity_count: Optional[int] = None,
                    footnotes_reported: Optional[bool] = None,
                    segment_count: Optional[int] = None,
                    scenario_count: Optional[int] = None,
                    tuples_reported: Optional[bool] = None,
                    has_presentation_linkbase: Optional[bool] = None,
                    has_calculation_linkbase: Optional[bool] = None):
        self.reports:Reports = reports
        self.reports._filing_summary = self
        self._short_name_map = short_name_map
        self._category_map = category_map
        self.input_files = input_files
        self.supplemental_files = supplemental_files
        self.report_format = report_format
        self.context_count = context_count
        self.element_count = element_count
        self.entity_count = entity_count
        self.footnotes_reported = footnotes_reported
        self.segment_count = segment_count
        self.scenario_count = scenario_count
        self.tuples_reported = tuples_reported
        self.has_presentation_linkbase = has_presentation_linkbase
        self.has_calculation_linkbase = has_calculation_linkbase
        self._filing_sgml = None

    @classmethod
    def parse(cls, xml_text:str):
        soup = BeautifulSoup(xml_text, 'xml')
        root = soup.find('FilingSummary')

        # Main fields
        report_format = child_text(root, 'ReportFormat')
        context_count = child_text(root, 'ContextCount')
        element_count = child_text(root, 'ElementCount')
        entity_count = child_text(root, 'EntityCount')
        footnotes_reported = strtobool(child_text(root, 'FootnotesReported'))
        segment_count = child_text(root, 'SegmentCount')
        scenario_count = child_text(root, 'ScenarioCount')
        tuples_reported = strtobool(child_text(root, 'TuplesReported'))
        has_presentation_linkbase = strtobool(child_text(root, 'HasPresentationLinkbase'))
        has_calculation_linkbase = strtobool(child_text(root, 'HasCalculationLinkbase'))
        # Reports
        reports: List[Report] = []
        short_name_map: Dict[str, Report] = {}
        category_map: Dict[str, List[Report]] = {}
        report_records = []
        for report_tag in root.find_all("Report"):
            record = {
                'instance': report_tag.get('instance'),
                'IsDefault': strtobool(child_text(report_tag, 'IsDefault')),
                'HasEmbeddedReports': strtobool(child_text(report_tag, 'HasEmbeddedReports')),
                'HtmlFileName': child_text(report_tag, 'HtmlFileName'),
                'LongName': child_text(report_tag, 'LongName'),
                'ReportType': child_text(report_tag, 'ReportType'),
                'Role': child_text(report_tag, 'Role'),
                'ParentRole': child_text(report_tag, 'ParentRole'),
                'ShortName': child_text(report_tag, 'ShortName'),
                'MenuCategory': child_text(report_tag, 'MenuCategory'),
                'Position': child_text(report_tag, 'Position')
            }
            report = Report(
                instance = report_tag.get('instance'),
                is_default = strtobool(child_text(report_tag, 'IsDefault')),
                has_embedded_reports = strtobool(child_text(report_tag, 'HasEmbeddedReports')),
                html_file_name = child_text(report_tag, 'HtmlFileName'),
                long_name = child_text(report_tag, 'LongName'),
                report_type = child_text(report_tag, 'ReportType'),
                role = child_text(report_tag, 'Role'),
                parent_role=child_text(report_tag, 'ParentRole'),
                short_name = child_text(report_tag, 'ShortName'),
                menu_category = child_text(report_tag, 'MenuCategory'),
                position = child_text(report_tag, 'Position')
            )
            reports.append(report)
            report_records.append(record)
            short_name_map[report.short_name] = report
            if report.menu_category not in category_map:
                category_map[report.menu_category] = []
            category_map[report.menu_category].append(report)

        # Reports Data
        reports_obj = Reports(data=pa.Table.from_pylist(report_records))
        # Input Files
        input_files_tag = root.find('InputFiles')
        input_files = []
        if input_files_tag:
            for file_tag in input_files_tag.find_all('File'):
                file = File(
                        file_name = file_tag.text,
                        doc_type = file_tag.get('doctype'),
                        is_definitely_fs = strtobool(file_tag.get('isDefinitelyFs')),
                        is_usgaap = strtobool(file_tag.get('isUsgaap')),
                        original = file_tag.get('original')
                )
                input_files.append(file)

        # Supplemental Files
        supplemental_files_tag = root.find('SupplementalFiles')
        supplemental_files = []
        if supplemental_files_tag:
            for file_tag in supplemental_files_tag.find_all('File'):
                file = File(
                        file_name = file_tag.text,
                        doc_type = file_tag.get('doctype'),
                        is_definitely_fs = strtobool(file_tag.get('isDefinitelyFs')),
                        is_usgaap = strtobool(file_tag.get('isUsgaap')),
                        original = file_tag.get('original')
                )
                supplemental_files.append(file)
        return cls( report_format=report_format,
                    short_name_map=short_name_map,
                    category_map=category_map,
                    context_count=context_count,
                    element_count=element_count,
                    entity_count=entity_count,
                    footnotes_reported=footnotes_reported,
                    segment_count=segment_count,
                    scenario_count=scenario_count,
                    tuples_reported=tuples_reported,
                    has_presentation_linkbase=has_presentation_linkbase,
                    has_calculation_linkbase=has_calculation_linkbase,
                    reports=reports_obj,
                    input_files=input_files,
                    supplemental_files=supplemental_files)

    def get_report_by_short_name(self, short_name: str) -> Optional[Report]:
        return self.reports.get_by_short_name(short_name)

    def get_reports_by_category(self, category: str) -> Reports:
        return self.reports.get_by_category(category)

    def get_reports_by_filename(self, file_name: str) -> Optional[Report]:
        return self.reports.get_by_filename(file_name)

    @property
    def statements(self):
        reports = self.get_reports_by_category('Statements')
        return Statements(reports)

    @property
    def tables(self):
        return self.get_reports_by_category('Tables')

    def __str__(self):
        return f"FilingSummary(report_format={self.report_format})"


    def __rich__(self):
        renderables = [self.reports]
        return Panel(
            Group(*renderables),
            box=box.ROUNDED,
            title="Filing Summary"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class StatementType(Enum):
    INCOME = "income"
    BALANCE = "balance"
    CASH_FLOW = "cash_flow"
    COMPREHENSIVE_INCOME = "comprehensive_income"
    EQUITY = "equity"


class StatementMapper:
    def __init__(self):
        # Define pattern matchers for each statement type
        self.patterns = {
            StatementType.INCOME: [
                (r'(?i)statement.*of.*(?:operation|income|earning)s?(?!\s+and\s+comprehensive)', 3),
                # High confidence direct match
                (r'(?i)(?:operation|income|earning)s?\s+statement', 2),  # Alternative format
                (r'(?i)profit.*loss', 1),  # P&L reference
            ],
            StatementType.BALANCE: [
                (r'(?i)balance\s*sheet', 3),  # Very consistent naming
                (r'(?i)statement.*of.*financial\s+position', 2),  # Alternative format
            ],
            StatementType.CASH_FLOW: [
                (r'(?i)statement.*of.*cash\s*flows?', 3),  # Primary pattern
                (r'(?i)cash\s*flows?\s*statement', 2),  # Alternative format
            ],
            StatementType.COMPREHENSIVE_INCOME: [
                (r'(?i)statement.*of.*comprehensive\s*(?:income|loss)', 3),  # Primary pattern
                (r'(?i)comprehensive\s*(?:income|loss)\s*statement', 2),  # Alternative format
            ],
            StatementType.EQUITY: [
                (r'(?i)statement.*of.*(?:stockholders|shareholders|owners)[\'\s]*equity', 3),  # Primary pattern
                (r'(?i)statement.*of.*changes\s+in\s+(?:stockholders|shareholders|owners)[\'\s]*equity', 3),
                # With "changes in"
                (r'(?i)statement.*of.*equity', 2),  # Generic equity
            ]
        }

        # Define combined statement patterns
        self.combined_patterns = [
            (r'(?i)statement.*of.*operations?\s+and\s+comprehensive\s*(?:income|loss)',
             {StatementType.INCOME, StatementType.COMPREHENSIVE_INCOME}),
        ]

    def normalize_statement(self, statement: str) -> str:
        """Normalize statement name by removing common variations."""
        statement = statement.strip().upper()
        # Remove common prefixes if they exist
        prefixes = ['CONSOLIDATED', 'COMBINED']
        for prefix in prefixes:
            if statement.startswith(prefix):
                statement = statement[len(prefix):].strip()
        return statement

    def match_statement(self, statement: str) -> Dict[StatementType, float]:
        """
        Match a statement name to possible statement types with confidence scores.
        Returns a dictionary of {StatementType: confidence_score}
        """
        normalized = self.normalize_statement(statement)
        scores: Dict[StatementType, float] = {}

        # First check for combined statements
        for pattern, types in self.combined_patterns:
            if re.search(pattern, normalized):
                for stmt_type in types:
                    scores[stmt_type] = 1.0
                return scores

        # Then check individual patterns
        for stmt_type, patterns in self.patterns.items():
            max_score = 0
            for pattern, weight in patterns:
                if re.search(pattern, normalized):
                    max_score = max(max_score, weight / 3.0)  # Normalize to 0-1 range
            if max_score > 0:
                scores[stmt_type] = max_score

        return scores

    def classify_statement(self, statement: str, threshold: float = 0.5) -> Set[StatementType]:
        """
        Classify a statement into one or more statement types.
        Returns a set of StatementType enums.
        """
        scores = self.match_statement(statement)
        return {stmt_type for stmt_type, score in scores.items() if score >= threshold}

    def get_best_matches(self, statements: List[str]) -> Dict[StatementType, str]:
        """
        Given a list of statement names, returns the best matching statement
        for each statement type.
        """
        result: Dict[StatementType, Tuple[str, float]] = {}

        for statement in statements:
            scores = self.match_statement(statement)
            for stmt_type, score in scores.items():
                if (stmt_type not in result or
                        score > result[stmt_type][1]):
                    result[stmt_type] = (statement, score)

        return {stmt_type: stmt for stmt_type, (stmt, _) in result.items()}


class Statements:

    """
    A wrapper class for detected financial statements in a filing summary.
    """
    def __init__(self, statement_reports:Reports):
        self._reports = statement_reports
        self.statements = [report.short_name for report in self._reports]
        self.mapper = StatementMapper()
        self._matches: Dict[StatementType, Tuple[str, float]] = {}
        self._initialize_matches()

    def _initialize_matches(self) -> None:
        """Initialize best matches for each statement type."""
        for statement in self.statements:
            scores = self.mapper.match_statement(statement)
            for stmt_type, score in scores.items():
                if (stmt_type not in self._matches or
                    score > self._matches[stmt_type][1]):
                    self._matches[stmt_type] = (statement, score)

    def _get_statement(self, stmt_type: StatementType, threshold: float = 0.5) -> Optional[Report]:
        """Helper method to get a statement of a specific type."""
        if stmt_type in self._matches:
            statement, score = self._matches[stmt_type]
            if score >= threshold:
                return self._reports.get_by_short_name(statement)
        return None

    def __getitem__(self, item):
        return self._reports[item]

    @property
    def balance_sheet(self) -> Optional[Report]:
        """Returns the detected balance sheet statement."""
        return self._get_statement(StatementType.BALANCE)

    @property
    def income_statement(self) -> Optional[Report]:
        """Returns the detected income statement."""
        return self._get_statement(StatementType.INCOME)

    @property
    def cash_flow_statement(self) -> Optional[Report]:
        """Returns the detected cash flow statement."""
        return self._get_statement(StatementType.CASH_FLOW)

    @property
    def comprehensive_income_statement(self) -> Optional[Report]:
        """Returns the detected comprehensive income statement."""
        return self._get_statement(StatementType.COMPREHENSIVE_INCOME)

    @property
    def equity_statement(self) -> Optional[Report]:
        """Returns the detected equity statement."""
        return self._get_statement(StatementType.EQUITY)

    @property
    def detected_statements(self) -> Dict[StatementType, str]:
        """Returns all detected statements with scores above threshold."""
        return {
            stmt_type: stmt for stmt_type, (stmt, score)
            in self._matches.items()
            if score >= 0.5
        }

    def __rich__(self):
        return self._reports


    def __repr__(self):
        return repr_rich(self.__rich__())