/# EdgarTools Entity Hierarchy Redesign

## Current Issues

The current API has several overlapping classes related to SEC entities:

1. `Entity`: Base representation of a SEC filer
2. `EntityData`: Extended entity data
3. `Company`: Represents public companies
4. `CompanyData`: Company-specific extended data
5. Various subclasses and related classes (CompanyFiling, EntityFacts, etc.)

This creates confusion about:
- When to use `Entity` vs `Company`
- The relationships between these classes
- What methods return which types of objects
- How funds and other non-corporate entities fit into this hierarchy

## Design Goals

1. Create a clearer conceptual model
2. Maintain backward compatibility where possible
3. Preserve convenient APIs like `Company("AAPL")`
4. Provide clear guidance on which class to use when
5. Establish consistent naming patterns

## Proposed Hierarchy

```
SecFiler (base abstract class)
├── Entity (concrete class for any SEC filer)
│   ├── Company (specialized for public companies)
│   └── Fund (specialized for investment funds)
│       └── FundClass (specific class of a fund)
```

### Class Details

#### `SecFiler` (Abstract Base Class)

```python
class SecFiler(ABC):
    """Abstract base class for all SEC filing entities."""
    
    @abstractmethod
    def get_filings(self, **kwargs) -> Filings:
        """Get filings for this entity."""
        pass
        
    @abstractmethod
    def get_facts(self) -> dict:
        """Get structured facts about this entity."""
        pass
    
    # Other common methods for all SEC filers
```

#### `Entity` (Concrete Implementation)

```python
class Entity(SecFiler):
    """Represents any entity that files with the SEC."""
    
    def __init__(self, cik_or_identifier: Union[str, int]):
        self.cik = normalize_cik(cik_or_identifier)
        self._data = None
    
    @property
    def data(self) -> EntityData:
        """Get detailed data for this entity."""
        if self._data is None:
            # Load entity data from SEC submissions API
            submissions_data = download_entity_submissions_from_sec(self.cik)
            self._data = parse_entity_submissions(submissions_data)
        return self._data
    
    def get_filings(self, 
                   *,
                   form: Union[str, List] = None,
                   accession_number: Union[str, List] = None,
                   file_number: Union[str, List] = None,
                   filing_date: Union[str, Tuple[str, str]] = None,
                   date: Union[str, Tuple[str, str]] = None,
                   is_xbrl: bool = None,
                   is_inline_xbrl: bool = None,
                   sort_by: Union[str, List[Tuple[str, str]]] = None,
                   trigger_full_load: bool = True) -> Filings:
        """
        Get the entity's filings and optionally filter by multiple criteria.
        
        This method has a special behavior for loading filings. When first called,
        it only loads the most recent filings. If trigger_full_load=True, it will 
        automatically fetch all historical filings from the SEC (potentially making 
        multiple API calls) as needed.
        
        Args:
            form: The form as a string e.g. '10-K' or List of strings ['10-Q', '10-K']
            accession_number: The accession number that identifies a filing
            file_number: The file number e.g. 001-39504
            filing_date: Filter by filing date (YYYY-MM-DD or range)
            date: Alias for filing_date
            is_xbrl: Whether the filing is XBRL
            is_inline_xbrl: Whether the filing is Inline XBRL
            sort_by: Sort criteria
            trigger_full_load: Whether to load all historical filings if not already loaded
            
        Returns:
            Filtered filings matching the criteria
        """
        # Simply delegate to the EntityData implementation
        # This preserves the lazy-loading behavior while keeping the API clean
        return self.data.get_filings(
            form=form,
            accession_number=accession_number,
            file_number=file_number,
            filing_date=filing_date or date,
            is_xbrl=is_xbrl,
            is_inline_xbrl=is_inline_xbrl,
            sort_by=sort_by,
            trigger_full_load=trigger_full_load
        )
        
    def get_facts(self) -> EntityFacts:
        """Get structured facts about this entity."""
        try:
            return get_company_facts(self.cik)
        except NoCompanyFactsFound:
            return None

    # Other methods common to all SEC entities
```

