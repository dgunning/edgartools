# Enhanced XBRL Standardization Design

## Overview

This document describes enhancements to the XBRL standardization system to address company-specific mapping requirements while maintaining backwards compatibility. The design introduces company-specific mappings that extend the core standardization without requiring downstream API changes.

## Problem Statement

The current standardization system has limitations when handling hierarchical taxonomies and business models:

1. **Over-broad Mapping**: Multiple distinct concepts map to the same standard concept
   - Tesla's automotive leasing and total revenue both map to "Revenue"
   - SG&A components and total SG&A both map to "Selling, General and Administrative Expense"
2. **Lost Granularity**: Specific concepts lose their business context
   - `tsla:AutomotiveLeasing` loses automotive context
   - `us-gaap_GeneralAndAdministrativeExpense` loses component vs total distinction
3. **Missing Hierarchy**: Parent-child relationships get flattened
   - Revenue components lose their relationship to total revenue
   - Expense components lose their relationship to total expenses
4. **No Company Context**: Company-specific business models aren't recognized

### Examples of Hierarchical Mapping Issues

#### Tesla Revenue Example

**Current Output (Problematic):**
```
Revenue                     $567         $3,038   # Automotive leasing
Revenue                  $24,927        $48,256   # Total revenue
```

**Desired Output:**
```
Revenue                  $24,927        $48,256   # Total revenue
├── Automotive Revenue   $24,360        $47,585   # Car sales
│   └── Automotive Leasing Revenue $567  $671     # Leasing subset
├── Energy Revenue          $X.X          $X.X    # Solar/batteries
└── Service Revenue         $X.X          $X.X    # Services
```

#### SG&A Expense Example

**Current Mapping (Problematic):**
```json
"Selling, General and Administrative Expense": [
  "us-gaap_SellingGeneralAndAdministrativeExpense",  // Total SG&A
  "us-gaap_GeneralAndAdministrativeExpense",         // G&A component only
  "us-gaap_SellingAndMarketingExpense"              // Selling component only
]
```

**Current Output (Problematic):**
```
Selling, General and Administrative Expense  $1,200  # Total SG&A
Selling, General and Administrative Expense    $800  # Just G&A component
Selling, General and Administrative Expense    $400  # Just Selling component
```

**Desired Output:**
```
Selling, General and Administrative Expense  $1,200  # Total SG&A
├── Selling Expense                            $400  # Selling component
├── General and Administrative Expense         $600  # G&A component  
└── Marketing Expense                          $200  # Marketing component
```

## Solution Architecture

### 1. Enhanced Directory Structure

```
edgar/xbrl/standardization/
├── concept_mappings.json           # Core US-GAAP mappings (unchanged)
├── company_mappings/               # New company-specific mappings
│   ├── tsla_mappings.json         # Tesla-specific concepts
│   ├── aapl_mappings.json         # Apple-specific concepts
│   ├── msft_mappings.json         # Microsoft-specific concepts
│   └── default_company_mappings.json  # Common patterns
└── core.py                        # Enhanced mapping logic
```

### 2. Company Mapping File Format

Each company mapping file follows this structure:

**Example: `tsla_mappings.json`**
```json
{
  "metadata": {
    "entity_identifier": "tsla",
    "company_name": "Tesla, Inc.",
    "cik": "1318605",
    "priority": "high",
    "created_date": "2024-01-01",
    "last_updated": "2024-06-25"
  },
  "concept_mappings": {
    "Automotive Revenue": [
      "tsla:AutomotiveRevenue",
      "tsla:AutomotiveSales",
      "tsla:VehicleRevenue"
    ],
    "Automotive Leasing Revenue": [
      "tsla:AutomotiveLeasing",
      "tsla:AutomotiveLeasingRevenue",
      "tsla:VehicleLeasingRevenue"
    ],
    "Energy Revenue": [
      "tsla:EnergyGenerationAndStorageRevenue",
      "tsla:EnergyRevenue",
      "tsla:SolarRevenue"
    ],
    "Service Revenue": [
      "tsla:ServicesAndOtherRevenue",
      "tsla:ServiceRevenue",
      "tsla:SuperchargerRevenue"
    ]
  },
  "hierarchy_rules": {
    "Revenue": {
      "children": [
        "Automotive Revenue",
        "Energy Revenue",
        "Service Revenue"
      ]
    },
    "Automotive Revenue": {
      "children": [
        "Automotive Leasing Revenue"
      ]
    }
  },
  "business_context": {
    "primary_revenue_streams": ["automotive", "energy", "services"],
    "revenue_model": "product_and_service",
    "key_metrics": ["vehicle_deliveries", "energy_deployments"]
  }
}
```

