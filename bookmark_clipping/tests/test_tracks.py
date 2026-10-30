import pytest
from pathlib import Path
from .Tracks import Track#, Tracks

GPS_FIXTURE = "./fixtures/Bike_ride.gpx"

class TestVideo:

    def test_timestamp(self):
        #the video should correclty extract the UNIX start_timestamp from a DJI_YYMMDDHHmmSS_000*_D_00N.mp4 formatted video

    def test_serialize(self):
        #turning a video to a string should return all the relevant metadata

    def test_get_duration(self):
        #should get the duration in seconds
    
class TestTrack:

    def test_read_file(self):
        #reading an xml formatted file should return a valid DataFrame object
        pass

    def test_serializa(self):
        #tutning a Track to a string should return a valid XML string with correct track content

    def test_get_point_at_time(self):
        #the method get_point_at_time should return a track point corresponding to the given unix time stamp 

    def test_get_timestamp(self):
        #the method get_timestamp should return the unix timestamp for a track point at a given index