#### `Company` (Specialization for Public Companies)

```python
class Company(Entity):
    """Represents a public company that files with the SEC."""
    
    def __init__(self, cik_or_ticker: Union[str, int]):
        # If it's a ticker, convert to CIK first
        if isinstance(cik_or_ticker, str) and not cik_or_ticker.isdigit():
            cik = find_cik(cik_or_ticker)
            if cik is None:
                raise ValueError(f"Could not find CIK for ticker {cik_or_ticker}")
            super().__init__(cik)
        else:
            super().__init__(cik_or_ticker)
    
    @property
    def data(self) -> CompanyData:  # Override return type
        """Get detailed data for this company."""
        return super().data
    
    def get_financials(self) -> Financials:
        """Get financial statements for this company."""
        # Implementation
        
    def get_ticker(self) -> Optional[str]:
        """Get the ticker symbol for this company."""
        # Implementation
    
    # Other company-specific methods
```

#### `Fund` (Specialization for Investment Funds)

```python
class Fund(Entity):
    """Represents an investment fund that files with the SEC."""
    
    def __init__(self, cik_or_identifier: Union[str, int]):
        # Handle fund-specific identifiers
        super().__init__(self._resolve_fund_identifier(cik_or_identifier))
        self._series_id = None
        
    @staticmethod
    def _resolve_fund_identifier(identifier):
        # Convert fund tickers or series IDs to CIK
        # Implementation
        
    def get_classes(self) -> List[FundClass]:
        """Get all share classes of this fund."""
        # Implementation
        
    def get_series(self) -> Optional[FundSeries]:
        """Get the fund series information."""
        # Implementation
        
    def get_portfolio(self) -> pd.DataFrame:
        """Get the most recent portfolio holdings."""
        # Implementation
```

#### `FundClass` (Representation of a Specific Fund Class)

```python
class FundClass:
    """Represents a specific class of an investment fund."""
    
    def __init__(self, class_id: str, fund: Fund):
        self.class_id = class_id
        self.fund = fund
        
    @property
    def ticker(self) -> Optional[str]:
        """Get the ticker for this fund class."""
        # Implementation
        
    @property
    def name(self) -> str:
        """Get the name of this fund class."""
        # Implementation
        
    def get_performance(self) -> pd.DataFrame:
        """Get performance data for this fund class."""
        # Implementation
```

## Factory Functions

To maintain backward compatibility and make the API intuitive:

```python
def get_entity(cik_or_identifier: Union[str, int]) -> Entity:
    """Get any SEC filing entity by CIK or identifier."""
    return Entity(cik_or_identifier)

def get_company(cik_or_ticker: Union[str, int]) -> Company:
    """Get a public company by CIK or ticker."""
    return Company(cik_or_ticker)

def get_fund(fund_identifier: str) -> Union[Fund, FundClass]:
    """
    Get a fund or fund class by identifier.
    
    Args:
        fund_identifier: Fund ticker (e.g., 'KINCX'), Series ID (e.g., 'S000001234'), 
                         or CIK number
                         
    Returns:
        Fund object if the identifier refers to a fund, or
        FundClass object if the identifier refers to a specific share class
    """
    # Determine if this is a fund class ticker like 'KINCX'
    if is_fund_class_ticker(fund_identifier):
        fund = _get_fund_for_class_ticker(fund_identifier)
        class_id = _get_class_id_for_ticker(fund_identifier)
        return FundClass(class_id, fund)
    
    # Otherwise return a Fund
    return Fund(fund_identifier)
```

## EntityData Implementation

A critical part of the design is the `EntityData` class that manages entity data and filing loading:

