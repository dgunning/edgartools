"""Data models for the Edgar test harness system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class Session:
    """A logical grouping of test runs.

    Sessions allow you to organize related test runs together,
    for example: all tests for a release, all tests for a specific feature,
    or all tests run on a particular date.
    """
    id: Optional[int] = None
    name: str = ""
    created_at: Optional[datetime] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'description': self.description,
            'tags': json.dumps(self.tags) if self.tags else '[]'
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create Session from dictionary."""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            description=data.get('description'),
            tags=json.loads(data.get('tags', '[]')) if data.get('tags') else []
        )


@dataclass
class TestRun:
    """A single execution of tests.

    Each test run represents one execution of the harness,
    tracking what was tested, when, and the configuration used.
    """
    id: Optional[int] = None
    session_id: Optional[int] = None
    name: str = ""
    test_type: str = "validation"  # 'comparison', 'validation', 'performance', 'regression'
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "running"  # 'running', 'completed', 'failed'
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'name': self.name,
            'test_type': self.test_type,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'config': json.dumps(self.config) if self.config else '{}'
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestRun':
        """Create TestRun from dictionary."""
        return cls(
            id=data.get('id'),
            session_id=data.get('session_id'),
            name=data.get('name', ''),
            test_type=data.get('test_type', 'validation'),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            status=data.get('status', 'running'),
            config=json.loads(data.get('config', '{}')) if data.get('config') else {}
        )


@dataclass
class TestResult:
    """Individual test result.

    Each TestResult represents the outcome of testing a single filing,
    including success/failure status, timing, and detailed information.
    """
    id: Optional[int] = None
    run_id: Optional[int] = None
    filing_accession: str = ""
    filing_form: str = ""
    filing_company: str = ""
    filing_date: str = ""
    test_name: str = ""
    status: str = "pending"  # 'pass', 'fail', 'error', 'skip'
    duration_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Set created_at if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'run_id': self.run_id,
            'filing_accession': self.filing_accession,
            'filing_form': self.filing_form,
            'filing_company': self.filing_company,
            'filing_date': self.filing_date,
            'test_name': self.test_name,
            'status': self.status,
            'duration_ms': self.duration_ms,
            'details': json.dumps(self.details) if self.details else '{}',
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestResult':
        """Create TestResult from dictionary."""
        return cls(
            id=data.get('id'),
            run_id=data.get('run_id'),
            filing_accession=data.get('filing_accession', ''),
            filing_form=data.get('filing_form', ''),
            filing_company=data.get('filing_company', ''),
            filing_date=data.get('filing_date', ''),
            test_name=data.get('test_name', ''),
            status=data.get('status', 'pending'),
            duration_ms=data.get('duration_ms'),
            details=json.loads(data.get('details', '{}')) if data.get('details') else {},
            error_message=data.get('error_message'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )


@dataclass
class FilingMetadata:
    """Cached filing metadata for analysis.

    Stores metadata about filings to avoid repeated API calls
    and enable fast querying of historical test data.
    """
    accession: str = ""
    form: str = ""
    company: str = ""
    cik: int = 0
    filing_date: str = ""
    period_end: Optional[str] = None
    cached_at: Optional[datetime] = None

    def __post_init__(self):
        """Set cached_at if not provided."""
        if self.cached_at is None:
            self.cached_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'accession': self.accession,
            'form': self.form,
            'company': self.company,
            'cik': self.cik,
            'filing_date': self.filing_date,
            'period_end': self.period_end,
            'cached_at': self.cached_at.isoformat() if self.cached_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilingMetadata':
        """Create FilingMetadata from dictionary."""
        return cls(
            accession=data.get('accession', ''),
            form=data.get('form', ''),
            company=data.get('company', ''),
            cik=data.get('cik', 0),
            filing_date=data.get('filing_date', ''),
            period_end=data.get('period_end'),
            cached_at=datetime.fromisoformat(data['cached_at']) if data.get('cached_at') else None
        )
