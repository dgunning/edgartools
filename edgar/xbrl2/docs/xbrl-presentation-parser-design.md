![img.png](img.png)# XBRL Presentation Linkbase Parser Design (Python)

## 1. Overview

The Presentation Linkbase Parser is responsible for processing the hierarchical structure defined in XBRL presentation linkbases. These linkbases define how elements should be arranged and displayed in financial statements and disclosures. This design document outlines a Python implementation for parsing presentation relationships and building structured hierarchies that can be used to reconstruct financial statements in their proper organization.

```
┌─────────────────┐     ┌─────────────────────────┐     ┌─────────────────┐
│                 │     │                         │     │                 │
│  Presentation   │────▶│  Presentation Linkbase  │────▶│  Hierarchical   │
│  Linkbase       │     │  Parser                 │     │  Structure      │
│                 │     │                         │     │                 │
└─────────────────┘     └─────────────────────────┘     └─────────────────┘
```

## 2. Input and Output

### 2.1 Input
- XBRL presentation linkbase file (XML file, typically with _pre.xml extension)
- Reference to taxonomy schema file for resolving element references
- Optionally, label linkbase for resolving element labels

### 2.2 Output
- Hierarchical structure of elements organized by extended link roles (ELRs)
- For each ELR: a tree structure with parent-child relationships
- Order information for proper arrangement of elements
- Label role information for determining which label type to use for display

## 3. Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│             Presentation Linkbase Parser                     │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ XML           │  │ Linkbase      │  │ Role          │    │
│  │ Parser        │  │ Processor     │  │ Extractor     │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Arc           │  │ Tree          │  │ Preferred     │    │
│  │ Processor     │  │ Builder       │  │ Label Handler │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Cycle         │  │ Element       │  │ Validation    │    │
│  │ Detector      │  │ Resolver      │  │ Engine        │    │
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

### 4.2 Presentation Relationship
```python
class PresentationRelationship:
    def __init__(self):
        self.from_element = ""      # Element ID/name of parent
        self.to_element = ""        # Element ID/name of child
        self.order = 0.0            # Order value (float to allow insertions)
        self.preferred_label = ""   # Preferred label role (e.g., periodStart, negated)
        self.role = ""              # Extended link role this relationship belongs to
        self.arcrole = ""           # Arc role (almost always "parent-child")
        self.priority = 0           # Priority of the arc (for conflict resolution)
```

### 4.3 Presentation Node
```python
class PresentationNode:
    def __init__(self):
        self.element_id = ""        # Element ID/name
        self.parent = None          # Parent node (None for root)
        self.children = []          # List of child nodes
        self.order = 0.0            # Ordering position among siblings
        self.preferred_label = ""   # Preferred label role
        self.depth = 0              # Depth in the tree (0 for root)
        
        # Information typically linked from schema and label linkbase
        self.element_name = ""      # Element name 
        self.standard_label = ""    # Standard label
        self.is_abstract = False    # Whether element is abstract
        self.labels = {}            # Dictionary of all labels by role
```

### 4.4 Presentation Tree
```python
class PresentationTree:
    def __init__(self):
        self.role_uri = ""          # Extended link role URI
        self.definition = ""        # Human-readable description
        self.root = None            # Root node of the tree
        self.all_nodes = {}         # Dictionary of all nodes by element ID
        self.order = 0              # Order of this tree among all trees
```

### 4.5 Presentation Network
```python
class PresentationNetwork:
    def __init__(self):
        self.roles = {}             # Dictionary of ExtendedLinkRole by URI
        self.relationships = []     # List of all PresentationRelationship objects
        self.trees = {}             # Dictionary of PresentationTree by role URI
```

## 5. Detailed Process Flow

### 5.1 Initialization and XML Parsing
1. Initialize parser with presentation linkbase file path
2. Set up XML parser with appropriate namespaces
3. Load linkbase file into DOM parser
4. Extract linkbase root element and validate it's a presentation linkbase

### 5.2 Role Extraction
1. Extract all extended link role (ELR) definitions 
2. Process role URIs, IDs, and definitions
3. Create role registry mapping URIs to role objects
4. Sort roles by their designated order if available