### 3. Enhanced StandardConcept Enum

Add granular concepts to support hierarchical business models:

```python
class StandardConcept(str, Enum):
    # Existing concepts...
    REVENUE = "Revenue"
    
    # Enhanced Revenue Hierarchy
    PRODUCT_REVENUE = "Product Revenue"
    SERVICE_REVENUE = "Service Revenue"
    SUBSCRIPTION_REVENUE = "Subscription Revenue"
    LEASING_REVENUE = "Leasing Revenue"
    
    # Industry-Specific Revenue Concepts
    AUTOMOTIVE_REVENUE = "Automotive Revenue"
    AUTOMOTIVE_LEASING_REVENUE = "Automotive Leasing Revenue"
    ENERGY_REVENUE = "Energy Revenue"
    SOFTWARE_REVENUE = "Software Revenue"
    HARDWARE_REVENUE = "Hardware Revenue"
    PLATFORM_REVENUE = "Platform Revenue"
    
    # Enhanced Expense Hierarchy
    SELLING_GENERAL_ADMIN_EXPENSE = "Selling, General and Administrative Expense"
    SELLING_EXPENSE = "Selling Expense"
    GENERAL_ADMIN_EXPENSE = "General and Administrative Expense"
    MARKETING_EXPENSE = "Marketing Expense"
    SALES_EXPENSE = "Sales Expense"
    
    # Operating Expense Components
    RESEARCH_DEVELOPMENT_EXPENSE = "Research and Development Expense"
    PERSONNEL_EXPENSE = "Personnel Expense"
    FACILITIES_EXPENSE = "Facilities Expense"
    PROFESSIONAL_SERVICES_EXPENSE = "Professional Services Expense"
    
    # Other hierarchical concepts for assets, liabilities, etc.
    # ...
```

### 4. Enhanced MappingStore Implementation

**Key Changes:**
- Load all company mappings at initialization
- Create merged mapping structure with priority scoring
- Implement smart company detection from concept prefixes
- Maintain backwards compatibility

```python
class EnhancedMappingStore(MappingStore):
    def __init__(self, source: Optional[str] = None, validate_with_enum: bool = False, read_only: bool = False):
        # Initialize core mappings first
        super().__init__(source, validate_with_enum, read_only)
        
        # Load all company mappings
        self.company_mappings = self._load_all_company_mappings()
        self.merged_mappings = self._create_merged_mappings()
        self.hierarchy_rules = self._load_hierarchy_rules()
    
    def _load_all_company_mappings(self) -> Dict[str, Dict]:
        """Load all company-specific mapping files from company_mappings/ directory."""
        mappings = {}
        company_dir = os.path.join(os.path.dirname(self.source or __file__), "company_mappings")
        
        if os.path.exists(company_dir):
            for file in os.listdir(company_dir):
                if file.endswith("_mappings.json"):
                    entity_id = file.replace("_mappings.json", "")
                    try:
                        with open(os.path.join(company_dir, file), 'r') as f:
                            company_data = json.load(f)
                            mappings[entity_id] = company_data
                    except (FileNotFoundError, json.JSONDecodeError) as e:
                        logger.warning(f"Failed to load {file}: {e}")
        
        return mappings
    
    def _create_merged_mappings(self) -> Dict[str, List[Tuple[str, str, int]]]:
        """Create merged mappings with priority scoring.
        
        Returns:
            Dict mapping standard concepts to list of (company_concept, source, priority) tuples
        """
        merged = {}
        
        # Add core mappings (priority 1 - lowest)
        for std_concept, company_concepts in self.mappings.items():
            merged[std_concept] = []
            for concept in company_concepts:
                merged[std_concept].append((concept, "core", 1))
        
        # Add company mappings (priority 2-3 - higher)
        for entity_id, company_data in self.company_mappings.items():
            concept_mappings = company_data.get("concept_mappings", {})
            priority_level = 3 if company_data.get("metadata", {}).get("priority") == "high" else 2
            
            for std_concept, company_concepts in concept_mappings.items():
                if std_concept not in merged:
                    merged[std_concept] = []
                for concept in company_concepts:
                    merged[std_concept].append((concept, entity_id, priority_level))
        
        return merged
    
    def get_standard_concept(self, company_concept: str, context: Dict = None) -> Optional[str]:
        """Get standard concept with smart company detection and priority resolution."""
        # Detect company from concept prefix (e.g., 'tsla:Revenue' -> 'tsla')
        detected_entity = self._detect_entity_from_concept(company_concept)
        
        # Search through merged mappings with priority
        candidates = []
        
        for std_concept, mapping_list in self.merged_mappings.items():
            for concept, source, priority in mapping_list:
                if concept == company_concept:
                    # Boost priority if it matches detected entity
                    effective_priority = priority
                    if detected_entity and source == detected_entity:
                        effective_priority = 4  # Highest priority for exact company match
                    
                    candidates.append((std_concept, effective_priority, source))
        
        # Return highest priority match
        if candidates:
            best_match = max(candidates, key=lambda x: x[1])
            return best_match[0]
        
        return None
    
    def _detect_entity_from_concept(self, concept: str) -> Optional[str]:
        """Detect entity identifier from concept name prefix."""
        if ':' in concept:
            prefix = concept.split(':')[0].lower()
            # Check if this prefix corresponds to a known company
            if prefix in self.company_mappings:
                return prefix
        return None
    
    def _load_hierarchy_rules(self) -> Dict[str, Dict]:
        """Load hierarchy rules from all company mappings."""
        all_rules = {}
        for entity_id, company_data in self.company_mappings.items():
            hierarchy_rules = company_data.get("hierarchy_rules", {})
            # Merge hierarchy rules (company-specific rules take precedence)
            all_rules.update(hierarchy_rules)
        return all_rules
```

