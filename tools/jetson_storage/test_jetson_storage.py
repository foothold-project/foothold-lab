"""Offline tests: no robot, no NAS. python3 -m unittest test_jetson_storage"""
import hashlib
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


GOOD = dict(sums='a' * 64, ailx01=dict(ok=True), nas=dict(ok=True))


class ClassifyTests(unittest.TestCase):
    def test_only_both_copies_verified_is_candidate(self):
        self.assertEqual(js.classify(folder(mark=GOOD)), 'backed_up')
        self.assertEqual(js.classify(folder(mark=dict(GOOD, nas=dict(ok=False)))), 'copy')
        self.assertEqual(js.classify(folder(mark=dict(GOOD, nas={}))), 'copy')
        self.assertEqual(js.classify(folder(mark=None)), 'copy')

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
