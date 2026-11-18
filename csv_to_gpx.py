from xml.dom import minidom
from pathlib import Path
import os 

import csv

tracks = [
            (csv.DictReader(open(track_path)), track_path)
            for track_path in Path(".").glob("**/*.csv")
        ]

def addTextNode(parent, name, text):
    node = root.createElement(name)
    parent.appendChild(node)
    node.appendChild(root.createTextNode(text))

for gpx in tracks:
    track = list(gpx[0])

    root = minidom.Document()
    xml = root.createElement('gpx') 
    root.appendChild(xml)

    xml.setAttribute("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    xml.setAttribute("xsi:schemaLocation", "http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd")
    xml.setAttribute("xmlns", "http://www.topografix.com/GPX/1/1")
    xml.setAttribute("version", "1.1")

    #timestamp metadata
    metadata = root.createElement('metadata')
    xml.appendChild(metadata)
    time = root.createTextNode(track[0]["timestamp"])
    metadata.appendChild(time)

    #trackpoints
    trk = root.createElement('trk') 
    xml.appendChild(trk)
    
    addTextNode(trk, 'name', gpx[1].name)
    addTextNode(trk, 'type', "bikeride")

    trkseg = root.createElement('trkseg') 
    trk.appendChild(trkseg)
    
    for row in track:
        trkpt = root.createElement('trkpt')
        trkseg.appendChild(trkpt)
        trkpt.setAttribute('lat', row["latitude"])
        trkpt.setAttribute('lon', row["longitude"])
        for key, val in row.items():
            if key == "latitude" or key == "longitude":
                continue
            addTextNode(trkpt, key, val)


    save_filepath = Path('.') / gpx[1].name 
    save_filepath = save_filepath.with_suffix(".gpx")
    with open(save_filepath, "w") as f: 
        f.write(root.toprettyxml(indent ="\t"))