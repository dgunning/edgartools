# XBRL Calculation Linkbase Parser Design (Python)

## 1. Overview

The Calculation Linkbase Parser is responsible for processing the mathematical relationships defined in XBRL calculation linkbases. These linkbases define summation-item relationships that specify how numeric values should add up in financial statements. This design document outlines a Python implementation for parsing calculation relationships, building calculation trees, and validating the mathematical consistency of XBRL facts.

```
┌─────────────────┐     ┌─────────────────────────┐     ┌─────────────────┐
│                 │     │                         │     │                 │
│  Calculation    │────▶│  Calculation Linkbase   │────▶│  Calculation    │
│  Linkbase       │     │  Parser                 │     │  Network        │
│                 │     │                         │     │                 │
└─────────────────┘     └─────────────────────────┘     └─────────────────┘
```

## 2. Input and Output

### 2.1 Input
- XBRL calculation linkbase file (XML file, typically with _cal.xml extension)
- Reference to taxonomy schema file for resolving element references
- Optional: Element information including balance types and period types

### 2.2 Output
- Calculation network organized by extended link roles (ELRs)
- For each ELR: a set of summation-item relationships with weights
- Validation capability to verify calculation consistency with instance data

## 3. Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Calculation Linkbase Parser                     │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ XML           │  │ Linkbase      │  │ Role          │    │
│  │ Parser        │  │ Processor     │  │ Extractor     │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Calculation   │  │ Weight        │  │ Balance       │    │
│  │ Arc Processor │  │ Handler       │  │ Evaluator     │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Calculation   │  │ Consistency   │  │ Validation    │    │
│  │ Tree Builder  │  │ Checker       │  │ Engine        │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 4. Data Structures

### 4.1 Extended Link Role (ELR)
```python
class ExtendedLinkRole:
    def __init__(self):
        self.role_uri = ""      # URI of the role (e.g., "http://example.com/role/BalanceSheet")
        self.role_id = ""       # ID of the role (optional)
        self.definition = ""    # Human-readable description
        self.order = 0          # Ordering value if provided
```

### 4.2 Calculation Relationship
```python
class CalculationRelationship:
    def __init__(self):
        self.from_element = ""      # Element ID/name of parent (summation)
        self.to_element = ""        # Element ID/name of child (item)
        self.weight = 1.0           # Weight value (1.0 for addition, -1.0 for subtraction)
        self.order = 0.0            # Order value (for presentation ordering)
        self.role = ""              # Extended link role this relationship belongs to
        self.arcrole = ""           # Arc role (almost always "summation-item")
        self.priority = 0           # Priority of the arc (for conflict resolution)
        self.prohibited = False     # Whether this relationship is prohibited
```

### 4.3 Calculation Node
```python
class CalculationNode:
    def __init__(self):
        self.element_id = ""        # Element ID/name
        self.children = []          # List of child nodes
        self.parent = None          # Parent node (None for root)
        self.weight = 1.0           # Weight of relationship to parent
        self.order = 0.0            # Ordering position among siblings
        
        # Information typically linked from schema
        self.balance_type = ""      # "debit", "credit", or None
        self.period_type = ""       # "instant" or "duration"
```

### 4.4 Calculation Tree
```python
class CalculationTree:
    def __init__(self):
        self.role_uri = ""          # Extended link role URI
        self.definition = ""        # Human-readable description
        self.root = None            # Root node of the tree
        self.all_nodes = {}         # Dictionary of all nodes by element ID
```

### 4.5 Calculation Network
```python
class CalculationNetwork:
    def __init__(self):
        self.roles = {}             # Dictionary of ExtendedLinkRole by URI
        self.relationships = []     # List of all CalculationRelationship objects
        self.trees = {}             # Dictionary of CalculationTree by role URI
```

### 4.6 Calculation Inconsistency
```python
class CalculationInconsistency:
    def __init__(self):
        self.parent_element = ""    # Parent element ID
        self.parent_value = None    # Parent element value
        self.calculated_value = None  # Value calculated from children
        self.difference = None      # Difference between parent and calculated value
        self.context_id = ""        # Context ID where inconsistency occurs
        self.children = []          # List of child elements and values causing inconsistency
```

