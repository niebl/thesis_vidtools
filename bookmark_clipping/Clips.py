if __package__:
    from .Bookmarks import Bookmarks, Bookmark
    from .Serializable import Serializable, SerializableCollection
else:
    from Bookmarks import Bookmarks, Bookmark
    from Serializable import Serializable, SerializableCollection
import av
from pathlib import Path
import subprocess
import json
import cv2
import numpy as np
from open_image_models import create_detector

class Clips(SerializableCollection):
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"
    items_attribute = "clips"

    def __init__(self, bookmarks, workdir=None, clips=None):
        self.workdir = workdir or DEFAULT_WORKDIR
        self.bookmarks = bookmarks
        self.clips = self.get_clips() if clips is None else clips

    @classmethod
    def from_file(cls, filepath=None):
        path = filepath or cls.DEFAULT_WORKDIR
        with open(path, "r") as file:
            data = json.load(file)
        return cls.from_dict(data)

    @classmethod
    def _from_dict(cls, in_dict):
        bookmarks = Bookmarks.from_dict(in_dict["bookmarks"])
        clips = list(map(lambda cl: 
            Clip(
                Bookmark.from_dict(cl["start"]), 
                Bookmark.from_dict(cl["end"]), 
                in_dict["workdir"], 
                cl["videoclip"], 
                observations=cl["observations"],
                discard=cl["discard"],
                uncertain=cl["uncertain"]), 
            in_dict["clips"])
        )
        return cls(bookmarks, in_dict["workdir"], clips)

    def to_dict(self):
        return {
            "workdir": str(self.workdir),
            "clips": [clip.to_dict() for clip in self.clips],
            "bookmarks": self.bookmarks.to_dict(),
        }


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
            clips.append(Clip(start_bookmark, end_bookmark, self.workdir, parent=self))

        for clip in clips:
            if not clip.validate():
                print(f"Invalid clip: {clip.start_bookmark.name} to {clip.end_bookmark.name}")
                return []
        return clips
    
    def save_clip_data(self, location=None):
        save_at = location or workdir / "clips.json"
        with open(save_at, "w") as f:
            f.write(str(self))
    
    def has_parity(self):
        # checks that every clip listed is contained in the bookmarks
        bookmark_set = set((b.filepath, b.timestamp) for b in self.bookmarks.bookmarks)
        for clip in self.clips:
            if (clip.start_bookmark.filepath, clip.start_bookmark.timestamp) not in bookmark_set:
                return False
            if (clip.end_bookmark.filepath, clip.end_bookmark.timestamp) not in bookmark_set:
                return False
        if len(self.clips) * 2 != len(self.bookmarks.bookmarks):
            return False
        return True

    def __str__(self):
        out = """{}""".format("\n".join(
                map(lambda b: str(b)+",", self.clips)
                )
            )
        out = out[:-1]

        return f"{{\"workdir\": \"{self.workdir}\", \"clips\":[{out}], \"bookmarks\":{str(self.bookmarks)}}}"

class Clip(Serializable):
    DEFAULT_WORKDIR = Path.home() / "Videos/clips"
    def __init__(self, start_bookmark, end_bookmark, workdir=None, videoclip=None, parent=None, observations=False, discard=False, uncertain=False):
        self.workdir = workdir
        self.start_bookmark = start_bookmark
        self.end_bookmark = end_bookmark
        self.files = [start_bookmark.filepath]
        #add second file if clip spans 2
        self.files.append(end_bookmark.filepath) if end_bookmark.filepath != start_bookmark.filepath else None
        self.videoclip = videoclip or ""
        self.parent = parent
        self.observations = observations or {}
        self.discard = discard
        self.uncertain = uncertain
        self.clip_detections = ClipDetections(self)

    def __str__(self):
        videoclip = f"\"{self.videoclip}\"" or "\"\""

        return json.dumps({
            "start": self.start_bookmark.asdict(), 
            "end": self.end_bookmark.asdict(), 
            "videoclip": self.videoclip or "",
            "clip_detections": self.clip_detections
        })

    def render_clip(self, output_path=None):
        source = list(map(lambda c: Path(c), self.files))
        start = int(self.start_bookmark.timestamp * 1000)/1000
        output = Path(output_path) if output_path else (
            Path(self.workdir) / f"{source[0].stem}_at_{start:.3f}s.mp4"
        )
        if output.exists():
            print(f"skipping {str(output)}. already exists")
            self.videoclip = output
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

    def clip_to_frames(self):
        print(self.videoclip)
        video = cv2.VideoCapture(self.videoclip)
        ok, frame = video.read()
        count = 0
        frames = []
        while ok:
            #cv2.imwrite("frame%04d.jpg".format(count), frame)
            #print('WRITTEN FRAME:',count)
            frames.append(frame)
            count+=1
            ok, frame = video.read()
        print(video)
        video.release()
        return frames

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

class ClipDetections(SerializableCollection):
    items_attribute = "detection_frames"

    def __init__(self, parent: Clip = None, detection_frames=[]):
        self.parent = parent
        self.detection_frames = detection_frames

    def run_licenseplate_detections(self):
        detector = create_detector("yolo-v9-t-640-license-plate-end2end")
        frames = self.parent.clip_to_frames()
        frame_detections = []

        for frame in frames:
            detections = detector.predict(frame)
            frame_detections.append(detections)
            if len(detections) > 0:
                annotated_image = detector.display_predictions(frame)
                #write to workdir
                output_path = Path(self.parent.workdir) / "annotated" / f"{self.parent.start_bookmark.name}_to_{self.parent.end_bookmark.name}_frame_{len(frame_detections)}.jpg"
                cv2.imwrite(str(output_path), annotated_image)

        return frame_detections

    def __str__(self):
        return json.dumps({
            "frames": self.objects 
        })

    def push(self, value:DetectionFrame):
        self.detection_frames.push(value)

class DetectionFrame(SerializableCollection):
    items_attribute = "detections"
    def __init__(self, frame_number, parent: ClipDetections = None, detections = []):
        self.parent = parent
        self.frame_number = frame_number
        self.detections = []

    def __str__(self):
        return json.dumps({
            "frame_number": self.frame_number,
            "detections": self.detection 
        })

    def get_index(self):
        return self.parent.detection_frames.index(self)

    def get_next_frame(self):
        return self.parent[self.get_index()+1]
    
    def get_prev_frame(self):
        return self.parent[self.get_index()+1]

class Detection(Serializable):
    def __init__(self, x1, y1, x2, y2, label, confidence, parent:DetectionFrame):
        self.bbox = {"x1":x1, "y1":y1, "x2":x2, "y2":y2}
        self.label = label
        self.parent = parent
        self.confidence = confidence

    def __str__(self):
        return json.dumps({
            "x": self.x,
            "y": self.y,
            "label": self.label 
        })


def main():
    bookmarks = Bookmarks()
    clips = Clips(bookmarks, Path.home() / "Projects/Bike Footage/clips_zurich")
    clips.render_all_clips()
    clips.save_clip_data(Path.home() / "Projects/Bike Footage/clips_zurich/clips.json")

if __name__ == "__main__":
    main()