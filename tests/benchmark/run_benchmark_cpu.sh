#!/bin/bash
# Copyright 2023 TeNPy Developers


# Perform benchmarks with a CPU
#  - tenpy v2.x with numpy block backend
#  - pure numpy
#
# Usage:
#  ./run_benchmark_cpu.sh [MOD]
#
# MOD : prefix of the modules to run, default "tdot"
# runs "$MOD"_tenpy.py and "$MOD"_numpy.py


set -e
DIR="$(dirname ${BASH_SOURCE[0]})"

if [ -n "$1" ]
then
    MOD="$1"
else
    MOD="tdot"
fi

common_args="-t 0.1 -b abelian numpy"
extra_args=(
    # 1 leg
    # no symmetry
    "-l 1 -q no_symmetry"
    # U(1) x U(1) x Z2
    "-l 1 -q u1_symmetry u1_symmetry z2_symmetry -s 2"
    "-l 1 -q u1_symmetry u1_symmetry z2_symmetry -s 5"
    "-l 1 -q u1_symmetry u1_symmetry z2_symmetry -s 20"
    # U(1)
    "-l 1 -q u1_symmetry -s 2"
    "-l 1 -q u1_symmetry -s 5"
    "-l 1 -q u1_symmetry -s 20"
    # Z2
    "-l 1 -q z2_symmetry -s 2"
    "-l 1 -q z2_symmetry -s 5"
    "-l 1 -q z2_symmetry -s 20"
    # 2 legs
    # no symmetry
    "-l 2 -q no_symmetry"
    # U(1) x U(1) x Z2
    "-l 2 -q u1_symmetry u1_symmetry z2_symmetry -s 2"
    "-l 2 -q u1_symmetry u1_symmetry z2_symmetry -s 5"
    "-l 2 -q u1_symmetry u1_symmetry z2_symmetry -s 20"
    # U(1)
    "-l 2 -q u1_symmetry -s 2"
    "-l 2 -q u1_symmetry -s 5"
    "-l 2 -q u1_symmetry -s 20"
    # Z2
    "-l 2 -q z2_symmetry -s 2"
    "-l 2 -q z2_symmetry -s 5"
    "-l 2 -q z2_symmetry -s 20"
)
for extra in "${extra_args[@]}"
do
    echo "========================================"
    echo "python $DIR/benchmark.py -m ${MOD}_tenpy $common_args $extra"
    python $DIR/benchmark.py -m ${MOD}_tenpy $common_args $extra
    echo "========================================"
    echo "python $DIR/benchmark.py -m ${MOD}_numpy $common_args $extra"
    python $DIR/benchmark.py -m ${MOD}_numpy $common_args $extra
done
# plot, if we have an X-server (otherwise matplotlib fails.)
test -n "$DISPLAY" && python $DIR/benchmark.py -p ${MOD}_*.txt
