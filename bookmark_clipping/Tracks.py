import pandas
from pathlib import Path
from .Serializable import Serializable, SerializableCollection

class Track(Serializable):
    def __init__(self, track):
        self.track = track, #Dataframe as read from GPX
        self.videos = []

class Video(Serializable):
    def __init__(self, file_location: Path, offset, start_timestamp = None parent_track = None ):
        self.location = file_location
        self.offset = offset
        self.start_timestamp or self.get_start_time() #infer from title or calculate from other videos
        self.duration #calculate

    def get_start_time(self):
        self
    
    def get_duration(self)