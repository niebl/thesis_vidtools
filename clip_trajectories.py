from Clipping import Clips
from pathlib import Path
import json
import argparse
import traceback
from datetime import date

WORKDIR = "./"
CLIPS = "clips.json"
VIDEOS = "videos/"
TRACKS = "tracks/"
OUTPUT = "output/"
GLOBAL_OFFSET = 0

def main():

    parser = argparse.ArgumentParser(epilog="v{}")
    parser.add_argument("-w", "--workdir", action="store", default=WORKDIR,
                help="workdir (default: ./ )")
    
    parser.add_argument("-c", "--clips", action="store", default=CLIPS,
                help="clips.json file to parse (default {{workdir}}/clips.json)")
    parser.add_argument("-v", "--videos", action="store", default=VIDEOS,
                help="directory of video files corresponding to the clips (default {{workdir}}/videos)")
    parser.add_argument("-t", "--tracks", action="store", default=TRACKS,
                help="directory of gpx files corresponding to the clips (default {{workdir}}/tracks)")
    parser.add_argument("-o", "--output", action="store", default=OUTPUT,
                help="directory to write output files to (default {{workdir}}/output)")
    
    parser.add_argument("-g", "--global_offset", action="store", default=GLOBAL_OFFSET,
                help="global offset between tracks and videos in seconds")
    parser.add_argument("-V", "--verbose", action="store_true",
                help="verbose command line output? (True/False)")

    args = parser.parse_args()

    wd = Path(args.workdir)
    clips = wd / args.clips
    tracks = wd / args.tracks
    videos = wd / args.videos
    output = wd / args.output
    global_offset = float(args.global_offset)
    verbose = args.verbose


    def log(*args):
        if verbose: print(*args)
    
    clips = Clips.from_file(clips, verbose=verbose) #Path.home() / "Projects/Bike Footage/clips_zurich/clips.json"
    for i, clip in enumerate(clips.clips):
        if clip.parent is None:
            print(clip)
            print(f"clip index {i} has no parent")
            exit()
        if clip.start is None or clip.end is None:
            print(clip)
            print(f"clip index {i} misses bookmark")
            exit()

    clips.workdir = wd #Path.home() / "Projects/Bike Footage/clips_zurich"
    if not clips.tracks:
        clips.read_tracks(
            track_dir=tracks, #Path.home() / "Projects/Bike Footage/clips_zurich/gps_traces",
            track_offset=global_offset # -133
        )
    log("done reading tracks")
    clips.read_videos(
        video_dir=videos #Path.home() / "Projects/Bike Footage"
    )
    log("done reading videos")

    #for each clip, save track geojson for the clip
    log("getting geometries")
    dates = set()
    for clip in clips.clips:
        try:
            try:
                if not clip.validate():
                    continue
            except Exception as e:
                print(e)
                continue
            
            date = clip.get_date()
            if date:
                dates.add(date)
            clip.geometry = clips.get_track_subsegment_for_clip(
                clip, m_start=2, m_end=2
                )
            
        except Exception as e:
            traceback.print_exc()
            print(e)
    
    n_clips = 0

    for day in dates:
        output_path = Path(clips.workdir) / "clip_tracks" / f"clips_{day}.geojson"
        #output_path = Path.home() / f"cloud/sciebo/Studium/0_Masterarbeit/gis/zurich/tracks_days/clips_{day}.geojson"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        log(output_path)
        feature_collection = clips.geometry_geojson(
            lambda c: c.get_date() == day,
            human_readable=True, skip_empty=True
            )
        n_clips += len(feature_collection["features"])
        with open(output_path, "w") as f:
            json.dump(feature_collection, f)

    print(f"successfully written {n_clips} clip trajectories out of {int(len(clips.bookmarks) / 2)} bookmarked clips")
    
    #clips.tracks = []
    clips.videos = []

    # TODO: deserialization with the correct references and preventing endless loops
    clips.save_clip_data(Path.home() / "Projects/Bike Footage/clips_zurich/clips.json")

if __name__ == "__main__":
    main()