from typing import Optional

import pandas as pd
from rich.console import Group, Text

from edgar._party import Filer
from edgar.richtools import df_to_rich_table, repr_rich
from edgar.xmltools import child_text, find_element, parse_xml

__all__ = [
    'EffectiveData',
    'Effect'
]





class EffectiveData:
    """

    """

    def __init__(self,
                 final_effective_date: str,
                 file_number: str,
                 accession_no: Optional[str],
                 submission_type: Optional[str],
                 form: Optional[str],
                 filer: Filer
                 ):
        self.final_effective_date: str = final_effective_date
        self.file_number: Optional[str] = file_number
        self.accession_no: Optional[str] = accession_no
        self.form: Optional[str] = form
        self.submission_type: str = submission_type
        self.filer: Filer = filer


class Effect:
    """
    A edgar submission parsed from an EFFECT form xml
    """

    def __init__(self,
                 submission_type: str,
                 effectiveness_data: EffectiveData,
                 is_live: bool,
                 schema_version: Optional[str] = None
                 ):
        self.submission_type = submission_type
        self.effectiveness_data = effectiveness_data
        self.is_live = is_live
        self.schema_version = schema_version

    @property
    def effective_date(self) -> str:
        return self.effectiveness_data.final_effective_date

    @property
    def cik(self):
        if self.effectiveness_data.filer:
            return self.effectiveness_data.filer.cik

    @property
    def entity(self):
        if self.effectiveness_data.filer:
            return self.effectiveness_data.filer.entity_name

    @property
    def source_submission_type(self):
        return self.effectiveness_data.submission_type or self.effectiveness_data.form or ""

    @property
    def source_accession_no(self):
        return self.effectiveness_data.accession_no

    def get_source_filing(self):
        from edgar import get_entity
        if self.source_accession_no:
            """Search for the source filing using the accession number"""
            company = get_entity(int(self.cik))
            filings = company.get_filings(accession_number=self.source_accession_no)
            if len(filings) == 1:
                return filings[0]
        elif self.effectiveness_data.file_number and self.effectiveness_data.form:
            """Search for the source filing using the file number and form"""
            company = get_entity(int(self.cik))
            filings = company.get_filings(file_number=self.effectiveness_data.file_number,
                                          form=self.effectiveness_data.form)
            if len(filings) > 0:
                return filings[0]
        return None

    def summary(self) -> pd.DataFrame:
        if hasattr(self, '_cached_summary'):
            return self._cached_summary
        self._cached_summary = pd.DataFrame([{"cik": self.cik,
                              "entity": self.entity,
                              "source": self.source_submission_type or "",
                              "live": self.is_live,
                              "effective": self.effective_date}]).set_index("entity")
        return self._cached_summary

    def __str__(self):
        return (f"EffectSubmission(effective='{self.effective_date}', type='{self.submission_type}', "
                f"is_live={self.is_live}, entity='{self.entity}')")

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        lines = []

        # === IDENTITY ===
        lines.append(f"EFFECT: {self.entity}")
        lines.append("")

        # === CORE METADATA ===
        lines.append(f"Effective Date: {self.effective_date}")
        lines.append(f"Source Form: {self.source_submission_type}")
        if self.source_accession_no:
            lines.append(f"Source Accession: {self.source_accession_no}")

        if detail == 'minimal':
            return "\n".join(lines)

        # === STANDARD ===
        lines.append(f"CIK: {self.cik}")

        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .get_source_filing()       Navigate to the source filing")
        lines.append("  .summary()                 Summary as DataFrame")
        lines.append("  .effective_date            When the filing became effective")
        lines.append("  .source_submission_type    Form type that was made effective")

        return "\n".join(lines)

    def __rich__(self):
        return Group(Text(f"{self.submission_type} filing for form {self.source_submission_type} filing", style="bold"),
                     df_to_rich_table(self.summary(), index_name="entity")
                     )

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_xml(cls,
                 submission_xml: str):
        """
        <edgarSubmission>
            <schemaVersion>X0101</schemaVersion>
            <submissionType>EFFECT</submissionType>
            <act>33</act>
            <testOrLive>LIVE</testOrLive>
            <effectiveData>
                <finalEffectivenessDispDate>2022-11-22</finalEffectivenessDispDate>
                <accessionNumber>0000038723-22-000117</accessionNumber>
                <submissionType>POS AM</submissionType>
                <filer>
                    <cik>0000038723</cik>
                    <entityName>1st FRANKLIN FINANCIAL CORP</entityName>
                    <fileNumber>333-237642</fileNumber>
                </filer>
            </effectiveData>
        </edgarSubmission>
        """
        # <edgarSubmission> is this form's document element, so the parsed root is
        # already it — no search needed (edgartools-07lk.11.3).
        root = parse_xml(submission_xml)

        # The submission carries two <submissionType> elements: the outer one is the
        # EFFECT notice itself, the inner one the form being made effective. Both
        # reads below are descendant searches returning the first match in document
        # order, which is what picks them apart — the same way bs4 did.
        effectiveness_el = find_element(root, "effectiveData")
        filer_el = find_element(effectiveness_el, "filer")

        return cls(
            submission_type=child_text(root, "submissionType"),
            schema_version=child_text(root, "schemaVersion"),
            is_live=child_text(root, "testOrLive") == 'LIVE',
            effectiveness_data=EffectiveData(
                final_effective_date=child_text(effectiveness_el, "finalEffectivenessDispDate"),
                accession_no=child_text(effectiveness_el, "accessionNumber"),
                file_number=child_text(effectiveness_el, "fileNumber"),
                submission_type=child_text(effectiveness_el, "submissionType"),
                form=child_text(effectiveness_el, "form"),
                filer=Filer(
                    cik=child_text(filer_el, "cik"),
                    entity_name=child_text(filer_el, "entityName"),
                    file_number=child_text(filer_el, "fileNumber")
                )
            )
        )
