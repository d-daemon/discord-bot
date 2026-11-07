import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cogs import photodownload


URL = "https://www.instagram.com/p/DJj6CXry060/?utm_source=ig_web_copy_link&vrfl=MzRlODBiNWFlZA==&srtk=MzRlODBiNWFlZA=="


class PhotoDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.download_dir = Path(self.temp_dir.name)
        sleep_patcher = patch.object(photodownload, "do_sleep")
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    @patch.object(photodownload.subprocess, "run")
    @patch.object(photodownload.shutil, "which", return_value="/usr/bin/gallery-dl")
    def test_gallery_dl_downloads_only_photos_and_preserves_existing_files(self, which, run):
        existing = self.download_dir / "existing.jpg"
        existing.write_bytes(b"existing")
        cookie_files = []

        def gallery_dl(command, **kwargs):
            self.assertEqual(command[-1], URL)
            cookie_file = Path(command[command.index("--cookies") + 1])
            cookie_files.append(cookie_file)
            self.assertIn("sessionid", cookie_file.read_text())
            output = Path(command[command.index("-d") + 1]) / "instagram"
            output.mkdir()
            (output / "01.jpg").write_bytes(b"first")
            (output / "02.png").write_bytes(b"second")
            (output / "video.mp4").write_bytes(b"video")
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = gallery_dl
        with patch.dict(os.environ, {"INSTAGRAM_COOKIES": "sessionid=test-value"}):
            photos = photodownload.download_instagram_photos(URL, str(self.download_dir))

        self.assertEqual([Path(photo).read_bytes() for photo in photos], [b"first", b"second"])
        self.assertEqual(existing.read_bytes(), b"existing")
        self.assertFalse(cookie_files[0].exists())
        self.assertEqual(len(list(self.download_dir.iterdir())), 3)

    @patch.object(photodownload.subprocess, "run")
    @patch.object(photodownload.shutil, "which", return_value="/usr/bin/gallery-dl")
    def test_gallery_failure_is_reported_and_cookies_removed(self, which, run):
        cookie_files = []

        def gallery_dl(command, **kwargs):
            cookie_files.append(Path(command[command.index("--cookies") + 1]))
            return subprocess.CompletedProcess(command, 1, "", "download failed")

        run.side_effect = gallery_dl
        with patch.dict(os.environ, {"INSTAGRAM_COOKIES": "sessionid=test-value"}):
            with self.assertRaisesRegex(RuntimeError, "gallery-dl could not download"):
                photodownload.download_instagram_photos(URL, str(self.download_dir))
        self.assertFalse(cookie_files[0].exists())
        self.assertEqual(list(self.download_dir.iterdir()), [])

    @patch.object(photodownload.subprocess, "run")
    @patch.object(photodownload.shutil, "which", return_value="/usr/bin/gallery-dl")
    def test_no_photos_fails(self, which, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with patch.dict(os.environ, {"INSTAGRAM_COOKIES": ""}):
            with self.assertRaisesRegex(FileNotFoundError, "No photo file"):
                photodownload.download_instagram_photos(URL, str(self.download_dir))
        self.assertNotIn("--cookies", run.call_args.args[0])
        self.assertEqual(list(self.download_dir.iterdir()), [])

    @patch.object(photodownload.shutil, "which", return_value=None)
    def test_missing_gallery_dl_is_reported(self, which):
        with self.assertRaisesRegex(RuntimeError, "gallery-dl is not installed"):
            photodownload.download_instagram_photos(URL, str(self.download_dir))
        self.assertEqual(list(self.download_dir.iterdir()), [])

    @patch.object(photodownload.subprocess, "run")
    @patch.object(photodownload.shutil, "which", return_value="/usr/bin/gallery-dl")
    def test_timeout_removes_cookies_and_temporary_downloads(self, which, run):
        cookie_files = []

        def gallery_dl(command, **kwargs):
            cookie_files.append(Path(command[command.index("--cookies") + 1]))
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        run.side_effect = gallery_dl
        with patch.dict(os.environ, {"INSTAGRAM_COOKIES": "sessionid=test-value"}):
            with self.assertRaises(subprocess.TimeoutExpired):
                photodownload.download_instagram_photos(URL, str(self.download_dir))
        self.assertFalse(cookie_files[0].exists())
        self.assertEqual(list(self.download_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
