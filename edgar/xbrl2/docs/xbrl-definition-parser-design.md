# XBRL Definition Linkbase Parser Design (Python)

## 1. Overview

The Definition Linkbase Parser is responsible for processing dimensional relationships defined in XBRL definition linkbases. These linkbases define the structure of tables, axes, domains, and domain members that organize facts in multi-dimensional disclosures. This design document outlines a Python implementation for parsing definition relationships, building dimensional structures, and supporting the interpretation of dimensionally qualified facts.

```
┌─────────────────┐     ┌─────────────────────────┐     ┌─────────────────┐
│                 │     │                         │     │                 │
│  Definition     │────▶│  Definition Linkbase    │────▶│  Dimensional    │
│  Linkbase       │     │  Parser                 │     │  Structure      │
│                 │     │                         │     │                 │
└─────────────────┘     └─────────────────────────┘     └─────────────────┘
```

## 2. Input and Output

### 2.1 Input
- XBRL definition linkbase file (XML file, typically with _def.xml extension)
- Reference to taxonomy schema file for resolving element references
- Optional: Element information including substitution groups and types

### 2.2 Output
- Dimensional structure organized by extended link roles (ELRs)
- For each ELR: tables, axes, domains, domain members, and their relationships
- Default members for each axis
- Line items associated with each table

## 3. Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Definition Linkbase Parser                      │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ XML           │  │ Linkbase      │  │ Role          │    │
│  │ Parser        │  │ Processor     │  │ Extractor     │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Definition    │  │ Dimensional   │  │ Default       │    │
│  │ Arc Processor │  │ Relationship  │  │ Member        │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Table         │  │ Dimension     │  │ Validation    │    │
│  │ Builder       │  │ Processor     │  │ Engine        │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 4. Data Structures

### 4.1 Extended Link Role (ELR)
```python
class ExtendedLinkRole:
    def __init__(self):
        self.role_uri = ""      # URI of the role (e.g., "http://example.com/role/DisclosureTable")
        self.role_id = ""       # ID of the role (optional)
        self.definition = ""    # Human-readable description
        self.order = 0          # Ordering value if provided
```

### 4.2 Definition Relationship
```python
class DefinitionRelationship:
    def __init__(self):
        self.from_element = ""      # Element ID/name of parent
        self.to_element = ""        # Element ID/name of child
        self.arcrole = ""           # Arc role (e.g., "hypercube-dimension", "dimension-domain")
        self.role = ""              # Extended link role this relationship belongs to
        self.order = 0.0            # Order value (for presentation ordering)
        self.priority = 0           # Priority of the arc (for conflict resolution)
        self.prohibited = False     # Whether this relationship is prohibited
        self.closed = False         # Whether the hypercube is closed (for all/notAll arcs)
        self.contextElement = ""    # "segment" or "scenario" for hypercube-dimension arcs
        self.targetRole = ""        # Target extended link role (for inter-role connections)
```

### 4.3 Table (Hypercube)
```python
class Table:
    def __init__(self):
        self.element_id = ""        # Element ID of the hypercube
        self.label = ""             # Label of the hypercube
        self.role_uri = ""          # Extended link role URI
        self.axes = []              # List of Axis objects
        self.line_items = []        # List of element IDs of line items
        self.closed = False         # Whether the hypercube is closed
        self.context_element = "segment"  # Default context element
```

### 4.4 Axis (Dimension)
```python
class Axis:
    def __init__(self):
        self.element_id = ""        # Element ID of the dimension
        self.label = ""             # Label of the dimension
        self.domain = None          # Domain object
        self.default_member = None  # Default member (often the domain itself)
        self.is_typed_dimension = False  # Whether this is a typed dimension
        self.typed_domain_ref = ""  # Reference to typed domain (if typed dimension)
```

### 4.5 Domain
```python
class Domain:
    def __init__(self):
        self.element_id = ""        # Element ID of the domain
        self.label = ""             # Label of the domain
        self.members = []           # List of Domain objects (members)
        self.parent = None          # Parent domain (None for top-level domain)
```

### 4.6 Dimensional Structure
```python
class DimensionalStructure:
    def __init__(self):
        self.roles = {}             # Dictionary of ExtendedLinkRole by URI
        self.relationships = []     # List of all DefinitionRelationship objects
        self.tables = {}            # Dictionary of tables by ELR
        self.all_axes = {}          # Dictionary of all axes by element ID
        self.all_domains = {}       # Dictionary of all domains by element ID
```

## 5. Detailed Process Flow

### 5.1 Initialization and XML Parsing
1. Initialize parser with definition linkbase file path
2. Set up XML parser with appropriate namespaces
3. Load linkbase file into DOM parser
4. Extract linkbase root element and validate it's a definition linkbase

### 5.2 Role Extraction
1. Extract all extended link role (ELR) definitions 
2. Process role URIs, IDs, and definitions
3. Create role registry mapping URIs to role objects
4. Sort roles by their designated order if available

### 5.3 Definition Arc Extraction
1. Extract all definition arcs (`<definitionArc>` elements)
2. For each arc:
   - Extract from/to attributes and resolve element references
   - Extract arcrole (e.g., hypercube-dimension, dimension-domain)
   - Extract additional attributes (targetRole, contextElement, closed)
   - Process arc priority and use attributes for conflict resolution
   - Create relationship object and add to collection

