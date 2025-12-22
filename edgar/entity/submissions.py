"""
Functions for retrieving entity submission data from the SEC.
"""
import json
from typing import Any, Dict, Optional

import httpx

from edgar.core import log
from edgar.entity.data import parse_entity_submissions
from edgar.httprequests import download_json
from edgar.storage import get_edgar_data_directory, is_using_local_storage

__all__ = [
    'get_entity_submissions',
    'download_entity_submissions_from_sec',
    'load_company_submissions_from_local',
    'create_entity_from_submissions_json',
    'create_entity_from_file',
    'create_company_from_file'
]


def load_company_submissions_from_local(cik: int) -> Optional[Dict[str, Any]]:
    """
    Load company submissions from local data.

    If the cached file is corrupted or empty, it will be re-downloaded automatically.
    """
    submissions_dir = get_edgar_data_directory() / "submissions"
    if not submissions_dir.exists():
        return None
    submissions_file = submissions_dir / f"CIK{cik:010}.json"

    # If file doesn't exist, download it
    if not submissions_file.exists():
        submissions_json = download_entity_submissions_from_sec(cik)
        if submissions_json:
            with open(submissions_file, "w", encoding='utf-8') as f:
                json.dump(submissions_json, f)
        return submissions_json

    # File exists, try to parse it
    try:
        return json.loads(submissions_file.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        # File is corrupted, log warning and re-download
        log.warning(f"Corrupted submissions cache file for CIK {cik}: {e}. Re-downloading...")
        try:
            submissions_json = download_entity_submissions_from_sec(cik)
            if submissions_json:
                # Write the fresh data to cache
                with open(submissions_file, "w", encoding='utf-8') as f:
                    json.dump(submissions_json, f)
                return submissions_json
            else:
                # If download failed, remove the corrupted file
                submissions_file.unlink(missing_ok=True)
                return None
        except Exception as download_error:
            log.error(f"Failed to re-download submissions for CIK {cik}: {download_error}")
            # Remove the corrupted file so it can be retried later
            submissions_file.unlink(missing_ok=True)
            return None


def download_entity_submissions_from_sec(cik: int) -> Optional[Dict[str, Any]]:
    """
    Get the company filings for a given cik.

    Note: This function no longer uses @lru_cache (removed in Issue #471 fix) to allow
    HttpxThrottleCache to control freshness. The HTTP cache now has a 30-second TTL
    for submissions, providing a balance between freshness and performance.

    Args:
        cik: The company CIK

    Returns:
        Optional[Dict[str, Any]]: The entity submissions JSON data, or None if not found
    """
    try:
        from edgar.urls import build_submissions_url
        submission_json = download_json(build_submissions_url(cik))
    except httpx.HTTPStatusError as e:
        # Handle the case where the cik is invalid and not found on Edgar
        if e.response.status_code == 404:
            return None
        else:
            raise
    return submission_json


def get_entity_submissions(cik: int) -> Optional[Any]:
    """
    Get the entity data from the SEC submissions endpoint.

    Note: This function no longer uses @lru_cache (removed in Issue #471 fix) to allow
    HttpxThrottleCache to control freshness with a 30-second TTL.

    Args:
        cik: The company CIK

    Returns:
        Optional[EntityData]: The entity data, or None if not found
    """
    # Check the environment var EDGAR_USE_LOCAL_DATA
    if is_using_local_storage():
        submissions_json = load_company_submissions_from_local(cik)
        if not submissions_json:
            submissions_json = download_entity_submissions_from_sec(cik)
    else:
        submissions_json = download_entity_submissions_from_sec(cik)
    if submissions_json:
        return parse_entity_submissions(submissions_json)


def create_entity_from_submissions_json(
    submissions_json: Dict[str, Any],
    entity_type: str = 'auto'
) -> Any:
    """
    Create an Entity object from a submissions JSON dictionary.

    This is particularly useful for testing, as it allows creating
    Entity objects from local JSON files or mock data, without
    making any API calls.

    Args:
        submissions_json: The submissions JSON dictionary (either from a file or API)
        entity_type: The type of entity to create ('company', 'fund', or 'auto' to detect)

    Returns:
        An Entity, Company, or Fund object, depending on the entity_type parameter.
        If entity_type is 'auto', it tries to detect the entity type from the data.
    """
    # Import locally to avoid circular imports
    from edgar.entity.core import Company, Entity
    from edgar.entity.data import parse_entity_submissions
    from edgar.funds import FundCompany

    # First, parse the submissions JSON to get the entity data
    entity_data = parse_entity_submissions(submissions_json)

    # Create the appropriate entity object based on the entity_type parameter
    if entity_type == 'auto':
        # Try to detect the entity type - if it has tickers or exchanges, it's likely a company
        if entity_data.tickers or hasattr(entity_data, 'exchanges') and entity_data.exchanges:
            entity_type = 'company'
        # More detection logic could be added here
        else:
            # Default to generic entity if we can't detect the type
            entity_type = 'entity'

    # Create and return the appropriate entity type
    if entity_type.lower() == 'company':
        entity = Company(entity_data.cik)
    elif entity_type.lower() == 'fund':
        entity = FundCompany(entity_data.cik)
    else:
        entity = Entity(entity_data.cik)

    # Set the data directly to avoid making API calls
    entity._data = entity_data
    entity._data._not_found = False

    # Mark the entity as having already loaded all filings to prevent fetching more
    entity._data._loaded_all_filings = True

    return entity


def create_entity_from_file(
    file_path: str,
    entity_type: str = 'auto'
) -> Any:
    """
    Create an Entity object from a local submissions JSON file.

    This is a convenience function that loads a JSON file and creates
    an Entity object from it, without making any API calls.

    Args:
        file_path: Path to a submissions JSON file
        entity_type: The type of entity to create ('company', 'fund', or 'auto' to detect)

    Returns:
        An Entity, Company, or Fund object, depending on the entity_type parameter.
    """
    import json
    from pathlib import Path

    # Load the JSON file
    try:
        with open(Path(file_path).expanduser(), 'r') as f:
            submissions_json = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.error(f"Error loading submissions JSON file: {e}")
        return None

    # Create the entity from the loaded JSON
    return create_entity_from_submissions_json(submissions_json, entity_type)


def create_company_from_file(file_path: str) -> Any:
    """
    Create a Company object from a local submissions JSON file.

    This is a convenience function specifically for creating companies,
    which is the most common use case.

    Args:
        file_path: Path to a submissions JSON file

    Returns:
        A Company object
    """
    return create_entity_from_file(file_path, entity_type='company')
