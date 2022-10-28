#!/bin/bash
# A sample script to launch evaluations on all the DTU datasets

dtu_scans_array=( \ 
                    "dtu_scan24" "dtu_scan37" "dtu_scan40" "dtu_scan55" "dtu_scan63" \
                    "dtu_scan65" "dtu_scan69" "dtu_scan83" "dtu_scan97" "dtu_scan105" \
                    "dtu_scan106" "dtu_scan110" "dtu_scan114" "dtu_scan118" "dtu_scan122" \
                )

for scan in ${dtu_scans_array[*]}; do
    python exp_runner.py --mode evaluate --conf ./confs/womask.conf --dataset_type dtu --case $scan --from_latest
done