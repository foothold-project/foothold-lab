"""시험 공통: 같은 프로세스에 OpenMP 런타임이 둘 로드되는 경고(Windows anaconda)를 넘긴다."""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# EX-41 tests must never inherit a live alert-delivery opt-in. Tests that
# exercise delivery inject local fake senders explicitly.
os.environ["EX41_ALLOW_EXTERNAL_ALERT_DELIVERY"] = "0"
