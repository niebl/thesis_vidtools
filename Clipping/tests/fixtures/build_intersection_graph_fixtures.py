"""Rebuild the local GraphML fixtures from the extracted Zurich OSM XML.

The OSM XML should be produced by osm_data/osmium_extract.sh. Run:
    python Clipping/tests/fixtures/build_intersection_graph_fixtures.py
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.geometry import LineString
from shapely.ops import unary_union


FIXTURE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FIXTURE_DIR.parents[2]
DEFAULT_MAPDATA_DIR = PROJECT_ROOT.parent / "mapdata"
sys.path.insert(0, str(PROJECT_ROOT))

from Clipping.tests.test_clips import CLIP_DIRECTION_FIXTURES


USEFUL_TAGS_WAY = [
    "access", "area", "bridge", "est_width", "highway", "junction",
    "landuse", "lanes", "maxspeed", "name", "oneway", "ref", "service",
    "tunnel", "width",
    "bicycle", "cycleway",
    "cycleway:left", "cycleway:right", "cycleway:both",
    "foot", "surface", "smoothness", "lit", "mtb:scale",
]

TOLERANCE_BY_WAY = {
    "motorway": 40,
    "trunk": 35,
    "primary": 30,
    "secondary": 25,
    "tertiary": 18,
    "unclassified": 15,
    "residential": 12,
    "living_street": 10,
    "service": 6,
    "cycleway": 8,
    "path": 4,
    "footway": 8,
    "pedestrian": 8,
    "track": 4,
}

DEFAULT_TOLERANCE = 12
EXCLUDE_SERVICE = {
    "parking_aisle", "driveway", "emergency_access", "drive-through",
    "parking", "bus", "alley", "spur", "yard", "private",
    "parking_aisle, driveway",
}
EXCLUDE_ACCESS = {"private", "destination", "permissive"}


def build_buffered_area(buffer_m):
    lines = [
        LineString([(point["lon"], point["lat"]) for point in fixture["geometry"]])
        for fixture in CLIP_DIRECTION_FIXTURES
    ]
    trajectories = gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")
    projected = trajectories.to_crs("EPSG:3857")
    buffered = unary_union(projected.geometry.buffer(buffer_m))
    return gpd.GeoSeries([buffered], crs=projected.crs).to_crs("EPSG:4326").iloc[0]


def contains_tag(value, tags):
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return any(tag in tags for tag in values)


def assign_tolerances(graph):
    tolerances = {}
    for node in graph.nodes:
        way_types = []
        for _, _, _, edge_data in graph.edges(node, keys=True, data=True):
            highway = edge_data.get("highway")
            if highway is None:
                continue
            way_types.extend(highway if isinstance(highway, list) else [highway])

        tolerances[node] = (
            max(TOLERANCE_BY_WAY.get(way, DEFAULT_TOLERANCE) for way in way_types)
            if way_types
            else DEFAULT_TOLERANCE
        )
    return tolerances


def drop_irrelevant_serviceways(graph):
    drop_edges = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        highway_is_service = contains_tag(data.get("highway"), {"service"})
        excluded_service = contains_tag(data.get("service"), EXCLUDE_SERVICE)
        excluded_access = contains_tag(data.get("access"), EXCLUDE_ACCESS)
        excluded_footway = contains_tag(data.get("foot"), {"yes"}) and (
            contains_tag(data.get("cycleway"), {"no"})
            or contains_tag(data.get("foot"), {"designated"})
        )
        if (highway_is_service and excluded_service) or excluded_access or excluded_footway:
            drop_edges.append((u, v, key))

    graph.remove_edges_from(drop_edges)
    graph.remove_nodes_from([node for node in graph.nodes if graph.degree(node) == 0])
    return graph


def build_graphs(osm_xml):
    ox.settings.useful_tags_way = USEFUL_TAGS_WAY
    unconsolidated = ox.graph_from_xml(osm_xml)

    tolerances = assign_tolerances(unconsolidated)
    consolidated = ox.project_graph(unconsolidated.copy())
    consolidated = drop_irrelevant_serviceways(consolidated)
    consolidated = ox.consolidate_intersections(
        consolidated,
        tolerance=tolerances,
        rebuild_graph=True,
        max_length=40,
    )
    consolidated = ox.project_graph(consolidated, to_latlong=True)
    return unconsolidated, consolidated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mapdata-dir",
        type=Path,
        default=DEFAULT_MAPDATA_DIR,
        help="Directory containing zurich_highways.osm from osmium_extract.sh.",
    )
    parser.add_argument(
        "--buffer-m",
        type=float,
        default=100.0,
        help="Buffer distance around the test trajectories, in meters.",
    )
    args = parser.parse_args()

    if args.buffer_m <= 0:
        parser.error("--buffer-m must be greater than zero")

    osm_xml = args.mapdata_dir / "zurich_highways.osm"
    if not osm_xml.is_file():
        parser.error(f"OSM XML not found: {osm_xml}")

    unconsolidated, consolidated = build_graphs(osm_xml)
    polygon = build_buffered_area(args.buffer_m)
    graphs = (
        (unconsolidated, "zurich_intersections_unconsolidated.graphml"),
        (consolidated, "zurich_intersections_consolidated.graphml"),
    )
    for graph, fixture_name in graphs:
        subset = ox.truncate.truncate_graph_polygon(
            graph,
            polygon,
            truncate_by_edge=True,
        )
        output_path = FIXTURE_DIR / fixture_name
        ox.io.save_graphml(subset, filepath=output_path)
        print(
            f"Wrote {output_path.name}: {len(subset.nodes)} nodes, "
            f"{len(subset.edges)} edges"
        )


if __name__ == "__main__":
    main()