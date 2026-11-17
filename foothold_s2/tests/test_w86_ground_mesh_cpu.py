"""w86_runtime.ground_mesh: 2.3.2 (문자열 열쇠) 와 3.0 ((prim, device) 튜플 열쇠) 둘 다에서 지면 mesh 를 찾는다."""
import pytest

from foothold_s2.rewards.w86_runtime import ground_mesh


def test_string_key_2x():
    assert ground_mesh({'/World/ground': 'M'}, 'cuda:0') == 'M'


def test_tuple_key_3x_exact_device():
    assert ground_mesh({('/World/ground', 'cuda:0'): 'A', ('/World/ground', 'cpu'): 'B'}, 'cpu') == 'B'


def test_tuple_key_device_object():
    class D:
        def __str__(self): return 'cuda:0'
    assert ground_mesh({('/World/ground', 'cuda:0'): 'A'}, D()) == 'A'


def test_single_tuple_other_device_name_is_used():
    assert ground_mesh({('/World/ground', 'cuda:0'): 'A'}, 'cuda') == 'A'


def test_missing_raises():
    with pytest.raises(ValueError):
        ground_mesh({('/World/other', 'cuda:0'): 'A'}, 'cuda:0')
    with pytest.raises(ValueError):
        ground_mesh({('/World/ground', 'cuda:0'): 'A', ('/World/ground', 'cpu'): 'B'}, 'cuda:1')
