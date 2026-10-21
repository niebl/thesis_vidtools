from Bookmarks import Bookmarks
import av
from pathlib import Path

class Clips:
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"

    def __init__(self, bookmarks, workdir=None):
        self.workdir = workdir or DEFAULT_WORKDIR
        self.bookmarks = bookmarks
        self.clips = self.get_clips()

    def get_clips(self):
        clips = []

        if len(self.bookmarks.bookmarks) % 2 != 0:
            print("odd number of bookmarks")
            return clips

        for i in range(0, len(self.bookmarks.bookmarks), 2):
            start_bookmark = self.bookmarks.bookmarks[i]
            end_bookmark = self.bookmarks.bookmarks[i+1]
            clips.append(Clip(start_bookmark, end_bookmark, self.workdir))

        for clip in clips:
            if not clip.validate():
                print(f"Invalid clip: {clip.start_bookmark.name} to {clip.end_bookmark.name}")
                return []
        return clips

    def __str__(self):
        return "\n".join(map(str, self.get_clips()))

class Clip:
    def __init__(self, start_bookmark, end_bookmark, workdir):
        self.workdir = workdir
        self.start_bookmark = start_bookmark
        self.end_bookmark = end_bookmark
        self.files = [start_bookmark.filepath]
        #add second file if clip spans 2
        self.files.append(end_bookmark.filepath) if end_bookmark.filepath != start_bookmark.filepath else None

    def __str__(self):
        return f"{self.get_duration()}s at {self.start_bookmark.name}"

    def validate(self):
        same_dir = Path(self.start_bookmark.filepath).parent == Path(self.end_bookmark.filepath).parent

        files= sorted(Path(self.start_bookmark.filepath).parent.glob("*"))
        start_index = files.index(Path(self.start_bookmark.filepath))
        end_index = files.index(Path(self.end_bookmark.filepath))
        direct_follow = abs(end_index - start_index) <= 1
        
        return same_dir and direct_follow

    def get_duration(self):
        if self.start_bookmark.filepath == self.end_bookmark.filepath:
            return self.end_bookmark.timestamp - self.start_bookmark.timestamp
        else:
            # get video duration of start file
            start_file = av.open(self.start_bookmark.filepath)
            start_duration = start_file.duration / av.time_base
            start_file.close() 
            trailing_duration = start_duration - self.start_bookmark.timestamp
            leading_duration = self.end_bookmark.timestamp
            return trailing_duration + leading_duration
            return None

def main():
    bookmarks = Bookmarks()
    clips = Clips(bookmarks, Path.home() / "Projects/Bike Footage")
    print(clips)

if __name__ == "__main__":
    main()