if __package__:
    from .Serializable import Serializable, SerializableCollection
else:
    from Serializable import Serializable, SerializableCollection
from open_image_models import create_detector
import cv2

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

    def interpolate(self):
        #TODO
        pass

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