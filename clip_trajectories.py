from Clipping import Clips
from pathlib import Path
import json

WORKDIR = "./"
CLIPS = f"clips.json"
VIDEOS = f"videos/"
TRACKS = f"tracks/"
OUTPUT = f"output/"
GLOBAL_OFFSET = 0

def main():
    try:
        parser = argparse.ArgumentParser(epilog="v{}")
        parser.add_argument("-w", "--workdir", action="store", argument_default=WORKDIR,
                    help="workdir (default: ./ )")
        
        parser.add_argument("-c", "--clips", action="store", argument_default=CLIPS,
                    help="clips.json file to parse (default \{workdir\}/clips.json)")
        parser.add_argument("-v", "--videos", action="store", argument_default=VIDEOS,
                    help="directory of video files corresponding to the clips (default \{workdir\}/videos)")
        parser.add_argument("-t", "--tracks", action="store", argument_default=TRACKS,
                    help="directory of gpx files corresponding to the clips (default \{workdir\}/tracks)")
        parser.add_argument("-o", "--output", action="store", argument_default=OUTPUT,
                    help="directory to write output files to (default \{workdir\}/output)")
        
        parser.add_argument("-g", "--global_offset", action="store", argument_default=GLOBAL_OFFSET,
                    help="global offset between tracks and videos in seconds")
        parser.add_argument("-v", "--verbose", action="store_true",
                    help="verbose command line output? (True/False)")

        args = parser.parse_args()

        WD = Path(args.workdir)
        CLIPS = WD / args.clips
        TRACKS = WD / args.tracks
        VIDEOS = WD / args.videos
        OUTPUT = WD / args.output
        GLOBAL_OFFSET = args.global_offset
        VERBOSE = args.verbose

    except Exception as e:
        print(e)

    def log(*args):
        if VERBOSE: print(*args)
    
    clips = Clips.from_file(CLIPS) #Path.home() / "Projects/Bike Footage/clips_zurich/clips.json"
    clips.workdir = WD #Path.home() / "Projects/Bike Footage/clips_zurich"
    if not clips.tracks:
        clips.read_tracks(
            track_dir=TRACKS, #Path.home() / "Projects/Bike Footage/clips_zurich/gps_traces",
            global_offset=GLOBAL_OFFSET # -133
        )
    log("done reading tracks")
    clips.read_videos(
        video_dir=VIDEOS #Path.home() / "Projects/Bike Footage"
    )
    log("done reading videos")

    #for each clip, save track geojson for the clip
    log("getting geometries")
    for clip in clips.clips:
        try:
            try:
                if not clip.validate():
                    break
            except Exception as e:
                raise(e)

            clip.geometry = clips.get_track_subsegment_for_clip(clip)
            if clip.geometry:
                geojson = clip.geometry_geojson()
                start = int(clip.start.pos * 1000)/1000
                output_path = Path(clips.workdir) / "clip_tracks" / f"{Path(clip.start.path).stem}_at_{start:.3f}s.geojson"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                log(output_path)
                with open(output_path, "w") as f:
                    json.dump(geojson, f)
        except Exception as e:
            traceback.print_exc()
            print(e)
            #break
    
    clips.tracks = []

    # TODO: deserialization with the correct references and preventing endless loops
    #clips.save_clip_data(Path.home() / "Projects/Bike Footage/clips_zurich/clips.json")

if __name__ == "__main__":
    main()