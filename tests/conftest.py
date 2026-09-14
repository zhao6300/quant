import os

for variable in ("PYTHONHASHSEED",):
    os.environ[variable] = "0"

for variable in (
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_NUM_THREADS",
):
    os.environ[variable] = "1"
