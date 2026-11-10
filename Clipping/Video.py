from pathlib import Path
if __package__:
    from .Serializable import Serializable, SerializableCollection
else:
    from Serializable import Serializable, SerializableCollection
import subprocess
import re
import json
from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo

class Video(Serializable):
    def __init__(self, path: Path, offset=None, start_timestamp = None, parent = None, oid:str=None, prev_vid=None, next_vid=None ):
        super().__init__(parent=parent, oid=oid)
        self.path = path if type(path) is Path else Path(path)
        self.offset = offset
        self.duration = self.get_duration()
        self.start_timestamp = start_timestamp
        self.prev_vid = prev_vid
        self.next_vid = next_vid
        # this is a problem before video is added to track. better call such methods from parent after creation:
        #if not self.start_timestamp and self.get_index() == 0:
        #    self.start_timestamp = self.get_timestamp() #infer from title or calculate from other videos

    def to_dict(self):
        data = self._to_dict(exclude_keys=["parent", "prev_vid", "next_vid", "verbose"])
        data["path"] = str(data["path"])
        if hasattr(self, "prev_vid") and self.prev_vid:
            data["prev_vid"] = str(self.prev_vid)
        if hasattr(self, "next_vid") and self.next_vid:
            data["next_vid"] = str(self.next_vid)
        return data
    
    def to_string(self):
        data = self.to_dict()
        return json.dumps(data)

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
        if type(self.path) is not Path:
            path = Path(self.path) #TODO: decide. is it string or 
        filename = path.stem
        title_stamp = re.search(r"\d+", filename).group()
        if len(title_stamp) != 14:
            #something went wrong
            raise Exception(f"filename contains wrong timestamp: {filename}")
            return None
        timestamp = datetime.strptime(title_stamp, '%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return timestamp.timestamp()

    def get_snippet_index(self):
        if type(self.path) is not Path:
            path = Path(self.path) #TODO: decide. is it string or PAth?
        filename = path.stem
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
            if hasattr(self, "prev_vid") and self.prev_vid: return self.prev_vid
            i = self.get_index() - 1
            if i < 0:
                return False
            return self.parent.videos[i]
        except Exception:
            return False

    def get_next(self):
        try:
            if hasattr(self, "next_vid") and self.next_vid: return self.next_vid
            i = self.get_index() + 1
            if i >= len(self.parent.videos):
                return False
            return self.parent.videos[i]
        except Exception:
            return False