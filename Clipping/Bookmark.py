from pathlib import Path
if __package__:
    from .Serializable import Serializable, SerializableCollection
else:
    from Serializable import Serializable, SerializableCollection

class Bookmark(Serializable):
    def __init__(self, pos, path, name, ver=2, oid=None):
        super().__init__(oid=oid)
        self.path = path
        self.pos = pos
        self.name = name
        self.ver = ver

    def to_dict(self):
        data = self._to_dict(exclude_keys=[
            "workdir",
            "parent",
            "verbose"
        ])
        return data

    def update_filename(self):
        #name = filename @ HH:MM:SS.ms
        hours = int(self.pos / 3600)
        minutes = int((self.pos % 3600) / 60)
        seconds = int(self.pos % 60)
        ms = int((self.pos % 1) * 1000)
        filename = Path(self.path).name
        self.name = f"{filename} @ {hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"
        return self