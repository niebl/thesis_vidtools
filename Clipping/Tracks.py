import pandas
from pathlib import Path
if __package__:
    from .Serializable import Serializable, SerializableCollection
    from .Video import Video
else:
    from Serializable import Serializable, SerializableCollection
    from Video import Video
from datetime import datetime
import gpxo
import json
import warnings
import traceback

class Track(SerializableCollection):
    items_attribute = "track"

    def __init__(self, track=[], videos = [], oid:str = None, verbose:bool=False):
        super().__init__(oid=oid, verbose=verbose)
        self.track = track #Dataframe as read from GPX
        self.videos = videos

    @classmethod
    def from_gpx_file(cls, file_path, global_offset=0, verbose=False):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=UserWarning,
                )
            df = gpxo.Track(file_path)

        data = df.data.copy()
        timestamps = pandas.to_datetime(data["time"], utc=True)
        data["time"] = timestamps.map(
            lambda value: value.timestamp()-global_offset if pandas.notna(value) else None
        )
        

        for column in data.columns:
            values = [
                None if pandas.isna(value) else (
                    value.item() if hasattr(value, "item") else value
                )
                for value in data[column]
            ]
            data[column] = pandas.Series(values, index=data.index, dtype=object)

        track = cls(cls.df_to_track(data), verbose=verbose)
        if verbose:
            print("read track from", track[0]["time"], "to", track[-1]["time"])
        return track

    @classmethod
    def from_file(cls, path=None):
        path = path or cls.DEFAULT_WORKDIR
        with open(path, "r") as file:
            data = json.load(file)
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data):
        data["videos"] = list(map(lambda v: Video.from_dict(v), data["videos"]))
        return cls._from_dict(data)

    @staticmethod
    def df_to_track(df):
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
    def track_to_df(in_dict):
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

    def add_video(self, video):
        self.videos.append(video)
        if not self == video.parent:
            video.parent = self
        if not video.start_timestamp:
            video.start_timestamp = video.get_timestamp()

    def update_start_times(self):
        for video in self.videos:
            if not video.start_timestamp: video.start_timestamp = video.get_timestamp()

    def update_offsets(self):
        for video in self.videos:
            if not video.offset: video.offset = video.get_offset()

    def get_video_by_title(self, title):
        return self.find_item(lambda v: v.path.stem == title, "videos")

    def get_point_timestamp(self, index):
        return self.track[index]["time"]

    def contains_time(self, ts, ts_format="unix"):
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

    def get_points_by_timestamp_range(self, start_ts, end_ts, ts_format="unix", max_closest=float("inf")):
        points = []
        for n in range(start_ts, end_ts):
            points.append(self.get_point_by_timestamp)