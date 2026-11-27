import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.argparser import ArgParse
from src.config import Config
from src.providers import ProviderRequest, ResolvedLink


class RunTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_passes_selected_provider_result_to_media_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(Path(directory) / "missing", Path(directory) / "cache")
            with patch("sys.argv", ["eiga-cli", "--tamil", "--dubbed", "-s", "leo", "-y", "2023"]):
                args = ArgParse().parse()
            provider = AsyncMock()
            provider.resolve.return_value = ResolvedLink(
                "https://cdn.example/movie.mp4", "Leo", "https://site.example/page")
            with patch("main.get_provider", return_value=provider) as get_provider, \
                 patch("main.Media") as media_class:
                media_class.return_value.process.return_value = True
                from main import run
                self.assertEqual(0, await run(args, config))

        get_provider.assert_called_once_with(config, dubbed=True)
        provider.resolve.assert_awaited_once()
        client, request = provider.resolve.await_args.args
        self.assertIsNotNone(client)
        self.assertEqual(ProviderRequest("leo", "2023", False), request)
        media_class.assert_called_once()
        self.assertEqual("https://cdn.example/movie.mp4", media_class.call_args.args[0])
        self.assertEqual("Leo", media_class.call_args.args[1])
        self.assertEqual("https://site.example/page", media_class.call_args.args[3]["Referer"])


if __name__ == "__main__":
    unittest.main()