### 5.3 Arc Extraction
1. Extract all presentation arcs (`<presentationArc>` elements)
2. For each arc:
   - Extract from/to attributes and resolve element references
   - Extract order attribute
   - Extract preferred label if specified
   - Process arc priority and use attributes for conflict resolution
   - Create relationship object and add to collection

### 5.4 Tree Construction
1. Group relationships by extended link role 
2. For each role:
   - Identify root elements (elements that appear as "from" but not "to")
   - Build tree from each root element by following relationships
   - Apply ordering to child elements
   - Handle duplicate relationships appropriately
   - Detect and resolve cycles (should not exist in valid linkbases)

### 5.5 Label Integration
1. If label linkbase is provided, integrate labels into presentation nodes
2. Process all label types (standard, period start/end, negated, etc.)
3. Associate appropriate labels based on preferred label roles

### 5.6 Validation
1. Check for orphan elements (connected to no parent or child)
2. Detect circular references
3. Validate use of preferred labels against available label roles
4. Check for relationship overrides and conflicts

## 6. Algorithms

### 6.1 Tree Construction Algorithm
```python
def build_presentation_tree(relationships, role_uri):
    """
    Build a presentation tree from a set of relationships for a specific role.
    
    Args:
        relationships: List of PresentationRelationship objects
        role_uri: The extended link role URI for which to build the tree
    
    Returns:
        PresentationTree object
    """
    tree = PresentationTree()
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
    
    # Create a dummy root if multiple roots found
    if len(root_elements) > 1:
        dummy_root = PresentationNode()
        dummy_root.element_id = f"_root_{role_uri.split('/')[-1]}"
        dummy_root.element_name = "Root"
        dummy_root.is_abstract = True
        tree.root = dummy_root
        tree.all_nodes[dummy_root.element_id] = dummy_root
        
        # Add all real roots as children of dummy root
        for element_id in sorted(root_elements):
            if element_id in from_map:
                # Find elements with no parent in this role
                child_node = _create_node_recursive(element_id, from_map, tree.all_nodes)
                child_node.parent = dummy_root
                dummy_root.children.append(child_node)
    else:
        # Single root case
        root_id = next(iter(root_elements))
        tree.root = _create_node_recursive(root_id, from_map, tree.all_nodes)
        
    # Sort all children by order
    _sort_tree_by_order(tree.root)
    
    return tree

def _create_node_recursive(element_id, from_map, all_nodes):
    """
    Recursively create nodes for an element and all its descendants.
    
    Args:
        element_id: The element ID to create a node for
        from_map: Map of from_element to relationships
        all_nodes: Dictionary to store all created nodes
    
    Returns:
        The created node
    """
    # Return existing node if already created
    if element_id in all_nodes:
        return all_nodes[element_id]
    
    # Create new node
    node = PresentationNode()
    node.element_id = element_id
    all_nodes[element_id] = node
    
    # Process children
    if element_id in from_map:
        # Sort relationships by order
        sorted_relationships = sorted(from_map[element_id], key=lambda r: r.order)
        
        for rel in sorted_relationships:
            child_id = rel.to_element
            
            # Check for cycles
            if child_id == element_id:
                continue  # Skip self-references
            
            child_node = _create_node_recursive(child_id, from_map, all_nodes)
            child_node.parent = node
            child_node.order = rel.order
            child_node.preferred_label = rel.preferred_label
            node.children.append(child_node)
    
    return node

def _sort_tree_by_order(node):
    """
    Sort all children in a tree by their order attribute.
    
    Args:
        node: The root node of the tree to sort
    """
    if node.children:
        node.children.sort(key=lambda n: n.order)
        
        for child in node.children:
            _sort_tree_by_order(child)
```

