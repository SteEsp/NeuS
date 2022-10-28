#!/bin/bash
# A sample script to launch evaluations on all the NeRF Synthetic datasets

dtu_scans_array=( \ 
                    "lego" \
                    "chair" \
                    "drums" \ 
                    # "ficus" \ 
                    "hotdog" \
                    # "mic" \ 
                    "ship" \ 
                    "materials" \ 
                )

for scan in ${dtu_scans_array[*]}; do
    python exp_runner.py --mode evaluate --conf ./confs/womask.conf --dataset_type blender --case $scan --from_latest
done