### 5.4 Relationship Processing
1. Filter out prohibited relationships
2. Group relationships by extended link role
3. For each role, process relationship types:
   - Process all/notAll arcs connecting line items to hypercubes
   - Process hypercube-dimension arcs connecting tables to axes
   - Process dimension-domain arcs connecting axes to domains
   - Process domain-member arcs defining domain hierarchies
   - Process dimension-default arcs identifying default members

### 5.5 Table Construction
1. Build tables for each extended link role
2. For each table:
   - Identify hypercube element
   - Find all associated axes via hypercube-dimension relationships
   - Find associated line items via has-hypercube relationships
   - Set closed attribute and context element

### 5.6 Axis and Domain Construction
1. For each axis:
   - Identify dimension element
   - Determine if explicit or typed dimension
   - Find associated domain via dimension-domain relationship
   - Identify default member via dimension-default relationship
   - Build domain hierarchy from domain-member relationships
   - For typed dimensions, extract typed domain reference

### 5.7 Schema Integration
1. If schema information is provided, validate element types:
   - Verify hypercubes have xbrli:hypercubeItem substitution group
   - Verify dimensions have xbrli:dimensionItem substitution group
   - Verify domains and members have standard item substitution group

## 6. Algorithms

### 6.1 Dimension Type Determination
```python
def determine_dimension_type(dimension_id, element_info):
    """
    Determine if a dimension is explicit or typed.
    
    Args:
        dimension_id: Element ID of the dimension
        element_info: Dictionary of element information from schema
    
    Returns:
        Tuple of (is_typed_dimension, typed_domain_ref)
    """
    # Default to explicit dimension
    is_typed = False
    typed_domain_ref = ""
    
    # Check if element info is available
    if element_info and dimension_id in element_info:
        # Check for typed dimension attribute
        if 'typedDomainRef' in element_info[dimension_id]:
            is_typed = True
            typed_domain_ref = element_info[dimension_id]['typedDomainRef']
    
    return is_typed, typed_domain_ref
```

### 6.2 Domain Hierarchy Construction
```python
def build_domain_hierarchy(domain_id, domain_member_rels, all_domains, element_labels=None):
    """
    Build a domain hierarchy from domain-member relationships.
    
    Args:
        domain_id: Element ID of the domain
        domain_member_rels: List of domain-member relationships
        all_domains: Dictionary to store all domains
        element_labels: Optional dictionary of element labels
    
    Returns:
        Domain object representing the hierarchy
    """
    # Create domain if not exists
    if domain_id not in all_domains:
        domain = Domain()
        domain.element_id = domain_id
        domain.label = element_labels.get(domain_id, domain_id) if element_labels else domain_id
        all_domains[domain_id] = domain
    else:
        domain = all_domains[domain_id]
    
    # Get all children of this domain
    child_rels = [rel for rel in domain_member_rels if rel.from_element == domain_id]
    
    # Sort by order attribute
    child_rels.sort(key=lambda rel: rel.order)
    
    # Process children
    for rel in child_rels:
        child_id = rel.to_element
        
        # Skip if cycle detected
        if child_id == domain_id:
            continue
            
        # Create child domain
        child_domain = build_domain_hierarchy(
            child_id, domain_member_rels, all_domains, element_labels
        )
        
        # Set parent relationship
        child_domain.parent = domain
        
        # Add to parent's members if not already there
        if child_domain not in domain.members:
            domain.members.append(child_domain)
    
    return domain
```