## 5. Detailed Process Flow

### 5.1 Initialization and XML Parsing
1. Initialize parser with calculation linkbase file path
2. Set up XML parser with appropriate namespaces
3. Load linkbase file into DOM parser
4. Extract linkbase root element and validate it's a calculation linkbase

### 5.2 Role Extraction
1. Extract all extended link role (ELR) definitions 
2. Process role URIs, IDs, and definitions
3. Create role registry mapping URIs to role objects
4. Sort roles by their designated order if available

### 5.3 Calculation Arc Extraction
1. Extract all calculation arcs (`<calculationArc>` elements)
2. For each arc:
   - Extract from/to attributes and resolve element references
   - Extract weight attribute (default to 1.0 if missing)
   - Extract order attribute
   - Process arc priority and use attributes for conflict resolution
   - Create relationship object and add to collection

### 5.4 Tree Construction
1. Group relationships by extended link role 
2. For each role:
   - Identify root elements (elements that appear as "from" but not "to")
   - Build calculation tree from each root element by following relationships
   - Apply ordering to child elements
   - Handle duplicate relationships appropriately
   - Detect and resolve cycles (should not exist in valid linkbases)

### 5.5 Schema Integration
1. If schema information is provided, integrate balance and period types into nodes
2. Verify that calculation weights are consistent with balance types according to XBRL rules
3. Flag or fix any inconsistencies in weight assignments

### 5.6 Validation
1. Ensure no prohibited relationships are included
2. Check that all elements have compatible period types
3. Verify that the network does not contain circular references
4. Check that the calculation parents have compatible data types with their children

## 6. Algorithms

### 6.1 Weight Validation Algorithm
```python
def validate_calculation_weight(relationship, element_info):
    """
    Validate that the weight of a calculation relationship is consistent with 
    balance types of parent and child elements.
    
    Args:
        relationship: CalculationRelationship object
        element_info: Dictionary mapping element IDs to their properties
    
    Returns:
        True if weight is valid, False otherwise
    """
    parent_id = relationship.from_element
    child_id = relationship.to_element
    weight = relationship.weight
    
    # Skip validation if element info is not available
    if not element_info or parent_id not in element_info or child_id not in element_info:
        return True
    
    parent_balance = element_info[parent_id].get('balance_type')
    child_balance = element_info[child_id].get('balance_type')
    
    # Skip validation if balance types are not available
    if not parent_balance or not child_balance:
        return True
    
    # XBRL calculation weight rules:
    # Parent balance | Child balance | Valid weight
    # --------------------------------------
    # debit         | debit         | 1.0
    # debit         | credit        | -1.0
    # credit        | debit         | -1.0
    # credit        | credit        | 1.0
    
    if parent_balance == child_balance:
        # Same balance type - weight should be 1.0
        return weight == 1.0
    else:
        # Different balance types - weight should be -1.0
        return weight == -1.0
```

