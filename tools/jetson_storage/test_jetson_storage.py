"""Offline tests: no robot, no NAS. python3 -m unittest test_jetson_storage"""
import hashlib
import time
import signal
import json
import os
import subprocess
import tempfile
import unittest

import jetson_sync as js
import jrec


def folder(**kw):
    f = dict(name='20261119-0520-x', size=1, idle_s=9999, sums='a' * 64, mark=None, recording=False)
    f.update(kw)
    return f


GOOD = dict(sums='a' * 64, ailx01=dict(ok=True, path=js.LOCAL + '/x'), nas=dict(ok=True, path=js.NROOT + '/x'))


class ClassifyTests(unittest.TestCase):
    def test_only_both_copies_verified_is_candidate(self):
        self.assertEqual(js.classify(folder(mark=GOOD)), 'backed_up')
        self.assertEqual(js.classify(folder(mark=dict(GOOD, nas=dict(ok=False)))), 'copy')
        self.assertEqual(js.classify(folder(mark=dict(GOOD, nas={}))), 'copy')
        self.assertEqual(js.classify(folder(mark=None)), 'copy')

    def test_mark_with_old_ailx01_path_is_redone(self):
        # 11/19 17:12 the ai-lx01 copy moved from /home/jay/data to the D drive
        old = dict(GOOD, ailx01=dict(ok=True, path='/home/jay/data/go2x_raw/jetson_go2_diag/records/x'))
        self.assertEqual(js.classify(folder(mark=old)), 'copy')

    def test_changed_sums_after_mark_is_copied_again(self):
        self.assertEqual(js.classify(folder(mark=GOOD, sums='b' * 64)), 'copy')

    def test_recording_and_young_folders_are_left_alone(self):
        self.assertEqual(js.classify(folder(mark=GOOD, recording=True)), 'recording')
        self.assertEqual(js.classify(folder(sums=None, idle_s=30)), 'young')
        self.assertEqual(js.classify(folder(sums=None)), 'make_sums')

    def test_delete_refuses_bad_name(self):
        self.assertEqual(js.delete('../x', yes=True), 2)


class RecordTests(unittest.TestCase):
    def test_start_gate(self):
        self.assertIsNone(jrec.start_refusal(20.0))
        self.assertIn('refused', jrec.start_refusal(19.9))

    def test_camera_profile_is_capped(self):
        self.assertEqual(jrec.PROFILES['camera'][1], 30)
        self.assertNotIn('/camera/camera/depth/image_rect_raw', jrec.PROFILES['map'][0])

    def test_ctrl_c_stops_the_bag_and_writes_the_record(self):
        # the fake bag sits in its own session like the real one and only leaves on SIGINT
        fake = 'trap \'touch "$2.closed"; exit 0\' INT; while :; do sleep 0.1; done'
        with tempfile.TemporaryDirectory() as d:
            code = ('import jrec, sys; jrec.ROS = sys.argv[1]; jrec.free_gb = lambda p: 100.0; '
                    'sys.exit(jrec.main(["map", "20260101-0000-t", "--seconds", "600", "--root", sys.argv[2]]))')
            here = os.path.dirname(os.path.abspath(__file__))
            p = subprocess.Popen(['python3', '-c', code, fake, d], cwd=here,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = os.path.join(d, '20260101-0000-t')
            for _ in range(50):
                if os.path.exists(os.path.join(out, 'bag.log')):
                    break
                time.sleep(0.1)
            time.sleep(1.0)
            p.send_signal(signal.SIGINT)
            rc = p.wait(30)
            log = p.stdout.read()
            p.stdout.close()
            self.assertEqual(rc, 0, log)
            self.assertTrue(os.path.exists(os.path.join(out, 'bag.closed')))
            with open(os.path.join(out, 'record.json')) as f:
                self.assertEqual(json.load(f)['stopped'], 'ctrl_c')
            self.assertTrue(os.path.exists(os.path.join(out, 'SHA256SUMS')))

    def test_sums_match_sha256sum_and_skip_mark(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'bag'))
            with open(os.path.join(d, 'bag', 'bag_0.db3'), 'wb') as f:
                f.write(b'depth')
            with open(os.path.join(d, 'record.json'), 'w') as f:
                f.write('{}')
            with open(os.path.join(d, jrec.MARK), 'w') as f:
                f.write('{}')
            self.assertEqual(jrec.write_sums(d), 2)
            r = subprocess.run(['sha256sum', '-c', '--quiet', 'SHA256SUMS'], cwd=d)
            self.assertEqual(r.returncode, 0)
            text = open(os.path.join(d, 'SHA256SUMS')).read()
            self.assertIn(hashlib.sha256(b'depth').hexdigest() + '  ./bag/bag_0.db3', text)
            self.assertNotIn(jrec.MARK, text)
            with open(os.path.join(d, 'bag', 'bag_0.db3'), 'ab') as f:
                f.write(b'!')
            r = subprocess.run(['sha256sum', '-c', '--quiet', 'SHA256SUMS'], cwd=d, capture_output=True)
            self.assertNotEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()
