from Bookmarks import Bookmarks
import av
from pathlib import Path
import subprocess

class Clips:
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"

    def __init__(self, bookmarks, workdir=None):
        self.workdir = workdir or DEFAULT_WORKDIR
        self.bookmarks = bookmarks
        self.clips = self.get_clips()

    def render_all_clips(self):
        for clip in self.clips:
            clip.render_clip()

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
    def __init__(self, start_bookmark, end_bookmark, workdir, videoclip=None):
        self.workdir = workdir
        self.start_bookmark = start_bookmark
        self.end_bookmark = end_bookmark
        self.files = [start_bookmark.filepath]
        #add second file if clip spans 2
        self.files.append(end_bookmark.filepath) if end_bookmark.filepath != start_bookmark.filepath else None
        self.videoclip = None

    def __str__(self):
        return f"{self.get_duration()}s at {self.start_bookmark.name}"

    def render_clip(self, output_path=None):
        source = list(map(lambda c: Path(c), self.files))
        start = int(self.start_bookmark.timestamp * 1000)/1000
        output = Path(output_path) if output_path else (
            Path(self.workdir) / f"{source[0].stem}_at_{start:.3f}s.mp4"
        )
        if output.exists():
            print(f"skipping {str(output)}. already exists")
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
            end = self.end_bookmark.timestamp

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
        same_dir = Path(self.start_bookmark.filepath).parent == Path(self.end_bookmark.filepath).parent

        files= sorted(Path(self.start_bookmark.filepath).parent.glob("*"))
        start_index = files.index(Path(self.start_bookmark.filepath))
        end_index = files.index(Path(self.end_bookmark.filepath))
        direct_follow = abs(end_index - start_index) <= 1

        duration_ok = self.get_duration() < 120
        
        return same_dir and direct_follow and duration_ok

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
    clips = Clips(bookmarks, Path.home() / "Projects/Bike Footage/clips_zurich")
    clips.render_all_clips()

if __name__ == "__main__":
    main()