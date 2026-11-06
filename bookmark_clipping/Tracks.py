import pandas
from pathlib import Path
if __package__:
    from .Serializable import Serializable, SerializableCollection
else:
    from Serializable import Serializable, SerializableCollection

import subprocess
from datetime import datetime
from dateutil import parser
import re
import gpxo
import json
from zoneinfo import ZoneInfo
import warnings
import traceback

class Track(SerializableCollection):
    items_attribute = "track"

    def __init__(self, track=[], videos = []):
        self.track = track #Dataframe as read from GPX
        self.videos = videos

    @classmethod
    def from_gpx_file(cls, file_path, global_offset=0):
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

        track = cls(cls.df_to_track(data))
        print("read track from", track[0]["time"], "to", track[-1]["time"])
        return track

    @classmethod
    def from_file(cls, path=None):
        path = path or cls.DEFAULT_WORKDIR
        with open(path, "r") as file:
            data = json.load(file)
        return cls.from_dict(data)
    
    @classmethod
    def _from_dict(self, in_dict):
        videos = list(map(lambda v: Video.from_dict(v), in_dict["videos"]))
        return Track(in_dict["track"], videos)

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

    def to_dict(self):
        return {
            "track": self.track,
            "videos": [video.to_dict() for video in self.videos],
        }

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

    def get_video(self, lambda_f):
        for video in self.videos:
            if lambda_f(video):
                return video
        return None

    def get_video_by_title(self, title):
        return self.get_video(lambda v: v.path.stem == title)

    def get_point_timestamp(self, index):
        return self.track[index]["time"]

    def contains_time(self, ts, ts_format="unix"):
        try:
            return self.track[0]["time"] <= ts and self.track[-1]["time"] >= ts
        except Exception as e:
            print(f"Error in contains, using timestamp {ts}", self.track[0]["time"],self.track[-1]["time"])
            return False

    def get_point_by_timestamp(self, ts, ts_format="unix"):
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
            print(closest_dist)
            if closest_dist < 5:
                return closest
            else:
                return None
        except Exception as e:
            raise e
            return None

    def get_points_by_timestamp_range(self, start_ts, end_ts, ts_format="unix"):
        points = []
        for n in range(start_ts, end_ts):
            points.append(self.get_point_by_timestamp)

class Video(Serializable):
    def __init__(self, path: Path, offset=None, start_timestamp = None, parent_track = None ):
        self.path = path
        self.offset = offset
        self.duration = self.get_duration()
        self.parent = parent_track
        self.start_timestamp = start_timestamp
        # this is a problem before video is added to track. better call such methods from parent after creation
        #if not self.start_timestamp and self.get_index() == 0:
        #    self.start_timestamp = self.get_timestamp() #infer from title or calculate from other videos

    @classmethod
    def _from_dict(cls, in_dict):
        return cls(
            Path(in_dict["path"]),
            in_dict.get("offset"),
            in_dict.get("start_timestamp"),
            None
        )

    def get_timestamp(self):
        if self.start_timestamp:
            return self.start_timestamp
        prev = self.get_prev()
        file_timestamp = self.get_file_timestamp()
        if prev:
            if prev.get_file_timestamp() == file_timestamp:
                return prev.get_timestamp() + prev.get_duration()
        return file_timestamp

    def get_offset(self):
        if self.offset is not None:
            return self.offset
        
        prev = self.get_prev()

        if self.offset is None and not prev:
            #raise Exception("First video has no offset")
            seg_id = self.get_snippet_index()
            return (seg_id-1)*-180 #A video segment is almost exactly 3 minutes

        if prev:
            return prev.get_offset()

    def get_file_timestamp(self):
        filename = self.path.stem
        title_stamp = re.search(r"\d+", filename).group()
        if len(title_stamp) != 14:
            #something went wrong
            raise Exception(f"filename contains wrong timestamp: {filename}")
            return None
        timestamp = datetime.strptime(title_stamp, '%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return timestamp.timestamp()

    def get_snippet_index(self):
        filename = self.path.stem
        try:
            return int(filename[-3:])
        except:
            raise ValueError(f"Unexpected filename: {self.path.name}")
    
    def get_recording_index(self):
        filename = self.path.stem
        try:
            return int(filename[-10:-6])
        except:
            raise ValueError(f"Unexpected filename: {self.path.name}")

    def get_duration(self):
        if not hasattr(self, "duration") or not self.duration:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", str(self.path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            return float(result.stdout)
        else:
            return self.duration

    def to_dict(self):
        return {
            "path": str(self.path),
            "offset": self.offset,
            "start_timestamp": self.start_timestamp,
            "duration": self.duration
        }

    def get_track_points(self):
        #gets the GPS track points coinciding with the given video
        start = self.start_timestamp - self.offset
        end = start 

        pass

    def get_index(self):
        try:
            if not self.parent:
                return 0
            return self.parent.videos.index(self)
        except Exception:
            return False

    def get_prev(self):
        try:
            i = self.get_index() - 1
            if i < 0:
                return False
            return self.parent.videos[i]
        except Exception:
            return False

    def get_next(self):
        try:
            i = self.get_index() + 1
            if i >= len(self.parent.videos):
                return False
            return self.parent.videos[i]
        except Exception:
            return False