### 6.2 Preferred Label Processing
```python
def apply_preferred_labels(presentation_node, label_map):
    """
    Apply preferred labels to a presentation node and its children.
    
    Args:
        presentation_node: The node to process
        label_map: Map of element ID to a dictionary of labels by role
    
    Returns:
        None (updates nodes in place)
    """
    element_id = presentation_node.element_id
    
    # Set labels if available in label map
    if element_id in label_map:
        presentation_node.labels = label_map[element_id]
        
        # Set standard label as default
        if 'http://www.xbrl.org/2003/role/label' in label_map[element_id]:
            presentation_node.standard_label = label_map[element_id]['http://www.xbrl.org/2003/role/label']
    
    # Apply preferred label if specified
    if presentation_node.preferred_label and presentation_node.preferred_label in presentation_node.labels:
        presentation_node.display_label = presentation_node.labels[presentation_node.preferred_label]
    else:
        presentation_node.display_label = presentation_node.standard_label
    
    # Process children recursively
    for child in presentation_node.children:
        apply_preferred_labels(child, label_map)
```

### 6.3 Cycle Detection
```python
def detect_cycles(relationships):
    """
    Detect cycles in a set of presentation relationships.
    
    Args:
        relationships: List of PresentationRelationship objects
    
    Returns:
        List of detected cycles
    """
    # Build adjacency map
    adjacency = {}
    for rel in relationships:
        adjacency.setdefault(rel.from_element, set()).add(rel.to_element)
    
    cycles = []
    visited = set()
    path = []
    
    def dfs(node):
        if node in path:
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return
        
        if node in visited:
            return
            
        visited.add(node)
        path.append(node)
        
        if node in adjacency:
            for neighbor in adjacency[node]:
                dfs(neighbor)
                
        path.pop()
    
    # Start DFS from each node
    for node in adjacency:
        path = []
        dfs(node)
    
    return cycles
```

## 7. Performance Considerations

### 7.1 Memory Optimization
- Use element IDs or references rather than full element objects in relationships
- Implement lazy loading of labels when large label linkbases are involved
- Reuse element objects across different trees when possible

### 7.2 Parsing Efficiency
- Pre-compile XPath expressions for common element selections
- Cache resolved element references
- Process arcs in batches grouped by extended link role

### 7.3 Scalability
- Implement parallel processing for independent extended link roles
- Consider incremental tree building for very large linkbases
- Design data structures for efficient navigation and search operations

## 8. Error Handling

### 8.1 Error Types
- XML parsing errors
- Invalid link structure
- Missing required attributes
- Circular references
- Inconsistent order attributes
- Duplicate relationships with different properties

### 8.2 Error Handling Strategy
- Implement hierarchical error classification
- Distinguish between fatal errors and warnings
- Provide clear error messages with specific locations
- Implement recovery strategies where possible
- Log all errors and warnings with appropriate context

### 8.3 Validation
- Validate against XBRL 2.1 specification requirements for presentation linkbases
- Check for proper arc structure
- Verify that referenced elements exist in the taxonomy schema
- Ensure no prohibited relationships are incorrectly processed

## 9. Extension Points

### 9.1 Custom Role Handlers
- Allow registration of handlers for specific extended link roles
- Support specialized processing for particular statement types
- Enable customized tree construction for specific roles

### 9.2 Tree Transformation
- Provide hooks for post-processing of presentation trees
- Support custom ordering algorithms
- Enable tree pruning and filtering

### 9.3 Integration Points
- Provide interfaces for integration with label and schema processors
- Support integration with calculation and definition linkbase processors
- Enable custom serialization formats

## 10. Implementation Example

