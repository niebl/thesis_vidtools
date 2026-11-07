import json, textwrap
from pathlib import Path
if __package__:
    from .Bookmark import Bookmark
    from .Serializable import Serializable, SerializableCollection
else:
    from Bookmark import Bookmark
    from Serializable import Serializable, SerializableCollection
# parsing bookmarking files as created by https://github.com/NurioHin/mpv-bookmarker

class Bookmarks(SerializableCollection):
    DEFAULT_LOCATION = Path.home() / ".config/mpv/bookmarker.json"
    items_attribute = "bookmarks"

    def __init__(self, 
            location:Path=None, 
            bookmarks=None
        ):
        self.location = location or self.DEFAULT_LOCATION
        self.bookmarks = self.parse_bookmarks() if bookmarks is None else bookmarks
    
    @classmethod
    def from_dict(cls, data):
        if isinstance(data, dict):
            in_dict = data
            in_dict["bookmarks"] = list(map(lambda b: Bookmark.from_dict(b), in_dict["bookmarks"]))
        else:
            in_dict = {}
        in_dict["bookmarks"] = list(map(lambda b: Bookmark.from_dict(b), data))
        in_dict["location"] = None
        return cls._from_dict(in_dict)

    def to_dict(self):
        return [bookmark.to_dict() for bookmark in self.bookmarks]

    def parse_bookmarks(self):
        with open(self.location, "r") as file:
            data = json.load(file)
        bookmarks = list(map(lambda b: Bookmark(b["pos"], b["path"], b["name"], b["ver"]), data))
        return bookmarks

    #WARNING: overwrites your bookmarks. make sure to have backups
    def save_bookmarks(self, location=None):
        save_at = location or self.location
        if save_at == self.DEFAULT_LOCATION:
            answer = input("Warning: Overwriting system default location. Continue? [y/N]")
            if answer.lower() in ["y","yes"]:
                pass
            else:
                return
        with open(save_at, "w") as f:
            f.write(str(self))

    def to_string(self):
        out = """{}""".format("\n".join(
                map(lambda b: str(b)+",", self.bookmarks)
                )
            )
        out = out[:-1]
        return f"[{out}]"
