import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import cached_codex_runtime as runtime

class RuntimeCacheTests(unittest.TestCase):
    def test_corrupt_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'runtime.tar.gz').write_bytes(b'original')
            (root/'manifest.json').write_text(json.dumps({'node':'22.23.3','codex':'0.154.0',
                'sha256':hashlib.sha256(b'original').hexdigest()}))
            with patch.object(runtime,'CACHE',root):
                runtime.validate_cache()
                (root/'runtime.tar.gz').write_bytes(b'changed')
                with self.assertRaisesRegex(RuntimeError,'hash mismatch'):runtime.validate_cache()

    def test_missing_cache_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime,'CACHE',Path(directory)):
            with self.assertRaises(FileNotFoundError):runtime.validate_cache()
