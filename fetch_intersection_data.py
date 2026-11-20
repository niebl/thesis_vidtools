from Clipping import Clips

from pathlib import Path
import os
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
import json
import argparse
import traceback
import osmnx
import math, time

def get_features_along_linestring(
    linestring_geojson: dict,
    buffer_m: float = 50.0,
    tags: dict | None = None,
):
    if tags is None:
        tags = {"highway": ["traffic_signals", "stop", "crossing"]}
    polygon = linestring_to_buffer_polygon(linestring_geojson, buffer_m)
    return osmnx.features_from_polygon(polygon, tags=tags)

def linestring_to_buffer_polygon(linestring_geojson: dict, buffer_m: float = 50.0):
    geom = shape(linestring_geojson)
    if geom.geom_type != "LineString":
        raise ValueError(f"Expected a LineString, got {geom.geom_type}.")

    gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")

    # Project to a local UTM CRS so the buffer distance is in meters.
    # For very long lines spanning multiple UTM zones, consider a custom CRS.
    gdf_proj = gdf.to_crs(gdf.estimate_utm_crs())

    # Buffer and dissolve to a single polygon, then back to WGS84 for OSMnx.
    buffered = gdf_proj.buffer(buffer_m).unary_union
    poly_wgs84 = (
        gpd.GeoSeries([buffered], crs=gdf_proj.crs)
        .to_crs("EPSG:4326")
        .geometry.unary_union
    )
    return poly_wgs84

def _remove_isolated_nodes(G):
    isolated = [n for n in G.nodes if G.degree(n) == 0]
    G.remove_nodes_from(isolated)   
    return G

def drop_service_ways(graph, exclude):
    exclude_access = {
        "private", "destination", "permissive"
    }
    edges = osmnx.graph_to_gdfs(graph, nodes=False, edges=True)
    mask = (edges["highway"] == "service" & edges["service"].isin(exclude))
    mask_private = (edges["access"].isin(exclude_access))
    footways = (edges["foot"].isin({"yes"}) & (edges["cycleway"].isin({"no"}) | edges["foot"].isin({"designated"})))

    drop_edges = pd.concat([edges[mask], edges[mask_private], edges[footways]])

    if len(drop_edges):
        # edges gdf index is (u, v, key) — exactly what remove_edges_from wants
        graph.remove_edges_from(list(drop_edges.index))
        graph = _remove_isolated_nodes(graph)   # clean up nodes left with no edges
    return graph

def main():
    WORKDIR = Path.home() / "Projects/Bike Footage/"
    INPUT_MAPDATA = WORKDIR / "mapdata" / "zurich_highways.osm"
    GRAPHML_LOCATION = WORKDIR / "mapdata" / "zurich_graph.graphml"
    GRAPHML_LOC_CONSOLIDATED = WORKDIR / "mapdata"
    TOLERANCE = 15

    osmnx.settings.useful_tags_way = [
        "access", "area", "bridge", "est_width", "highway", "junction",
        "landuse", "lanes", "maxspeed", "name", "oneway", "ref", "service",
        "tunnel", "width",                          # defaults
        "bicycle", "cycleway",                      # bike access + on-road infra
        "cycleway:left", "cycleway:right", "cycleway:both",
        "foot", "surface", "smoothness", "lit", "mtb:scale",
    ]

    TOLERANCE_BY_WAY = {
        "motorway": 40,
        "trunk": 35,
        "primary": 35,
        "secondary": 30,
        "tertiary": 20,
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

    EXCLUDE_SERVICE = {
        "parking_aisle", "driveway", "emergency_access", "drive-through",
        "parking", "bus", "alley", "spur", "yard", "private", "parking_aisle, driveway"
    }

    start = time.time()
    verbose = True    
    def log(*args):
        current = time.time()
        runtime = math.floor( (current - start) * 1000 )
        runtime = str(f"{runtime:,d}").rjust(13," ") + "ms"

        if verbose: print(runtime, *args)

    #presupposes clip_trajectories.py output
    log("- loading clip data...")

    clips = WORKDIR / "clips_zurich/clips.json"
    clips = Clips.from_file(clips, verbose=True)
    log("- relinking clip data...")
    clips.build_parent_tree()
    clips.relink()


    # load OSM graph
    graph = None
    if os.path.isfile(str(GRAPHML_LOCATION)):
        log("- loading graph from file...")
        graph = osmnx.io.load_graphml(filepath=GRAPHML_LOCATION)
        log(f"      Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    else:
        log("- building graph from osm data...")
        graph = osmnx.graph_from_xml(INPUT_MAPDATA)
        log(f"      Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        log("- saving graph...")
        osmnx.io.save_graphml(graph, filepath=GRAPHML_LOCATION)

    #log("- saving graph nodes and edges for viewing...")
    #nodes, edges = osmnx.graph_to_gdfs(graph, nodes=True, edges=True)
    #nodes = nodes.explore()
    #edges = edges.explore()
    #nodes.save("nodes.html")
    #edges.save("edges.html")

    graphml_consolidated_file = GRAPHML_LOC_CONSOLIDATED / f"zurich_dynamic_consolidation.graphml"

    DEFAULT = 12
    if os.path.isfile((str(graphml_consolidated_file))):
        log("- loading consolidated graph from file...")
        graph = osmnx.io.load_graphml(filepath=graphml_consolidated_file)
    else:
        log("- assigning per-node tolerances...")
        tolerances = {}
        for node in graph.nodes:
            way_types = []
            for _, _, _, edge_data in graph.edges(node, keys=True, data=True):
                way = edge_data.get("highway")
                if way is None:
                    continue
                way_types.extend(way if isinstance(way, list) else [way])

            if way_types:
                tolerances[node] = max(
                    TOLERANCE_BY_WAY.get(w, DEFAULT) for w in way_types
                )
            else:
                tolerances[node] = DEFAULT

        log("- projecting graph to meter-based CRS...")
        graph = osmnx.project_graph(graph)

        
        log("- dropping irrelevant serviceways...")
        graph = drop_service_ways(graph, EXCLUDE_SERVICE)
        log(f"      Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        log("- consolidating intersections...")
        graph = osmnx.consolidate_intersections(
            graph, 
            tolerance=tolerances, 
            rebuild_graph=True,
            max_length=40,
            #dead_ends=False,
            )

        log("- reprojecting graph back...")
        graph = osmnx.project_graph(graph, to_latlong=True)

        log("- saving consolidated graph...")
        osmnx.io.save_graphml(graph, filepath=graphml_consolidated_file)

    log("- saving graph to files...")
    nodes, edges = osmnx.graph_to_gdfs(graph, nodes=True, edges=True)
    nodes.to_file(WORKDIR / "mapdata" / "nodes_zurich.geojson", driver="GeoJSON")
    edges.to_file(WORKDIR / "mapdata" / "edges_zurich.geojson", driver="GeoJSON")

    #print(f"Intersections found: {len(intersections)}")
    #print(intersections[["x", "y", "street_count"]].head())

    # 2. Nearby signals / crossings / stop signs (join to intersections as needed)
    #features = get_features_along_linestring(linestring, buffer_m=50)
    #print(f"OSM features found: {len(features)}")
    #print(features[["element_type", "osmid"]].head())

if __name__ == "__main__":
    main()