```python
class EntityData:
    """Container for entity data loaded from SEC submissions API."""
    
    def __init__(self,
                cik: int,
                name: str,
                # Other entity properties
                filings: 'EntityFilings',
                files: List[str]  # Additional filing data files
                ):
        self.cik: int = cik
        self.name: str = name
        # Other properties initialized
        self.filings = filings
        self._files = files
        self._loaded_all_filings: bool = False  # Track if all filings are loaded
    
    def _load_older_filings(self):
        """
        Load the older filings from additional data files.
        This is a critical method that loads historical filing data
        by downloading and processing additional submissions files.
        """
        if not self._files:
            return
            
        # Implementation that loads data from self._files
        # and updates self.filings
        
        # Mark that all filings have been loaded
        self._loaded_all_filings = True
        
    # This gets called by Entity.get_filings()
    def get_filings(self, 
                  form: Union[str, List] = None,
                  trigger_full_load: bool = True,
                  **kwargs) -> 'EntityFilings':
        """
        Get entity filings with lazy loading behavior.
        
        The critical behavior to maintain is the conditional loading of all
        filing history only when needed, controlled by the trigger_full_load parameter.
        """
        # Trigger loading of all historical filings if needed
        if not self._loaded_all_filings and trigger_full_load:
            self._load_older_filings()
            
        # Apply filters and return filings
        # Implementation details...
```

This design preserves the important lazy-loading behavior where:
1. When an Entity is first created, only the most recent filings are loaded
2. When `get_filings()` is called with `trigger_full_load=True`, it loads all historical filings
3. Subsequent calls use the cached complete filing data

## Implementation Notes for Fund Handling

For Funds, we have a challenge because tickers like "KINCX" and "KINAX" map to the same fund but different share classes. 

Options for handling this:

1. **Return the FundClass directly**:
   ```python
   result = get_fund("KINCX")  # Returns a FundClass
   print(result)  # "Kinetics Internet Fund, Advisor Class C"
   ```

2. **Return the Fund with methods to access classes**:
   ```python
   fund = get_fund("KINCX")  # Returns a Fund
   class_c = fund.get_class("C")  # Get the specific class
   print(fund)  # "Kinetics Internet Fund"
   print(class_c)  # "Advisor Class C"
   ```

The recommended approach is a hybrid that makes both patterns usable:
- If a class-specific identifier is provided (like a class ticker), return the FundClass
- If a fund-level identifier is provided (like a fund CIK), return the Fund

## Usage Examples

```python
# Working with companies
apple = Company("AAPL")  # Convenient constructor using ticker
apple_filings = apple.get_filings(form="10-K")
apple_financials = apple.get_financials()

# Working with general entities
entity = Entity("0000320193")  # Using CIK
entity_filings = entity.get_filings()

# Using factory functions
apple2 = get_company("AAPL")  # Same as Company("AAPL")
entity2 = get_entity("0000320193")  # Same as Entity("0000320193")

# Working with funds
fund = get_fund("S000007331")  # Using Series ID, returns Fund
fund_classes = fund.get_classes()

# Working with fund classes
class_c = get_fund("KINCX")  # Using class ticker, returns FundClass
print(class_c.fund.name)  # Access the parent fund
print(class_c.name)  # "Advisor Class C"
```

## Backward Compatibility

To maintain backward compatibility:

1. Keep `Company()` as a public constructor that resolves tickers
2. Ensure `get_entity()` and `get_company()` continue to work as before
3. Maintain existing method signatures on `Entity` and `Company`
4. Use class-based inheritance to ensure LSP compliance
5. Gradually transition documentation to the new model

## Documentation Improvements

Add explicit documentation:

1. **When to use which class**:
   - Use `Company` when working with public corporations
   - Use `Fund` when working with investment funds
   - Use `Entity` for general SEC filers or when the entity type is unknown

2. **Method return type clarity**:
   - Document return types clearly for all methods
   - Explain when methods may return different types based on input

3. **Class diagrams**:
   - Add visual representation of class relationships
   - Show inheritance hierarchy and important methods

## Conclusion

This redesign creates a clearer conceptual model while maintaining the convenient APIs that users rely on. It properly expresses the "is-a" relationships (a Company is-a Entity) while allowing specialized functionality for different entity types.

The design addresses the Fund/FundClass relationship by having a clear ownership model (FundClass belongs to a Fund) while still providing convenient access through the `get_fund()` factory function.