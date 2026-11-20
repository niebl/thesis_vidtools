import pandas
from pathlib import Path
if __package__:
    from .Serializable import Serializable, SerializableCollection
    from .Video import Video
    from .Trajectory import Trajectory
else:
    from Serializable import Serializable, SerializableCollection
    from Video import Video
    from Trajectory import Trajectory
from datetime import datetime
import gpxo
import json
import warnings
import traceback
from xml.dom import minidom

class Track(Trajectory):
    items_attribute = "track"

    def __init__(self, track=[], videos = [], oid:str = None, verbose:bool=False):
        super().__init__(oid=oid, verbose=verbose)
        self.track = track #Dataframe as read from GPX
        self.videos = videos

    # track_offset:= at sync point, timestamp_track - timestamp_video in seconds
    @classmethod
    def from_gpx_file(cls, file_path, track_offset=0, verbose=False):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=UserWarning,
                )
            df = gpxo.Track(file_path)

        data = df.data.copy()
        
        metadata = minidom.parse(str(file_path)).getElementsByTagName("metadata")[0]
        metadata_offset = metadata.getElementsByTagName("offset")
        track_offset = float(metadata_offset[0].firstChild.data) if len(metadata_offset) > 0 else track_offset
        
        timestamps = pandas.to_datetime(data["time"], utc=True)
        data["time"] = timestamps.map(
            lambda value: value.timestamp()-track_offset if pandas.notna(value) else None
        )
        

        for column in data.columns:
            values = [
                None if pandas.isna(value) else (
                    value.item() if hasattr(value, "item") else value
                )
                for value in data[column]
            ]
            data[column] = pandas.Series(values, index=data.index, dtype=object)

        track = cls(cls.df_to_trajectory(data), verbose=verbose)
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
        data["videos"] = list(map(lambda v: Video.from_dict(v), data.get("videos", [])))
        return cls._from_dict(data)

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