if __package__:
    from .Bookmarks import Bookmarks, Bookmark
    from .Serializable import Serializable, SerializableCollection
    from .Tracks import Track, Video
    from .Clip import Clip
else:
    from Bookmarks import Bookmarks, Bookmark
    from Serializable import Serializable, SerializableCollection
    from Tracks import Track, Video
    from Clip import Clip
from pathlib import Path
import subprocess
import json
import traceback
import re

class Clips(SerializableCollection):
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"
    items_attribute = "clips"

    # workdir, clips, tracks, bookmark
    def __init__(self, bookmarks=None, workdir=DEFAULT_WORKDIR, clips=None, tracks=None, oid:str=None, verbose:bool=False):
        super().__init__(workdir=workdir, collection=clips, items_attribute=self.items_attribute, oid=oid)
        self.clips = self.read_clips() if clips is None else clips
        self.tracks = tracks
        self.bookmarks = bookmarks
        self.verbose = verbose

    @classmethod
    def from_file(cls, filepath=None, verbose:bool=False):
        path = filepath or cls.DEFAULT_WORKDIR
        with open(path, "r") as file:
            data = json.load(file)
        return cls.from_dict(data, verbose=verbose)

    @classmethod
    def from_dict(cls, data, verbose:bool=False):
        data["bookmarks"] = Bookmarks.from_dict(data["bookmarks"])
        data["clips"] = list(map(lambda c: Clip.from_dict(c), data.get("clips", [])))
        data["tracks"] = list(map(lambda t: Track.from_dict(t), data.get("tracks", [])))
        data["verbose"] = verbose
        return cls._from_dict(data)

    def to_dict(self):
        data = self._to_dict(exclude_keys=[
            "verbose"
        ])
        return data

    def read_clips(self):
        clips = []

        if len(self.bookmarks.bookmarks) % 2 != 0:
            raise Exception("odd number of bookmarks")
            return clips
    
        for i in range(0, len(self.bookmarks.bookmarks), 2):
            start = self.bookmarks.bookmarks[i]
            end = self.bookmarks.bookmarks[i+1]
            clips.append(Clip(start, end, self.workdir, parent=self))

        for clip in clips:
            if not clip.validate():
                raise Exception(f"Invalid clip: {clip.start.name} to {clip.end.name}")
                return []
        return clips

    def read_tracks(self, track_dir:Path = None, global_offset = 0):
        if track_dir is None:
            raise Exception(f"No track directory was given")
            return
        if self.tracks is None or self.tracks == []:
            self.tracks = []
        else:
            #TODO: raise warning?
            self.log("tracks are already read. Not checking for duplicates")
        #read track dir and parse each track.gpx file
        ls = [
            track_dir for track_dir in Path(track_dir).glob("**/*.gpx")
        ]
        if len(ls) == 0:
            raise Exception(f"no tracks found in {str(video_dir)}")
        for track in ls:
            self.tracks.append(Track.from_gpx_file(track, global_offset=global_offset, verbose=self.verbose))

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
        if len(videos_ls) == 0:
            raise Exception(f"no videos found in {str(video_dir)}")

        for i, video_path in enumerate(videos_ls):
            video = Video(Path(video_path))
            videos.append(video)
            if i == 0 or video.get_file_timestamp() != videos[i-1].get_file_timestamp():
                #if first in array or first in recording session, always get file timestamp
                video.timestamp = video.get_file_timestamp()
                video.offset = video.get_offset() #get offset, in case it doesnt start at 001
            # assign next and prev, infer timestamps and offset
            else:
                videos[i-1].next_vid = video
                video.prev_vid = videos[i-1]
                video.timestamp = video.get_timestamp()
                video.offset = video.get_offset()

            parent_track = self.get_track_for_timestamp(video.timestamp)
            if parent_track:
                self.log("getting track for video (start, end, video)")
                self.log(parent_track[0]["time"], parent_track[-1]["time"], video)
                video.parent = parent_track
                parent_track.videos.append(video)
                
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
            raise Exception(f"getting track failed: No tracks found")
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

    def get_track_subsegment_for_clip(
                self, 
                clip,
                margin=0, #margin at start and end of clip in seconds
                m_start=None, #margin at start in s
                m_end=None #margin at end in s
            ):
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

        start_timestamp = start_video.get_timestamp() - start_video.get_offset() + clip.start.pos
        end_timestamp = end_video.get_timestamp() - end_video.get_offset() + clip.end.pos
        #apply margin
        start_timestamp -= m_start or margin
        end_timestamp += m_end or margin
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

def main():
    bookmarks = Bookmarks(Path.home() / "Projects/Bike Footage/bookmarker.json")
    clips = Clips(bookmarks, Path.home() / "Projects/Bike Footage/clips_zurich")
    clips.render_all_clips()

if __name__ == "__main__":
    main()