### 6.3 Table Construction Algorithm
```python
def build_dimensional_tables(relationships, role_uri, element_info=None, element_labels=None):
    """
    Build dimensional tables from a set of relationships for a specific role.
    
    Args:
        relationships: List of DefinitionRelationship objects
        role_uri: The extended link role URI for which to build tables
        element_info: Optional dictionary of element information
        element_labels: Optional dictionary of element labels
    
    Returns:
        List of Table objects
    """
    # Filter relationships for this role
    role_rels = [r for r in relationships if r.role == role_uri]
    
    # Group relationships by arcrole
    has_hypercube_rels = [r for r in role_rels if r.arcrole.endswith('all')]
    hypercube_dimension_rels = [r for r in role_rels 
                             if r.arcrole.endswith('hypercube-dimension')]
    dimension_domain_rels = [r for r in role_rels 
                           if r.arcrole.endswith('dimension-domain')]
    domain_member_rels = [r for r in role_rels 
                         if r.arcrole.endswith('domain-member')]
    dimension_default_rels = [r for r in role_rels 
                            if r.arcrole.endswith('dimension-default')]
    
    # Process all tables (hypercubes) in this role
    tables = []
    all_domains = {}
    
    # Find all hypercubes
    hypercube_ids = set()
    for rel in has_hypercube_rels:
        hypercube_ids.add(rel.to_element)
    
    # Process each hypercube
    for hypercube_id in hypercube_ids:
        table = Table()
        table.element_id = hypercube_id
        table.label = element_labels.get(hypercube_id, hypercube_id) if element_labels else hypercube_id
        table.role_uri = role_uri
        
        # Find linkbase attributes from has-hypercube relationship
        for rel in has_hypercube_rels:
            if rel.to_element == hypercube_id:
                table.closed = rel.closed
                table.context_element = rel.contextElement
                
                # Add line items from abstract element
                line_items_id = rel.from_element
                # Find all descendants of line items abstract element
                line_items = _find_line_items(line_items_id, domain_member_rels, element_info)
                table.line_items = line_items
        
        # Find dimensions for this hypercube
        for rel in hypercube_dimension_rels:
            if rel.from_element == hypercube_id:
                dimension_id = rel.to_element
                
                # Create axis
                axis = Axis()
                axis.element_id = dimension_id
                axis.label = element_labels.get(dimension_id, dimension_id) if element_labels else dimension_id
                
                # Check if typed dimension
                if element_info:
                    axis.is_typed_dimension, axis.typed_domain_ref = determine_dimension_type(
                        dimension_id, element_info
                    )
                
                # If explicit dimension, find domain and members
                if not axis.is_typed_dimension:
                    # Find domain for this dimension
                    for dim_domain_rel in dimension_domain_rels:
                        if dim_domain_rel.from_element == dimension_id:
                            domain_id = dim_domain_rel.to_element
                            
                            # Build domain hierarchy
                            domain = build_domain_hierarchy(
                                domain_id, domain_member_rels, all_domains, element_labels
                            )
                            axis.domain = domain
                            
                            # Find default member
                            for default_rel in dimension_default_rels:
                                if default_rel.from_element == dimension_id:
                                    default_id = default_rel.to_element
                                    if default_id in all_domains:
                                        axis.default_member = all_domains[default_id]
                                    break
                            
                            # If no explicit default, use domain as default
                            if not axis.default_member:
                                axis.default_member = domain
                            
                            break
                
                table.axes.append(axis)
        
        tables.append(table)
    
    return tables

def _find_line_items(abstract_id, domain_member_rels, element_info):
    """
    Find all line items under an abstract element.
    
    Args:
        abstract_id: Element ID of the abstract line items element
        domain_member_rels: List of domain-member relationships
        element_info: Optional dictionary of element information
    
    Returns:
        List of element IDs representing line items
    """
    line_items = []
    
    # Get all children of the abstract element
    child_rels = [rel for rel in domain_member_rels if rel.from_element == abstract_id]
    
    for rel in child_rels:
        child_id = rel.to_element
        
        # Check if abstract
        is_abstract = False
        if element_info and child_id in element_info:
            is_abstract = element_info[child_id].get('abstract', False)
        
        if is_abstract:
            # If abstract, recursively find its children
            line_items.extend(_find_line_items(child_id, domain_member_rels, element_info))
        else:
            # If not abstract, add as a line item
            line_items.append(child_id)
    
    return line_items
```

### 6.4 Default Member Resolution
```python
def resolve_default_members(axes, dimension_default_rels):
    """
    Resolve default members for dimensions.
    
    Args:
        axes: List of Axis objects
        dimension_default_rels: List of dimension-default relationships
    
    Returns:
        Dictionary mapping dimension IDs to default member IDs
    """
    default_members = {}
    
    # Process explicit defaults from dimension-default relationships
    for rel in dimension_default_rels:
        dimension_id = rel.from_element
        default_id = rel.to_element
        default_members[dimension_id] = default_id
    
    # For dimensions without explicit defaults, use domain as default
    for axis in axes:
        if axis.element_id not in default_members and axis.domain:
            default_members[axis.element_id] = axis.domain.element_id
    
    return default_members
```

## 7. Performance Considerations

### 7.1 Memory Optimization
- Use element IDs rather than full element objects in relationships
- Implement sharing of domain objects across multiple dimensions
- Consider lazy loading of domain hierarchies for very large taxonomies

### 7.2 Parsing Efficiency
- Pre-compile XPath expressions for common element selections
- Cache resolved element references
- Process relationship groups in parallel for large linkbases

### 7.3 Scalability
- Implement incremental construction of dimensional structures
- Design data structures for efficient dimension/member lookups
- Use lazy validation of dimensional relationships

## 8. Error Handling

### 8.1 Error Types
- XML parsing errors
- Invalid relationship structures
- Missing required elements (dimensions without domains)
- Cyclic domain hierarchies
- Invalid element substitution groups

### 8.2 Error Handling Strategy
- Distinguish between structural errors and validation warnings
- Provide detailed error messages with context
- Implement recovery strategies for non-fatal errors
- Log all errors and warnings with appropriate severity

### 8.3 Validation
- Validate against XBRL Dimensions 1.0 specification
- Check for proper relationship structure
- Verify element substitution groups match their roles
- Ensure no prohibited arcs are incorrectly processed

## 9. Extension Points

### 9.1 Custom Arc Handlers
- Allow registration of handlers for specific definition arcroles
- Support specialized processing for custom dimensional structures
- Enable customized validation rules

### 9.2 Dimensional Query Interface
- Provide APIs for querying dimensional structures
- Support filtering facts by dimensional qualifiers
- Enable complex dimensional analysis

### 9.3 Integration Points
- Provide interfaces for integration with instance document processors
- Support integration with presentation and calculation parsers
- Enable visualization of dimensional hierarchies

## 10. Implementation Example