### 6.2 Calculation Tree Construction Algorithm
```python
def build_calculation_tree(relationships, role_uri, element_info=None):
    """
    Build a calculation tree from a set of relationships for a specific role.
    
    Args:
        relationships: List of CalculationRelationship objects
        role_uri: The extended link role URI for which to build the tree
        element_info: Optional dictionary of element information
    
    Returns:
        CalculationTree object
    """
    tree = CalculationTree()
    tree.role_uri = role_uri
    
    # Filter relationships for this role
    role_relationships = [r for r in relationships if r.role == role_uri]
    
    # Group relationships by source element
    from_map = {}
    to_map = {}
    
    for rel in role_relationships:
        from_map.setdefault(rel.from_element, []).append(rel)
        to_map.setdefault(rel.to_element, []).append(rel)
    
    # Find root elements (appear as 'from' but not as 'to')
    root_elements = set(from_map.keys()) - set(to_map.keys())
    
    # If no root found, use all 'from' elements as potential roots
    if not root_elements:
        root_elements = set(from_map.keys())
    
    # Create multiple trees if needed (one for each root)
    root_nodes = []
    for element_id in sorted(root_elements):
        if element_id in from_map:
            root_node = _create_calculation_node_recursive(
                element_id, from_map, tree.all_nodes, 1.0, element_info
            )
            root_nodes.append(root_node)
    
    # If only one root, use it directly
    if len(root_nodes) == 1:
        tree.root = root_nodes[0]
    else:
        # Create a dummy root to hold multiple roots
        dummy_root = CalculationNode()
        dummy_root.element_id = f"_root_{role_uri.split('/')[-1]}"
        tree.all_nodes[dummy_root.element_id] = dummy_root
        
        for node in root_nodes:
            node.parent = dummy_root
            node.weight = 1.0  # Weight to dummy root is always 1.0
            dummy_root.children.append(node)
            
        tree.root = dummy_root
    
    return tree

def _create_calculation_node_recursive(element_id, from_map, all_nodes, weight, element_info=None):
    """
    Recursively create nodes for an element and all its descendants.
    
    Args:
        element_id: The element ID to create a node for
        from_map: Map of from_element to relationships
        all_nodes: Dictionary to store all created nodes
        weight: Weight of this element to its parent
        element_info: Optional dictionary of element information
    
    Returns:
        The created node
    """
    # Return existing node if already created
    if element_id in all_nodes:
        return all_nodes[element_id]
    
    # Create new node
    node = CalculationNode()
    node.element_id = element_id
    node.weight = weight
    all_nodes[element_id] = node
    
    # Add schema information if available
    if element_info and element_id in element_info:
        node.balance_type = element_info[element_id].get('balance_type')
        node.period_type = element_info[element_id].get('period_type')
    
    # Process children
    if element_id in from_map:
        # Sort relationships by order
        sorted_relationships = sorted(from_map[element_id], key=lambda r: r.order)
        
        for rel in sorted_relationships:
            child_id = rel.to_element
            
            # Check for cycles
            if child_id == element_id or child_id in all_nodes:
                continue  # Skip self-references and already processed nodes
            
            child_weight = rel.weight
            child_node = _create_calculation_node_recursive(
                child_id, from_map, all_nodes, child_weight, element_info
            )
            child_node.parent = node
            child_node.order = rel.order
            node.children.append(child_node)
    
    return node
```

### 6.3 Calculation Consistency Checking Algorithm
```python
def check_calculation_consistency(calculation_tree, facts, contexts, tolerance=0.01):
    """
    Check calculation consistency for a specific calculation tree and set of facts.
    
    Args:
        calculation_tree: CalculationTree object
        facts: List of facts from instance document
        contexts: Dictionary of contexts by ID
        tolerance: Tolerance for rounding differences
    
    Returns:
        List of CalculationInconsistency objects
    """
    inconsistencies = []
    
    # Create lookup map for facts by element ID and context ID
    fact_map = {}
    for fact in facts:
        if hasattr(fact, 'numeric_value') and fact.numeric_value is not None:
            key = (fact.concept_local_name, fact.context_ref)
            fact_map[key] = fact
    
    # Process calculation tree
    for context_id, context in contexts.items():
        # Skip contexts without periods or with segment/scenario (for simplicity)
        if not hasattr(context, 'period') or not context.period:
            continue
            
        _check_subtree_consistency(calculation_tree.root, fact_map, context_id, inconsistencies, tolerance)
    
    return inconsistencies

def _check_subtree_consistency(node, fact_map, context_id, inconsistencies, tolerance):
    """
    Recursively check calculation consistency for a subtree.
    
    Args:
        node: Current CalculationNode
        fact_map: Map of facts by (element_id, context_id)
        context_id: Context ID to check
        inconsistencies: List to append inconsistencies to
        tolerance: Tolerance for rounding differences
    
    Returns:
        Tuple of (has_value, value) for this subtree
    """
    # Skip calculation for dummy roots
    if node.element_id.startswith('_root_'):
        return False, None
    
    # Check if this node has a fact
    element_id = node.element_id.split(':')[-1] if ':' in node.element_id else node.element_id
    fact_key = (element_id, context_id)
    
    has_fact = fact_key in fact_map
    fact_value = fact_map[fact_key].numeric_value if has_fact else None
    
    # If no children, just return the value
    if not node.children:
        return has_fact, fact_value
    
    # Calculate sum of children
    children_sum = 0
    children_values = []
    all_children_have_values = True
    
    for child in node.children:
        child_has_value, child_value = _check_subtree_consistency(
            child, fact_map, context_id, inconsistencies, tolerance
        )
        
        if child_has_value:
            weighted_value = child_value * child.weight
            children_sum += weighted_value
            children_values.append((child.element_id, child_value, child.weight, weighted_value))
        else:
            all_children_have_values = False
    
    # If all children have values and this node has a value, check consistency
    if all_children_have_values and has_fact and len(children_values) > 0:
        difference = abs(fact_value - children_sum)
        
        if difference > tolerance:
            # Create inconsistency record
            inconsistency = CalculationInconsistency()
            inconsistency.parent_element = node.element_id
            inconsistency.parent_value = fact_value
            inconsistency.calculated_value = children_sum
            inconsistency.difference = difference
            inconsistency.context_id = context_id
            inconsistency.children = children_values
            
            inconsistencies.append(inconsistency)
    
    return has_fact, fact_value
```

