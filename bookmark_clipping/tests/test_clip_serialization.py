import pytest

import json
from ..Bookmarks import Bookmark, Bookmarks
from ..Clips import Clip, Clips
from .test_bookmark_serialization import TestBookmark

CLIPS_FIXTURE = """{\"workdir\": \"/home/user/Projects/Videos\", \"clips\":[{\"start\": {\"pos\": 40.5405, \"name\": \"DJI_117_0007_D_003.mp4 @ 00:00:40.540\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/DJI_117_0007_D_003.mp4\"}, \"end\": {\"pos\": 48.782067, \"name\": \"DJI_117_0007_D_003.mp4 @ 00:00:48.782\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/DJI_117_0007_D_003.mp4\"}, \"videoclip\": \"/home/user/Projects/Videos/DJI_20240901110117_0007_D_003_at_40.540s.mp4\", \"observations\": {}, \"discard\": false, \"uncertain\": false},
{\"start\": {\"pos\": 60.927533, \"name\": \"DJI_117_0007_D_003.mp4 @ 00:01:00.927\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/DJI_117_0007_D_003.mp4\"}, \"end\": {\"pos\": 11.878533, \"name\": \"117_0007_D_003.mp4 @ 00:00:11.878\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/117_0007_D_003.mp4\"}, \"videoclip\": \"/home/user/Projects/Videos/DJI_20240901110117_0007_D_003_at_60.927s.mp4\", \"observations\": {}, \"discard\": false, \"uncertain\": false},
{\"start\": {\"pos\": 32.298933, \"name\": \"848_0008_D_001.mp4 @ 00:00:32.298\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_001.mp4\"}, \"end\": {\"pos\": 47.714333, \"name\": \"848_0008_D_001.mp4 @ 00:00:47.714\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_001.mp4\"}, \"videoclip\": \"/home/user/Projects/Videos/DJI_20240901110848_0008_D_002_at_32.298s.mp4\", \"observations\": {}, \"discard\": false, \"uncertain\": false}], "bookmarks":[{\"pos\":40.5405,\"name\": \"DJI_117_0007_D_003.mp4 @ 00:00:40.540\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/117_0007_D_003.mp4\"},
{\"pos\":48.782067,\"name\": \"117_0007_D_003.mp4 @ 00:00:48.782\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/117_0007_D_003.mp4\"},
{\"pos\":60.927533,\"name\": \"117_0007_D_003.mp4 @ 00:01:00.927\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/117_0007_D_003.mp4\"},
{\"pos\":11.878533,\"name\": \"848_0008_D_001.mp4 @ 00:00:11.878\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_001.mp4\"},
{\"pos\":32.298933,\"name\": \"848_0008_D_002.mp4 @ 00:00:32.298\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_002.mp4\"}]}"""
CLIP_FIXTURE = "{\"start\": {\"pos\": 65.2692, \"name\": \"DJI_806_0009_D_002.mp4 @ 00:01:05.269\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/DJI_806_0009_D_002.mp4\"}, \"end\": {\"pos\": 87.520767, \"name\": \"DJI_806_0009_D_002.mp4 @ 00:01:27.520\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/DJI_806_0009_D_002.mp4\"}, \"videoclip\": \"/home/user/Projects/Videos/DJI_806_0009_D_002_at_65.269s.mp4\", \"observations\": {}, \"discard\": false, \"uncertain\": false}"

WORKDIR = "/home/user/Projects/Videos"


class TestClip:
    ### HELPERS:
    @staticmethod
    def clip_conditions(clip, clip_fixture=CLIP_FIXTURE):
        data = json.loads(clip_fixture)
        return (
            type(clip) == Clip
            and TestBookmark.bookmark_conditions(clip.start_bookmark, json.dumps(data["start"]))
            and TestBookmark.bookmark_conditions(clip.end_bookmark, json.dumps(data["end"]))
            and clip.videoclip == data["videoclip"]
            and clip.observations == data["observations"]
            and clip.discard == data["discard"]
            and clip.uncertain == data["uncertain"]
        )

    def test_clip_from_dict(self):
        in_dict = json.loads(CLIP_FIXTURE)
        clip = Clip.from_dict(in_dict)
        assert self.clip_conditions(clip)

    def test_clip_from_string(self):
        clip = Clip.from_string(CLIP_FIXTURE)
        assert self.clip_conditions(clip)

    def test_clip_to_string(self):
        clip = Clip.from_string(CLIP_FIXTURE)
        assert json.loads(str(clip)) == json.loads(CLIP_FIXTURE)


class TestClips:
    ### HELPERS:
    @staticmethod
    def clips_conditions(clips):
        data = json.loads(CLIPS_FIXTURE)
        return (
            type(clips) == Clips
            and clips.workdir == data["workdir"]
            and len(clips.clips) == len(data["clips"])
            and type(clips.clips[0]) == Clip
            and TestBookmark.bookmark_conditions(clips.clips[0].start_bookmark, json.dumps(data['clips'][0]["start"]))
            and TestBookmark.bookmark_conditions(clips.clips[0].end_bookmark,   json.dumps(data['clips'][0]["end"]))
            and TestClip.clip_conditions(clips.clips[0], json.dumps(data['clips'][0]))
            and len(clips.bookmarks.bookmarks) == len(data["bookmarks"])
            and type(clips.bookmarks.bookmarks[0]) == Bookmark
        )

    def test_clips_from_dict(self):
        in_dict = json.loads(CLIPS_FIXTURE)
        clips = Clips.from_dict(in_dict)
        assert self.clips_conditions(clips)

    def test_clips_from_string(self):
        clips = Clips.from_string(CLIPS_FIXTURE)
        assert self.clips_conditions(clips)

    def test_clips_to_string(self):
        clips = Clips.from_string(CLIPS_FIXTURE)
        assert json.loads(str(clips)) == json.loads(CLIPS_FIXTURE)