### 10.1 Basic Parser Implementation
```python
import xml.etree.ElementTree as ET
import re
from collections import defaultdict
import logging

class DefinitionLinkbaseParser:
    def __init__(self, options=None):
        self.options = options or {}
        self.roles = {}
        self.relationships = []
        self.tables = {}
        self.all_axes = {}
        self.all_domains = {}
        self.element_info = {}  # Information about elements from schema
        
        # Define namespaces
        self.ns = {
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xbrldt': 'http://xbrl.org/2005/xbrldt'
        }
        
        # Common arcroles
        self.arcroles = {
            'all': 'http://xbrl.org/int/dim/arcrole/all',
            'notAll': 'http://xbrl.org/int/dim/arcrole/notAll',
            'hypercube-dimension': 'http://xbrl.org/int/dim/arcrole/hypercube-dimension',
            'dimension-domain': 'http://xbrl.org/int/dim/arcrole/dimension-domain',
            'domain-member': 'http://xbrl.org/int/dim/arcrole/domain-member',
            'dimension-default': 'http://xbrl.org/int/dim/arcrole/dimension-default'
        }
    
    def parse(self, linkbase_path, schema_info=None, element_labels=None):
        """
        Parse an XBRL definition linkbase file.
        
        Args:
            linkbase_path: Path to the definition linkbase file
            schema_info: Optional dictionary of element information from schema
            element_labels: Optional dictionary of element labels
        
        Returns:
            Dictionary containing parsed dimensional structure
        """
        try:
            # Store schema info and labels if provided
            if schema_info:
                self.element_info = schema_info
                
            # Parse XML
            tree = ET.parse(linkbase_path)
            root = tree.getroot()
            
            # Extract namespaces
            self._extract_namespaces(root)
            
            # Extract roles
            self._extract_roles(root)
            
            # Extract relationships
            self._extract_relationships(root)
            
            # Filter out prohibited relationships
            self._filter_prohibited_relationships()
            
            # Build tables
            self._build_tables(element_labels)
            
            # Validate the structure
            self._validate_structure()
            
            return {
                'roles': self.roles,
                'relationships': self.relationships,
                'tables': self.tables,
                'all_axes': self.all_axes,
                'all_domains': self.all_domains
            }
            
        except Exception as e:
            logging.error(f"Error parsing definition linkbase: {str(e)}")
            raise
    
    def _extract_namespaces(self, root):
        """Extract and register all namespaces from the document."""
        # Add all namespaces from root to our namespace dictionary
        for prefix, uri in root.nsmap.items() if hasattr(root, 'nsmap') else []:
            if prefix is not None:  # lxml uses None for the default namespace
                self.ns[prefix] = uri
    
    def _extract_roles(self, root):
        """Extract extended link roles from the linkbase."""
        # Look for roleRef elements
        role_refs = root.findall(f'.//{{{self.ns["link"]}}}roleRef')
        
        for role_ref in role_refs:
            role_uri = role_ref.get(f'{{{self.ns["xlink"]}}}href')
            role_id = role_ref.get('roleURI')
            
            # Create role object
            role = ExtendedLinkRole()
            role.role_uri = role_id
            role.role_id = role_uri.split('#')[-1] if role_uri else ""
            
            # Try to get definition from schema info if available
            if self.element_info and role.role_id in self.element_info:
                role.definition = self.element_info[role.role_id].get('definition', '')
            
            self.roles[role.role_uri] = role
        
        # If no roles found in roleRef, extract from extended links
        if not self.roles:
            definition_links = root.findall(f'.//{{{self.ns["link"]}}}definitionLink')
            for link in definition_links:
                role_uri = link.get(f'{{{self.ns["xlink"]}}}role')
                if role_uri and role_uri not in self.roles:
                    role = ExtendedLinkRole()
                    role.role_uri = role_uri
                    
                    # Try to extract a readable name from the URI
                    name_match = re.search(r'/([^/]+)$', role_uri)
                    if name_match:
                        role.definition = name_match.group(1).replace('_', ' ')
                    
                    self.roles[role.role_uri] = role
    
    def _extract_relationships(self, root):
        """Extract definition relationships from the linkbase."""
        definition_links = root.findall(f'.//{{{self.ns["link"]}}}definitionLink')
        
        for link in definition_links:
            role_uri = link.get(f'{{{self.ns["xlink"]}}}role')
            if not role_uri:
                continue
                
            # Get all arcs in this link
            arcs = link.findall(f'.//{{{self.ns["link"]}}}definitionArc')
            
            for arc in arcs:
                # Get required attributes
                from_attr = arc.get(f'{{{self.ns["xlink"]}}}from')
                to_attr = arc.get(f'{{{self.ns["xlink"]}}}to')
                arcrole = arc.get(f'{{{self.ns["xlink"]}}}arcrole')
                
                if not from_attr or not to_attr or not arcrole:
                    continue
                
                # Find locator elements for from/to
                from_locator = link.find(f'.//{{{self.ns["link"]}}}loc[@{{{self.ns["xlink"]}}}label="{from_attr}"]')
                to_locator = link.find(f'.//{{{self.ns["link"]}}}loc[@{{{self.ns["xlink"]}}}label="{to_attr}"]')
                
                if not from_locator or not to_locator:
                    continue
                
                # Extract element references
                from_href = from_locator.get(f'{{{self.ns["xlink"]}}}href')
                to_href = to_locator.get(f'{{{self.ns["xlink"]}}}href')
                
                from_element = self._extract_element_id(from_href)
                to_element = self._extract_element_id(to_href)
                
                # Create relationship
                rel = DefinitionRelationship()
                rel.from_element = from_element
                rel.to_element = to_element
                rel.role = role_uri
                rel.arcrole = arcrole
                
                # Get optional attributes
                order_attr = arc.get('order')
                rel.order = float(order_attr) if order_attr else 0.0
                
                priority_attr = arc.get('priority')
                rel.priority = int(priority_attr) if priority_attr else 0
                
                # Get XBRL Dimensions specific attributes
                if arcrole.endswith('all') or arcrole.endswith('notAll'):
                    # has-hypercube relationship
                    closed_attr = arc.get(f'{{{self.ns["xbrldt"]}}}closed')
                    rel.closed = closed_attr == 'true' if closed_attr else False
                    
                    context_element_attr = arc.get(f'{{{self.ns["xbrldt"]}}}contextElement')
                    rel.contextElement = context_element_attr if context_element_attr else 'segment'
                
                # Get targetRole if present
                target_role_attr = arc.get('targetRole')
                rel.targetRole = target_role_attr if target_role_attr else ''
                
                # Check use attribute (prohibited relationships should be filtered)
                use_attr = arc.get('use', 'optional')
                if use_attr == 'prohibited':
                    rel.prohibited = True
                
                self.relationships.append(rel)
    
    def _extract_element_id(self, href):
        """Extract element ID from an href attribute."""
        if not href:
            return ""
            
        # Parse the href to get element ID
        parts = href.split('#')
        if len(parts) > 1:
            return parts[1]
        return ""
    
    def _filter_prohibited_relationships(self):
        """Remove relationships that are effectively prohibited."""
        # Group by from/to/role/arcrole
        rel_dict = defaultdict(list)
        for rel in self.relationships:
            key = (rel.from_element, rel.to_element, rel.role, rel.arcrole)
            rel_dict[key].append(rel)
        
        # Keep only effective arcs (highest priority non-prohibited)
        effective_rels = []
        for key, rels in rel_dict.items():
            # Sort by priority (highest first)
            sorted_rels = sorted(rels, key=lambda r: r.priority, reverse=True)
            
            # Find highest priority non-prohibited relationship
            for rel in sorted_rels:
                if not rel.prohibited:
                    effective_rels.append(rel)
                    break
        
        self.relationships = effective_rels
    
    def _build_tables(self, element_labels):
        """Build dimensional tables from relationships."""
        # Process each role
        for role_uri in self.roles.keys():
            tables = build_dimensional_tables(
                self.relationships,
                role_uri,
                self.element_info,
                element_labels
            )
            
            if tables:
                self.tables[role_uri] = tables
                
                # Add axes and domains to global collections
                for table in tables:
                    for axis in table.axes:
                        self.all_axes[axis.element_id] = axis
                        if axis.domain:
                            self._add_domain_to_collection(axis.domain)
    
    def _add_domain_to_collection(self, domain):
        """Add a domain and all its members to the global collection."""
        if domain.element_id not in self.all_domains:
            self.all_domains[domain.element_id] = domain
            
            # Process members recursively
            for member in domain.members:
                self._add_domain_to_collection(member)
    
    def _validate_structure(self):
        """Validate the dimensional structure."""
        # Check for required relationships
        for table in sum(self.tables.values(), []):
            # Hypercube should have at least one dimension
            if not table.axes:
                logging.warning(f"Table {table.element_id} has no dimensions")
            
            # Each dimension should have a domain (for explicit dimensions)
            for axis in table.axes:
                if not axis.is_typed_dimension and not axis.domain:
                    logging.warning(f"Explicit dimension {axis.element_id} has no domain")
                
                # Each dimension should have a default member
                if not axis.is_typed_dimension and not axis.default_member:
                    logging.warning(f"Dimension {axis.element_id} has no default member")
```

