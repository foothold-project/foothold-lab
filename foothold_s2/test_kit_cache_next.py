import importlib.util
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).with_name('kit_cache_next.py')


class CacheArgsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), 'cache launch adapter missing')

    def test_actual_script_argv_preserves_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'probe.py'
            p.write_text('import sys,json;print(json.dumps(sys.argv[1:]))', encoding='utf-8')
            r = subprocess.run([sys.executable, str(MODULE), '--script', str(p), '--',
                                '--out', 'folder with spaces', '--kit_args', '--/renderer/test=true'],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            args = json.loads(r.stdout)
            self.assertEqual(args[:2], ['--out', 'folder with spaces'])
            self.assertIn('--/renderer/test=true', args[-1])
            self.assertIn('--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache', args[-1])
            self.assertNotIn('Budget', args[-1])

    def test_module_argv_and_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'cache_probe.py').write_text('import sys,json;print(json.dumps(sys.argv[1:]));sys.exit(7)', encoding='utf-8')
            r = subprocess.run([sys.executable, str(MODULE), '--module', 'cache_probe', '--', '--seed', '42'],
                               cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 7, r.stderr)
            self.assertEqual(json.loads(r.stdout)[:2], ['--seed', '42'])

    def test_replaces_existing_cache_not_other_kit_flags(self):
        spec = importlib.util.spec_from_file_location('adapter', MODULE)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        args = m.with_cache(['--kit_args=--/UJITSO/datastore/localCachePath=C:/old', '--kit_args', '--/renderer/a=1'])
        self.assertEqual(sum(a.startswith('--kit_args=') for a in args), 1)
        self.assertNotIn('C:/old', args[-1])
        self.assertIn('--/renderer/a=1', args[-1])

    def test_real_argparse_accepts_leading_dash_kit_value(self):
        spec = importlib.util.spec_from_file_location('adapter', MODULE)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        parser = argparse.ArgumentParser()
        parser.add_argument('--kit_args', type=str, default='')
        parsed = parser.parse_args(m.with_cache([]))
        self.assertEqual(parsed.kit_args, '--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache')

    def test_recorder_local_adapter_preserves_other_settings(self):
        path = MODULE.parent/'eval'/'video25'/'record_25e_x28.py'
        spec = importlib.util.spec_from_file_location('recorder_next', path)
        rec = importlib.util.module_from_spec(spec); spec.loader.exec_module(rec)
        result = rec._w33b_cache_args('--/renderer/a=1')
        self.assertEqual(result, '--/renderer/a=1 --/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache')


if __name__ == '__main__':
    unittest.main()