## 7. Performance Considerations

### 7.1 Memory Optimization
- Use element IDs rather than full element objects in relationships
- Implement efficient lookups for fact validation
- Consider sparse matrix techniques for large calculation networks

### 7.2 Parsing Efficiency
- Pre-compile XPath expressions for common element selections
- Cache resolved element references
- Process arcs in batches grouped by extended link role

### 7.3 Scalability
- Implement parallel processing for independent extended link roles
- Use lazy evaluation for calculation validation
- Design efficient data structures for incremental validation

## 8. Error Handling

### 8.1 Error Types
- XML parsing errors
- Inconsistent calculation weights
- Invalid relationship structures
- Circular references
- Calculation inconsistencies
- Period type mismatches

### 8.2 Error Handling Strategy
- Distinguish between structural errors (in the linkbase) and validation errors (with instance data)
- Provide detailed error messages with context
- Implement recovery strategies for non-fatal errors
- Log warnings for calculation inconsistencies
- Support different tolerance levels for calculation validation

### 8.3 Validation
- Validate against XBRL 2.1 calculation linkbase requirements
- Check that weights are consistent with balance types
- Ensure no prohibited arcs are incorrectly processed
- Verify period type compatibility in summation-item relationships

## 9. Extension Points

### 9.1 Custom Validation Rules
- Allow registration of custom consistency rules
- Support additional validation logic beyond standard XBRL rules
- Enable entity-specific validation thresholds

### 9.2 Calculator Extensions
- Support plugins for alternative calculation methods
- Allow custom rounding and tolerance handling
- Enable integration with specialized numeric processing

### 9.3 Integration Points
- Provide interfaces for integration with instance document processors
- Support integration with presentation linkbase processors
- Enable custom reporting of calculation inconsistencies

## 10. Implementation Example

