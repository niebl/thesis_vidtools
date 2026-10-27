from Bookmarks import Bookmarks, Bookmark
from Clips import Clip, Clips
import json
from pathlib import Path
import tkinter as tk
import mpv
import queue

def main():
    clips = Clips.from_file(Path.home() / "Projects/Bike Footage/clips_zurich/clips.json")
    print("Clips parity to Bookmarks:", clips.has_parity())
    player = Player()
    clips.clips = clips.clips[0:5]
    player.play_clips(clips)
    

class Player(mpv.MPV):
    OVERLAY_ID = 99
    def __init__(self):
        super().__init__(ytdl=True, osc=True, osd_bar=True)
        self._pressed_keys = queue.Queue()

        def capture_key(key):
            @self.on_key_press(key)
            def enqueue_key():
                self._pressed_keys.put(key)

        for key in [str(number) for number in range(10)] + ['y', 'n', 'ESC', 'DEL', '?']:
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

        if not append_result(self.ask("how many lanes are crossed?: ", clip=clip)):
            return results
        elif not append_result(self.ask("is there a traffic light? (y / n): ", ["y", "n"], clip=clip)):
            return results
        elif not append_result(self.ask("does the cyclist cross or pass a median? (y / n): ", ["y", "n"], clip=clip)):
            return results
        elif not append_result(self.ask("how many cars cross the riders path, or pass the driver adjacently?: ", user_input=True, clip=clip)):
            return results

        return results
        #stop playback and return results once answers are collected

    def play_clips(self, clips):
        for clip in clips:
            if clip.discard:
                continue
            print(f"clip: {clip.start_bookmark.name} to {clip.end_bookmark.name}, uncertain: {clip.uncertain}")
            self.play_clip(clip)
            #collect results for each clip
            #stop playback and return results once answers are collected
        self.stop()

    def ask(self, question, options=None, user_input=False, timeout=None, clip=None):
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


if __name__ == "__main__":
    main()