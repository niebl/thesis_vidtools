from pathlib import Path
if __package__:
    from .Serializable import Serializable, SerializableCollection, OID
else:
    from Serializable import Serializable, SerializableCollection, OID
import subprocess
import re
import json
from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo

class Video(Serializable):
    def __init__(self, path: Path, offset=None, start_timestamp = None, parent = None, oid:str=None, prev_vid=None, next_vid=None, duration=None, peers=None):
        super().__init__(parent=parent, oid=oid)
        self.path = path if type(path) is Path else Path(path)
        self.offset = offset
        self.duration = duration or self.get_duration()
        self.start_timestamp = start_timestamp
        self.peers = peers or {
            "prev_vid": prev_vid, 
            "next_vid": next_vid
        }
        # this is a problem before video is added to track. better call such methods from parent after creation:
        #if not self.start_timestamp and self.get_index() == 0:
        #    self.start_timestamp = self.get_timestamp() #infer from title or calculate from other videos

    def to_dict(self):
        data = self._to_dict(exclude_keys=["parent", "peers", "verbose"])
        data["path"] = str(data["path"])
        data["peers"] = {
            "prev_vid": None,
            "next_vid": None
        }
        if self.peers.get("prev_vid"):
            data["peers"]["prev_vid"] = str(self.peers["prev_vid"].oid)
        if self.peers.get("next_vid"):
            data["peers"]["next_vid"] = str(self.peers["next_vid"].oid)
        return data

    @classmethod
    def from_dict(cls, data):
        if data.get("peers",{}).get("prev_vid"):
            data["peers"]["prev_vid"] = OID(data["peers"]["prev_vid"])
        if data.get("peers",{}).get("next_vid"): 
            data["peers"]["next_vid"] = OID(data["peers"]["next_vid"])
        return cls._from_dict(data)

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

        file_fts = self.get_file_timestamp()
        seg_id = self.get_snippet_index()

        if prev:
            prev_fts = prev.get_file_timestamp()
            prev_seg_id = prev.get_snippet_index()
            if prev_fts == file_fts and seg_id == prev_seg_id+1: 
                return prev.get_offset()

        return (seg_id-1)*-180 #A video segment is almost exactly 3 minutes


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
        else: path = self.path
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

    def get_index(self):
        try:
            if not self.parent:
                return 0
            return self.parent.videos.index(self)
        except Exception:
            return False

    def get_prev(self):
        try:
            if self.peers.get("prev_vid"): return self.peers.get("prev_vid")
            i = self.get_index() - 1
            if i < 0:
                return None
            return self.parent.videos[i]
        except Exception:
            return None

    # technically works, but fallback might be broken
    def get_next(self):
        try:
            if self.peers.get("next_vid"): return self.peers.get("next_vid")
            i = self.get_index() + 1
            if i >= len(self.parent.videos):
                return None
            return self.parent.videos[i]
        except Exception:
            return None