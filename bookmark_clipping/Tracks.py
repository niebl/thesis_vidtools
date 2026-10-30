import pandas
from pathlib import Path
from .Serializable import Serializable, SerializableCollection
import subprocess
from datetime import datetime
from dateutil import parser
import re
import gpxo
import json
from zoneinfo import ZoneInfo

class Track(SerializableCollection):
    items_attribute = "track"

    def __init__(self, track=[], videos = []):
        self.track = track #Dataframe as read from GPX
        self.videos = videos

    @classmethod
    def from_gpx_file(cls, file_path):
        df = gpxo.Track(file_path)
        data = df.data.copy()
        timestamps = pandas.to_datetime(data["time"], utc=True)
        print("THE gpx TIMESTAMPS")
        print(timestamps[0])
        print(timestamps[0].timestamp())
        data["time"] = timestamps.map(
            lambda value: value.timestamp() if pandas.notna(value) else None
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
        return track

    @classmethod
    def from_file(cls, filepath=None):
        path = filepath or cls.DEFAULT_WORKDIR
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
        if self.videos[0].offset is None:
            raise Exception("First video has no offset")
        for video in self.videos[1:]:
            if video.get_file_timestamp() == video.get_prev().get_file_timestamp():
                video.offset = video.get_prev().offset + video.get_duration()
            else:
                duration = video.get_timestamp() - video.get_prev().get_timestamp()
                video.offset = video.get_prev().offset + duration

    def get_video(self, lambda_f):
        for video in self.videos:
            if lambda_f(video):
                return video
        return None

    def get_video_by_title(self, title):
        return self.get_video(lambda v: v.filepath.stem == title) or False

    def get_point_timestamp(self, index):
        return self.track[index]["time"]

    def get_point_by_timestamp(self, ts, ts_format="unix"):
        def ts_filter(p, ts):
            diff = p["time"] - ts
            if diff > 5 or diff < 0:
                return 99999999999999999 #TODO: use something more elegant
            else: 
                return diff
            
        if ts_format is "unix":
            return min(self.track,
                key = lambda p: ts_filter(p, ts)
                )

    def get_points_by_timestamp_range(self, start_ts, end_ts, ts_format="unix"):
        points = []
        for n in range(start_ts, end_ts):
            points.append(self.get_point_by_timestamp)

class Video(Serializable):
    def __init__(self, filepath: Path, offset=None, start_timestamp = None, parent_track = None ):
        self.filepath = filepath
        self.offset = offset # track-strart - video start
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
        offset_from_first = 0
        prev = self.get_prev()
        if prev:
            if prev.get_file_timestamp() == self.get_file_timestamp():
                return prev.get_timestamp() + prev.get_duration()
        return self.get_file_timestamp()

    def get_file_timestamp(self):
        filename = self.filepath.stem
        title_stamp = re.search(r"\d+", filename).group()
        if len(title_stamp) != 14:
            #something went wrong
            return None
        timestamp = datetime.strptime(title_stamp, '%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo("Europe/Berlin"))
        print(str(timestamp))
        return timestamp.timestamp()
    
    def get_duration(self):
        if not hasattr(self, "duration") or not self.duration:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", str(self.filepath)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            return float(result.stdout)
        else:
            return self.duration

    def to_dict(self):
        return {
            "path": str(self.filepath),
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
        if not self.parent:
            return 0
        return self.parent.videos.index(self)

    def get_prev(self):
        i = self.get_index() - 1
        if i < 0:
            print("no prev found")
            return False
        print("prev found")
        print(self.parent.videos[i])
        return self.parent.videos[i]

    def get_next(self):
        i = self.get_index() + 1
        if i >= len(self.parent.videos):
            return False
        return self.parent.videos[i]