### 5. Priority Resolution System

**Priority Levels:**
1. **Priority 4**: Exact company prefix match (e.g., `tsla:AutomotiveLeasing` matched by Tesla mappings)
2. **Priority 3**: High-priority company mappings for standard concepts
3. **Priority 2**: Standard company mappings
4. **Priority 1**: Core US-GAAP mappings (fallback)

**Resolution Example:**
```python
# For concept "tsla:AutomotiveLeasing"
# 1. Detect entity: "tsla"
# 2. Find in tsla_mappings.json: "Automotive Leasing Revenue" (Priority 4)
# 3. Return "Automotive Leasing Revenue"

# For concept "us-gaap:Revenue" with Tesla context
# 1. No entity prefix detected
# 2. Check company mappings for enhanced granularity (Priority 2-3)
# 3. Fall back to core mapping: "Revenue" (Priority 1)
```

### 6. Backwards Compatibility

**Existing APIs remain unchanged:**
```python
# This continues to work exactly as before
mapper = ConceptMapper(MappingStore())
standardized = standardize_statement(data, mapper)

# But now automatically gets enhanced company-specific mappings
```

**Migration Path:**
1. **Phase 1**: Deploy enhanced system with Tesla mappings
2. **Phase 2**: Add Apple, Microsoft, and other major companies
3. **Phase 3**: Implement hierarchy preservation in rendering
4. **Phase 4**: Add machine learning for automated mapping discovery

### 7. Hierarchy Preservation (Future Enhancement)

**Enhanced standardize_statement function:**
```python
def standardize_statement_with_hierarchy(
    statement_data: List[Dict[str, Any]], 
    mapper: ConceptMapper,
    preserve_hierarchy: bool = True
) -> List[Dict[str, Any]]:
    """Standardize statement while preserving hierarchical relationships."""
    
    if not preserve_hierarchy:
        return standardize_statement(statement_data, mapper)
    
    # Apply hierarchy rules during standardization
    # Maintain parent-child relationships
    # Group related concepts under appropriate parents
    pass
```

### 8. Core Mapping Updates Required

The enhanced design requires updates to `concept_mappings.json` to separate aggregate and component concepts:

**Current Problematic Mappings:**
```json
"Selling, General and Administrative Expense": [
  "us-gaap_SellingGeneralAndAdministrativeExpense",  // Total SG&A
  "us-gaap_GeneralAndAdministrativeExpense",         // Component only
  "us-gaap_SellingAndMarketingExpense"              // Component only
]
```

**Enhanced Mappings:**
```json
"Selling, General and Administrative Expense": [
  "us-gaap_SellingGeneralAndAdministrativeExpense"   // Total SG&A only
],
"Selling Expense": [
  "us-gaap_SellingAndMarketingExpense",
  "us-gaap_SellingExpense"
],
"General and Administrative Expense": [
  "us-gaap_GeneralAndAdministrativeExpense",
  "us-gaap_AdministrativeExpense"
],
"Marketing Expense": [
  "us-gaap_MarketingExpense",
  "us-gaap_AdvertisingExpense"
]
```

**Hierarchy Rules in Core or Company Mappings:**
```json
"hierarchy_rules": {
  "Selling, General and Administrative Expense": {
    "children": [
      "Selling Expense",
      "General and Administrative Expense", 
      "Marketing Expense"
    ]
  }
}
```

## Implementation Plan

### **CAUTION: Phased Rollout with Backwards Compatibility**