### 10.1 Basic Parser Implementation
```python
import xml.etree.ElementTree as ET
import re
from collections import defaultdict
import logging

class CalculationLinkbaseParser:
    def __init__(self, options=None):
        self.options = options or {}
        self.roles = {}
        self.relationships = []
        self.trees = {}
        self.element_info = {}  # Information about elements from schema
        
        # Define namespaces
        self.ns = {
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xbrli': 'http://www.xbrl.org/2003/instance'
        }
    
    def parse(self, linkbase_path, schema_info=None):
        """
        Parse an XBRL calculation linkbase file.
        
        Args:
            linkbase_path: Path to the calculation linkbase file
            schema_info: Optional dictionary of element information from schema
        
        Returns:
            Dictionary containing parsed calculation network
        """
        try:
            # Store schema info if provided
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
            
            # Build calculation trees
            self._build_trees()
            
            # Validate the network
            self._validate_network()
            
            return {
                'roles': self.roles,
                'relationships': self.relationships,
                'trees': self.trees
            }
            
        except Exception as e:
            logging.error(f"Error parsing calculation linkbase: {str(e)}")
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
            calculation_links = root.findall(f'.//{{{self.ns["link"]}}}calculationLink')
            for link in calculation_links:
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
        """Extract calculation relationships from the linkbase."""
        calculation_links = root.findall(f'.//{{{self.ns["link"]}}}calculationLink')
        
        for link in calculation_links:
            role_uri = link.get(f'{{{self.ns["xlink"]}}}role')
            if not role_uri:
                continue
                
            # Get all arcs in this link
            arcs = link.findall(f'.//{{{self.ns["link"]}}}calculationArc')
            
            for arc in arcs:
                # Get required attributes
                from_attr = arc.get(f'{{{self.ns["xlink"]}}}from')
                to_attr = arc.get(f'{{{self.ns["xlink"]}}}to')
                
                if not from_attr or not to_attr:
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
                rel = CalculationRelationship()
                rel.from_element = from_element
                rel.to_element = to_element
                rel.role = role_uri
                rel.arcrole = arc.get(f'{{{self.ns["xlink"]}}}arcrole')
                
                # Get optional attributes
                weight_attr = arc.get('weight')
                rel.weight = float(weight_attr) if weight_attr else 1.0
                
                order_attr = arc.get('order')
                rel.order = float(order_attr) if order_attr else 0.0
                
                priority_attr = arc.get('priority')
                rel.priority = int(priority_attr) if priority_attr else 0
                
                # Check use attribute (prohibited relationships should be filtered)
                use_attr = arc.get('use', 'optional')
                if use_attr == 'prohibited':
                    rel.prohibited = True
                
                self.relationships.append(rel)
        
        # Filter out prohibited relationships
        self._filter_prohibited_relationships()
    
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
        # Group by from/to/role
        rel_dict = defaultdict(list)
        for rel in self.relationships:
            key = (rel.from_element, rel.to_element, rel.role)
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
    
    def _build_trees(self):
        """Build calculation trees for each role."""
        # Group relationships by role
        role_rels = defaultdict(list)
        for rel in self.relationships:
            role_rels[rel.role].append(rel)
        
        # Build tree for each role
        for role_uri, rels in role_rels.items():
            tree = build_calculation_tree(rels, role_uri, self.element_info)
            
            # Set definition from role registry
            if role_uri in self.roles:
                tree.definition = self.roles[role_uri].definition
            
            self.trees[role_uri] = tree
    
    def _validate_network(self):
        """Validate the calculation network."""
        # Validate weights based on balance types
        for rel in self.relationships:
            if not validate_calculation_weight(rel, self.element_info):
                logging.warning(
                    f"Invalid calculation weight: {rel.weight} for relationship "
                    f"from {rel.from_element} to {rel.to_element}"
                )
```

### 10.2 Calculation Validation Example
```python
def validate_instance_calculations(calculation_network, instance_parser_result, tolerance=0.01):
    """
    Validate calculations in an instance document using a calculation network.
    
    Args:
        calculation_network: Parsed calculation network
        instance_parser_result: Result from instance document parser
        tolerance: Tolerance for rounding differences
    
    Returns:
        List of calculation inconsistencies
    """
    facts = instance_parser_result['facts']
    contexts = instance_parser_result['contexts']
    
    all_inconsistencies = []
    
    # Process each calculation tree
    for role_uri, tree in calculation_network['trees'].items():
        # Check for inconsistencies in this tree
        inconsistencies = check_calculation_consistency(tree, facts, contexts, tolerance)
        
        for inconsistency in inconsistencies:
            # Enrich with role information
            inconsistency.role_uri = role_uri
            inconsistency.role_definition = tree.definition
            all_inconsistencies.append(inconsistency)
    
    return all_inconsistencies
```

