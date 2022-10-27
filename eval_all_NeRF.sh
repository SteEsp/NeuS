#!/bin/bash
# A sample script to launch evaluations on all the NeRF Synthetic datasets

python exp_runner.py --mode evaluate --conf ./confs/womask.conf --dataset_type blender --case lego