if __package__:
    from .Bookmarks import Bookmarks, Bookmark
    from .Serializable import Serializable, SerializableCollection
else:
    from Bookmarks import Bookmarks, Bookmark
    from Serializable import Serializable, SerializableCollection
from pathlib import Path
import av
import overpass
from turf.bbox import bbox
from turf.destination import destination
from turf.helpers import point

class Clip(Serializable):
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"
    def __init__(
            self, 
            start:Bookmark, 
            end:Bookmark, 
            workdir:Path=None,
            map_data_path:Path=None, 
            videoclip=None,
            geometry=None, 
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
        self.map_data_path = map_data_path
        self.videoclip = videoclip or ""
        self.parent = parent
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
                raise Exception("clip invalid, not same dir {self}")
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
        except Exception as e: print("clip invalid", e)

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

    def geometry_geojson(self):
        #TODO: probably needs more work to work
        coordinates = []
        for point in self.geometry:
            coordinates.append([point["lon"], point["lat"]])
        return {
            "type": "LineString",
            "coordinates": coordinates
        }

    def get_bbox(self, margin=10):
        if not self.geometry:
            raise ValueError("clip geometry is empty")
        if margin < 0:
            raise ValueError("margin must be non-negative")

        west, south, east, north = bbox(self.geometry_geojson())
        if margin == 0:
            return [west, south, east, north]

        longitude_latitude = south if abs(south) >= abs(north) else north
        west = destination(
            point([west, longitude_latitude]), margin, -90, {"units": "meters"}
        )["geometry"]["coordinates"][0]
        east = destination(
            point([east, longitude_latitude]), margin, 90, {"units": "meters"}
        )["geometry"]["coordinates"][0]
        south = destination(
            point([(west + east) / 2, south]), margin, 180, {"units": "meters"}
        )["geometry"]["coordinates"][1]
        north = destination(
            point([(west + east) / 2, north]), margin, 0, {"units": "meters"}
        )["geometry"]["coordinates"][1]

        return [south, west, north, east]