import json

# Charger le fichier JSON
with open("events_extracted.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = {}
edges = []

def add_node(node_id, node_type, extra_info=None):
    """
    Add a node if it does not exist.
    extra_info: dictionary of additional data to store
    """
    if node_id not in nodes:
        nodes[node_id] = {
            "id": node_id,
            "name": node_id,
            "type": node_type
        }
        if extra_info:
            nodes[node_id].update(extra_info)

for i, event in enumerate(data["events"]):

    event_id = f"event_{i}"

    # Add event node with all info
    add_node(event_id, "Event", {
        "name": event.get("title", event_id),
        "description": event.get("description", ""),
        "time": event.get("approximate_time", "")
    })

    # Actors
    for actor in event.get("actors", []):
        add_node(actor, "Person")  # optionally you can store extra info about actor
        edges.append({
            "id": f"actor_{i}_{actor}",
            "source": actor,
            "target": event_id,
            "type": "PARTICIPATED_IN"
        })

    # Places
    for place in event.get("places", []):
        add_node(place, "Place")  # optionally store extra info about place
        edges.append({
            "id": f"place_{i}_{place}",
            "source": event_id,
            "target": place,
            "type": "HAPPENED_IN"
        })

    # Keywords
    for keyword in event.get("keywords", []):
        add_node(keyword, "Keyword")  # optionally store extra info
        edges.append({
            "id": f"keyword_{i}_{keyword}",
            "source": event_id,
            "target": keyword,
            "type": "HAS_TOPIC"
        })

graph = {
    "nodes": list(nodes.values()),
    "edges": edges
}

with open("graph.json", "w", encoding="utf-8") as f:
    json.dump(graph, f, indent=2, ensure_ascii=False)

print("✅ graph.json created with full details")