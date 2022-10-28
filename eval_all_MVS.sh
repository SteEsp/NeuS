#!/bin/bash
# A sample script to launch evaluations on all the BlendedMVS datasets

dtu_scans_array=( \ 
                    "bmvs_bear" \
                    "bmvs_clock" \
                    "bmvs_dog" \
                    "bmvs_durian" \
                    "bmvs_jade" \
                    "bmvs_man" \
                    "bmvs_sculpture" \
                    "bmvs_stone" \
                )

for scan in ${dtu_scans_array[*]}; do
    python exp_runner.py --mode evaluate --conf ./confs/womask.conf --dataset_type dtu --case $scan --from_latest --sphere_only_query
done