### 10.1 Basic Parser Implementation
```python
import xml.etree.ElementTree as ET
import re
from collections import defaultdict
import logging

class PresentationLinkbaseParser:
    def __init__(self, options=None):
        self.options = options or {}
        self.roles = {}
        self.relationships = []
        self.trees = {}
        self.element_info = {}  # Information about elements from schema
        self.labels = {}        # Element labels from label linkbase
        
        # Define namespaces
        self.ns = {
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xbrli': 'http://www.xbrl.org/2003/instance'
        }
    
    def parse(self, linkbase_path, schema_info=None, labels=None):
        """
        Parse an XBRL presentation linkbase file.
        
        Args:
            linkbase_path: Path to the presentation linkbase file
            schema_info: Optional dictionary of element information from schema
            labels: Optional dictionary of element labels from label linkbase
        
        Returns:
            Dictionary containing parsed presentation network
        """
        try:
            # Store schema info and labels if provided
            if schema_info:
                self.element_info = schema_info
            if labels:
                self.labels = labels
                
            # Parse XML
            tree = ET.parse(linkbase_path)
            root = tree.getroot()
            
            # Extract namespaces
            self._extract_namespaces(root)
            
            # Extract roles
            self._extract_roles(root)
            
            # Extract relationships
            self._extract_relationships(root)
            
            # Build presentation trees
            self._build_trees()
            
            # Apply labels if available
            if labels:
                self._apply_labels()
            
            # Validate the network
            self._validate_network()
            
            return {
                'roles': self.roles,
                'relationships': self.relationships,
                'trees': self.trees
            }
            
        except Exception as e:
            logging.error(f"Error parsing presentation linkbase: {str(e)}")
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
            presentation_links = root.findall(f'.//{{{self.ns["link"]}}}presentationLink')
            for link in presentation_links:
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
        """Extract presentation relationships from the linkbase."""
        presentation_links = root.findall(f'.//{{{self.ns["link"]}}}presentationLink')
        
        for link in presentation_links:
            role_uri = link.get(f'{{{self.ns["xlink"]}}}role')
            if not role_uri:
                continue
                
            # Get all arcs in this link
            arcs = link.findall(f'.//{{{self.ns["link"]}}}presentationArc')
            
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
                rel = PresentationRelationship()
                rel.from_element = from_element
                rel.to_element = to_element
                rel.role = role_uri
                rel.arcrole = arc.get(f'{{{self.ns["xlink"]}}}arcrole')
                
                # Get optional attributes
                order_attr = arc.get('order')
                rel.order = float(order_attr) if order_attr else 0.0
                
                priority_attr = arc.get('priority')
                rel.priority = int(priority_attr) if priority_attr else 0
                
                preferred_label = arc.get('preferredLabel')
                rel.preferred_label = preferred_label
                
                # Check use attribute (prohibited relationships should be filtered)
                use_attr = arc.get('use', 'optional')
                if use_attr == 'prohibited':
                    # Store prohibited relationship for later filtering
                    rel.prohibited = True
                else:
                    rel.prohibited = False
                
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
        """Build presentation trees for each role."""
        # Group relationships by role
        role_rels = defaultdict(list)
        for rel in self.relationships:
            role_rels[rel.role].append(rel)
        
        # Build tree for each role
        for role_uri, rels in role_rels.items():
            tree = build_presentation_tree(rels, role_uri)
            
            # Set definition from role registry
            if role_uri in self.roles:
                tree.definition = self.roles[role_uri].definition
                tree.order = self.roles[role_uri].order
            
            self.trees[role_uri] = tree
    
    def _apply_labels(self):
        """Apply labels to presentation nodes."""
        for tree in self.trees.values():
            if tree.root:
                apply_preferred_labels(tree.root, self.labels)
    
    def _validate_network(self):
        """Validate the presentation network."""
        # Check for cycles
        cycles = detect_cycles(self.relationships)
        if cycles:
            # Log cycles as warnings
            for cycle in cycles:
                logging.warning(f"Cycle detected in presentation relationships: {' -> '.join(cycle)}")
        
        # Check for orphan elements (not connected to any tree)
        all_elements = set()
        for rel in self.relationships:
            all_elements.add(rel.from_element)
            all_elements.add(rel.to_element)
        
        tree_elements = set()
        for tree in self.trees.values():
            if tree.all_nodes:
                tree_elements.update(tree.all_nodes.keys())
        
        orphans = all_elements - tree_elements
        if orphans:
            logging.warning(f"Orphan elements found in presentation linkbase: {orphans}")
```

### 10.2 Tree Navigation Example
```python
def print_presentation_tree(tree, node=None, indent=0):
    """
    Print a presentation tree in a hierarchical format.
    
    Args:
        tree: The PresentationTree object
        node: The current node (None for root)
        indent: Current indentation level
    """
    if node is None:
        node = tree.root
        print(f"Presentation Tree for: {tree.definition} ({tree.role_uri})")
    
    if node is None:
        print("Empty tree")
        return
    
    # Print node with indentation
    label = node.display_label if hasattr(node, 'display_label') else node.standard_label
    element_id = node.element_id
    
    print(f"{'  ' * indent}{label} [{element_id}]")
    
    # Print children recursively
    for child in node.children:
        print_presentation_tree(tree, child, indent + 1)
```

