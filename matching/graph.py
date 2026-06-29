from typing import List, Set, Dict, Tuple
from collections import defaultdict
from domain.models import RawRecord
from matching.rules import is_match

def build_connected_components(records: List[RawRecord]) -> List[List[RawRecord]]:
    """
    Groups records that belong to the same candidate using Connected Components.
    Time Complexity: O(N^2) where N is the number of records.
    For production with millions of records, blocking/LSH should be used before this step.
    For this assignment, N^2 on an in-memory batch is acceptable.
    """
    n = len(records)
    adj_list: Dict[int, List[int]] = defaultdict(list)
    
    # Build Graph
    for i in range(n):
        for j in range(i + 1, n):
            if is_match(records[i], records[j]):
                adj_list[i].append(j)
                adj_list[j].append(i)
                
    # Find Connected Components
    visited: Set[int] = set()
    components: List[List[RawRecord]] = []
    
    for i in range(n):
        if i not in visited:
            component_indices = []
            queue = [i]
            visited.add(i)
            
            while queue:
                curr = queue.pop(0)
                component_indices.append(curr)
                
                for neighbor in adj_list[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
                        
            components.append([records[idx] for idx in component_indices])
            
    return components
