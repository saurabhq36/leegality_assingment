import heapq
from typing import Dict, List, Optional, Tuple


def dijkstra(
    graph: Dict[int, List[Tuple[int, float]]],
    source: int,
    destination: int,
) -> Optional[Tuple[float, List[int]]]:
    """Find the minimum-latency path in a graph with positive edge weights."""
    distances: Dict[int, float] = {source: 0.0}
    previous: Dict[int, int] = {}
    heap = [(0.0, source)]
    heapq.heapify(heap)

    while heap:
        current_distance, current_node = heapq.heappop(heap)

        # A shorter distance may have been added after this heap entry.
        if current_distance > distances[current_node]:
            continue

        if current_node == destination:
            path = [destination]
            while path[-1] != source:
                path.append(previous[path[-1]])
            path.reverse()
            return current_distance, path

        for neighbor, latency in graph.get(current_node, []):
            new_distance = current_distance + latency
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                previous[neighbor] = current_node
                heapq.heappush(heap, (new_distance, neighbor))

    return None