### 10.3 Processing Presentation Trees for Financial Statements
```python
def get_statement_structure(presentation_network, role_definition_pattern=None, role_uri=None):
    """
    Get the structure of a financial statement from the presentation network.
    
    Args:
        presentation_network: The parsed presentation network
        role_definition_pattern: Regex pattern to match role definitions (e.g., '.*Balance Sheet.*')
        role_uri: Specific role URI to use (overrides pattern if provided)
    
    Returns:
        List of dictionaries representing the statement structure
    """
    if not presentation_network or not presentation_network.get('trees'):
        return []
    
    # Find the appropriate tree
    target_tree = None
    
    if role_uri and role_uri in presentation_network['trees']:
        target_tree = presentation_network['trees'][role_uri]
    elif role_definition_pattern:
        pattern = re.compile(role_definition_pattern, re.IGNORECASE)
        
        for tree in presentation_network['trees'].values():
            if pattern.match(tree.definition or ""):
                target_tree = tree
                break
    
    if not target_tree or not target_tree.root:
        return []
    
    # Convert tree to a flat structure
    return _tree_to_structure(target_tree.root)

def _tree_to_structure(node, depth=0):
    """
    Convert a presentation tree node to a flat structure.
    
    Args:
        node: The current node
        depth: Current depth in tree
    
    Returns:
        List of dictionaries representing the structure
    """
    result = []
    
    # Add current node
    label = node.display_label if hasattr(node, 'display_label') else node.standard_label
    
    node_info = {
        'element_id': node.element_id,
        'label': label,
        'depth': depth,
        'is_abstract': node.is_abstract,
        'preferred_label': node.preferred_label
    }
    
    result.append(node_info)
    
    # Add children recursively
    for child in node.children:
        result.extend(_tree_to_structure(child, depth + 1))
    
    return result
```

## 11. Testing Strategy

### 11.1 Unit Tests
- Test XML parsing capability with sample linkbase files
- Validate relationship extraction with controlled input
- Test tree construction algorithm with different hierarchy structures
- Verify label application and preferred label handling
- Use pytest for organizing and executing tests

### 11.2 Integration Tests
- Test end-to-end parsing of sample presentation linkbases
- Verify correct extraction and tree building with real-world files
- Test integration with schema and label information

### 11.3 Performance Tests
- Measure parsing time for linkbases of varying sizes
- Test memory usage patterns
- Verify tree navigation performance

### 11.4 Regression Tests
- Maintain a suite of real-world presentation linkbases
- Compare tree structures against known-good baselines
- Verify backwards compatibility with older XBRL versions

## 12. Usage Example

### 12.1 Basic Usage
```python
# Create parser instance
parser = PresentationLinkbaseParser()

# Parse presentation linkbase
parsed_network = parser.parse('company-20231231_pre.xml')

# Print available roles
print("Available presentation roles:")
for role_uri, role in parsed_network['roles'].items():
    print(f"- {role.definition} ({role_uri})")

# Find and print balance sheet structure
balance_sheet_pattern = '.*balance sheet.*|.*statement of financial position.*'
balance_sheet = get_statement_structure(parsed_network, role_definition_pattern=balance_sheet_pattern)

print("\nBalance Sheet Structure:")
for item in balance_sheet:
    indent = '  ' * item['depth']
    label = item['label']
    print(f"{indent}{label}")
```

