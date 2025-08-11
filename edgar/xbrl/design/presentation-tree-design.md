# Presentation Tree Design for Multi-Period Statements

## Problem Statement

The current statement ordering fix correctly positions major sections (Operating Expenses before Operating Income) but breaks the hierarchical presentation tree structure. Child concepts (R&D, SG&A) appear disconnected from their parents instead of being grouped under them.

### Current Issue
```
Operating Expenses           $(57,467)  # Parent - correct position
Operating Income            $123,216   # Sibling - correct position  
Net Income                  $93,736    # Sibling - correct position
  R&D Expense               $31,370    # Child - WRONG! Should be under Operating Expenses
  SG&A Expense              $26,097    # Child - WRONG! Should be under Operating Expenses
```

### Desired Result
```
Operating Expenses          $(57,467)  # Parent
  R&D Expense               $31,370    # Child - correct hierarchical position
  SG&A Expense              $26,097    # Child - correct hierarchical position
Operating Income            $123,216   # Sibling
Net Income                  $93,736    # Sibling
```

## Design Approach

### 1. Virtual Presentation Tree Structure

Create a tree structure that preserves parent-child relationships while allowing semantic ordering:

```python
class PresentationNode:
    """Represents a node in the virtual presentation tree"""
    
    def __init__(self, concept: str, label: str, level: int, metadata: Dict):
        self.concept = concept
        self.label = label 
        self.level = level
        self.metadata = metadata
        self.children: List[PresentationNode] = []
        self.parent: Optional[PresentationNode] = None
        self.semantic_order: float = 999.0
        
    def add_child(self, child: 'PresentationNode'):
        """Add a child node and set parent relationship"""
        child.parent = self
        self.children.append(child)
        
    def sort_children(self, ordering_manager):
        """Sort children using semantic ordering while preserving hierarchy"""
        # Sort direct children by semantic order
        self.children.sort(key=lambda x: x.semantic_order)
        
        # Recursively sort grandchildren
        for child in self.children:
            child.sort_children(ordering_manager)
    
    def flatten_to_list(self) -> List['PresentationNode']:
        """Flatten tree to ordered list while preserving hierarchy"""
        result = [self]
        for child in self.children:
            result.extend(child.flatten_to_list())
        return result


class VirtualPresentationTree:
    """Builds and manages virtual presentation tree for stitched statements"""
    
    def __init__(self, ordering_manager):
        self.ordering_manager = ordering_manager
        self.root_nodes: List[PresentationNode] = []
        self.all_nodes: Dict[str, PresentationNode] = {}
    
    def build_tree(self, concept_metadata: Dict, concept_ordering: Dict) -> List[PresentationNode]:
        """
        Build presentation tree from concept metadata and ordering.
        
        Args:
            concept_metadata: Metadata for each concept including level
            concept_ordering: Semantic ordering positions
            
        Returns:
            Flattened list of nodes in correct presentation order
        """
        # Step 1: Create nodes for all concepts
        self._create_nodes(concept_metadata, concept_ordering)
        
        # Step 2: Build parent-child relationships based on levels
        self._build_hierarchy()
        
        # Step 3: Apply semantic ordering within sibling groups
        self._apply_semantic_ordering()
        
        # Step 4: Flatten tree to linear list
        return self._flatten_tree()
```

### 2. Hierarchy Detection Algorithm

```python
def _build_hierarchy(self):
    """Build parent-child relationships based on level and context"""
    
    # Sort nodes by their original order to maintain context
    nodes_by_order = sorted(self.all_nodes.values(), 
                           key=lambda x: x.metadata.get('original_index', 999))
    
    parent_stack = []  # Stack of potential parents
    
    for node in nodes_by_order:
        current_level = node.level
        
        # Find the appropriate parent by traversing up the stack
        while parent_stack and parent_stack[-1].level >= current_level:
            parent_stack.pop()
        
        if parent_stack:
            # Found a parent - add as child
            parent = parent_stack[-1]
            parent.add_child(node)
        else:
            # No parent - this is a root node
            self.root_nodes.append(node)
        
        # This node could be a parent for subsequent nodes
        parent_stack.append(node)


def _apply_semantic_ordering(self):
    """Apply semantic ordering within sibling groups"""
    
    # Sort root nodes by semantic order
    self.root_nodes.sort(key=lambda x: x.semantic_order)
    
    # Sort children within each parent
    for root in self.root_nodes:
        root.sort_children(self.ordering_manager)


def _flatten_tree(self) -> List[PresentationNode]:
    """Flatten tree to linear list preserving hierarchy"""
    result = []
    
    for root in self.root_nodes:
        result.extend(root.flatten_to_list())
    
    return result
```

### 3. Integration with StatementStitcher

