if __package__:
    from .Serializable import Serializable, SerializableCollection
else:
    from Serializable import Serializable, SerializableCollection
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
from enum import Enum

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
            self.log(closest_dist)
            if closest_dist < max_closest:
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