### 10.3 Reporting Calculation Inconsistencies
```python
def report_calculation_inconsistencies(inconsistencies, element_labels=None):
    """
    Generate a human-readable report of calculation inconsistencies.
    
    Args:
        inconsistencies: List of CalculationInconsistency objects
        element_labels: Optional dictionary mapping element IDs to labels
    
    Returns:
        List of formatted inconsistency messages
    """
    reports = []
    
    for i, inconsistency in enumerate(inconsistencies):
        # Get element label if available
        parent_label = element_labels.get(inconsistency.parent_element) if element_labels else None
        parent_display = parent_label or inconsistency.parent_element
        
        # Format header
        header = f"Calculation Inconsistency #{i+1}: {parent_display}"
        if hasattr(inconsistency, 'role_definition') and inconsistency.role_definition:
            header += f" in {inconsistency.role_definition}"
        
        # Format details
        details = [
            header,
            f"Context: {inconsistency.context_id}",
            f"Reported Value: {inconsistency.parent_value:,.2f}",
            f"Calculated Value: {inconsistency.calculated_value:,.2f}",
            f"Difference: {inconsistency.difference:,.2f}"
        ]
        
        # Format children
        details.append("Contributing Items:")
        for child_element, child_value, weight, weighted_value in inconsistency.children:
            child_label = element_labels.get(child_element) if element_labels else None
            child_display = child_label or child_element
            
            weight_sign = "+" if weight > 0 else "-"
            details.append(
                f"  {child_display}: {child_value:,.2f} × {weight} = {weighted_value:,.2f}"
            )
        
        reports.append("\n".join(details))
    
    return reports
```

## 11. Testing Strategy

### 11.1 Unit Tests
- Test XML parsing capability with sample calculation linkbase files
- Validate relationship extraction with controlled input
- Test weight validation logic with different balance type combinations
- Test tree construction algorithm with various hierarchical structures
- Verify calculation consistency checking with predefined test cases
- Use pytest for organizing and executing tests

### 11.2 Integration Tests
- Test end-to-end parsing of sample calculation linkbases
- Verify correct extraction and tree building with real-world files
- Test integration with schema and instance information
- Verify calculation validation against real instance documents

### 11.3 Performance Tests
- Measure parsing time for calculation linkbases of varying sizes
- Test calculation validation performance with large instance documents
- Verify memory usage patterns for complex calculation networks

### 11.4 Regression Tests
- Maintain a suite of real-world calculation linkbases
- Compare tree structures against known-good baselines
- Verify calculation validation results against expected outcomes
- Test with known inconsistency cases to ensure proper detection

## 12. Usage Example

### 12.1 Basic Usage
```python
# Create parser instance
parser = CalculationLinkbaseParser()

# Parse calculation linkbase
parsed_network = parser.parse(
    'company-20231231_cal.xml',
    # Pass schema info if available
    schema_info=schema_parser.parse('company-20231231.xsd')
)

# Print available roles
print("Available calculation roles:")
for role_uri, role in parsed_network['roles'].items():
    print(f"- {role.definition} ({role_uri})")

# Print calculation relationships for a specific role
balance_sheet_role = next(
    (role_uri for role_uri, role in parsed_network['roles'].items() 
     if 'balance sheet' in (role.definition or '').lower()),
    None
)

if balance_sheet_role:
    relationships = [r for r in parsed_network['relationships'] if r.role == balance_sheet_role]
    print(f"\nCalculation relationships in balance sheet ({len(relationships)}):")
    for rel in relationships:
        weight_sign = "+" if rel.weight > 0 else "-"
        print(f"{rel.from_element} {weight_sign}= {rel.to_element}")
```

### 12.2 Validating Calculations in an Instance
```python
# Parse instance document
instance_parser = XBRLInstanceParser()
instance_result = instance_parser.parse('company-20231231.xml')

# Validate calculations
inconsistencies = validate_instance_calculations(
    parsed_network,
    instance_result,
    tolerance=0.01  # Allow for small rounding differences
)

# Report inconsistencies
if inconsistencies:
    print(f"\nFound {len(inconsistencies)} calculation inconsistencies:")
    
    # Get labels if available
    label_parser = LabelLinkbaseParser()
    labels = label_parser.parse('company-20231231_lab.xml')
    element_labels = {id: info['labels'].get('standard') for id, info in labels.items()}
    
    # Generate reports
    reports = report_calculation_inconsistencies(inconsistencies, element_labels)
    for report in reports:
        print("\n" + report)
        print("-" * 80)
else:
    print("\nNo calculation inconsistencies found.")
```

