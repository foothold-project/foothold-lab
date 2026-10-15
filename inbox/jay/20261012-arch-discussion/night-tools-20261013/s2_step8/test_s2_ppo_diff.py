"""Parent-matched sample standard deviation and single-student declaration."""
import torch
from s2_runner_17v import normalize_advantages,S2RunnerError


def main():
    normalized=normalize_advantages(torch.tensor([-1.,1.]))
    assert torch.allclose(normalized,torch.tensor([-2**-.5,2**-.5]),atol=1e-6)
    print("PASS parent_sample_std_known_answer")
    try:normalize_advantages(torch.tensor([1.]))
    except S2RunnerError:print("PASS degenerate_sample_rejected")
    else:raise AssertionError("degenerate_sample_rejected")

if __name__=="__main__":main()
