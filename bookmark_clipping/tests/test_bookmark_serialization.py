import pytest
import json

from ..Bookmarks import Bookmark, Bookmarks

BOOKMARKS_FIXTURE = """[{\"pos\":40.5405,\"name\": \"DJI_117_0007_D_003.mp4 @ 00:00:40.540\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/117_0007_D_003.mp4\"},
{\"pos\":48.782067,\"name\": \"117_0007_D_003.mp4 @ 00:00:48.782\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/117_0007_D_003.mp4\"},
{\"pos\":60.927533,\"name\": \"117_0007_D_003.mp4 @ 00:01:00.927\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/117_0007_D_003.mp4\"},
{\"pos\":11.878533,\"name\": \"848_0008_D_001.mp4 @ 00:00:11.878\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_001.mp4\"},
{\"pos\":32.298933,\"name\": \"848_0008_D_002.mp4 @ 00:00:32.298\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_002.mp4\"},
{\"pos\":47.714333,\"name\": \"848_0008_D_002.mp4 @ 00:00:47.714\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_002.mp4\"}]"""
BOOKMARK_FIXTURE = "{\"pos\":19.019,\"name\": \"848_0008_D_003.mp4 @ 00:00:19.018\", \"version\": 2, \"path\": \"/home/user/Projects/Videos/848_0008_D_003.mp4\"}"

class TestBookmark:
    ### HELPERS:
    @staticmethod
    def bookmark_conditions(bookmark, bookmark_fixture=BOOKMARK_FIXTURE):
        data = json.loads(bookmark_fixture)
        cond1 = type(bookmark) == Bookmark
        cond2 = bookmark.filepath == data["path"] and bookmark.version == data["version"] and bookmark.name == data["name"] and bookmark.timestamp == data["pos"]
        return cond1 and cond2

    ### TESTS:
    def test_bookmark_from_dict(self):
        in_dict = json.loads(BOOKMARK_FIXTURE)
        bookmark = Bookmark.from_dict(in_dict)
        assert self.bookmark_conditions(bookmark)
    
    def test_bookmark_from_string(self):
        bookmark = Bookmark.from_string(BOOKMARK_FIXTURE)
        assert self.bookmark_conditions(bookmark)

    def test_bookmark_to_string(self):
        bookmark = Bookmark.from_string(BOOKMARK_FIXTURE)
        assert str(bookmark) == BOOKMARK_FIXTURE

class TestBookmarks:
    ### HELPERS:
    @staticmethod
    def bookmarks_conditions(bookmarks):
        cond1 = type(bookmarks) == Bookmarks
        cond2 = bookmarks.location == Bookmarks.DEFAULT_LOCATION 
        cond3 = type(bookmarks.bookmarks[0]) == Bookmark
        return cond1 and cond2 and cond3

    #TESTS:
    def test_bookmarks_from_dict(self):
        in_dict = json.loads(BOOKMARKS_FIXTURE)
        bookmarks = Bookmarks.from_dict(in_dict)
        assert self.bookmarks_conditions(bookmarks)
    
    def test_bookmarks_from_string(self):
        bookmarks = Bookmarks.from_string(BOOKMARKS_FIXTURE)
        assert self.bookmarks_conditions(bookmarks)

    def test_bookmarks_to_string(self):
        bookmarks = Bookmarks.from_string(BOOKMARKS_FIXTURE)
        assert str(bookmarks) == BOOKMARKS_FIXTURE