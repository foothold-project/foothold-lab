from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from foothold_s2.runtime_environment import (
    current_runtime_identity,
    expected_runtime_paths,
    validate_runtime_identity,
)


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_installed_isaac311_environment_matches_pinned_identity(self):
        identity = current_runtime_identity()
        expected_python, expected_module = expected_runtime_paths()
        self.assertEqual(identity["python_executable"].lower(),
                         str(expected_python).lower())
        self.assertEqual(identity["rsl_rl_module"].lower(), str(expected_module).lower())
        self.assertEqual(identity["rsl_rl_version"], "3.1.2")
        self.assertFalse(identity["ppo_constructor_storage"])
        self.assertTrue(identity["ppo_init_storage"])

    def test_rejects_python_path_module_path_and_version_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = root / "rsl_rl" / "__init__.py"
            ppo = root / "rsl_rl" / "algorithms" / "ppo.py"
            ppo.parent.mkdir(parents=True)
            module.parent.mkdir(exist_ok=True)
            module.write_text("", encoding="utf-8")
            ppo.write_text("class PPO:\n def __init__(self, policy): pass\n def init_storage(self): pass\n",
                           encoding="utf-8")
            args = {"python_executable": sys.executable, "rsl_rl_module": module,
                    "rsl_rl_version": "3.1.2", "ppo_source": ppo,
                    "expected_python": sys.executable, "expected_module": module}
            self.assertTrue(validate_runtime_identity(**args)["ppo_init_storage"])
            with self.assertRaisesRegex(ValueError, "Python interpreter mismatch"):
                validate_runtime_identity(**{**args, "expected_python": root / "other-python.exe"})
            with self.assertRaisesRegex(ValueError, "module path mismatch"):
                validate_runtime_identity(**{**args, "expected_module": root / "other" / "__init__.py"})
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                validate_runtime_identity(**{**args, "rsl_rl_version": "0.0.0"})

    def test_rejects_storage_constructor_api_or_missing_init_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = root / "rsl_rl" / "__init__.py"
            ppo = root / "ppo.py"
            module.parent.mkdir(parents=True)
            module.write_text("", encoding="utf-8")
            common = {"python_executable": sys.executable, "rsl_rl_module": module,
                      "rsl_rl_version": "3.1.2", "ppo_source": ppo,
                      "expected_python": sys.executable, "expected_module": module}
            ppo.write_text("class PPO:\n def __init__(self, policy, storage): pass\n def init_storage(self): pass\n",
                           encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "API differs"):
                validate_runtime_identity(**common)
            ppo.write_text("class PPO:\n def __init__(self, policy): pass\n",
                           encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "API differs"):
                validate_runtime_identity(**common)


if __name__ == "__main__":
    unittest.main()