#### **Phase 0: Risk Mitigation (Week 1)**
1. **Create comprehensive test baseline** of current standardization output
2. **Identify all existing usage** of standardized statements in codebase
3. **Document current behavior** for regression testing
4. **Design feature flags** to enable/disable enhanced standardization
5. **Create rollback plan** if issues arise

### Phase 1: Additive Changes Only (Week 2-3)
1. **DO NOT modify `concept_mappings.json`** initially
2. Create `company_mappings/` directory structure  
3. Implement `EnhancedMappingStore` class with **fallback to current behavior**
4. Add Tesla-specific mappings as **pure additions**
5. **Feature flag**: `ENHANCED_STANDARDIZATION=false` by default
6. Add comprehensive test coverage

### Phase 2: Tesla-Specific Testing (Week 4)
1. **Enable enhanced standardization for Tesla only** via feature flag
2. **Test Tesla revenue categorization** thoroughly
3. **Validate no regressions** in non-Tesla companies
4. **Performance testing** with enhanced mappings
5. **User acceptance testing** with Tesla statements

### Phase 3: Gradual Core Mapping Updates (Week 5-6) - **HIGH RISK**
1. **Only if Phase 2 is completely successful**
2. **One concept at a time** - start with least-used concepts
3. **Extend `StandardConcept` enum** with new hierarchical concepts
4. **Add new mappings** without removing existing ones initially
5. **Extensive regression testing** after each change
6. **Immediate rollback capability** if any issues

### Phase 4: Advanced Features (Week 7+) - **ONLY IF PHASES 1-3 SUCCESSFUL**
1. Implement hierarchy preservation in rendering
2. Add business context awareness
3. Create mapping validation tools
4. Add machine learning for mapping discovery

### **ABORT CONDITIONS**
- Any regression in existing standardized output
- Performance degradation > 10%
- Any breaking change in existing APIs
- User complaints about changed standardization

## Benefits

1. **Backwards Compatibility**: Zero changes required to existing code
2. **Extensibility**: Easy to add new companies by dropping JSON files
3. **Granular Control**: Company-specific business logic and concepts
4. **Smart Resolution**: Automatic company detection and priority-based mapping
5. **Maintenance**: Clear separation between core and company-specific mappings
6. **Performance**: All mappings loaded once at initialization for fast runtime lookups

## Testing Strategy

1. **Unit Tests**: Test enhanced mapping store functionality
2. **Integration Tests**: Verify Tesla revenue categorization fixes
3. **Regression Tests**: Ensure existing standardization continues to work
4. **Performance Tests**: Validate memory usage and lookup speed
5. **Company-Specific Tests**: Test each company mapping file

## Risk Mitigation

### **Critical Safety Measures**

1. **Feature Flags**: 
   ```python
   ENHANCED_STANDARDIZATION = os.getenv('ENHANCED_STANDARDIZATION', 'false').lower() == 'true'
   ENHANCED_COMPANIES = os.getenv('ENHANCED_COMPANIES', '').split(',')  # ['tsla']
   ```

2. **Fallback Mechanism**: Always fall back to core mappings if enhanced mappings fail

3. **Validation Pipeline**:
   - Validate all company mapping files against StandardConcept enum
   - Automated regression testing on every change
   - Performance benchmarking on large datasets

4. **Comprehensive Logging**:
   ```python
   logger.info(f"Enhanced mapping applied: {concept} -> {standard_concept} (source: {source})")
   logger.warning(f"Fallback to core mapping: {concept} -> {standard_concept}")
   ```

5. **Monitoring & Alerting**:
   - Track mapping success rates and conflicts
   - Monitor performance metrics
   - Alert on unexpected mapping changes

6. **Rollback Plans**:
   - **Immediate**: Set `ENHANCED_STANDARDIZATION=false` 
   - **Company-specific**: Remove company from `ENHANCED_COMPANIES`
   - **Nuclear**: Remove `company_mappings/` directory entirely

### **Testing Strategy**

1. **Baseline Creation**: Generate standardized output for top 100 companies with current system
2. **Regression Testing**: Ensure 100% compatibility when enhanced features disabled
3. **A/B Testing**: Compare enhanced vs current standardization side-by-side
4. **Performance Testing**: Measure memory usage and lookup times
5. **Integration Testing**: Test with rendering, statements, and downstream systems

## Success Metrics

1. **Tesla Revenue Issue**: Resolved with proper categorization
2. **Backwards Compatibility**: 100% of existing tests pass
3. **Performance**: No significant impact on initialization or lookup times
4. **Coverage**: Support for top 10 companies by market cap
5. **Accuracy**: >95% mapping accuracy for company-specific concepts