if __package__:
    from .Bookmarks import Bookmarks, Bookmark
    from .Serializable import Serializable, SerializableCollection
else:
    from Bookmarks import Bookmarks, Bookmark
    from Serializable import Serializable, SerializableCollection
from pathlib import Path
import av
from datetime import datetime as dt
from datetime import date

class Clip(Serializable):
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
            oid:str=None
        ):
        super().__init__(workdir=workdir, parent=parent, oid=oid)
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

    def geometry_geojson(self, human_readable=False):
        #TODO: probably needs more work to work
        coordinates = []
        if self.geometry is None: 
            self.geometry = []
        for point in self.geometry:
            coordinates.append([point["lon"], point["lat"]])
        start = int(self.start.pos * 1000)/1000
        properties = {
            "name": f"{Path(self.start.path).stem}_at_{start:.3f}s",
            "duration": self.get_duration(),
            "bookmarks": {
                "start": self.start.to_dict(), "end":self.end.to_dict()
                }
        }
        if self.parent:
            track = self.parent.get_track_for_clip(self)
            if track is not None:
                video_start = track.get_video_by_title(Path(self.start.path).stem)
                video_end = track.get_video_by_title(Path(self.end.path).stem)

                properties["start"] = self.video_infos(video_start, human_readable)
                properties["end"] = self.video_infos(video_end, human_readable)
                properties["day"] = str(self.get_date())
        return {
            "type": "LineString",
            "coordinates": coordinates,
            "properties": properties
        }