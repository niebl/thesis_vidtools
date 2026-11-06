if __package__:
    from .Bookmarks import Bookmarks, Bookmark
    from .Serializable import Serializable, SerializableCollection
    from .Tracks import Track, Video
else:
    from Bookmarks import Bookmarks, Bookmark
    from Serializable import Serializable, SerializableCollection
    from Tracks import Track, Video
import av
from pathlib import Path
import subprocess
import json
import traceback
import re

class Clips(SerializableCollection):
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"
    items_attribute = "clips"

    def __init__(self, bookmarks=None, workdir=DEFAULT_WORKDIR, clips=None, tracks=None):
        super().__init__(workdir=workdir, collection=clips, items_attribute=self.items_attribute)
        self.clips = self.read_clips() if clips is None else clips
        print(self.clips)
        self.tracks = tracks
        self.bookmarks = bookmarks

    @classmethod
    def from_file(cls, filepath=None):
        path = filepath or cls.DEFAULT_WORKDIR
        with open(path, "r") as file:
            data = json.load(file)
        return cls.from_dict(data)

    @classmethod
    def _from_dict(cls, in_dict):
        try:
            bookmarks = Bookmarks.from_dict(in_dict["bookmarks"])
        except AttributeError as e:
            bookmarks = Bookmarks(in_dict["bookmarks"])

        try:
            clips = list(map(lambda cl: 
                Clip(
                    start=Bookmark.from_dict(cl["start"]), 
                    end=Bookmark.from_dict(cl["end"]), 
                    workdir=in_dict["workdir"], 
                    videoclip=cl["videoclip"], 
                    observations=cl["observations"],
                    discard=cl["discard"],
                    uncertain=cl["uncertain"]),
                in_dict["clips"])
            )
        except Exception as e:
            print(e)
            clips = []
        tracks = list(map(lambda tr: Track.from_dict(tr), in_dict.get("tracks", [])))
        return cls(bookmarks, in_dict["workdir"], clips, tracks)

    def to_dict(self):
        return {
            "workdir": str(self.workdir),
            "clips": [clip.to_dict() for clip in self.clips] if self.clips else [],
            "bookmarks": self.bookmarks.to_dict() if type(self.bookmarks) == Bookmarks else self.bookmarks,
            "tracks": [track.to_dict() for track in self.tracks] if self.tracks else []
        }

    def read_clips(self):
        clips = []

        if len(self.bookmarks.bookmarks) % 2 != 0:
            print("odd number of bookmarks")
            return clips
    
        for i in range(0, len(self.bookmarks.bookmarks), 2):
            start = self.bookmarks.bookmarks[i]
            end = self.bookmarks.bookmarks[i+1]
            clips.append(Clip(start, end, self.workdir, parent=self))

        for clip in clips:
            if not clip.validate():
                print(f"Invalid clip: {clip.start.name} to {clip.end.name}")
                return []
        return clips

    def read_tracks(self, track_dir:Path = None, global_offset = 0):
        if track_dir is None:
            #TODO: raise exception
            return
        if self.tracks is None or self.tracks == []:
            self.tracks = []
        else:
            #TODO: raise warning?
            print("tracks are already read. Not checking for duplicates")
        #read track dir and parse each track.gpx file
        ls = Path(track_dir).glob("**/*.gpx")
        for track in ls:
            self.tracks.append(Track.from_gpx_file(track, global_offset=global_offset))

    def read_videos(self, video_dir:Path = None):
        if not self.tracks:
            return False #todo: raise exceptions
        if not video_dir:
            return False #TODO: see above

        videos = []
        videos_ls = [
            video_path
            for video_path in Path(video_dir).glob("**/*.mp4")
            if re.fullmatch(r"DJI_\d{14}_\d{4}_D_\d{3}", video_path.stem)
        ]

        #2 step process. 
        #   1. assigns all videos to tracks based on title timestamps
        for video_path in videos_ls:
            video = Video(video_path)
            videos.append(video)
            if self.tracks:
                parent_track = self.get_track_for_timestamp(video.get_file_timestamp())
                if parent_track:
                    print(parent_track[0]["time"], parent_track[-1]["time"], video)
                    video.parent = parent_track
                    parent_track.videos.append(video)
            else:
                return False #TODO: see above

        #   2. infers unix timestamp of videos... 
        for track in self.tracks:
            track.videos[0].start_timestamp = track.videos[0].get_timestamp() #?
            for video in track.videos[1:]:
                #assumption is that index cutoffs are only at the beginning of recording days
                video.start_timestamp = video.get_timestamp()
                #assumption is also that offset is constant between gps and camera across recordings
                video.offset = video.get_offset()
        
        #...and rearrange
        for video in videos:
            if not video.start_timestamp:
                #this one fell outside the tracks
                continue
            if self.get_track_for_timestamp(video.start_timestamp) != video.parent:
                video.parent.videos.remove(video)
                video.parent = self.get_track_for_timestamp(video.get_timestamp())
                if not video.parent:
                    continue
                video.parent.videos.append(video)
                video.parent.videos.sort(key=lambda v: v.filepath.name)
                
    def get_track_for_timestamp(self, ts):
        if not self.tracks:
            return None
        results = list(filter(
            lambda t: t.contains_time(ts), 
            self.tracks
        ))
        if len(results) == 1:
            return results[0]
        elif len(results) > 1:
            raise ValueError("more than 1 track match timestamp. Do you have duplicates?")
        return None

    def get_track_for_clip(self, clip):
        if not self.tracks:
            return None
        #it might be possible otherwise, but we assume that there is only one track per clip
        if not clip.validate:
            raise Exception("clip invalid", clip)
        start = Path(clip.start.path)
        end = Path(clip.end.path)

        # search all tracks for a video name
        for track in self.tracks:
            start_video = track.get_video_by_title(start.stem)
            end_video = track.get_video_by_title(end.stem)
            if start_video and end_video:
                start_offset = start_video.get_offset() or 0
                end_offset = end_video.get_offset() or 0
                if (track.contains_time(start_video.get_timestamp() - start_offset) or 
                    track.contains_time(end_video.get_timestamp() - end_offset) or
                    track.contains_time(start_video.get_timestamp() + start_video.get_duration() - start_offset) or
                    track.contains_time(end_video.get_timestamp() + end_video.get_duration() - end_offset)
                    ):
                    return track 
        return None

    def get_track_subsegment_for_clip(self, clip):
        track = self.get_track_for_clip(clip)
        if not track:
            raise Exception(f"getting subsegment failed: No track for clip {clip}")
            return None
        
        start_video = track.get_video_by_title(
            Path(clip.start.path).stem
        )
        end_video = track.get_video_by_title(
            Path(clip.end.path).stem
        )
        if not start_video or not end_video:
            raise Exception(f"getting subsegment failed: start or end video failed")
            return None

        start_timestamp = start_video.get_timestamp() - start_video.get_offset() + clip.start.timestamp
        end_timestamp = end_video.get_timestamp() - end_video.get_offset() + clip.end.timestamp
        if not start_timestamp or not end_timestamp:
            raise Exception(f"getting subsegment failed: start or end timestamp failed")
            return None

        start_point = track.get_point_by_timestamp(start_timestamp)
        end_point = track.get_point_by_timestamp(end_timestamp)
        if not start_point or not end_point:
            raise Exception(f"getting subsegment failed: start or end point failed {start_point}, {end_point}, using {start_timestamp} and {end_timestamp} as arguments")
            return None
        start_index = track.track.index(start_point)
        end_index = track.track.index(end_point)
        return track.track[start_index:end_index+1]

    def render_all_clips(self):
        for clip in self.clips:
            clip.render_clip()
    
    def save_clip_data(self, location=None):
        save_at = location or workdir / "clips.json"
        with open(save_at, "w") as f:
            f.write(str(self))
    
    def has_parity(self):
        # checks that every clip listed is contained in the bookmarks
        bookmark_set = set((b.path, b.pos) for b in self.bookmarks.bookmarks)
        for clip in self.clips:
            if (clip.start.path, clip.start.pos) not in bookmark_set:
                return False
            if (clip.end.path, clip.end.pos) not in bookmark_set:
                return False
        if len(self.clips) * 2 != len(self.bookmarks.bookmarks):
            return False
        return True

