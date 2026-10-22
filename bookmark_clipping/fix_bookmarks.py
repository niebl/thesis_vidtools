#Procedural code for fixing the bookmarks as i had recorded them
from Bookmarks import Bookmarks
from pathlib import Path
import os

def main():
    bookmarks = Bookmarks()
    #dedupe_and_rename(bookmarks)
    print(bookmarks)

def dedupe_and_rename(bookmarks):
    #remove all bookmarks from /home/dings/Projects/Bike Footage/06/ because those were duplicates
    bookmarks.bookmarks = list(filter(
        lambda b: not b.filepath.startswith(
                os.path.abspath("/home/dings/Projects/Bike Footage/06"+os.sep)
            ),
        bookmarks.bookmarks
    ))

    #update bookmark names for timestamps changed
    bookmarks.map(lambda b: b.update_filename())
    bookmarks.save_bookmarks()
    
if __name__ == "__main__":
    main()