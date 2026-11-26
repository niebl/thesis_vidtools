if __package__:
    from .Bookmarks import Bookmarks, Bookmark
    from .Trajectory import *
else:
    from Bookmarks import Bookmarks, Bookmark
    from Trajectory import *
from pathlib import Path
import av
from datetime import datetime as dt
from datetime import date
from math import atan2, cos, degrees, radians, sin

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
import shapely
import osmnx
import pyproj

class Clip(Trajectory):
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"
    def __init__(
            self, 
            start:Bookmark, 
            end:Bookmark, 
            workdir:Path=None, 
            videoclip=None, 
            geometry:list=None,
            observations:dict=False, 
            discard=False, 
            uncertain=False,
            parent=None,
            oid:str=None,
            intersection_graph:osmnx.graph=None,
            consolidated_graph:osmnx.graph=None
        ):
        super().__init__(workdir=workdir, parent=parent, oid=oid, items_attribute="geometry")
        self.start = start
        self.end = end
        self.files = [start.path]
        #add second file if clip spans 2
        self.files.append(end.path) if end.path != start.path else None
        self.videoclip = videoclip or ""
        self.geometry = geometry
        self.observations = observations or {}
        self.discard = discard
        self.uncertain = uncertain
        self.intersection_graph = None
        self.consolidated_graph = None

    @classmethod
    def from_dict(cls, data):
        data["start"] = Bookmark.from_dict(data["start"])
        data["end"] = Bookmark.from_dict(data["end"])
        return cls._from_dict(data)

    def to_dict(self):
        data = self._to_dict(exclude_keys=[
            "files",
            "parent",
            "workdir",
            "verbose"
        ])
        return data

    def has_bookmarks(self):
        return (type(self.start) == Bookmark and type(self.end) == Bookmark)

    def render_clip(self, output_path=None):
        source = list(map(lambda c: Path(c), self.files))
        start = int(self.start.pos * 1000)/1000
        output = Path(output_path) if output_path else (
            Path(self.workdir) / f"{source[0].stem}_at_{start:.3f}s.mp4"
        )
        if output.exists():
            print(f"skipping {str(output)}. already exists")
            self.videoclip = output
            return output
        output.parent.mkdir(parents=True, exist_ok=True)

        if len(source) > 1:
            duration = int(self.get_duration() * 1000)/1000
            vid1 = source[0]
            vid2 = source[1]
            filter_complex = f"[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[midv][mida];[midv]trim=start={start}:duration={duration},setpts=PTS-STARTPTS[outv];[mida]atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS[outa]"
            command = [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(vid1),
                "-i", str(vid2),
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-c:a", "aac",
                "-movflags", "+faststart",
                str(output)
            ]
            subprocess.run(command, check=True)
        
        else:
            end = self.end.pos

            command = [
                "ffmpeg", "-hide_banner", "-y",
                "-ss", str(start),
                "-i", str(source[0]),
                "-t", str(end - start),
                "-c:v", "libx264",
                "-c:a", "aac",
                str(output),
            ]
            subprocess.run(command, check=True)
        
        self.videoclip = output
        return output

    def validate(self):
        try:
            same_dir = Path(self.start.path).parent == Path(self.end.path).parent
            if not same_dir:
                raise Exception(f"clip invalid, not same dir {self}")
            files= sorted(Path(self.start.path).parent.glob("*"))
            start_index = files.index(Path(self.start.path))
            end_index = files.index(Path(self.end.path))
            direct_follow = abs(end_index - start_index) <= 1
            if not same_dir:
                raise Exception("clip invalid, direct follow not fulfilled {self}")
            duration_ok = self.get_duration() < 120
            if not same_dir:
                raise Exception("clip invalid, duration not okay {self}")

            return same_dir and direct_follow and duration_ok and self.has_bookmarks()
        except Exception as e: 
            print("clip invalid", e)
            

    def get_duration(self):
        if self.start.path == self.end.path:
            return self.end.pos - self.start.pos
        else:
            # get video duration of start file
            start_file = av.open(self.start.path)
            start_duration = start_file.duration / av.time_base
            start_file.close() 
            trailing_duration = start_duration - self.start.pos
            leading_duration = self.end.pos
            return trailing_duration + leading_duration
            return None

    def unix_to_iso(self, ts):
        if not isinstance(ts,dt):
            return dt.fromtimestamp(float(ts)).isoformat()
        else:
            ts.isoformat()

    def video_infos(self, video, human_readable=False):
        return {
                "name": video.path.name,
                "f_ts": self.unix_to_iso(video.get_file_timestamp()) if human_readable else video.get_file_timestamp(),
                "ts": self.unix_to_iso(video.get_timestamp()) if human_readable else video.get_timestamp(),
                "offset": video.get_offset()
            }

    def get_date(self):
        track = self.parent.get_track_for_clip(self)
        if track is not None:
            video_start = track.get_video_by_title(Path(self.start.path).stem)
            return date.fromtimestamp(video_start.get_file_timestamp())
        else: return None

    def simplify(self, distance=10):
        if not self.geometry or len(self.geometry) < 2:
            return pd.DataFrame(self.geometry or [])

        points = pd.DataFrame(self.geometry)
        gdf = gpd.GeoDataFrame(
            points,
            geometry=gpd.points_from_xy(points["lon"], points["lat"]),
            crs="EPSG:4326",
        )
        projected = gdf.to_crs(gdf.estimate_utm_crs())
        line = shape(self.geometry_geojson()["geometry"])
        simplified = gpd.GeoSeries([line], crs="EPSG:4326").to_crs(
            projected.crs
        ).simplify(distance, preserve_topology=False).iloc[0]

        source_coordinates = [(point.x, point.y) for point in projected.geometry]
        kept = [
            min(
                range(len(source_coordinates)),
                key=lambda index: (source_coordinates[index][0] - coordinate[0]) ** 2
                + (source_coordinates[index][1] - coordinate[1]) ** 2,
            )
            for coordinate in simplified.coords
        ]
        rows = [gdf.iloc[index].drop(labels="geometry").copy() for index in kept]

        for index, row in enumerate(rows):
            if index == 0:
                row["dist"] = row["dur"] = row["vel"] = row["orient"] = 0.0
                continue

            previous = gdf.iloc[kept[index - 1]]
            current = gdf.iloc[kept[index]]
            delta_time = float(current["time"] - previous["time"])
            distance_km = projected.geometry.iloc[kept[index - 1]].distance(
                projected.geometry.iloc[kept[index]]
            ) / 1000
            longitude_delta = radians(current["lon"] - previous["lon"])
            latitude_start = radians(previous["lat"])
            latitude_end = radians(current["lat"])
            bearing_y = sin(longitude_delta) * cos(latitude_end)
            bearing_x = (
                cos(latitude_start) * sin(latitude_end)
                - sin(latitude_start) * cos(latitude_end) * cos(longitude_delta)
            )

            row["dist"] = distance_km
            row["dur"] = delta_time
            row["vel"] = distance_km * 3600 / delta_time if delta_time > 0 else 0.0
            row["orient"] = (degrees(atan2(bearing_y, bearing_x)) + 360) % 360

        return self.df_to_trajectory(pd.DataFrame(rows).reset_index(drop=True))

    def detect_turns(self, angle_threshold=30, min_velocity=5):
        if not self.geometry or len(self.geometry) < 3:
            return []

        turn_events = []
        current_event = []

        for point in self.geometry:
            angle_change = point.get("angle_change")
            velocity = point.get("vel", 0)

            #TODO: this still includes angle change from non-qualifying points in window
            qualifies = (
                angle_change is not None
                and abs(angle_change) >= angle_threshold
                and velocity is not None
                and velocity >= min_velocity
            )

            if qualifies:
                current_event.append(point)
            elif current_event: #only gets called when not qualified, appends event if exists
                turn_events.append(current_event)
                current_event = []

        if current_event:
            turn_events.append(current_event)
        
        #check betweeen events. merge events if they are close in time and velocity is low enough
        merged_events = []
        for i, event in enumerate(turn_events):
            if i == 0:
                merged_events.append(event)
                continue

            previous_event = merged_events[-1]
            time_gap = event[0]["time"] - previous_event[-1]["time"]
            #average velocity in segment between events
            between_segment = [p for p in self.geometry if previous_event[-1]["time"] < p["time"] < event[0]["time"]]
            btw_avg_velocity = sum(p.get("vel", 0) for p in between_segment) / len(between_segment) if between_segment else 0

            # merge events if they are close in time and velocity is low enough
            if time_gap <= 6 and btw_avg_velocity <= min_velocity:
                merged_events[-1].extend(event)
            else:
                merged_events.append(event)
        return merged_events

    def moving_window_heading_change(self, window_size=7):
        if not self.geometry or len(self.geometry) < 2:
            return None

        for i in range(len(self.geometry)):
            p1 = self.geometry[max(0, i - window_size)]
            p2 = self.geometry[i]

            if p1.get("orient") is None or p2.get("orient") is None:
                continue

            angle_diff = (p2["orient"] - p1["orient"] + 180) % 360 - 180

            self.geometry[i]["angle_change"] = angle_diff

    def moving_window_angle_compare(self, window_size=4, node_geom=None):
        if not self.geometry or len(self.geometry) < 2:
            return None

        for i in range(len(self.geometry)):
            p1 = self.geometry[max(0, i - window_size)]
            p2 = self.geometry[i]

            if p1.get("angle") is None or p2.get("angle") is None:
                continue

            angle_diff = (p2["angle"] - p1["angle"] + 180) % 360 - 180

            self.geometry[i]["angle_change"] = angle_diff

    def infer_turn_direction(self, window_size=7, angle_threshold=20, min_velocity=5):        
        self.moving_window_heading_change(window_size=window_size)
        turn_events = self.detect_turns(
            angle_threshold=angle_threshold, min_velocity=min_velocity
        )
        if not turn_events:
            return "straight"
        event_changes = [
            max(event, key=lambda point: abs(point["angle_change"]))["angle_change"]
            for event in turn_events
        ]
        if len(event_changes) > 1 and abs(sum(event_changes)) <= max(angle_threshold, 30):
            return "straight"

        topology_graph = self.consolidated_graph
        if topology_graph is None:
            topology_graph = getattr(self, "intersection_topology", None)

        if topology_graph is None or self.intersection_graph is None:
            turning_point = max(
                (point for event in turn_events for point in event),
                key=lambda point: abs(point["angle_change"]),
            )
            change = turning_point["angle_change"]
            if abs(change) < angle_threshold:
                return "straight"
            return "right" if change > 0 else "left"

        self.intersection_graph = osmnx.bearing.add_edge_bearings(
            self.intersection_graph
        )

        def normalize_bearing(bearing):
            return (bearing + 180) % 360 - 180

        def bearing_between(start, end):
            longitude_delta = radians(end["lon"] - start["lon"])
            latitude_start = radians(start["lat"])
            latitude_end = radians(end["lat"])
            bearing_y = sin(longitude_delta) * cos(latitude_end)
            bearing_x = (
                cos(latitude_start) * sin(latitude_end)
                - sin(latitude_start) * cos(latitude_end) * cos(longitude_delta)
            )
            return degrees(atan2(bearing_y, bearing_x)) % 360

        def average_position(points):
            return {
                "lat": sum(point["lat"] for point in points) / len(points),
                "lon": sum(point["lon"] for point in points) / len(points),
            }

        def average_bearing(points):
            bearings = [
                bearing_between(start, end)
                for start, end in zip(points, points[1:])
                if (start["lat"], start["lon"]) != (end["lat"], end["lon"])
            ]
            if not bearings:
                return None
            return normalize_bearing(degrees(atan2(
                sum(sin(radians(value)) for value in bearings),
                sum(cos(radians(value)) for value in bearings),
            )))

        trajectory_matches = []
        for endpoint, points in (
            ("start", self.geometry[:3]),
            ("end", self.geometry[-3:]),
        ):
            bearing = average_bearing(points)
            if bearing is None:
                continue
            if endpoint == "start":
                bearing = normalize_bearing(bearing + 180)
            trajectory_matches.append((endpoint, average_position(points), bearing))

        if len(trajectory_matches) != 2:
            return "straight"

        geod = pyproj.Geod(ellps="WGS84")
        event_matches = []
        for event in turn_events:
            turning_point = max(
                event, key=lambda point: abs(point["angle_change"])
            )
            point_geom = shape({
                "type": "Point",
                "coordinates": (turning_point["lon"], turning_point["lat"]),
            })
            legs = self.get_intersection_legs(point_geom)
            candidates = {"start": [], "end": []}

            for orig_id, other, data in legs:
                leg_bearing = data.get("bearing")
                if leg_bearing is None:
                    start_node = self.intersection_graph.nodes[orig_id]
                    end_node = self.intersection_graph.nodes[other]
                    leg_bearing = bearing_between(
                        {"lat": start_node["y"], "lon": start_node["x"]},
                        {"lat": end_node["y"], "lon": end_node["x"]},
                    )
                leg_bearing = normalize_bearing(float(leg_bearing))
                node = self.intersection_graph.nodes[orig_id]

                for endpoint, position, trajectory_bearing in trajectory_matches:
                    angle_difference = abs(normalize_bearing(
                        leg_bearing - trajectory_bearing
                    ))
                    _, _, distance = geod.inv(
                        position["lon"], position["lat"], node["x"], node["y"]
                    )
                    candidates[endpoint].append({
                        "angle_difference": angle_difference,
                        "distance_m": distance,
                        "leg_bearing": leg_bearing,
                    })

            if not candidates["start"] or not candidates["end"]:
                continue
            best_start = min(
                candidates["start"],
                key=lambda match: (match["angle_difference"], match["distance_m"]),
            )
            best_end = min(
                candidates["end"],
                key=lambda match: (match["angle_difference"], match["distance_m"]),
            )
            incoming_bearing = normalize_bearing(best_start["leg_bearing"] + 180)
            turn_angle = normalize_bearing(best_end["leg_bearing"] - incoming_bearing)
            direction = (
                "straight" if abs(turn_angle) <= angle_threshold
                else "right" if turn_angle > 0
                else "left"
            )
            alignment_error = max(
                best_start["angle_difference"], best_end["angle_difference"]
            )
            event_matches.append((
                alignment_error,
                best_start["distance_m"] + best_end["distance_m"],
                direction,
                turn_angle,
                turning_point,
            ))

        if not event_matches:
            turning_point = max(
                (point for event in turn_events for point in event),
                key=lambda point: abs(point["angle_change"]),
            )
            change = turning_point["angle_change"]
            return "right" if change > 0 else "left"

        alignment_error, _, direction, turn_angle, turning_point = min(
            event_matches, key=lambda match: (match[0], match[1])
        )
        if alignment_error > 60:
            self.uncertain = True
        print(
            f"    Detected {direction} turn at time {turning_point['time']} "
            f"(intersection bearing change={turn_angle:.1f} degrees, "
            f"alignment error={alignment_error:.1f} degrees)."
        )
        return direction

    def get_intersection_legs(self, poi):
        consolidated_g = self.consolidated_graph
        if consolidated_g is None:
            consolidated_g = getattr(self, "intersection_topology", None)
        if consolidated_g is None or self.intersection_graph is None:
            return []

        node_id = osmnx.nearest_nodes(consolidated_g, X=poi.x, Y=poi.y)
        orig_ids = consolidated_g.nodes[node_id].get("osmid_original", [])
        if not isinstance(orig_ids, list):
            orig_ids = [orig_ids]
        orig_ids = [int(orig_id) for orig_id in orig_ids]
        orig_set = set(orig_ids)

        legs = []
        exclude = ["path", "cycleway", "footway", "steps", "track"]
        for orig_id in orig_ids:
            if orig_id not in self.intersection_graph:
                print(f"    Original node {orig_id} not found in intersection graph.")
                continue
            for u, v, key, data in self.intersection_graph.edges(orig_id, keys=True, data=True):
                other = v if u == orig_id else u
                if other in orig_set or data.get("highway") in exclude:
                    continue
                legs.append((orig_id, other, data))
        return legs

    def set_intersection_graphs(self, path_graph=None, path_consolidated=None, buffer=300, graph=None, consolidated=None):
        proj_to_3857 = pyproj.Transformer.from_crs(
            pyproj.CRS('EPSG:4326'), pyproj.CRS('EPSG:3857'), 
            always_xy=True).transform
        proj_to_4326 = pyproj.Transformer.from_crs(
            pyproj.CRS('EPSG:3857'), pyproj.CRS('EPSG:4326'), 
            always_xy=True).transform
        
        # get buffer around clip maneuver geometry
        trajectory = shape(self.geometry_geojson()["geometry"])
        traj_3857 = shapely.ops.transform(proj_to_3857, trajectory)
        buffer = shapely.buffer(traj_3857, distance=buffer)
        buffer = shapely.ops.transform(proj_to_4326, buffer)

        #get consolidated intersections and cut to a buffer
        consolidated = consolidated or osmnx.io.load_graphml(filepath=path_consolidated)

        consolidated = osmnx.truncate.truncate_graph_polygon(
            consolidated, buffer, truncate_by_edge=True
            )
        self.consolidated_graph = consolidated
        
        #get intersection geometry from .osm file or argument
        graph = graph or osmnx.io.load_graphml(filepath = path_graph)
        graph = osmnx.truncate.truncate_graph_polygon(
            graph, buffer, truncate_by_edge=True
            )
        self.intersection_graph = graph

    def geometry_geojson(self, human_readable=False, geom_type:GeometryType=GeometryType.LineString):
        coordinates = []
        if self.geometry is None: 
            self.geometry = []
        geom = super().geometry_geojson(geom_type=geom_type)
        start = int(self.start.pos * 1000)/1000
        properties = {
            "name": f"{Path(self.start.path).stem}_at_{start:.3f}s",
            "duration": self.get_duration(),
            "bookmarks": {
                "start": self.start.to_dict(), "end":self.end.to_dict()
                }
        }
        if self.parent and len(self.parent.tracks) > 0:
            track = self.parent.get_track_for_clip(self)
            if track is not None:
                video_start = track.get_video_by_title(Path(self.start.path).stem)
                video_end = track.get_video_by_title(Path(self.end.path).stem)
                properties["start"] = self.video_infos(video_start, human_readable)
                properties["end"] = self.video_infos(video_end, human_readable)
                properties["day"] = str(self.get_date())
        geom["properties"].update(properties)
        if geom_type == GeometryType.Points:
            for i, point in enumerate(self.geometry):
                geom["features"][i]["properties"] = {
                    ['ele']:      point['ele'],
                    ['dist']:     point['dist'],
                    ['orient']:   point['orient'],
                    ['dur']:      point['dur'],
                    ['vel']:      point['vel']
                }
        return geom