### 12.3 Analyzing Calculation Structure
```python
def analyze_calculation_structure(calculation_network):
    """
    Analyze the structure of a calculation network.
    
    Args:
        calculation_network: Parsed calculation network
    
    Returns:
        Dictionary with analysis results
    """
    analysis = {
        'total_relationships': len(calculation_network['relationships']),
        'total_roles': len(calculation_network['roles']),
        'total_trees': len(calculation_network['trees']),
        'role_statistics': {},
        'element_statistics': {}
    }
    
    # Analyze by role
    role_counts = {}
    for rel in calculation_network['relationships']:
        role_counts[rel.role] = role_counts.get(rel.role, 0) + 1
    
    for role_uri, count in role_counts.items():
        role_def = calculation_network['roles'].get(role_uri, ExtendedLinkRole()).definition
        analysis['role_statistics'][role_uri] = {
            'definition': role_def,
            'relationship_count': count
        }
    
    # Analyze elements
    element_counts = {}
    for rel in calculation_network['relationships']:
        element_counts[rel.from_element] = element_counts.get(rel.from_element, 0) + 1
        element_counts[rel.to_element] = element_counts.get(rel.to_element, 0) + 1
    
    # Find top elements by usage
    sorted_elements = sorted(element_counts.items(), key=lambda x: x[1], reverse=True)
    analysis['element_statistics']['top_elements'] = sorted_elements[:10]
    
    # Count element summation relationships
    summation_elements = {}
    for rel in calculation_network['relationships']:
        summation_elements[rel.from_element] = summation_elements.get(rel.from_element, 0) + 1
    
    analysis['element_statistics']['top_summation_elements'] = sorted(
        summation_elements.items(), key=lambda x: x[1], reverse=True
    )[:10]
    
    return analysis

# Example usage
calculation_analysis = analyze_calculation_structure(parsed_network)
print("\nCalculation Network Analysis:")
print(f"Total relationships: {calculation_analysis['total_relationships']}")
print(f"Total roles: {calculation_analysis['total_roles']}")

print("\nTop summation elements:")
for element, count in calculation_analysis['element_statistics']['top_summation_elements']:
    print(f"- {element}: {count} children")
```

## 13. Advanced Features

### 13.1 Cross-Statement Calculation Validation

XBRL allows elements to be reused across different statements. This can create challenges for validation when the same element appears in multiple calculation trees. To handle this:

```python
def validate_cross_statement_calculations(calculation_network, instance_result):
    """
    Validate calculations across different statements/roles.
    
    Args:
        calculation_network: Parsed calculation network
        instance_result: Result from instance document parser
    
    Returns:
        Dictionary with cross-statement analysis
    """
    # Find elements that appear in multiple roles
    element_roles = defaultdict(set)
    
    for rel in calculation_network['relationships']:
        element_roles[rel.from_element].add(rel.role)
        element_roles[rel.to_element].add(rel.role)
    
    cross_statement_elements = {
        element: roles for element, roles in element_roles.items() if len(roles) > 1
    }
    
    # Check for inconsistent usage
    inconsistencies = []
    
    for element, roles in cross_statement_elements.items():
        # Get facts for this element
        element_facts = [
            fact for fact in instance_result['facts'] 
            if fact.concept_local_name == element.split(':')[-1]
        ]
        
        # Compare usage across roles
        for role1, role2 in itertools.combinations(roles, 2):
            # Find relationships in both roles
            rels1 = [r for r in calculation_network['relationships'] 
                   if r.role == role1 and (r.from_element == element or r.to_element == element)]
            rels2 = [r for r in calculation_network['relationships'] 
                   if r.role == role2 and (r.from_element == element or r.to_element == element)]
            
            # Compare calculation weights
            for rel1 in rels1:
                for rel2 in rels2:
                    if (rel1.from_element == rel2.from_element and 
                        rel1.to_element == rel2.to_element and 
                        rel1.weight != rel2.weight):
                        
                        inconsistencies.append({
                            'element': element,
                            'role1': role1,
                            'role2': role2,
                            'relationship1': rel1,
                            'relationship2': rel2
                        })
    
    return {
        'cross_statement_elements': cross_statement_elements,
        'inconsistencies': inconsistencies
    }
```

