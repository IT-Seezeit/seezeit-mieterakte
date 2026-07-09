from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from src.nextcloud_client import NextcloudClient


class EnsureFolderTests(TestCase):
    def setUp(self) -> None:
        settings = SimpleNamespace(
            create_folders=True,
            nextcloud_base_url="https://nextcloud.invalid",
            nextcloud_username="technical-user",
            nextcloud_app_password="secret",
        )
        safety = SimpleNamespace(dry_run=False)
        self.client = NextcloudClient(settings, safety)
        self.request = Mock()
        self.requests_patcher = patch(
            "src.nextcloud_client.requests",
            SimpleNamespace(request=self.request),
        )
        self.requests_patcher.start()
        self.addCleanup(self.requests_patcher.stop)

    def test_409_is_skipped_when_propfind_finds_folder(self) -> None:
        self.request.side_effect = [
            Mock(status_code=409, text="parent conflict"),
            Mock(status_code=207, text="multistatus"),
        ]

        result = self.client.ensure_folder("team/1160_residence")

        self.assertFalse(result["created"])
        self.assertTrue(result["skipped_existing"])
        self.assertEqual(self.request.call_args_list[1].args[0], "PROPFIND")
        self.assertEqual(self.request.call_args_list[1].kwargs["headers"], {"Depth": "0"})

    def test_409_raises_when_propfind_does_not_find_folder(self) -> None:
        self.request.side_effect = [
            Mock(status_code=409, text="missing parent"),
            Mock(status_code=404, text="not found"),
        ]

        with self.assertRaisesRegex(RuntimeError, "HTTP 409; response body: missing parent"):
            self.client.ensure_folder("team/1160_residence")

    def test_200_and_201_are_created(self) -> None:
        for status_code in (200, 201):
            with self.subTest(status_code=status_code):
                self.request.return_value = Mock(status_code=status_code, text="")
                result = self.client.ensure_folder("team/1160_residence")
                self.assertTrue(result["created"])
                self.assertFalse(result["skipped_existing"])

    def test_405_is_skipped(self) -> None:
        self.request.return_value = Mock(status_code=405, text="")

        result = self.client.ensure_folder("team/1160_residence")

        self.assertFalse(result["created"])
        self.assertTrue(result["skipped_existing"])

    def test_other_status_raises_runtime_error_with_body(self) -> None:
        self.request.return_value = Mock(status_code=500, text="server failure")

        with self.assertRaisesRegex(RuntimeError, "HTTP 500; response body: server failure"):
            self.client.ensure_folder("team/1160_residence")
