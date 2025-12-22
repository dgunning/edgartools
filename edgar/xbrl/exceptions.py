"""
XBRL-specific exceptions.
"""

from dataclasses import dataclass
from typing import List


@dataclass 
class StatementNotFound(Exception):
    """Exception raised when a statement cannot be resolved with sufficient confidence."""
    statement_type: str
    confidence: float
    found_statements: List[str]
    entity_name: str = "Unknown"
    cik: str = "Unknown"
    period_of_report: str = "Unknown"
    reason: str = ""

    def __str__(self):
        base_msg = f"Failed to resolve {self.statement_type} for {self.entity_name} (CIK: {self.cik}, Period: {self.period_of_report})"
        if self.confidence > 0:
            confidence_msg = f"Low confidence match: {self.confidence:.2f}"
        else:
            confidence_msg = "No matching statements found"

        if self.found_statements:
            found_msg = f"Found statements: {self.found_statements}"
        else:
            found_msg = "No statements available"

        details = f"{base_msg}. {confidence_msg}. {found_msg}"
        if self.reason:
            details += f". {self.reason}"

        return details