### 13.2 Handling Calculation Exceptions

In real-world filings, some calculation inconsistencies are expected due to rounding, specially handled values, or intentional discrepancies. To handle these exceptions:

```python
def register_calculation_exceptions(validator, exceptions):
    """
    Register known calculation exceptions with the validator.
    
    Args:
        validator: The calculation validator
        exceptions: List of exception rules
    """
    validator.exceptions = exceptions
    
    # Example exception format:
    # [
    #     {
    #         'element_id': 'Assets',
    #         'context_pattern': '.*2023-12-31',  # Regex for context
    #         'tolerance': 1.0  # Custom tolerance for this specific case
    #     }
    # ]
    
    # Patch the consistency check
    original_check = validator.check_calculation_consistency
    
    def check_with_exceptions(tree, facts, contexts, default_tolerance=0.01):
        inconsistencies = original_check(tree, facts, contexts, default_tolerance)
        
        # Filter out registered exceptions
        filtered = []
        for inconsistency in inconsistencies:
            is_exception = False
            
            for exception in validator.exceptions:
                element_match = (inconsistency.parent_element == exception['element_id'])
                context_match = (
                    re.match(exception['context_pattern'], inconsistency.context_id)
                    if 'context_pattern' in exception else True
                )
                tolerance_match = (
                    inconsistency.difference <= exception.get('tolerance', default_tolerance)
                )
                
                if element_match and context_match and not tolerance_match:
                    # It's an exception but outside tolerance
                    inconsistency.is_registered_exception = True
                    filtered.append(inconsistency)
                    break
                elif element_match and context_match and tolerance_match:
                    # It's a fully matched exception - drop it
                    is_exception = True
                    break
            
            if not is_exception:
                filtered.append(inconsistency)
                
        return filtered
    
    # Replace the method
    validator.check_calculation_consistency = check_with_exceptions
```

### 13.3 Integration with pandas for Analysis

```python
def calculation_network_to_dataframe(calculation_network):
    """
    Convert calculation relationships to a pandas DataFrame for analysis.
    
    Args:
        calculation_network: The parsed calculation network
    
    Returns:
        pandas DataFrame with calculation relationships
    """
    import pandas as pd
    
    data = []
    
    for rel in calculation_network['relationships']:
        # Get role description
        role_desc = ""
        if rel.role in calculation_network['roles']:
            role_desc = calculation_network['roles'][rel.role].definition
        
        data.append({
            'from_element': rel.from_element,
            'to_element': rel.to_element,
            'weight': rel.weight,
            'role_uri': rel.role,
            'role_description': role_desc,
            'order': rel.order
        })
    
    df = pd.DataFrame(data)
    
    return df

# Example usage
import pandas as pd

df = calculation_network_to_dataframe(parsed_network)
print("\nCalculation Relationships DataFrame:")
print(df.head())

# Analyze weights
print("\nWeight distribution:")
print(df['weight'].value_counts())

# Find elements with the most children
parent_counts = df.groupby('from_element').size().sort_values(ascending=False)
print("\nTop parent elements:")
print(parent_counts.head(10))
```

## 14. Conclusion

The XBRL Calculation Linkbase Parser is designed to efficiently process and validate the mathematical relationships defined in XBRL calculation linkbases. By implementing this design in Python, you'll have a robust foundation for validating the numerical consistency of financial statements and detecting calculation inconsistencies.

The parser handles the complexity of XBRL calculation arcs, including weights, balance types, and relationship priorities. It provides a clean, accessible calculation model that can be used for validating instance document facts, analyzing calculation structures, and identifying potential reporting issues.

When combined with the Instance Document Parser and Presentation Linkbase Parser, this component enables comprehensive validation and analysis of XBRL-based financial reports, ensuring that data is not only structurally correct but also mathematically consistent.