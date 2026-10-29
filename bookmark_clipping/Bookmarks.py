import json, textwrap
from pathlib import Path
from .Serializable import Serializable, SerializableCollection

# parsing bookmarking files as created by https://github.com/NurioHin/mpv-bookmarker

class Bookmarks(SerializableCollection):
    DEFAULT_LOCATION = Path.home() / ".config/mpv/bookmarker.json"
    items_attribute = "bookmarks"

    def __init__(self, location = None, bookmarks = None):
        self.location = location or self.DEFAULT_LOCATION
        self.bookmarks = self.parse_bookmarks() if bookmarks is None else bookmarks

    @classmethod
    def _from_dict(cls, in_dict):
        location = None
        if isinstance(in_dict, dict):
            location = in_dict.get("location")
            in_dict = in_dict["bookmarks"]
        #assumes array
        bookmarks = list(map(
            lambda b: Bookmark(b["pos"], b["path"], b["name"], b["version"]), 
            in_dict))
        return cls(location=location, bookmarks=bookmarks)

    def to_dict(self):
        return [bookmark.to_dict() for bookmark in self.bookmarks]

    def parse_bookmarks(self):
        with open(self.location, "r") as file:
            data = json.load(file)
        bookmarks = list(map(lambda b: Bookmark(b["pos"], b["path"], b["name"], b["version"]), data))
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

    #def __str__(self):
    #    return textwrap.dedent("""\
    #        {}
    #        """.format("\n".join(
    #            map(lambda b: b.filepath + " --- " + str(b), self.bookmarks)
    #            ))
    #        )

    def __str__(self):
        out = """{}""".format("\n".join(
                map(lambda b: str(b)+",", self.bookmarks)
                )
            )
        out = out[:-1]
        return f"[{out}]"
    
class Bookmark(Serializable):
    def __init__(self, timestamp, filepath, name, ver=2):
        self.filepath = filepath
        self.timestamp = timestamp
        self.name = name
        self.version = ver
    
    @classmethod
    def _from_dict(cls, in_dict):
        return cls(in_dict["pos"], in_dict["path"], in_dict["name"], in_dict["version"])

    def update_filename(self):
        #name = filename @ HH:MM:SS.ms
        hours = int(self.timestamp / 3600)
        minutes = int((self.timestamp % 3600) / 60)
        seconds = int(self.timestamp % 60)
        ms = int((self.timestamp % 1) * 1000)
        filename = Path(self.filepath).name
        self.name = f"{filename} @ {hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"
        return self

    def __str__(self):
        return f"{{\"pos\":{self.timestamp},\"name\": \"{self.name}\", \"version\": {self.version}, \"path\": \"{self.filepath}\"}}"

    def to_dict(self):
        return {
            "pos": self.timestamp,
            "name": self.name,
            "version": self.version,
            "path": self.filepath
        }
    
