#!/bin/bash
D=/root/onnx_pp1; B=/network-volume/limseokheon/ame2_pp1; RUN=$B/logs/rsl_rl/go2_gaze_teacher/tp424_in_p1_s5_from17000
PY=/workspace/isaaclab/_isaac_sim/python.sh
cd $D && sed -i 's/\r$//' export_ame2_onnx.py parity_ref.py || exit 1
[ -e $D/export2 ] || [ -e $D/rec_v2 ] && { echo V2_FAILED exists; exit 1; }
mkdir -p $D/rec_v2 && cp $D/rec/rec_flat.npz $D/rec/rec_stairs.npz $D/rec/rec_meta.json $D/rec_v2/ || exit 1
timeout 900 $PY $D/export_ame2_onnx.py $B $RUN model_16999.pt $D/export2 > $D/export2.log 2>&1
grep '^EXPORT_' $D/export2.log || { tail -5 $D/export2.log; echo V2_FAILED export; exit 1; }
timeout 900 $PY $D/parity_ref.py $B $RUN model_16999.pt $D/rec_v2 > $D/ref2.log 2>&1
grep '^REF_' $D/ref2.log | cut -c1-600 || { tail -5 $D/ref2.log; echo V2_FAILED ref; exit 1; }
echo V2_DONE
