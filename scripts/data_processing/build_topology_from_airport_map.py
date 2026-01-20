import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path

import shapefile
from shapely.geometry import LineString
from shapely.strtree import STRtree


def utm_to_latlon(easting, northing, zone_number=49, northern=True):
    # WGS84 UTM -> lat/lon conversion (meters to degrees).
    a = 6378137.0
    e = 0.08181919084262149
    e_sq = e * e
    k0 = 0.9996

    x = easting - 500000.0
    y = northing
    if not northern:
        y -= 10000000.0

    m = y / k0
    mu = m / (a * (1 - e_sq / 4 - 3 * e_sq * e_sq / 64 - 5 * e_sq * e_sq * e_sq / 256))

    e1 = (1 - math.sqrt(1 - e_sq)) / (1 + math.sqrt(1 - e_sq))
    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512

    phi1 = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    n1 = a / math.sqrt(1 - e_sq * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = e_sq / (1 - e_sq) * math.cos(phi1) ** 2
    r1 = a * (1 - e_sq) / ((1 - e_sq * math.sin(phi1) ** 2) ** 1.5)
    d = x / (n1 * k0)

    lat = (
        phi1
        - (n1 * math.tan(phi1) / r1)
        * (
            d**2 / 2
            - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e_sq / (1 - e_sq)) * d**4 / 24
            + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e_sq / (1 - e_sq) - 3 * c1**2)
            * d**6
            / 720
        )
    )

    lon = (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e_sq / (1 - e_sq) + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)

    lon0 = math.radians(zone_number * 6 - 183)
    lon = lon0 + lon

    return math.degrees(lat), math.degrees(lon)


def normalize_token(token):
    if token is None:
        return ""
    token = token.strip().upper()
    if token.endswith("跑道"):
        token = token.replace("跑道", "")
    ap_match = re.match(r"^(AP\d+)[LR]$", token)
    if ap_match:
        return ap_match.group(1)
    return token


def load_stands(stand_shp_path):
    reader = shapefile.Reader(str(stand_shp_path), encoding="gbk")
    stands = {}
    for rec in reader.iterRecords():
        code = normalize_token(rec["code"] or "")
        if not code or not re.match(r"^\d+$", code):
            continue
        x = rec["POINT_X"]
        y = rec["POINT_Y"]
        if x is None or y is None:
            continue
        stands[code] = {
            "code": code,
            "name": (rec["NAME"] or "").strip(),
            "x": float(x),
            "y": float(y),
            "max_span_w": (rec["max_span_w"] or "").strip(),
            "max_air_le": (rec["max_air_le"] or "").strip(),
        }
    return stands


def load_taxiway_records(taxi_shp_path):
    reader = shapefile.Reader(str(taxi_shp_path), encoding="gbk")
    records = []
    runway_token_hints = set()
    for rec, shape in zip(reader.iterRecords(), reader.iterShapes()):
        raw_road_name = rec["RoadName"] or ""
        road_name = normalize_token(raw_road_name)
        if not road_name:
            continue
        tokens = [normalize_token(t) for t in road_name.split("-") if normalize_token(t)]
        if not tokens:
            continue
        for raw_token in raw_road_name.split("-"):
            if "跑道" in raw_token:
                runway_token_hints.add(normalize_token(raw_token))
        records.append(
            {
                "road_name": road_name,
                "tokens": tokens,
                "points": [(pt[0], pt[1]) for pt in shape.points],
            }
        )
    return records, runway_token_hints


def build_edges_from_paths(stands, stand_shp_path, token_is_runway, canonical_runway_token):
    reader = shapefile.Reader(str(stand_shp_path), encoding="gbk")
    path_fields = [f[0] for f in reader.fields if f[0].startswith("path_")]
    edge_counts = defaultdict(int)
    tokens_seen = set()

    for rec in reader.iterRecords():
        code = normalize_token(rec["code"] or "")
        if not code or code not in stands:
            continue
        stand_id = f"stand_{code}"
        for field in path_fields:
            path_value = rec[field]
            if not path_value:
                continue
            tokens = [normalize_token(t) for t in path_value.split("-") if normalize_token(t)]
            if not tokens:
                continue
            normalized_tokens = []
            for token in tokens:
                if token_is_runway(token):
                    token = canonical_runway_token(token)
                normalized_tokens.append(token)
            tokens_seen.update(normalized_tokens)
            node_ids = [stand_id]
            for token in normalized_tokens:
                node_type = "runway" if token_is_runway(token) else "taxiway"
                node_ids.append(f"{node_type}_{token}")
            for start, end in zip(node_ids, node_ids[1:]):
                if start == end:
                    continue
                key = tuple(sorted([start, end]))
                edge_counts[key] += 1

    return edge_counts, tokens_seen


