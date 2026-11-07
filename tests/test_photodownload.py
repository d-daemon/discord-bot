import asyncio
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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
    def test_gallery_dl_downloads_only_photos_and_preserves_existing_files(
        self, which, run
    ):
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
            photos = photodownload.download_instagram_photos(
                URL, str(self.download_dir)
            )

        self.assertEqual(
            [Path(photo).read_bytes() for photo in photos], [b"first", b"second"]
        )
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

    def test_video_cover_download_writes_only_thumbnail_and_cleans_cookie(self):
        ydl_instances = []

        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options
                ydl_instances.append(self)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def extract_info(self, url, *, download):
                self.download = download
                (self.download_dir / "cover.jpg").write_bytes(b"cover")

        FakeYoutubeDL.download_dir = self.download_dir
        cookie_files = []
        original_cookie_writer = photodownload.write_instagram_cookie_file

        def write_cookie(value):
            cookie_file = original_cookie_writer(value)
            cookie_files.append(Path(cookie_file))
            return cookie_file

        with (
            patch.object(photodownload, "YoutubeDL", FakeYoutubeDL),
            patch.object(
                photodownload, "write_instagram_cookie_file", side_effect=write_cookie
            ),
            patch.dict(os.environ, {"INSTAGRAM_COOKIES": "sessionid=test-value"}),
        ):
            covers = photodownload.download_video_cover(
                "https://www.instagram.com/reel/example/", str(self.download_dir)
            )

        self.assertEqual([Path(path).read_bytes() for path in covers], [b"cover"])
        self.assertTrue(ydl_instances[0].download)
        self.assertTrue(ydl_instances[0].options["skip_download"])
        self.assertTrue(ydl_instances[0].options["writethumbnail"])
        self.assertFalse(cookie_files[0].exists())

    def test_video_permalink_uses_cover_without_gallery_download(self):
        cover = Mock(return_value=["cover.jpg"])
        photos = Mock()
        with (
            patch.object(photodownload, "download_video_cover", cover),
            patch.object(photodownload, "download_instagram_photos", photos),
        ):
            result = photodownload.download_media_assets(
                "https://www.instagram.com/reel/example/", str(self.download_dir)
            )

        self.assertEqual(result, ["cover.jpg"])
        cover.assert_called_once()
        photos.assert_not_called()

    def test_post_without_still_images_falls_back_to_video_cover(self):
        cover = Mock(return_value=["cover.jpg"])
        with (
            patch.object(
                photodownload,
                "download_instagram_photos",
                side_effect=FileNotFoundError("no stills"),
            ),
            patch.object(photodownload, "download_video_cover", cover),
        ):
            result = photodownload.download_media_assets(
                "https://www.instagram.com/p/video-post/", str(self.download_dir)
            )

        self.assertEqual(result, ["cover.jpg"])
        cover.assert_called_once()

    def test_non_instagram_video_url_downloads_its_cover(self):
        cover = Mock(return_value=["cover.jpg"])
        photos = Mock()
        with (
            patch.object(photodownload, "download_video_cover", cover),
            patch.object(photodownload, "download_instagram_photos", photos),
        ):
            result = photodownload.download_media_assets(
                "https://www.youtube.com/watch?v=example", str(self.download_dir)
            )

        self.assertEqual(result, ["cover.jpg"])
        cover.assert_called_once()
        photos.assert_not_called()

    def test_extension_setup_registers_photo_cog(self):
        bot = SimpleNamespace(add_cog=AsyncMock())
        with patch.dict(os.environ, {"BOT_DATA_DIR": str(self.download_dir)}):
            asyncio.run(photodownload.setup(bot))

        bot.add_cog.assert_awaited_once()
        self.assertIsInstance(
            bot.add_cog.await_args.args[0], photodownload.PhotoDownload
        )


if __name__ == "__main__":
    unittest.main()
