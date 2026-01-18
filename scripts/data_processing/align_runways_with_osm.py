import json
import math
import re
from pathlib import Path

import shapefile
from shapely.geometry import LineString


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def runway_id_from_ref(ref):
    return f"runway_{ref.replace('/', '_')}"


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


def latlon_to_utm(lat, lon, zone_number=49):
    # WGS84 lat/lon -> UTM (meters).
    a = 6378137.0
    e = 0.08181919084262149
    e_sq = e * e
    k0 = 0.9996

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon0 = math.radians(zone_number * 6 - 183)

    n = a / math.sqrt(1 - e_sq * math.sin(lat_rad) ** 2)
    t = math.tan(lat_rad) ** 2
    c = e_sq / (1 - e_sq) * math.cos(lat_rad) ** 2
    a_ = math.cos(lat_rad) * (lon_rad - lon0)

    m = a * (
        (1 - e_sq / 4 - 3 * e_sq**2 / 64 - 5 * e_sq**3 / 256) * lat_rad
        - (3 * e_sq / 8 + 3 * e_sq**2 / 32 + 45 * e_sq**3 / 1024) * math.sin(2 * lat_rad)
        + (15 * e_sq**2 / 256 + 45 * e_sq**3 / 1024) * math.sin(4 * lat_rad)
        - (35 * e_sq**3 / 3072) * math.sin(6 * lat_rad)
    )

    easting = (
        k0
        * n
        * (
            a_
            + (1 - t + c) * a_**3 / 6
            + (5 - 18 * t + t**2 + 72 * c - 58 * e_sq / (1 - e_sq)) * a_**5 / 120
        )
        + 500000.0
    )
    northing = k0 * (m + n * math.tan(lat_rad) * (a_**2 / 2 + (5 - t + 9 * c + 4 * c**2) * a_**4 / 24))
    return easting, northing


def main():
    project_root = Path(__file__).resolve().parents[2]
    topo_path = project_root / "scripts" / "data_processing" / "topology_map_based.json"
    osm_path = project_root / "data" / "spatial" / "osm_runways_zlxy.json"
    osm_geo_path = project_root / "data" / "spatial" / "osm_runways_zlxy_geo.json"

    with open(topo_path, "r", encoding="utf-8") as f:
        topo = json.load(f)
    with open(osm_path, "r", encoding="utf-8") as f:
        osm = json.load(f)
    with open(osm_geo_path, "r", encoding="utf-8") as f:
        osm_geo = json.load(f)

    runway_nodes = {
        node_id: node
        for node_id, node in topo["nodes"].items()
        if node.get("type") == "runway"
    }
    osm_runways = osm.get("runways", [])
    if not runway_nodes or not osm_runways:
        raise ValueError("Missing runway nodes or OSM runway data")

    pairs = []
    for node_id, node in runway_nodes.items():
        for osm_runway in osm_runways:
            dist = haversine_m(node["lat"], node["lon"], osm_runway["lat"], osm_runway["lon"])
            pairs.append((dist, node_id, osm_runway["ref"]))

    pairs.sort(key=lambda x: x[0])
    used_nodes = set()
    used_refs = set()
    mapping = {}
    for dist, node_id, ref in pairs:
        if node_id in used_nodes or ref in used_refs:
            continue
        mapping[node_id] = ref
        used_nodes.add(node_id)
        used_refs.add(ref)
        if len(mapping) == min(len(runway_nodes), len(osm_runways)):
            break

    # Rename runway nodes and update coordinates to OSM centers.
    for old_id, ref in mapping.items():
        new_id = runway_id_from_ref(ref)
        osm_runway = next(r for r in osm_runways if r["ref"] == ref)
        node = topo["nodes"].pop(old_id)
        node["id"] = new_id
        node["ref"] = ref
        node["lat"] = osm_runway["lat"]
        node["lon"] = osm_runway["lon"]
        node["length_m"] = osm_runway.get("length_m")
        node["surface"] = osm_runway.get("surface")
        topo["nodes"][new_id] = node

    # Update edges to new runway node ids.
    id_map = {old_id: runway_id_from_ref(ref) for old_id, ref in mapping.items()}
    for edge in topo["edges"]:
        if edge["from"] in id_map:
            edge["from"] = id_map[edge["from"]]
        if edge["to"] in id_map:
            edge["to"] = id_map[edge["to"]]

    # Build runway line geometries in UTM.
    runway_lines = {}
    for runway in osm_geo.get("runways", []):
        ref = runway.get("ref")
        geom = runway.get("geometry", [])
        if not ref or len(geom) < 2:
            continue
        points_utm = [latlon_to_utm(p["lat"], p["lon"]) for p in geom]
        runway_lines[runway_id_from_ref(ref)] = LineString(points_utm)

    # Connect taxiways to runways by geometry intersection.
    taxi_shp_path = project_root / "data" / "raw" / "机场平面图" / "TaxiRoad" / "TaxiRoad.shp"
    reader = shapefile.Reader(str(taxi_shp_path), encoding="gbk")
    edge_set = set()
    for edge in topo["edges"]:
        edge_set.add(tuple(sorted([edge["from"], edge["to"]])))

    tolerance = 2.0
    runway_ids = set(runway_lines.keys())
    for rec, shape in zip(reader.iterRecords(), reader.iterShapes()):
        road_name = normalize_token(rec["RoadName"] or "")
        if not road_name:
            continue
        tokens = [normalize_token(t) for t in road_name.split("-") if normalize_token(t)]
        if len(tokens) != 1:
            continue
        token = tokens[0]
        node_id = f"taxiway_{token}"
        if node_id not in topo["nodes"]:
            continue
        if runway_id_from_ref(token) in runway_ids:
            continue
        if len(shape.points) < 2:
            continue
        line = LineString(shape.points)
        if line.is_empty:
            continue
        for runway_id, runway_line in runway_lines.items():
            if line.intersects(runway_line) or line.distance(runway_line) <= tolerance:
                edge_key = tuple(sorted([node_id, runway_id]))
                if edge_key in edge_set:
                    continue
                topo["edges"].append(
                    {
                        "from": edge_key[0],
                        "to": edge_key[1],
                        "distance": line.distance(runway_line),
                        "usage_count": 1,
                    }
                )
                edge_set.add(edge_key)

    with open(topo_path, "w", encoding="utf-8") as f:
        json.dump(topo, f, ensure_ascii=False, indent=2)

    print("Aligned runways using OSM centers and connected taxiways to runways.")


if __name__ == "__main__":
    main()