def build_topology(stand_shp_path, taxi_shp_path, output_path):
    stands = load_stands(stand_shp_path)
    taxiway_records, runway_token_hints = load_taxiway_records(taxi_shp_path)

    runway_pair_map = {
        "05L": "05L_23R",
        "23R": "05L_23R",
        "05R": "05R_23L",
        "23L": "05R_23L",
    }

    paired_runway_tokens = set(runway_pair_map.values())

    def token_is_runway(token):
        return (
            re.match(r"^\d{2}[LR]$", token) is not None
            or token in runway_token_hints
            or token in runway_pair_map
            or token in paired_runway_tokens
        )

    def canonical_runway_token(token):
        return runway_pair_map.get(token, token)

    edge_counts, route_tokens = build_edges_from_paths(
        stands, stand_shp_path, token_is_runway, canonical_runway_token
    )

    nodes = {}
    for code, stand in stands.items():
        lat, lon = utm_to_latlon(stand["x"], stand["y"])
        node_id = f"stand_{code}"
        nodes[node_id] = {
            "id": node_id,
            "type": "stand",
            "lat": lat,
            "lon": lon,
            "name": stand["name"],
            "max_span_w": stand["max_span_w"],
            "max_air_le": stand["max_air_le"],
            "x": stand["x"],
            "y": stand["y"],
        }

    points_primary = defaultdict(list)
    points_fallback = defaultdict(list)
    for record in taxiway_records:
        tokens = []
        for token in record["tokens"]:
            if token_is_runway(token):
                tokens.append(canonical_runway_token(token))
            else:
                tokens.append(token)
        points = record["points"]
        if not points:
            continue
        if len(tokens) == 1:
            points_primary[tokens[0]].extend(points)
        for token in tokens:
            points_fallback[token].extend(points)

    for token in route_tokens:
        node_type = "runway" if token_is_runway(token) else "taxiway"
        node_id = f"{node_type}_{token}"
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "lat": None,
                "lon": None,
                "x": None,
                "y": None,
            }

    all_tokens = set(points_fallback.keys()).union(route_tokens)
    for token in all_tokens:
        points = points_primary.get(token) or points_fallback.get(token) or []
        if not points:
            continue
        x_sum = sum(p[0] for p in points)
        y_sum = sum(p[1] for p in points)
        x = x_sum / len(points)
        y = y_sum / len(points)
        node_type = "runway" if token_is_runway(token) else "taxiway"
        node_id = f"{node_type}_{token}"
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "lat": None,
                "lon": None,
                "x": None,
                "y": None,
            }
        lat, lon = utm_to_latlon(x, y)
        nodes[node_id]["lat"] = lat
        nodes[node_id]["lon"] = lon
        nodes[node_id]["x"] = x
        nodes[node_id]["y"] = y

    # RoadName 内部连接（例如 A5-A）
    for record in taxiway_records:
        tokens = []
        for token in record["tokens"]:
            if token_is_runway(token):
                tokens.append(canonical_runway_token(token))
            else:
                tokens.append(token)
        if len(tokens) < 2:
            continue
        node_ids = []
        for token in tokens:
            node_type = "runway" if token_is_runway(token) else "taxiway"
            node_ids.append(f"{node_type}_{token}")
        for start, end in zip(node_ids, node_ids[1:]):
            if start == end:
                continue
            key = tuple(sorted([start, end]))
            edge_counts[key] += 1

    # 基于几何交点补全滑行道连接（仅使用单一 RoadName 记录）
    geoms = []
    geom_meta = []
    for record in taxiway_records:
        tokens = []
        for token in record["tokens"]:
            if token_is_runway(token):
                tokens.append(canonical_runway_token(token))
            else:
                tokens.append(token)
        if len(tokens) != 1:
            continue
        points = record["points"]
        if len(points) < 2:
            continue
        line = LineString(points)
        if line.is_empty:
            continue
        geoms.append(line)
        geom_meta.append({"token": tokens[0]})

    tree = STRtree(geoms)
    tolerance = 1.0
    for idx, geom in enumerate(geoms):
        for other_idx in tree.query(geom):
            if other_idx <= idx:
                continue
            other_geom = geoms[other_idx]
            if not (geom.intersects(other_geom) or geom.distance(other_geom) <= tolerance):
                continue
            token_a = geom_meta[idx]["token"]
            token_b = geom_meta[other_idx]["token"]
            if token_a == token_b:
                continue
            node_type_a = "runway" if token_is_runway(token_a) else "taxiway"
            node_type_b = "runway" if token_is_runway(token_b) else "taxiway"
            node_a = f"{node_type_a}_{token_a}"
            node_b = f"{node_type_b}_{token_b}"
            key = tuple(sorted([node_a, node_b]))
            edge_counts[key] += 1

    adjacency = defaultdict(set)
    for (start, end), _ in edge_counts.items():
        adjacency[start].add(end)
        adjacency[end].add(start)

    # Connect isolated taxiways by nearest geometry (conservative threshold).
    max_taxiway_gap_m = 25.0
    lines_by_token = defaultdict(list)
    for record in taxiway_records:
        tokens = []
        for token in record["tokens"]:
            if token_is_runway(token):
                tokens.append(canonical_runway_token(token))
            else:
                tokens.append(token)
        if len(tokens) != 1:
            continue
        points = record["points"]
        if len(points) < 2:
            continue
        line = LineString(points)
        if line.is_empty:
            continue
        lines_by_token[tokens[0]].append(line)

    all_lines = []
    line_meta = []
    for token, lines in lines_by_token.items():
        for line in lines:
            all_lines.append(line)
            line_meta.append({"token": token})

    if all_lines:
        tree = STRtree(all_lines)
        for node_id, node in nodes.items():
            if node.get("type") != "taxiway":
                continue
            if adjacency.get(node_id):
                continue
            token = node_id.replace("taxiway_", "")
            if token not in lines_by_token:
                continue
            best = None
            for line in lines_by_token[token]:
                for idx in tree.query(line):
                    cand_line = all_lines[idx]
                    cand_token = line_meta[idx]["token"]
                    if cand_token == token:
                        continue
                    dist = line.distance(cand_line)
                    if dist <= max_taxiway_gap_m and (best is None or dist < best[0]):
                        best = (dist, cand_token)
            if best:
                dist, cand_token = best
                other_id = f"taxiway_{cand_token}"
                key = tuple(sorted([node_id, other_id]))
                if key not in edge_counts:
                    edge_counts[key] = 1
                    adjacency[node_id].add(other_id)
                    adjacency[other_id].add(node_id)

    # Connect isolated stands to nearest taxiway node (conservative threshold).
    max_stand_gap_m = 40.0
    taxiway_nodes = [node_id for node_id, node in nodes.items() if node.get("type") == "taxiway"]
    for node_id, node in nodes.items():
        if node.get("type") != "stand":
            continue
        if adjacency.get(node_id):
            continue
        if node.get("x") is None or node.get("y") is None:
            continue
        best = None
        for taxi_id in taxiway_nodes:
            taxi_node = nodes[taxi_id]
            if taxi_node.get("x") is None or taxi_node.get("y") is None:
                continue
            dist = math.hypot(node["x"] - taxi_node["x"], node["y"] - taxi_node["y"])
            if dist <= max_stand_gap_m and (best is None or dist < best[0]):
                best = (dist, taxi_id)
        if best:
            dist, taxi_id = best
            key = tuple(sorted([node_id, taxi_id]))
            if key not in edge_counts:
                edge_counts[key] = 1
                adjacency[node_id].add(taxi_id)
                adjacency[taxi_id].add(node_id)

    # Fill missing coordinates from neighbors.
    missing = True
    while missing:
        missing = False
        for node_id, node in nodes.items():
            if node["x"] is not None and node["y"] is not None:
                continue
            neighbor_points = []
            for neighbor_id in adjacency.get(node_id, []):
                neighbor = nodes.get(neighbor_id)
                if neighbor and neighbor["x"] is not None and neighbor["y"] is not None:
                    neighbor_points.append((neighbor["x"], neighbor["y"]))
            if neighbor_points:
                node["x"] = sum(p[0] for p in neighbor_points) / len(neighbor_points)
                node["y"] = sum(p[1] for p in neighbor_points) / len(neighbor_points)
                lat, lon = utm_to_latlon(node["x"], node["y"])
                node["lat"] = lat
                node["lon"] = lon
                missing = True

    # Fallback to overall centroid for any remaining nodes.
    known_points = [(n["x"], n["y"]) for n in nodes.values() if n["x"] is not None and n["y"] is not None]
    if known_points:
        avg_x = sum(p[0] for p in known_points) / len(known_points)
        avg_y = sum(p[1] for p in known_points) / len(known_points)
        avg_lat, avg_lon = utm_to_latlon(avg_x, avg_y)
        for node in nodes.values():
            if node["x"] is None or node["y"] is None:
                node["x"] = avg_x
                node["y"] = avg_y
                node["lat"] = avg_lat
                node["lon"] = avg_lon

    edges = []
    for (start, end), usage_count in edge_counts.items():
        start_node = nodes.get(start)
        end_node = nodes.get(end)
        if not start_node or not end_node:
            continue
        dx = start_node["x"] - end_node["x"]
        dy = start_node["y"] - end_node["y"]
        distance = math.hypot(dx, dy)
        edges.append(
            {
                "from": start,
                "to": end,
                "distance": distance,
                "usage_count": usage_count,
            }
        )

    # Remove internal x/y fields before saving.
    for node in nodes.values():
        node.pop("x", None)
        node.pop("y", None)

    output = {
        "nodes": nodes,
        "edges": edges,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Topology saved: {output_path}")
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)}")


def main():
    project_root = Path(__file__).resolve().parents[2]
    stand_shp_path = project_root / "data" / "raw" / "机场平面图" / "Standno" / "Standno_Self_Property.shp"
    taxi_shp_path = project_root / "data" / "raw" / "机场平面图" / "TaxiRoad" / "TaxiRoad.shp"
    output_path = project_root / "scripts" / "data_processing" / "topology_map_based.json"

    build_topology(stand_shp_path, taxi_shp_path, output_path)


if __name__ == "__main__":
    main()
