from pathlib import Path
import pytest
from curve_read import summarize_events, read_curves


def test_known_windows_floor_ratio_probe_spikes_and_no_future_leak():
    events=[(1,1.,'Loss/learning_rate',1e-5),(2,1.,'Loss/learning_rate',1e-4),
            (2,2.,'Loss/learning_rate',1e-5),(3,1.,'Loss/learning_rate',1e-5),
            (1,1.,'Loss/kl_probe/ppo_mean',.004),(2,1.,'Loss/kl_probe/ppo_mean',.03),
            (1,1.,'Policy/mean_noise_std',.4),(2,1.,'Policy/mean_noise_std',.3),
            (1,1.,'Train/mean_episode_length',900),(2,1.,'Train/mean_episode_length',800)]
    d=summarize_events(events,2,window=2)
    assert d['current']['lr_floor_fraction']==1
    assert d['current']['lr_n']==2
    assert d['current']['kl_probe_spikes']==1
    assert d['current']['kl_probe_n']==2
    assert d['duplicate_tag_steps']==1 and d['prescription'] is None
    assert d['current']['tags']['Policy/mean_noise_std']['last']==.3


def test_actual_tensorboard_reader_preserves_snapshot_and_missing(tmp_path):
    from tensorboard.summary.writer.event_file_writer import EventFileWriter
    from tensorboard.compat.proto.event_pb2 import Event
    from tensorboard.compat.proto.summary_pb2 import Summary
    run=tmp_path/'run';run.mkdir();w=EventFileWriter(str(run))
    for n,v in [(1,1e-5),(2,1e-4)]:
        w.add_event(Event(wall_time=n,step=n,summary=Summary(value=[Summary.Value(tag='Loss/learning_rate',simple_value=v)])))
    w.flush();w.close()
    d=read_curves(run,2,tmp_path/'out')
    assert d['current']['lr_floor_fraction']==.5
    assert d['current']['kl_probe_n']==0 and d['current']['kl_probe_spikes'] is None
    assert d['sources'] and Path(d['sources'][0]['snapshot']).is_file()
    assert read_curves(tmp_path/'empty',2,tmp_path/'other')['state']=='MISSING'
