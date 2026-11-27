#!/bin/bash

# Zurich
#Download from https://download.geofabrik.de/europe/switzerland/switzerland-latest.osm.pbf
# wget https://download.geofabrik.de/europe/switzerland/switzerland-latest.osm.pbf
osmium extract -b 8.623,47.383,8.467,47.442 switzerland-261118.osm.pbf -o zurich.osm.pbf
osmium tags-filter zurich.osm.pbf \
  w/highway=motorway,trunk,primary,secondary,tertiary,unclassified,residential,service,living_street,cycleway,path,pedestrian,track \
  --overwrite -o zurich_highways.osm.pbf
# converting osm.pbf to .osm xml: 
osmium cat zurich_highways.osm.pbf -o zurich_highways.osm

# Muenster
# wget https://download.geofabrik.de/europe/germany/nordrhein-westfalen/muenster-regbez/muenster-regbez-latest.osm.pbf
osmium tags-filter extract.osm.pbf w/highway -o highways.osm.pbf
osmium extract -b 7.470016,51.832383,7.781067,52.064734 muenster-regbez-261117.osm.pbf -o muenster.osm.pbf
# TODO: filtering
osmium cat muenster.osm.pbf -o muenster.osm