### 10.2 Context Qualification Example
```python
def get_dimensional_context_info(context, dimensional_structure):
    """
    Extract dimensional information from a context.
    
    Args:
        context: Context object from instance parser
        dimensional_structure: Result from definition linkbase parser
    
    Returns:
        Dictionary mapping dimension IDs to member IDs
    """
    dimensions = {}
    
    # Process segment
    if hasattr(context.entity, 'segment') and context.entity.segment:
        for item in context.entity.segment:
            if hasattr(item, 'dimension_name') and hasattr(item, 'member_name'):
                dimensions[item.dimension_name] = item.member_name
    
    # Process scenario
    if hasattr(context, 'scenario') and context.scenario:
        for item in context.scenario:
            if hasattr(item, 'dimension_name') and hasattr(item, 'member_name'):
                dimensions[item.dimension_name] = item.member_name
    
    return dimensions
```

### 10.3 Finding Facts for a Table
```python
def find_facts_for_table(table, facts, contexts, dimensional_structure):
    """
    Find all facts that belong to a specific table.
    
    Args:
        table: Table object
        facts: List of facts from instance document
        contexts: Dictionary of contexts by ID
        dimensional_structure: Result from definition linkbase parser
    
    Returns:
        List of facts that belong to this table
    """
    table_facts = []
    
    # Get line items for this table
    line_items = table.line_items
    
    # Process each fact
    for fact in facts:
        # Check if fact is a line item for this table
        concept_local_name = fact.concept_local_name
        if concept_local_name not in line_items:
            continue
        
        # Get context for this fact
        if fact.context_ref not in contexts:
            continue
            
        context = contexts[fact.context_ref]
        
        # Get dimensional qualifiers for this context
        context_dimensions = get_dimensional_context_info(context, dimensional_structure)
        
        # Check if dimensions match table's axes
        belongs_to_table = True
        
        if table.closed:
            # For closed hypercubes, context must only use dimensions in this table
            table_axes = [axis.element_id for axis in table.axes]
            
            for dim_id in context_dimensions:
                if dim_id not in table_axes:
                    belongs_to_table = False
                    break
        
        # Check each axis in the table
        for axis in table.axes:
            if axis.is_typed_dimension:
                # Typed dimensions would need special handling - skip for now
                continue
                
            if axis.element_id in context_dimensions:
                # Context specifies this dimension - check if member is valid
                member_id = context_dimensions[axis.element_id]
                
                # Check if member is in this dimension's domain
                if not _is_member_in_domain(member_id, axis.domain):
                    belongs_to_table = False
                    break
            else:
                # Context doesn't specify this dimension, should use default
                # Nothing to check here - fact is still valid
                pass
        
        if belongs_to_table:
            table_facts.append(fact)
    
    return table_facts

def _is_member_in_domain(member_id, domain):
    """
    Check if a member is in a domain or its descendants.
    
    Args:
        member_id: Element ID of the member to check
        domain: Domain object to check against
    
    Returns:
        True if member is in domain, False otherwise
    """
    # Check if member is the domain itself
    if domain.element_id == member_id:
        return True
    
    # Check each member recursively
    for member in domain.members:
        if _is_member_in_domain(member_id, member):
            return True
    
    return False
```

