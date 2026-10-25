#Procedural code for fixing the bookmarks as i had recorded them
from Bookmarks import *
from Clips import *
from pathlib import Path
import os

import cv2
import numpy as np
from open_image_models import create_detector

def main():
    clips = Clips.from_file("/home/dings/Projects/Bike Footage/clips_zurich/clips.json")
    fr_det = clips[0].clip_detections.run_licenseplate_detections()

if __name__ == "__main__":
    main()