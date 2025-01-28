from dataclasses import dataclass
from typing import List, Optional, Dict, Union
from bs4 import BeautifulSoup
from edgar.xmltools import child_text
from edgar.core import strtobool, DataPager, PagingState, log
from edgar.richtools import repr_rich
from rich.console import Group
from rich.table import Table
from rich.panel import Panel
from rich import box
import pyarrow as pa
import pyarrow.compute as pc

__all__ = ['Report', 'File', 'FilingSummary']

class Reports:

    def __init__(self,
                 data:pa.Table,
                 original_state: Optional[PagingState] = None):
        self.data:pa.Table = data
        self.data_pager = DataPager(data)
        self._original_state = original_state or PagingState(0, len(self.data))

    def __len__(self):
        return len(self.data)

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

    @staticmethod
    def create_from_record(data:pa.Table):
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
                position=data['Position'][0].as_py()
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
        return Reports(data)

    def get_by_filename(self, file_name: str):
        """
        Get a single report by file name
        """
        data = self.data.filter(pc.equal(self.data['HtmlFileName'], file_name))
        if len(data) ==1:
            return Reports.create_from_record(data)

    def get_by_short_name(self, short_name: str):
        """
        Get a single report by short name
        """
        data = self.data.filter(pc.equal(self.data['ShortName'], short_name))
        if len(data) == 1:
            return Reports.create_from_record(data)

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
            return Reports.create_from_record(data)
        return Reports(data)

    def __rich__(self):
        table = Table(
            title="Reports",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
            box=box.SIMPLE
        )
        table.add_column("#", justify="left")
        table.add_column("Short Name", style="dim", width=40)
        table.add_column("Category", justify="left")
        table.add_column("File Name", justify="left")

        # Get current page from data pager
        current_page = self.data_pager.current()

        # Iterate through rows in current page
        for i in range(len(current_page)):
            position = current_page['Position'][i].as_py()

            row = [
                str(position) if position else "-",
                current_page['ShortName'][i].as_py(),
                current_page['MenuCategory'][i].as_py() or "",
                current_page['HtmlFileName'][i].as_py() or ""
            ]
            table.add_row(*row)

        elements=[table]

        return Panel(
            Group(*elements),
            title="Reports",
            border_style="bold grey54"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

@dataclass
class Report:
    is_default: bool
    has_embedded_reports: bool
    long_name: str
    short_name: str
    menu_category: Optional[str]
    position:Optional[int]
    instance: Optional[str]
    html_file_name: Optional[str]
    report_type: Optional[str]
    role: Optional[str]
    parent_role: Optional[str] = None

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

    @property
    def statements(self):
        return self.get_reports_by_category('Statements')

    @property
    def tables(self):
        return self.get_reports_by_category('Tables')

    def __str__(self):
        return f"FilingSummary(report_format={self.report_format})"