## 11. Testing Strategy

### 11.1 Unit Tests
- Test XML parsing capability with sample definition linkbase files
- Validate relationship extraction with controlled input
- Test table construction algorithm with various dimensional structures
- Verify domain hierarchy building with nested domains
- Test default member resolution with explicit and implicit defaults
- Use pytest for organizing and executing tests

### 11.2 Integration Tests
- Test end-to-end parsing of sample definition linkbases
- Verify correct extraction and processing of dimensional structures
- Test integration with schema, presentation, and calculation information
- Verify context qualification against instance documents

### 11.3 Performance Tests
- Measure parsing time for definition linkbases of varying sizes
- Test domain hierarchy construction performance with deep hierarchies
- Verify memory usage patterns for complex dimensional structures

### 11.4 Regression Tests
- Maintain a suite of real-world definition linkbases
- Compare dimensional structures against known-good baselines
- Verify table structures against expected outcomes
- Test with complex dimensional hierarchies

## 12. Usage Example

### 12.1 Basic Usage
```python
# Create parser instance
parser = DefinitionLinkbaseParser()

# Parse definition linkbase
parsed_structure = parser.parse(
    'company-20231231_def.xml',
    # Pass schema info if available
    schema_info=schema_parser.parse('company-20231231.xsd'),
    # Pass labels if available
    element_labels=label_parser.get_labels()
)

# Print available roles with tables
print("Available tables by role:")
for role_uri, tables in parsed_structure['tables'].items():
    role_def = parsed_structure['roles'].get(role_uri).definition
    print(f"- {role_def} ({role_uri}): {len(tables)} tables")

# Print table structure for a specific role
segment_role = next(
    (role_uri for role_uri, role in parsed_structure['roles'].items() 
     if 'segment' in (role.definition or '').lower()),
    None
)

if segment_role and segment_role in parsed_structure['tables']:
    tables = parsed_structure['tables'][segment_role]
    
    for table in tables:
        print(f"\nTable: {table.label}")
        print(f"Line items: {len(table.line_items)}")
        print(f"Axes ({len(table.axes)}):")
        
        for axis in table.axes:
            print(f"  - {axis.label}")
            
            if axis.domain:
                print(f"    Domain: {axis.domain.label}")
                print(f"    Members: {len(axis.domain.members)}")
                
                if axis.default_member:
                    print(f"    Default: {axis.default_member.label}")
```

### 12.2 Querying Facts by Dimension
```python
def query_facts_by_dimension(facts, contexts, dimension_id, member_id=None):
    """
    Query facts qualified by a specific dimension and optionally member.
    
    Args:
        facts: List of facts from instance parser
        contexts: Dictionary of contexts from instance parser
        dimension_id: Element ID of the dimension to filter by
        member_id: Optional element ID of the member to filter by
    
    Returns:
        List of facts qualified by the dimension/member
    """
    filtered_facts = []
    
    for fact in facts:
        # Get context
        if fact.context_ref not in contexts:
            continue
            
        context = contexts[fact.context_ref]
        
        # Extract dimensional qualifiers
        has_dimension = False
        matches_member = True
        
        # Check segment
        if hasattr(context.entity, 'segment') and context.entity.segment:
            for item in context.entity.segment:
                if (hasattr(item, 'dimension_name') and 
                        hasattr(item, 'member_name') and
                        item.dimension_name == dimension_id):
                    has_dimension = True
                    
                    if member_id and item.member_name != member_id:
                        matches_member = False
                    
                    break
        
        # Check scenario
        if not has_dimension and hasattr(context, 'scenario') and context.scenario:
            for item in context.scenario:
                if (hasattr(item, 'dimension_name') and 
                        hasattr(item, 'member_name') and
                        item.dimension_name == dimension_id):
                    has_dimension = True
                    
                    if member_id and item.member_name != member_id:
                        matches_member = False
                    
                    break
        
        if has_dimension and matches_member:
            filtered_facts.append(fact)
    
    return filtered_facts

# Example usage
instance_parser = XBRLInstanceParser()
instance_result = instance_parser.parse('company-20231231.xml')

# Find facts qualified by the "ReportingSegment" dimension
segment_facts = query_facts_by_dimension(
    instance_result['facts'],
    instance_result['contexts'],
    'ReportingSegmentAxis'
)

print(f"\nFound {len(segment_facts)} facts qualified by segment dimension")

# Find facts qualified by a specific segment
product_segment_facts = query_facts_by_dimension(
    instance_result['facts'],
    instance_result['contexts'],
    'ReportingSegmentAxis',
    'ProductSegmentMember'
)

print(f"Found {len(product_segment_facts)} facts for the product segment")
```