class Clip(Serializable):
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"
    def __init__(
            self, 
            start:Bookmark, 
            end:Bookmark, 
            workdir:Path=None, 
            videoclip=None, 
            observations:dict=False, 
            discard=False, 
            uncertain=False,
            parent=None 
        ):
        super().__init__(workdir=workdir, parent=parent)
        self.start = start
        self.end = end
        self.files = [start.path]
        #add second file if clip spans 2
        self.files.append(end.path) if end.path != start.path else None
        self.videoclip = videoclip or ""
        self.parent = parent
        self.geometry = None
        self.observations = observations or {}
        self.discard = discard
        self.uncertain = uncertain

    @classmethod
    def _from_dict(cls, in_dict):
        start = Bookmark.from_dict(in_dict["start"])
        end = Bookmark.from_dict(in_dict["end"])
        return cls(
            start=start,
            end=end,
            workdir=in_dict.get("workdir", None),
            videoclip=in_dict["videoclip"],
            observations=in_dict["observations"],
            discard=in_dict["discard"],
            uncertain=in_dict["uncertain"],
        )

    def to_dict(self):
        out = {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "videoclip": str(self.videoclip) or "",
            "observations": self.observations,
            "discard": self.discard,
            "uncertain": self.uncertain,
        }
        return out

    def has_bookmarks(self):
        return (type(self.start) == Bookmark and type(self.end) == Bookmark)

    def render_clip(self, output_path=None):
        source = list(map(lambda c: Path(c), self.files))
        start = int(self.start.timestamp * 1000)/1000
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
            end = self.end.timestamp

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

            files= sorted(Path(self.start.path).parent.glob("*"))
            start_index = files.index(Path(self.start.path))
            end_index = files.index(Path(self.end.path))
            direct_follow = abs(end_index - start_index) <= 1

            duration_ok = self.get_duration() < 120

            return same_dir and direct_follow and duration_ok and self.has_bookmarks()
        except:
            return False

    def get_duration(self):
        if self.start.path == self.end.path:
            return self.end.timestamp - self.start.timestamp
        else:
            # get video duration of start file
            start_file = av.open(self.start.path)
            start_duration = start_file.duration / av.time_base
            start_file.close() 
            trailing_duration = start_duration - self.start.timestamp
            leading_duration = self.end.timestamp
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

