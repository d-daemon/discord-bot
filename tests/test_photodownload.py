import asyncio
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
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

    def test_single_photo_download_completes_private_response(self):
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                defer=AsyncMock(), is_done=Mock(return_value=True)
            ),
            followup=SimpleNamespace(send=AsyncMock()),
            channel=SimpleNamespace(send=AsyncMock()),
            user=SimpleNamespace(id=42, mention="<@42>"),
            edit_original_response=AsyncMock(),
        )
        send_photos = AsyncMock()
        with (
            patch.dict(os.environ, {"BOT_DATA_DIR": str(self.download_dir)}),
            patch.object(
                photodownload, "download_media_assets", return_value=["photo.jpg"]
            ),
            patch.object(photodownload, "send_photos", new=send_photos),
        ):
            cog = photodownload.PhotoDownload(SimpleNamespace())
            asyncio.run(type(cog).download_photo.callback(cog, interaction, URL))

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.edit_original_response.assert_awaited_once_with(
            content="Your photo was sent to the channel."
        )
        interaction.edit_original_response.return_value.delete.assert_awaited_once_with(
            delay=10
        )
        send_photos.assert_awaited_once_with(
            interaction.channel,
            interaction.user,
            ["photo.jpg"],
            "<@42> Here is your downloaded photo:",
        )

    def test_photo_selection_error_remains_ephemeral_after_defer(self):
        request_dir = self.download_dir / "request"
        request_dir.mkdir()
        owner = SimpleNamespace(id=42, mention="<@42>")
        original_interaction = SimpleNamespace(
            channel=SimpleNamespace(send=AsyncMock()), user=owner
        )
        view = photodownload.PhotoSelectionView(
            original_interaction, ["photo.jpg"], request_dir
        )
        prompt = SimpleNamespace(delete=AsyncMock())
        view.prompt_message = cast(Any, prompt)
        selection = view.children[0]
        selection._values = ["0"]
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                defer=AsyncMock(), is_done=Mock(return_value=True)
            ),
            user=owner,
            followup=SimpleNamespace(send=AsyncMock()),
            edit_original_response=AsyncMock(),
            message=SimpleNamespace(delete=AsyncMock()),
        )

        with (
            patch.object(
                photodownload,
                "send_photos",
                new_callable=AsyncMock,
                side_effect=RuntimeError("send failed"),
            ),
            patch.object(
                photodownload.asyncio, "sleep", new_callable=AsyncMock
            ) as sleep,
        ):
            asyncio.run(selection.callback(interaction))

        interaction.response.defer.assert_awaited_once_with(
            ephemeral=True, thinking=True
        )
        interaction.followup.send.assert_awaited_once_with(
            "The selected photo could not be sent.",
            ephemeral=True,
            delete_after=10,
        )
        prompt.delete.assert_awaited_once_with()
        sleep.assert_not_awaited()

    def test_selected_photo_deletes_ephemeral_prompt_after_three_seconds(self):
        request_dir = self.download_dir / "request"
        request_dir.mkdir()
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        view = photodownload.PhotoSelectionView(
            original, ["photo-1.jpg", "photo-2.jpg"], request_dir
        )
        prompt = SimpleNamespace(delete=AsyncMock())
        view.prompt_message = cast(Any, prompt)
        selection = view.children[0]
        selection._values = ["1"]
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),
            message=SimpleNamespace(delete=AsyncMock()),
        )
        calls = Mock()
        send = AsyncMock()
        sleep = AsyncMock()
        calls.attach_mock(send, "send")
        calls.attach_mock(sleep, "sleep")
        calls.attach_mock(prompt.delete, "delete")

        with (
            patch.object(photodownload, "send_photos", new=send),
            patch.object(photodownload.asyncio, "sleep", new=sleep),
        ):
            asyncio.run(selection.callback(interaction))

        self.assertEqual(
            calls.mock_calls,
            [
                unittest.mock.call.send(
                    original.channel,
                    owner,
                    ["photo-2.jpg"],
                    "<@42> Here is your selected photo:",
                ),
                unittest.mock.call.sleep(3),
                unittest.mock.call.delete(),
            ],
        )
        interaction.edit_original_response.assert_awaited_once_with(
            content="Your photo was sent to the channel."
        )
        interaction.message.delete.assert_not_awaited()
        self.assertFalse(request_dir.exists())

    def test_multiple_selected_photos_use_plural_responses(self):
        request_dir = self.download_dir / "request"
        request_dir.mkdir()
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        photos = ["photo-1.jpg", "photo-2.jpg"]
        view = photodownload.PhotoSelectionView(original, photos, request_dir)
        selection = view.children[0]
        selection._values = ["0", "1"]
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),
        )

        with patch.object(photodownload, "send_photos", new_callable=AsyncMock) as send:
            asyncio.run(selection.callback(interaction))

        send.assert_awaited_once_with(
            original.channel,
            owner,
            photos,
            "<@42> Here are your selected photos:",
        )
        interaction.edit_original_response.assert_awaited_once_with(
            content="Your photos were sent to the channel."
        )

    def test_multiple_selected_photos_use_plural_error(self):
        request_dir = self.download_dir / "request"
        request_dir.mkdir()
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        view = photodownload.PhotoSelectionView(
            original, ["photo-1.jpg", "photo-2.jpg"], request_dir
        )
        selection = view.children[0]
        selection._values = ["0", "1"]
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                defer=AsyncMock(), is_done=Mock(return_value=True)
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        with patch.object(
            photodownload,
            "send_photos",
            new_callable=AsyncMock,
            side_effect=RuntimeError("send failed"),
        ):
            asyncio.run(selection.callback(interaction))

        interaction.followup.send.assert_awaited_once_with(
            "The selected photos could not be sent.",
            ephemeral=True,
            delete_after=10,
        )

    def test_photo_selection_prompt_deletion_failure_is_logged(self):
        request_dir = self.download_dir / "request"
        request_dir.mkdir()
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        view = photodownload.PhotoSelectionView(original, ["photo.jpg"], request_dir)
        error = photodownload.discord.HTTPException(
            Mock(status=403, reason="Forbidden"), "Cannot delete prompt"
        )
        prompt = SimpleNamespace(delete=AsyncMock(side_effect=error))
        view.prompt_message = cast(Any, prompt)
        selection = view.children[0]
        selection._values = ["0"]
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),
        )

        with (
            patch.object(photodownload, "send_photos", new_callable=AsyncMock),
            patch.object(photodownload.asyncio, "sleep", new_callable=AsyncMock),
            self.assertLogs(photodownload.logger, level="ERROR") as logs,
        ):
            asyncio.run(selection.callback(interaction))

        prompt.delete.assert_awaited_once_with()
        self.assertIn("Failed to delete the photo selection", logs.output[0])
        self.assertFalse(request_dir.exists())

    @patch.object(photodownload.subprocess, "run")
    @patch.object(photodownload.shutil, "which", return_value="/usr/bin/gallery-dl")
    def test_carousel_photos_and_selection_follow_post_order(self, which, run):
        def gallery_dl(command, **kwargs):
            self.assertEqual(
                command[command.index("--filename") + 1], "{num:02}.{extension}"
            )
            output = Path(command[command.index("-d") + 1]) / "instagram"
            output.mkdir()
            for position in (3, 1, 2):
                (output / f"{position:02}.jpg").write_bytes(
                    f"photo {position}".encode()
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = gallery_dl
        with patch.dict(os.environ, {"INSTAGRAM_COOKIES": ""}):
            photos = photodownload.download_instagram_photos(
                URL, str(self.download_dir)
            )

        self.assertEqual(
            [Path(photo).read_bytes() for photo in photos],
            [b"photo 1", b"photo 2", b"photo 3"],
        )
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        view = photodownload.PhotoSelectionView(original, photos, self.download_dir)
        selection = view.children[0]
        self.assertEqual(
            [(option.label, option.value) for option in selection.options],
            [("Image 1", "0"), ("Image 2", "1"), ("Image 3", "2")],
        )
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),
            followup=SimpleNamespace(send=AsyncMock()),
            message=SimpleNamespace(delete=AsyncMock()),
        )
        with (
            patch.object(photodownload, "send_photos", new_callable=AsyncMock) as send,
        ):
            for index in range(3):
                with self.subTest(index=index):
                    view = photodownload.PhotoSelectionView(
                        original, photos, self.download_dir
                    )
                    selection = view.children[0]
                    selection._values = [str(index)]
                    with patch.object(view, "cleanup", new_callable=AsyncMock):
                        asyncio.run(selection.callback(interaction))
                    self.assertEqual(
                        Path(send.await_args.args[2][0]).read_bytes(),
                        f"photo {index + 1}".encode(),
                    )

    @patch.object(photodownload.subprocess, "run")
    @patch.object(photodownload.shutil, "which", return_value="/usr/bin/gallery-dl")
    def test_twenty_carousel_photos_remain_in_numeric_order(self, which, run):
        def gallery_dl(command, **kwargs):
            output = Path(command[command.index("-d") + 1]) / "instagram"
            output.mkdir()
            for position in range(20, 0, -1):
                (output / f"{position:02}.jpg").write_bytes(str(position).encode())
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = gallery_dl
        with patch.dict(os.environ, {"INSTAGRAM_COOKIES": ""}):
            photos = photodownload.download_instagram_photos(
                URL, str(self.download_dir)
            )
        self.assertEqual(
            [Path(photo).read_bytes() for photo in photos],
            [str(position).encode() for position in range(1, 21)],
        )

    def test_selection_is_limited_to_twenty_images(self):
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        photos = [f"photo-{index}.jpg" for index in range(25)]
        view = photodownload.PhotoSelectionView(original, photos, self.download_dir)
        selection = view.children[0]
        self.assertEqual(len(selection.options), 20)
        self.assertEqual(selection.max_values, 20)
        self.assertEqual(selection.options[-1].label, "Image 20")

    def test_cancel_selection_cleans_up_without_sending_photos(self):
        request_dir = self.download_dir / "request"
        request_dir.mkdir()
        photo_path = request_dir / "photo.jpg"
        photo_path.write_bytes(b"photo")
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        view = photodownload.PhotoSelectionView(
            original, [str(photo_path)], request_dir
        )
        cancel = cast(photodownload.PhotoSelectionCancel, view.children[1])
        interaction = SimpleNamespace(
            response=SimpleNamespace(edit_message=AsyncMock()),
            user=owner,
            message=SimpleNamespace(delete=AsyncMock()),
        )

        with patch.object(photodownload, "send_photos", new_callable=AsyncMock) as send:
            asyncio.run(cancel.callback(cast(Any, interaction)))
            asyncio.run(view.on_timeout())

        interaction.response.edit_message.assert_awaited_once_with(
            content="Photo selection canceled.", view=None, delete_after=5
        )
        interaction.message.delete.assert_awaited_once_with(delay=5)
        self.assertFalse(request_dir.exists())
        send.assert_not_awaited()

    def test_photo_selection_cancel_is_limited_to_requester(self):
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(channel=SimpleNamespace(), user=owner)
        view = photodownload.PhotoSelectionView(
            original, ["photo.jpg"], self.download_dir
        )
        unauthorized = SimpleNamespace(
            user=SimpleNamespace(id=43),
            response=SimpleNamespace(
                is_done=Mock(return_value=False), send_message=AsyncMock()
            ),
        )

        allowed = asyncio.run(view.interaction_check(unauthorized))

        self.assertFalse(allowed)
        unauthorized.response.send_message.assert_awaited_once_with(
            "This image selection is not for you.",
            ephemeral=True,
            delete_after=10,
        )

    def test_photo_selection_timeout_still_sends_all_photos(self):
        request_dir = self.download_dir / "request"
        request_dir.mkdir()
        photo_paths = [
            str(request_dir / "photo-1.jpg"),
            str(request_dir / "photo-2.jpg"),
        ]
        owner = SimpleNamespace(id=42, mention="<@42>")
        original = SimpleNamespace(
            channel=SimpleNamespace(send=AsyncMock()), user=owner
        )
        view = photodownload.PhotoSelectionView(original, photo_paths, request_dir)

        with patch.object(photodownload, "send_photos", new_callable=AsyncMock) as send:
            asyncio.run(view.on_timeout())

        send.assert_awaited_once_with(
            original.channel,
            owner,
            photo_paths,
            "<@42> No images were selected; here are all the photos:",
        )
        self.assertFalse(request_dir.exists())

    def test_carousel_prompt_states_twenty_image_limit(self):
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            channel=SimpleNamespace(send=AsyncMock()),
            user=SimpleNamespace(id=42, mention="<@42>"),
        )
        with (
            patch.dict(os.environ, {"BOT_DATA_DIR": str(self.download_dir)}),
            patch.object(
                photodownload,
                "download_media_assets",
                return_value=["photo-1.jpg", "photo-2.jpg"],
            ),
        ):
            cog = photodownload.PhotoDownload(SimpleNamespace())
            asyncio.run(type(cog).download_photo.callback(cog, interaction, URL))

        self.assertEqual(
            interaction.followup.send.await_args.args[0],
            "Choose image(s) to download.",
        )

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