### 12.3 Reconstructing Tables with Data
```python
def reconstruct_table(table, facts, contexts, dimensional_structure, element_labels=None):
    """
    Reconstruct a table with data from an instance document.
    
    Args:
        table: Table object from definition parser
        facts: List of facts from instance parser
        contexts: Dictionary of contexts from instance parser
        dimensional_structure: Result from definition linkbase parser
        element_labels: Optional dictionary of element labels
    
    Returns:
        Dictionary representing the reconstructed table with data
    """
    # Find all facts for this table
    table_facts = find_facts_for_table(table, facts, contexts, dimensional_structure)
    
    # Group facts by line item and dimensional qualifiers
    fact_matrix = {}
    
    for fact in table_facts:
        concept = fact.concept_local_name
        context_id = fact.context_ref
        context = contexts[context_id]
        
        # Get dimensional qualifiers
        dimensions = get_dimensional_context_info(context, dimensional_structure)
        
        # Create a key for this combination of dimensions
        dim_key = tuple(sorted([f"{dim}={val}" for dim, val in dimensions.items()]))
        
        # Add to matrix
        if concept not in fact_matrix:
            fact_matrix[concept] = {}
            
        fact_matrix[concept][dim_key] = fact
    
    # Construct table structure
    result = {
        'table_id': table.element_id,
        'table_label': element_labels.get(table.element_id, table.element_id) if element_labels else table.element_id,
        'axes': [],
        'line_items': [],
        'data': {}
    }
    
    # Add axes information
    for axis in table.axes:
        axis_info = {
            'id': axis.element_id,
            'label': element_labels.get(axis.element_id, axis.element_id) if element_labels else axis.element_id,
            'members': []
        }
        
        # Add domain members
        if axis.domain:
            axis_info['domain'] = {
                'id': axis.domain.element_id,
                'label': element_labels.get(axis.domain.element_id, axis.domain.element_id) if element_labels else axis.domain.element_id
            }
            
            # Collect members
            all_members = []
            _collect_domain_members(axis.domain, all_members)
            
            for member in all_members:
                member_info = {
                    'id': member.element_id,
                    'label': element_labels.get(member.element_id, member.element_id) if element_labels else member.element_id
                }
                axis_info['members'].append(member_info)
        
        result['axes'].append(axis_info)
    
    # Add line items
    for line_item in table.line_items:
        item_label = element_labels.get(line_item, line_item) if element_labels else line_item
        result['line_items'].append({
            'id': line_item,
            'label': item_label
        })
    
    # Add data
    result['data'] = fact_matrix
    
    return result

def _collect_domain_members(domain, result_list):
    """
    Recursively collect all members in a domain hierarchy.
    
    Args:
        domain: Domain object
        result_list: List to append members to
    """
    # Add this domain
    result_list.append(domain)
    
    # Add all children recursively
    for member in domain.members:
        _collect_domain_members(member, result_list)
```

## 13. Advanced Features

### 13.1 Handling Typed Dimensions

Typed dimensions allow for values that aren't predefined as explicit domain members. To handle these:

```python
def process_typed_dimension_value(typed_value_element):
    """
    Process the value of a typed dimension.
    
    Args:
        typed_value_element: XML element containing the typed value
    
    Returns:
        Processed typed dimension value
    """
    # This will depend on the specific type of the typed dimension
    # Simple example for text or numeric values
    if typed_value_element.text:
        return typed_value_element.text.strip()
        
    # For more complex values, may need to process child elements
    children = list(typed_value_element)
    if children:
        # Process according to the element's structure
        # This is just a placeholder - actual implementation would depend on the specific typed domain
        return {child.tag: child.text for child in children}
        
    return None

def extract_typed_dimensions(segment_element, schema_info=None):
    """
    Extract typed dimensions from a segment element.
    
    Args:
        segment_element: XML segment element
        schema_info: Optional schema information
    
    Returns:
        Dictionary mapping dimension IDs to typed values
    """
    typed_dimensions = {}
    
    for child in segment_element:
        # Check if this is a typed dimension
        if 'dimension' in child.attrib:
            dimension_id = child.attrib['dimension']
            
            # Get the typed domain definition if available
            typed_domain_ref = None
            if schema_info and dimension_id in schema_info:
                typed_domain_ref = schema_info[dimension_id].get('typedDomainRef')
            
            # Process typed dimension value
            # There should be exactly one child element containing the value
            value_elements = list(child)
            if value_elements:
                typed_value = process_typed_dimension_value(value_elements[0])
                typed_dimensions[dimension_id] = typed_value
    
    return typed_dimensions
```

### 13.2 Cross-Role References

XBRL dimensions can use targetRole to reference relationships in other extended link roles:

```python
def resolve_target_roles(relationships):
    """
    Resolve target roles in definition relationships.
    
    Args:
        relationships: List of DefinitionRelationship objects
    
    Returns:
        Dictionary mapping (from_element, to_element, role) to target_role
    """
    target_roles = {}
    
    for rel in relationships:
        if rel.targetRole:
            key = (rel.from_element, rel.to_element, rel.role)
            target_roles[key] = rel.targetRole
    
    return target_roles

def build_complete_dimensional_structure(relationships, roles):
    """
    Build a complete dimensional structure resolving target roles.
    
    Args:
        relationships: List of DefinitionRelationship objects
        roles: Dictionary of ExtendedLinkRole objects
    
    Returns:
        Dictionary with complete dimensional structure
    """
    # First build target role map
    target_roles = resolve_target_roles(relationships)
    
    # Group relationships by role
    role_rels = defaultdict(list)
    for rel in relationships:
        role_rels[rel.role].append(rel)
    
    # Process each role
    complete_structure = {}
    
    for role_uri, role in roles.items():
        # Build initial structure for this role
        structure = build_dimensional_tables(role_rels[role_uri], role_uri)
        
        # Find relationships with target roles
        for rel in role_rels[role_uri]:
            if rel.targetRole:
                # This relationship points to another role
                # In a full implementation, we would follow these references
                # and merge the dimensional structures
                pass
        
        complete_structure[role_uri] = structure
    
    return complete_structure
```

### 13.3 Integration with pandas for Analysis

```python
def dimensions_to_dataframe(dimensional_structure):
    """
    Convert dimensional structure to pandas DataFrames for analysis.
    
    Args:
        dimensional_structure: Result from definition linkbase parser
    
    Returns:
        Dictionary of pandas DataFrames
    """
    import pandas as pd
    
    result = {
        'tables': None,
        'axes': None,
        'domains': None,
        'relationships': None
    }
    
    # Create tables DataFrame
    tables_data = []
    for role_uri, tables in dimensional_structure['tables'].items():
        role_def = dimensional_structure['roles'].get(role_uri, ExtendedLinkRole()).definition
        
        for table in tables:
            tables_data.append({
                'table_id': table.element_id,
                'table_label': table.label,
                'role_uri': role_uri,
                'role_definition': role_def,
                'line_items_count': len(table.line_items),
                'axes_count': len(table.axes),
                'closed': table.closed,
                'context_element': table.context_element
            })
    
    result['tables'] = pd.DataFrame(tables_data)
    
    # Create axes DataFrame
    axes_data = []
    for axis_id, axis in dimensional_structure['all_axes'].items():
        axes_data.append({
            'axis_id': axis.element_id,
            'axis_label': axis.label,
            'is_typed': axis.is_typed_dimension,
            'typed_domain_ref': axis.typed_domain_ref if axis.is_typed_dimension else None,
            'domain_id': axis.domain.element_id if axis.domain else None,
            'domain_label': axis.domain.label if axis.domain else None,
            'default_member_id': axis.default_member.element_id if axis.default_member else None,
            'members_count': len(axis.domain.members) if axis.domain else 0
        })
    
    result['axes'] = pd.DataFrame(axes_data)
    
    # Create domains DataFrame
    domains_data = []
    
    def _add_domain_to_data(domain, parent_id=None, depth=0):
        domains_data.append({
            'domain_id': domain.element_id,
            'domain_label': domain.label,
            'parent_id': parent_id,
            'depth': depth,
            'children_count': len(domain.members)
        })
        
        for member in domain.members:
            _add_domain_to_data(member, domain.element_id, depth + 1)
    
    for domain_id, domain in dimensional_structure['all_domains'].items():
        if not domain.parent:  # Only process top-level domains
            _add_domain_to_data(domain)
    
    result['domains'] = pd.DataFrame(domains_data)
    
    # Create relationships DataFrame
    rel_data = []
    for rel in dimensional_structure['relationships']:
        rel_data.append({
            'from_element': rel.from_element,
            'to_element': rel.to_element,
            'arcrole': rel.arcrole,
            'role_uri': rel.role,
            'order': rel.order,
            'priority': rel.priority,
            'closed': rel.closed,
            'context_element': rel.contextElement,
            'target_role': rel.targetRole
        })
    
    result['relationships'] = pd.DataFrame(rel_data)
    
    return result

# Example usage
import pandas as pd

dfs = dimensions_to_dataframe(parsed_structure)

print("\nTables summary:")
print(dfs['tables'][['table_id', 'role_definition', 'axes_count']].head())

print("\nAxes summary:")
print(dfs['axes'][['axis_id', 'is_typed', 'members_count']].head())

# Analyze relationship types
print("\nArcrole distribution:")
arcrole_counts = dfs['relationships']['arcrole'].value_counts()
print(arcrole_counts)
```

## 14. Conclusion

The XBRL Definition Linkbase Parser is designed to efficiently process and structure the dimensional relationships defined in XBRL definition linkbases. By implementing this design in Python, you'll have a robust foundation for understanding the multi-dimensional aspects of XBRL financial reports, particularly those found in SEC filings.

The parser handles the complexity of XBRL dimensions, including tables, axes, domains, and their relationships. It provides a clean, accessible model that can be used for organizing dimensionally qualified facts, analyzing complex disclosures, and reconstructing tabular data from instance documents.

When combined with the Instance Document Parser, Presentation Linkbase Parser, and Calculation Linkbase Parser, this component completes the core set of XBRL linkbase parsers needed for a comprehensive XBRL processing system. Together, these components enable the full interpretation and analysis of XBRL-based financial reports, preserving both the data and its complex multi-dimensional structure.
    