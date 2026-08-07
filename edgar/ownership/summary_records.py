"""
Per-row records for ownership-form summaries (3, 4, 5).

``SecurityHolding`` is a single beneficial-ownership holding (Form 3);
``TransactionActivity`` is a single normalized transaction (Forms 4/5). The
``OwnershipSummary`` hierarchy in ``summary`` aggregates collections of these.
"""
from dataclasses import dataclass
from typing import Any, Optional, Union

from edgar.ownership.core import detect_10b5_1_plan, safe_numeric

__all__ = [
    'SecurityHolding',
    'TransactionActivity',
]


@dataclass
class SecurityHolding:
    """Represents a security holding (for Form 3)"""
    security_type: str  # "non-derivative" or "derivative"
    security_title: str
    shares: int
    direct_ownership: bool
    ownership_nature: str = ""
    underlying_security: str = ""
    underlying_shares: int = 0
    exercise_price: Optional[float] = None
    exercise_date: str = ""
    expiration_date: str = ""

    @property
    def ownership_description(self) -> str:
        """Get description of ownership"""
        if self.direct_ownership:
            return "Direct"
        elif self.ownership_nature:
            return f"Indirect ({self.ownership_nature})"
        else:
            return "Indirect"

    @property
    def is_derivative(self) -> bool:
        """Check if this is a derivative security"""
        return self.security_type == "derivative"


@dataclass
class TransactionActivity:
    """Represents a specific transaction activity type"""
    transaction_type: str
    code: str
    shares: Any = 0  # Handle footnote references
    value: Any = 0
    price_per_share: Any = None  # Add explicit price per share field
    description: str = ""
    security_type: str = "non-derivative"  # "non-derivative" or "derivative"
    security_title: str = ""
    underlying_security: str = ""  # For derivative securities
    exercise_date: Optional[str] = None
    expiration_date: Optional[str] = None
    footnote_ids: str = ""  # Newline-separated footnote IDs (e.g., "F1\nF2")
    footnotes_text: str = ""  # Combined text of all footnotes for this transaction

    @property
    def shares_numeric(self) -> Optional[Union[int, float]]:
        """Get shares as a numeric value, handling footnotes"""
        return safe_numeric(self.shares)

    @property
    def value_numeric(self) -> Optional[float]:
        """Get value as a numeric value, handling footnotes"""
        return safe_numeric(self.value)

    @property
    def price_numeric(self) -> Optional[float]:
        """Get price as a numeric value, handling footnotes"""
        return safe_numeric(self.price_per_share)

    @property
    def is_derivative(self) -> bool:
        """Check if this is a derivative transaction"""
        return self.security_type == "derivative"

    @property
    def is_10b5_1_plan(self) -> Optional[bool]:
        """
        Check if this transaction was executed under a Rule 10b5-1 trading plan.

        Rule 10b5-1 trading plans allow insiders to set up predetermined trading
        schedules to avoid accusations of insider trading.

        Returns:
            True if 10b5-1 plan detected in transaction footnotes
            False if footnotes exist but no plan mentioned
            None if no footnotes available for this transaction
        """
        return detect_10b5_1_plan(self.footnotes_text)

    @property
    def code_description(self) -> str:
        """Get a description for the transaction code"""
        code_descriptions = {
            'P': 'Open Market Purchase',
            'S': 'Open Market Sale',
            'A': 'Grant/Award',
            'M': 'Option Exercise',
            'F': 'Tax Withholding',
            'G': 'Gift',
            'X': 'Option Exercise',
            'D': 'Disposition to Issuer',
            'C': 'Conversion',
            'E': 'Expiration of Short Position',
            'H': 'Expiration of Long Position',
            'I': 'Discretionary Transaction',
            'O': 'Exercise of Out-of-Money Derivative',
            'U': 'Disposition (Tender of Shares)',
            'Z': 'Deposit/Withdrawal (Voting Trust)'
        }
        return code_descriptions.get(self.code, f"Other ({self.code})")

    @property
    def display_name(self) -> str:
        """Get the display name for the transaction"""
        if self.description:
            return self.description

        if self.security_type == "derivative":
            base_desc = self.code_description
            if self.underlying_security:
                return f"{base_desc} ({self.underlying_security})"
            return base_desc

        return self.code_description

    @property
    def style(self) -> str:
        """Get appropriate style for the transaction type"""
        if self.transaction_type == "purchase":
            return "green bold"
        elif self.transaction_type == "sale":
            return "red bold"
        elif self.transaction_type == "tax":
            return "yellow"
        elif self.transaction_type == "award":
            return "blue"
        elif self.transaction_type == "exercise":
            return "magenta"
        elif self.transaction_type == "conversion":
            return "cyan"
        elif self.transaction_type == "expiration":
            return "dim"
        else:
            return "white"
