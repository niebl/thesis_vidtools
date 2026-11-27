if __package__:
    from .Serializable import Serializable, SerializableCollection
else:
    from Serializable import Serializable, SerializableCollection
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, shape
import shapely as shp
from enum import Enum
import math
import pyproj

class GeometryType(Enum):
        LineString = LineString
        Points = Point

class Trajectory(SerializableCollection):
    def __init__(
            self, 
            geometry:list=[], 
            oid:str=None, 
            verbose:bool=False, 
            workdir=None,
            parent=None,
            items_attribute:str=None
            ):
        items_attribute = "geometry"

        super().__init__(oid=oid, verbose=verbose, workdir=workdir, items_attribute=items_attribute)
        self.geometry = geometry

    @staticmethod
    def df_to_trajectory(df):
        df.rename(columns={
            'latitude (°)': 'lat', 
            'longitude (°)': 'lon',
            'elevation (m)': 'ele',
            'distance (km)': 'dist',
            'compass (°)': 'orient',
            'duration (s)': 'dur',
            'velocity (km/h)': 'vel',
            }, inplace=True)
        data = df.to_dict(orient='records')
        return data

    @staticmethod
    def trajectory_to_df(in_dict, geom_type):
        df = pandas.DataFrame.from_dict(
            in_dict,
            orient='records'
            )
        df.rename(columns={
            'lat':      'latitude (°)',
            'lon':      'longitude (°)',
            'ele':      'elevation (m)',
            'dist':     'distance (km)',
            'orient':   'compass (°)',
            'dur':      'duration (s)',
            'vel':      'velocity (kmh)'
            }, inplace=True)
        return df

    @staticmethod
    def transform(feature, source='3857', destination='4326'):
        proj = pyproj.Transformer.from_crs(
            pyproj.CRS(f'EPSG:{str(source)}'), pyproj.CRS(f'EPSG:{str(destination)}'), 
            always_xy=True).transform
        return shp.ops.transform(proj, feature)

    def get_point_timestamp(self, index):
        return self.track[index]["time"]
    
    def contains_timestamp(self, ts, ts_format="unix"):
        try:
            return self.track[0]["time"] <= ts and self.track[-1]["time"] >= ts
        except Exception as e:
            print(f"Error in contains, using timestamp {ts}", self.track[0]["time"],self.track[-1]["time"])
            return False
    
    def get_point_by_timestamp(self, ts, ts_format="unix", max_closest=float("inf")):
        try:
            if not self.track:
                raise ValueError("track is empty")
            closest_dist = float("inf")
            closest = None
            for p in self.track:
                dist = abs(p["time"] - ts)
                if dist < closest_dist:
                    closest = p
                    closest_dist = dist 
            
            #point = min(
            #    (p for p in self.track if 0 <= p["time"] - ts <= 2),
            #    key=lambda point: point["time"] - ts,
            #    default=None,
            #)
            #self.log(closest_dist)
            if closest_dist < max_closest:
                self.log("closest found point:", closest)
                return closest
            else:
                return None
        except Exception as e:
            raise e
            return None

    def get_trajectory_by_timeframe(self, start_ts, end_ts, ts_format="unix", max_closest=float("inf")):
        points = []
        for n in range(start_ts, end_ts):
            points.append(self.get_point_by_timestamp)

    def geometry_geojson(self, geom_type:GeometryType=LineString):
        geom = []
        if geom_type == GeometryType.LineString:
            geom = {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "LineString","coordinates": []}
                }
            for point in self.geometry:
                geom["geometry"]["coordinates"].append([point["lon"], point["lat"]])
        elif geom_type == GeometryType.Points:
            geom = {"type": "FeatureCollection", "features": []}
            for point in self.geometry:
                geom["features"].append({
                    "properties": {},"geometry": {"type": "Point",
                        "coordinates": (point["lon"], point["lat"])
                    }
                })
        return geom

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
            longitude_delta = math.radians(current["lon"] - previous["lon"])
            latitude_start = math.radians(previous["lat"])
            latitude_end = math.radians(current["lat"])
            bearing_y = math.sin(longitude_delta) * math.cos(latitude_end)
            bearing_x = (
                math.cos(latitude_start) * math.sin(latitude_end)
                - math.sin(latitude_start) * math.cos(latitude_end) * math.cos(longitude_delta)
            )

            row["dist"] = distance_km
            row["dur"] = delta_time
            row["vel"] = distance_km * 3600 / delta_time if delta_time > 0 else 0.0
            row["orient"] = (math.degrees(math.atan2(bearing_y, bearing_x)) + 360) % 360

        return self.df_to_trajectory(pd.DataFrame(rows).reset_index(drop=True))

    def detect_turns(self, angle_threshold=30, min_velocity=5):
        if not self.geometry or len(self.geometry) < 3:
            return []
        turn_events = []
        current_event = []

        for point in self.geometry:
            angle_change = point.get("angle_change")
            velocity = point.get("vel", 0)

            #TODO: this still includes angle change from non-qualifying points

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

        return turn_events

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