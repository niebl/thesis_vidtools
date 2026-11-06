import pytest
import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..Tracks import Track, Video

FIXTURES = Path(__file__).parent / "fixtures"
GPS_FIXTURE = FIXTURES / "Bike_ride.gpx"
VIDEO_FIXTURE = FIXTURES / "DJI_20240901110552_0007_D_001.mp4"
VIDEO_FIXTURES = [
    FIXTURES / "DJI_20240901110505_0007_D_003.mp4",
    FIXTURES / "DJI_20240901110505_0007_D_004.mp4",
    VIDEO_FIXTURE,
]
VIDEO_SERIALIZATION_FIXTURE = {
    "path": str(VIDEO_FIXTURE),
    "offset": -12.5,
    "start_timestamp": 1725181552.0,
}


def unix_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

class TestVideo:

    def test_timestamp(self):
        video = Video(VIDEO_FIXTURE, offset=0)
        expected = datetime(
            2024, 9, 1, 11, 5, 52, tzinfo=ZoneInfo("Europe/Berlin")
        ).timestamp()
        assert video.get_timestamp() == expected

    def test_serialize(self):
        video = Video(
            VIDEO_FIXTURE,
            offset=VIDEO_SERIALIZATION_FIXTURE["offset"],
            start_timestamp=VIDEO_SERIALIZATION_FIXTURE["start_timestamp"],
        )
        serialized = video.to_dict()

        assert str(video.path) == VIDEO_SERIALIZATION_FIXTURE["path"]
        assert serialized["path"] == VIDEO_SERIALIZATION_FIXTURE["path"]
        assert serialized["offset"] == VIDEO_SERIALIZATION_FIXTURE["offset"]
        assert serialized["start_timestamp"] == VIDEO_SERIALIZATION_FIXTURE["start_timestamp"]
        assert serialized["duration"] == pytest.approx(6.006, abs=0.05)
        assert str(video) == video.to_string()

    def test_get_duration(self):
        video = Video(VIDEO_FIXTURE, offset=0)

        assert video.get_duration() == pytest.approx(6.006, abs=0.05)

    def test_get_prev_next(self):
        track = Track(Track.from_gpx_file(GPS_FIXTURE))
        for path in VIDEO_FIXTURES:
            track.add_video(Video(path, offset=0, parent_track=track))

        assert track.videos[0].get_prev() is False
        assert track.videos[0].get_next() is track.videos[1]
        assert track.videos[1].get_prev() is track.videos[0]
        assert track.videos[1].get_next() is track.videos[2]
        assert track.videos[2].get_prev() is track.videos[1]
        assert track.videos[2].get_next() is False
    
class TestTrack:

    def test_from_gpx(self):
        track = Track.from_gpx_file(GPS_FIXTURE)

        assert isinstance(track, Track)
        assert not not track.track
        assert "lat" and "lon" and "ele" and "time" in track[0]
        assert track[0]["lat"] == pytest.approx(47.414008)
        assert track[0]["lon"] == pytest.approx(8.550946)

    def test_serialize(self):
        track = Track.from_gpx_file(GPS_FIXTURE)
        track.videos = []
        serialized = str(track)
        data = json.loads(serialized)
        first_point = data["track"][0]

        assert data["videos"] == []
        assert first_point is not None
        print(type(first_point))
        assert float(first_point.get("lat")) == pytest.approx(47.414008)
        assert float(first_point.get("lon")) == pytest.approx(8.550946)

        track.videos = [Video(VIDEO_FIXTURES[0], offset=0, parent_track=track)]
        serialized_with_video = json.loads(str(track))
        assert len(serialized_with_video["videos"]) == 1
        serialized_video = serialized_with_video["videos"][0]
        assert serialized_video["path"] == str(VIDEO_FIXTURES[0])
        assert serialized_video["offset"] == 0
        assert serialized_video["start_timestamp"] is None
        assert serialized_video["duration"] == pytest.approx(10.01, abs=0.05)

    def test_get_point_by_timestamp(self):
        track = Track(Track.from_gpx_file(GPS_FIXTURE))
        timestamp = unix_timestamp("2024-09-01T09:03:40Z")
        point = track.get_point_by_timestamp(timestamp)

        assert point["lat"] == pytest.approx(47.414017)
        assert point["lon"] == pytest.approx(8.550942)
        assert point["time"] == timestamp

    def test_get_point_timestamp(self):
        track_data = Track.from_gpx_file(GPS_FIXTURE)
        track = Track(track_data)
        expected = unix_timestamp("2024-09-01T09:03:40Z")

        assert track.get_point_timestamp(4) == expected

    def test_find_items_video(self):
        track = Track(Track.from_gpx_file(GPS_FIXTURE))
        videos = [Video(path, offset=0, parent_track=track) for path in VIDEO_FIXTURES]
        track.videos = videos

        assert track.find_item(lambda video: video.path == VIDEO_FIXTURES[1], "videos") is videos[1]
        assert track.find_item(lambda video: video.path.name.endswith("missing.mp4"), "videos") is None

    def test_get_video_by_title(self):
        track = Track.from_gpx_file(GPS_FIXTURE)
        videos = [Video(path, offset=0, parent_track=track) for path in VIDEO_FIXTURES]
        track.videos = videos

        assert track.get_video_by_title(VIDEO_FIXTURES[1].stem) is videos[1]
        assert track.get_video_by_title("not_a_video.mp4") is None

    def test_update_start_times(self):
        track = Track.from_gpx_file(GPS_FIXTURE)
        videos = [Video(path, offset=None, parent_track=track) for path in VIDEO_FIXTURES]
        videos[0].offset = 0
        videos[2].offset = -5
        track.videos = videos

        track.update_start_times()
        track.update_offsets()

        track_start = track.get_point_by_timestamp(videos[0].start_timestamp - videos[0].offset)

        assert videos[0].start_timestamp == track_start["time"]
        assert videos[1].start_timestamp == pytest.approx(
            videos[0].start_timestamp + videos[0].duration
        )
        assert videos[2].start_timestamp - videos[2].offset == pytest.approx(
            videos[2].start_timestamp - -5
        ) #might need a better test case here
        assert videos[2].start_timestamp == pytest.approx(track_start["time"] - 5)