import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, MultiPoint, Point
from shapely.strtree import STRtree


def load_geojson(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def meters_to_degrees(meters: float) -> float:
    return meters / 111000.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def normalize_label(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def normalize_id_token(value: str) -> str:
    return re.sub(r"\s+", "", value)


def iter_lines(geometry: dict) -> list[LineString]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    lines = []
    if geom_type == "LineString":
        if len(coords) >= 2:
            lines.append(LineString(coords))
    elif geom_type == "MultiLineString":
        for segment in coords:
            if len(segment) >= 2:
                lines.append(LineString(segment))
    return lines


def iter_points(geometry: dict) -> list[Point]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    points = []
    if geom_type == "Point" and coords:
        points.append(Point(coords))
    elif geom_type == "MultiPoint" and coords:
        points.extend(Point(pt) for pt in coords)
    return points


def sort_runway_label(label: str) -> tuple[int, str]:
    match = re.match(r"(\d+)([A-Z]*)", label)
    if not match:
        return (999, label)
    return (int(match.group(1)), match.group(2))


def build_taxiway_assignments(
    taxiway_centerlines: dict,
    taxiway_labels: dict,
    max_label_distance_m: float,
) -> tuple[list[LineString], list[str | None], dict[str, list[Point]], list[dict]]:
    lines = []
    line_props = []
    for feature in taxiway_centerlines.get("features", []):
        for line in iter_lines(feature.get("geometry", {})):
            lines.append(line)
            line_props.append(feature.get("properties", {}))

    label_points = []
    label_names = []
    label_points_by_name: dict[str, list[Point]] = defaultdict(list)
    for feature in taxiway_labels.get("features", []):
        props = feature.get("properties", {})
        label = normalize_label(props.get("RESOURCE_C")) or normalize_label(props.get("NAME"))
        if not label:
            continue
        for point in iter_points(feature.get("geometry", {})):
            label_points.append(point)
            label_names.append(label)
            label_points_by_name[label].append(point)

    line_labels: list[str | None] = [None] * len(lines)
    if not lines or not label_points:
        return lines, line_labels, label_points_by_name, line_props

    max_distance_deg = meters_to_degrees(max_label_distance_m)
    tree = STRtree(label_points)
    for idx, line in enumerate(lines):
        label_idx = tree.nearest(line)
        if label_idx is None:
            continue
        label_point = label_points[label_idx]
        dist = line.distance(label_point)
        if dist > max_distance_deg:
            continue
        line_labels[idx] = label_names[label_idx]

    return lines, line_labels, label_points_by_name, line_props


def build_runway_nodes(
    runway_centerlines: dict,
    runway_labels: dict,
) -> tuple[list[LineString], list[dict]]:
    runway_lines = []
    for feature in runway_centerlines.get("features", []):
        for line in iter_lines(feature.get("geometry", {})):
            runway_lines.append(line)

    label_points = []
    label_names = []
    for feature in runway_labels.get("features", []):
        props = feature.get("properties", {})
        label = normalize_label(props.get("NAME")) or normalize_label(props.get("RESOURCE_C"))
        if not label:
            continue
        for point in iter_points(feature.get("geometry", {})):
            label_points.append(point)
            label_names.append(label)

    labels_by_line = defaultdict(list)
    if runway_lines and label_points:
        tree = STRtree(runway_lines)
        for label, point in zip(label_names, label_points):
            line_idx = tree.nearest(point)
            if line_idx is None:
                continue
            labels_by_line[line_idx].append(label)

    nodes = []
    for idx, line in enumerate(runway_lines):
        labels = sorted(set(labels_by_line.get(idx, [])), key=sort_runway_label)
        if labels:
            pair_id = "_".join(labels)
            name = "/".join(labels)
        else:
            pair_id = f"unknown_{idx + 1}"
            name = f"Runway {idx + 1}"
        centroid = line.centroid
        nodes.append(
            {
                "id": f"runway_{pair_id}",
                "type": "runway",
                "lat": centroid.y,
                "lon": centroid.x,
                "name": name,
                "labels": labels,
                "segment_count": 1,
            }
        )

    return runway_lines, nodes


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Tianfu airport topology from outputs GeoJSON.")
    parser.add_argument("--output", default="outputs/tianfu_topology.json")
    parser.add_argument("--report", default="outputs/tianfu_topology_report.txt")
    parser.add_argument("--label-distance-m", type=float, default=200.0)
    parser.add_argument("--taxiway-link-m", type=float, default=20.0)
    parser.add_argument("--stand-link-m", type=float, default=140.0)
    parser.add_argument("--runway-link-m", type=float, default=20.0)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    outputs_dir = project_root / "outputs"

    stand_label_path = outputs_dir / "tianfu_stand_label.geojson"
    taxiway_label_path = outputs_dir / "tianfu_taxiway_label.geojson"
    taxiway_centerline_path = outputs_dir / "tianfu_taxiway_centerline.geojson"
    runway_label_path = outputs_dir / "tianfu_runway_label.geojson"
    runway_centerline_path = outputs_dir / "tianfu_runway_centerline.geojson"

    for path in [
        stand_label_path,
        taxiway_label_path,
        taxiway_centerline_path,
        runway_label_path,
        runway_centerline_path,
    ]:
        if not path.exists():
            raise FileNotFoundError(f"Missing input: {path}")

    stand_labels = load_geojson(stand_label_path)
    taxiway_labels = load_geojson(taxiway_label_path)
    taxiway_centerlines = load_geojson(taxiway_centerline_path)
    runway_labels = load_geojson(runway_label_path)
    runway_centerlines = load_geojson(runway_centerline_path)

    taxiway_lines, line_labels, taxiway_label_points, _ = build_taxiway_assignments(
        taxiway_centerlines,
        taxiway_labels,
        max_label_distance_m=args.label_distance_m,
    )

    runway_lines, runway_nodes = build_runway_nodes(runway_centerlines, runway_labels)
    runway_node_by_id = {node["id"]: node for node in runway_nodes}

    nodes: dict[str, dict] = {}
    edges_meta: dict[tuple[str, str], dict] = {}

    taxiway_nodes_by_label: dict[str, str] = {}
    for label, points in taxiway_label_points.items():
        assigned_lines = [
            taxiway_lines[idx]
            for idx, line_label in enumerate(line_labels)
            if line_label == label
        ]
        if assigned_lines:
            geom = MultiLineString(assigned_lines)
            centroid = geom.centroid
        else:
            centroid = MultiPoint(points).centroid
        node_id = f"taxiway_{normalize_id_token(label)}"
        taxiway_nodes_by_label[label] = node_id
        nodes[node_id] = {
            "id": node_id,
            "type": "taxiway",
            "lat": centroid.y,
            "lon": centroid.x,
            "name": label,
            "segment_count": len(assigned_lines),
            "label_point_count": len(points),
        }

    for node in runway_nodes:
        nodes[node["id"]] = node

    stand_counts = Counter()
    stand_unmatched = 0
    stand_tree = None
    stand_line_labels = None
    if taxiway_lines:
        labeled_line_indices = [idx for idx, label in enumerate(line_labels) if label]
        labeled_lines = [taxiway_lines[idx] for idx in labeled_line_indices]
        labeled_labels = [line_labels[idx] for idx in labeled_line_indices]
        if labeled_lines:
            stand_tree = STRtree(labeled_lines)
            stand_line_labels = labeled_labels

    for feature in stand_labels.get("features", []):
        props = feature.get("properties", {})
        stand_code = normalize_label(props.get("RESOURCE_C")) or normalize_label(props.get("NAME"))
        if not stand_code:
            continue
        base_code = normalize_id_token(stand_code)
        stand_counts[base_code] += 1
        suffix = stand_counts[base_code]
        if suffix == 1:
            node_id = f"stand_{base_code}"
        else:
            node_id = f"stand_{base_code}_{suffix}"

        points = iter_points(feature.get("geometry", {}))
        if not points:
            continue
        point = points[0]

        nodes[node_id] = {
            "id": node_id,
            "type": "stand",
            "lat": point.y,
            "lon": point.x,
            "code": stand_code,
            "label": props.get("NAME") or "",
        }

        if stand_tree is None:
            continue
        line_idx = stand_tree.nearest(point)
        if line_idx is None:
            stand_unmatched += 1
            continue
        line = stand_tree.geometries[line_idx]
        dist = line.distance(point)
        if dist > meters_to_degrees(args.stand_link_m):
            stand_unmatched += 1
            continue
        label = stand_line_labels[line_idx]
        taxiway_node_id = taxiway_nodes_by_label.get(label)
        if not taxiway_node_id:
            stand_unmatched += 1
            continue
        key = tuple(sorted([node_id, taxiway_node_id]))
        edge = edges_meta.setdefault(key, {"usage_count": 0, "edge_types": set()})
        edge["usage_count"] += 1
        edge["edge_types"].add("stand-taxiway")

    if taxiway_lines:
        tree = STRtree(taxiway_lines)
        distance_threshold = meters_to_degrees(args.taxiway_link_m)
        for idx, line in enumerate(taxiway_lines):
            label = line_labels[idx]
            if not label:
                continue
            for other_idx in tree.query(line):
                if other_idx <= idx:
                    continue
                other_label = line_labels[other_idx]
                if not other_label or other_label == label:
                    continue
                other_line = taxiway_lines[other_idx]
                if line.distance(other_line) > distance_threshold:
                    continue
                node_a = taxiway_nodes_by_label[label]
                node_b = taxiway_nodes_by_label[other_label]
                key = tuple(sorted([node_a, node_b]))
                edge = edges_meta.setdefault(key, {"usage_count": 0, "edge_types": set()})
                edge["usage_count"] += 1
                edge["edge_types"].add("taxiway-taxiway")

    if taxiway_lines and runway_lines:
        runway_threshold = meters_to_degrees(args.runway_link_m)
        for idx, line in enumerate(taxiway_lines):
            label = line_labels[idx]
            if not label:
                continue
            taxiway_node_id = taxiway_nodes_by_label[label]
            for runway_idx, runway_line in enumerate(runway_lines):
                if line.distance(runway_line) > runway_threshold:
                    continue
                runway_node = runway_nodes[runway_idx]["id"]
                key = tuple(sorted([taxiway_node_id, runway_node]))
                edge = edges_meta.setdefault(key, {"usage_count": 0, "edge_types": set()})
                edge["usage_count"] += 1
                edge["edge_types"].add("taxiway-runway")

    edges = []
    for (node_a, node_b), meta in edges_meta.items():
        node_a_info = nodes.get(node_a)
        node_b_info = nodes.get(node_b)
        if not node_a_info or not node_b_info:
            continue
        distance = haversine(
            node_a_info["lat"],
            node_a_info["lon"],
            node_b_info["lat"],
            node_b_info["lon"],
        )
        edges.append(
            {
                "from": node_a,
                "to": node_b,
                "distance": distance,
                "usage_count": meta["usage_count"],
                "edge_types": sorted(meta["edge_types"]),
            }
        )

    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "airport": {
            "icao": "ZUTF",
            "name": "成都天府国际机场",
            "source": "outputs/tianfu_*",
        },
        "nodes": nodes,
        "edges": edges,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    adjacency = defaultdict(set)
    for edge in edges:
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])

    isolated_nodes = [node_id for node_id in nodes if not adjacency.get(node_id)]
    counts = Counter(node["type"] for node in nodes.values())
    report_lines = [
        "Tianfu topology report",
        f"Nodes: {len(nodes)}",
        f"Edges: {len(edges)}",
        "Node types:",
        f"  - runway: {counts.get('runway', 0)}",
        f"  - taxiway: {counts.get('taxiway', 0)}",
        f"  - stand: {counts.get('stand', 0)}",
        f"Unmatched stands (no nearby taxiway): {stand_unmatched}",
        f"Isolated nodes: {len(isolated_nodes)}",
    ]
    if isolated_nodes:
        report_lines.append("Isolated node ids:")
        report_lines.extend(f"  - {node_id}" for node_id in isolated_nodes[:200])

    report_path = project_root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Saved topology: {output_path}")
    print(f"Saved report: {report_path}")
    print(f"Nodes: {len(nodes)} | Edges: {len(edges)}")


if __name__ == "__main__":
    main()