### 12.2 Integration with Instance Document
```python
def create_financial_statement(instance_parser_result, presentation_parser_result, role_uri, context_id):
    """
    Create a financial statement by combining instance and presentation information.
    
    Args:
        instance_parser_result: Result from instance document parser
        presentation_parser_result: Result from presentation linkbase parser
        role_uri: Role URI for the statement to create
        context_id: Context ID for the facts to include
    
    Returns:
        List of dictionaries representing the statement with values
    """
    if role_uri not in presentation_parser_result['trees']:
        return []
    
    # Get presentation tree
    tree = presentation_parser_result['trees'][role_uri]
    
    # Get facts from instance
    facts = instance_parser_result['facts']
    contexts = instance_parser_result['contexts']
    
    # Create lookup dictionary for facts by element and context
    fact_lookup = {}
    for fact in facts:
        if fact.context_ref == context_id:
            fact_lookup[fact.concept_local_name] = fact
    
    # Process the tree to create the statement
    return _create_statement_from_tree(tree.root, fact_lookup)

def _create_statement_from_tree(node, fact_lookup, depth=0):
    """
    Create a statement structure from a presentation tree with values from facts.
    
    Args:
        node: Current node in presentation tree
        fact_lookup: Dictionary of facts by element name
        depth: Current depth in tree
    
    Returns:
        List of dictionaries representing the statement with values
    """
    result = []
    
    # Get label to display
    label = node.display_label if hasattr(node, 'display_label') else node.standard_label
    
    # Look up fact for this element
    fact = fact_lookup.get(node.element_id.split(':')[-1]) if ':' in node.element_id else fact_lookup.get(node.element_id)
    
    item = {
        'element_id': node.element_id,
        'label': label,
        'depth': depth,
        'is_abstract': node.is_abstract,
        'value': fact.numeric_value if fact and hasattr(fact, 'numeric_value') else None,
        'string_value': fact.value if fact else None,
        'decimals': fact.decimals if fact else None,
        'has_children': len(node.children) > 0
    }
    
    result.append(item)
    
    # Process children
    for child in node.children:
        result.extend(_create_statement_from_tree(child, fact_lookup, depth + 1))
    
    return result
```

### 12.3 Formatting Financial Statements
```python
def format_financial_statement(statement_data, indent_size=2):
    """
    Format a financial statement for display or output.
    
    Args:
        statement_data: List of dictionaries representing the statement
        indent_size: Number of spaces to use for each indentation level
    
    Returns:
        Formatted string representation of the statement
    """
    lines = []
    
    for item in statement_data:
        # Skip items with no value and no children unless they're abstract
        if not item['is_abstract'] and item['value'] is None and not item['has_children']:
            continue
            
        # Create indentation
        indent = ' ' * (item['depth'] * indent_size)
        
        # Format label
        label = item['label']
        
        # Format value
        value_str = ''
        if item['value'] is not None:
            # Format numeric value based on decimals
            if item['decimals'] is not None and item['decimals'] != 'INF':
                decimals = int(item['decimals']) if item['decimals'] != 'INF' else 2
                format_str = f"{{:,.{max(0, decimals)}f}}"
                value_str = format_str.format(item['value'])
            else:
                value_str = f"{item['value']:,}"
                
        # Combine label and value
        if item['is_abstract']:
            line = f"{indent}{label}"
        else:
            line = f"{indent}{label:<60} {value_str:>15}"
            
        lines.append(line)
    
    return '\n'.join(lines)
```

### 12.4 Complete Example
```python
# Create parsers
instance_parser = XBRLInstanceParser()
presentation_parser = PresentationLinkbaseParser()

# Parse files
instance_result = instance_parser.parse('company-20231231.xml')
presentation_result = presentation_parser.parse(
    'company-20231231_pre.xml', 
    # Pass schema info if available
    schema_info=schema_parser.parse('company-20231231.xsd'),
    # Pass labels if available
    labels=label_parser.parse('company-20231231_lab.xml')
)

# Find a context for the balance sheet date
balance_sheet_context = None
for ctx_id, ctx in instance_result['contexts'].items():
    if (ctx.period.type == 'instant' and 
            ctx.period.instant == datetime(2023, 12, 31).date() and
            not ctx.scenario and 
            not ctx.entity.segment):
        balance_sheet_context = ctx_id
        break

# Find the balance sheet role
balance_sheet_role = None
for role_uri, tree in presentation_result['trees'].items():
    if 'balance sheet' in tree.definition.lower() or 'statement of financial position' in tree.definition.lower():
        balance_sheet_role = role_uri
        break

# Create balance sheet
if balance_sheet_context and balance_sheet_role:
    balance_sheet_data = create_financial_statement(
        instance_result,
        presentation_result,
        balance_sheet_role,
        balance_sheet_context
    )
    
    # Format and print
    formatted_balance_sheet = format_financial_statement(balance_sheet_data)
    print(formatted_balance_sheet)
else:
    print("Could not find appropriate balance sheet context or role")
```