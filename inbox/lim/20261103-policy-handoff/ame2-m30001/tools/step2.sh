#!/bin/bash
set -u
D=/root/onnx_x9c; B=/network-volume/limseokheon/ame2_x8; AV=/network-volume/limseokheon/derived_ctl424/avg_X9C_13000_14999
PY=/workspace/isaaclab/_isaac_sim/python.sh
cd $D && sed -i 's/\r$//' *.py *.sh && md5sum *.py
[ -e $D/export ] && { echo STEP2_FAILED export exists; exit 1; }
nice -n 10 timeout 900 $PY $D/export_ame2_onnx.py $B $AV model_avg.pt $D/export > $D/export.log 2>&1
grep -E '^EXPORT_' $D/export.log | cut -c1-600 || { tail -8 $D/export.log; echo STEP2_FAILED; exit 1; }
ls -la $D/export; sha256sum $D/export/*
echo STEP2_END
