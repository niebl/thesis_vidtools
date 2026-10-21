#!/bin/bash

for file in *.LRF
do
  mv "$file" "${file%.LRF}.mp4"
done