def main():
    #bookmarks = Bookmarks(Path.home() / "Projects/Bike Footage/bookmarker.json")
    #clips = Clips(bookmarks, Path.home() / "Projects/Bike Footage/clips_zurich")
    #clips.render_all_clips()
    
    clips = Clips.from_file(Path.home() / "Projects/Bike Footage/clips_zurich/clips.json")
    clips.workdir = Path.home() / "Projects/Bike Footage/clips_zurich"
    clips.read_tracks(
        track_dir=Path.home() / "Projects/Bike Footage/clips_zurich/gps_traces",
        global_offset=-133
    )
    print("read tracks")
    clips.read_videos(
        video_dir=Path.home() / "Projects/Bike Footage"
    )
    print("read videos")

    #clips.bookmarks = []

    #for each clip, save track geojson for the clip
    print("getting geometries")
    for clip in clips.clips:
        try:
            if not clip.validate():
                raise Exception("clip not valid:", str(clip))
            if not clip.has_bookmarks():
                raise Exception("clip has no bookmarks:", str(clip))
            clip.geometry = clips.get_track_subsegment_for_clip(clip)
            if clip.geometry:
                geojson = clip.geometry_geojson()
                start = int(clip.start.timestamp * 1000)/1000
                output_path = Path(clips.workdir) / "clip_tracks" / f"{Path(clip.start.path).stem}_at_{start:.3f}s.geojson"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                print(output_path)
                with open(output_path, "w") as f:
                    json.dump(geojson, f)
        except Exception as e:
            traceback.print_exc()
            print(e)
            #break
    
    clips.tracks = []

    # TODO: deserialization with the correct references and preventing endless loops
    #clips.save_clip_data(Path.home() / "Projects/Bike Footage/clips_zurich/clips.json")

if __name__ == "__main__":
    main()