Update the StatementStitcher to use the presentation tree:

```python
def _format_output_with_ordering(self, statements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Format output using virtual presentation tree"""
    
    # Get semantic ordering
    concept_ordering = {}
    if self.ordering_manager:
        concept_ordering = self.ordering_manager.determine_ordering(statements)
    
    # Build virtual presentation tree
    tree = VirtualPresentationTree(self.ordering_manager)
    ordered_nodes = tree.build_tree(self.concept_metadata, concept_ordering)
    
    # Build output from ordered nodes
    result = {
        'periods': [(pid, self.period_dates.get(pid, pid)) for pid in self.periods],
        'statement_data': []
    }
    
    for node in ordered_nodes:
        # Create item maintaining original structure
        item = {
            'label': node.metadata.get('latest_label', node.concept),
            'level': node.level,
            'is_abstract': node.metadata['is_abstract'],
            'is_total': node.metadata['is_total'],
            'concept': node.metadata['original_concept'],
            'values': {},
            'decimals': {}
        }
        
        # Add values for each period
        for period_id in self.periods:
            if period_id in self.data[node.concept]:
                item['values'][period_id] = self.data[node.concept][period_id]['value']
                item['decimals'][period_id] = self.data[node.concept][period_id]['decimals']
        
        # Set has_values flag
        item['has_values'] = len(item['values']) > 0
        
        # Include items with values or abstract items
        if item['has_values'] or item['is_abstract']:
            result['statement_data'].append(item)
    
    return result
```

### 4. Enhanced Ordering Manager Integration

The ordering manager needs to work with the tree structure:

```python
class StatementOrderingManager:
    """Enhanced to work with presentation trees"""
    
    def determine_ordering_for_tree(self, statements: List[Dict], 
                                   concept_metadata: Dict) -> Dict[str, float]:
        """
        Determine ordering that considers both semantics and hierarchy.
        
        This method provides semantic ordering while respecting that
        the tree structure will be preserved separately.
        """
        # Get base semantic ordering
        base_ordering = self.determine_ordering(statements)
        
        # Adjust ordering to account for hierarchy preservation
        # Parent concepts should have lower numbers than their children
        # within the same semantic section
        
        adjusted_ordering = {}
        
        for concept, metadata in concept_metadata.items():
            base_order = base_ordering.get(concept, 999.0)
            level = metadata.get('level', 0)
            
            # Adjust order based on level to ensure proper tree sorting
            # Parent (level 0) gets base order
            # Children (level 1+) get base order + small increment based on level
            adjusted_order = base_order + (level * 0.01)
            
            adjusted_ordering[concept] = adjusted_order
            
        return adjusted_ordering
```

### 5. Example Tree Structure

For the Apple income statement, the tree would look like:

```
Root Level (level 0):
├─ Contract Revenue (semantic_order: 0.0)
├─ Cost of Goods and Services Sold (semantic_order: 100.0)  
├─ Gross Profit (semantic_order: 200.0)
├─ Operating Expenses (semantic_order: 300.0)
│  ├─ Research and Development Expense (level 1, semantic_order: 300.01)
│  └─ Selling, General and Administrative Expense (level 1, semantic_order: 300.02)
├─ Operating Income (semantic_order: 400.0)
├─ Nonoperating Income/Expense (semantic_order: 500.0)
├─ Income Before Tax (semantic_order: 600.0)
├─ Income Tax Expense (semantic_order: 700.0)
├─ Net Income (semantic_order: 800.0)
└─ Earnings Per Share (semantic_order: 900.0)
   ├─ Earnings Per Share (Basic) (level 1, semantic_order: 900.01)
   ├─ Earnings Per Share (Diluted) (level 1, semantic_order: 900.02)
   ├─ Shares Outstanding (Basic) (level 1, semantic_order: 900.03)
   └─ Shares Outstanding (Diluted) (level 1, semantic_order: 900.04)
```

### 6. Implementation Steps

1. **Create PresentationNode and VirtualPresentationTree classes**
2. **Update StatementStitcher to capture original ordering context**
3. **Implement hierarchy detection based on level progression**
4. **Integrate semantic ordering within tree structure**
5. **Update output formatting to use tree-flattened order**
6. **Test with Apple multi-period statements**

### 7. Benefits

- **Preserves hierarchy**: Parent-child relationships maintained
- **Applies semantic ordering**: Major sections in correct order
- **Maintains presentation logic**: Similar to XBRL Presentation Linkbase
- **Flexible**: Can handle varying hierarchy depths
- **Backward compatible**: Falls back gracefully for single statements

This approach treats the stitched statement like a virtual XBRL presentation with intelligent ordering applied at each tree level, ensuring both semantic correctness and hierarchical integrity.