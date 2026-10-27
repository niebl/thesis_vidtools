from Bookmarks import Bookmarks, Bookmark
from Clips import Clip, Clips
import json
from pathlib import Path
import tkinter as tk
import mpv
import queue

def main():
    clips = Clips.from_file(Path.home() / "Projects/Bike Footage/clips_zurich/clips_rated.json")
    print("Clips parity to Bookmarks:", clips.has_parity())
    player = Player()
    player.rate_clips(clips)
    

class Player(mpv.MPV):
    OVERLAY_ID = 99
    def __init__(self):
        super().__init__(ytdl=True, osc=True, osd_bar=True)
        self._pressed_keys = queue.Queue()

        def capture_key(key):
            @self.on_key_press(key)
            def enqueue_key():
                self._pressed_keys.put(key)

        for key in [str(number) for number in range(10)] + [
            'y', 'n', 'ESC', 'DEL', '?', 'UP', 'DOWN', 'ENTER'
        ]:
            capture_key(key)

        @self.on_key_press('LEFT')
        def seek_backward():
            self.seek(-1, 'relative')
            self.command('show-progress')

        @self.on_key_press('RIGHT')
        def seek_forward():
            self.seek(1, 'relative')
            self.command('show-progress')

        @self.on_key_press('SPACE')
        def toggle_pause():
            self.pause = not self.pause

        @self.on_key_press('[')
        def decrease_speed():
            self.speed /= 1.1

        @self.on_key_press(']')
        def increase_speed():
            self.speed *= 1.1


    #takes clip object
    def play_clip(self, clip):
        self.clip = clip
        self.play(clip.videoclip)
        self.loop = "inf"

        results = []

        def append_result(result):
            if result == "UNCERTAIN":
                results.append(None)
                clip.uncertain = True
                return False
            elif result == "DISCARD":
                results.append(None)
                clip.discard = True
                return False
            else:
                results.append(result)
                return True

        if not append_result(self.ask("is there a traffic light? (y / n): ", ["y", "n"])):
            return results
        elif not append_result(self.count("how many lanes are crossed or passed?: ", "lanes", 1)):
            return results
        elif not append_result(self.ask("does the cyclist cross or pass a median? (y / n): ", ["y", "n"])):
            return results
        elif not append_result(self.count("How many cars cross the rider's path or pass adjacently?: ", "cars")):
            return results

        clip.observations = {
            "traffic_light": results[0],
            "lanes_crossed": results[1],
            "crosses_median": results[2],
            "cars": results[3],
            "clip_length": clip.get_duration(),
            "traffic_index": (results[3] / results[1]) / clip.get_duration()
        }
        return results
        #stop playback and return results once answers are collected

    def rate_clips(self, clips, save_to=Path.home() / "Projects/Bike Footage/clips_zurich/clips_rated.json"):
        for clip in clips:
            if clip.discard:
                print("skipping discarded clip")
                continue
            
            #skip if results populated
            if (clip.observations.get("lanes_crossed") is not None and
                clip.observations.get("traffic_light") is not None and
                clip.observations.get("crosses_median") is not None and
                clip.observations.get("cars") is not None):
                continue

            print(f"clip: {clip.start_bookmark.name} to {clip.end_bookmark.name}, uncertain: {clip.uncertain}")
            self.play_clip(clip)
            
            clips.save_clip_data(save_to)
        self.stop()

    def ask(self, question, options=None, user_input=False, timeout=None):
        if user_input:
            print(question)
            user_input = input()
            return user_input

        print(question)
        if options == ["y", "n"]:
            accepted_keys = {"y", "n"}
        elif options:
            print(", ".join(f"{i + 1}. {option}" for i, option in enumerate(options)))
            accepted_keys = {str(number) for number in range(1, len(options) + 1)}
        else:
            accepted_keys = {str(number) for number in range(10)}

        while True:
            try:
                key = self._pressed_keys.get(timeout=timeout)
            except queue.Empty:
                return None
            if key == "?":
                #mark as uncertain and return
                print("clip marked UNCERTAIN")
                return "UNCERTAIN"
            if key == "DEL":
                #mark as discard and return
                print("clip marked DISCARD")
                return "DISCARD"
            if key == "ESC":
                return None
            if key in accepted_keys:
                print(f"            {key}")
                return key

    def count(self, question, object="count", start = 0):
        count = start
        print(question)

        def display_count():
            print(f"\r\033[K{object}: {count}  (Up/Down, Enter), ('2'/'1', '4')", end="", flush=True)
            self.command("show-text", f"{object}: {count}", "30000")

        display_count()
        while True:
            key = self._pressed_keys.get()
            if key == "UP" or key == "2":
                count += 1
                display_count()
            elif key == "DOWN" or key == "1":
                count = max(0, count - 1)
                display_count()
            elif key == "ENTER" or key == "4":
                print()
                self.command("show-text", f"Cars counted: {count}", "3000")
                return count
            elif key == "DEL":
                print("\nclip marked DISCARD")
                return "DISCARD"
            elif key == "ESC":
                print()
                return None
            elif key == "?":
                print("\nclip marked UNCERTAIN")
                return "UNCERTAIN"


if __name__ == "__main__":
    main()