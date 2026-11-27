import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from src.argparser import ArgParse


class ArgParseTests(unittest.TestCase):
    def parse(self, *argv: str) -> ArgParse:
        with patch("sys.argv", ["eiga-cli", *argv]):
            return ArgParse().parse()

    def assertRejected(self, *argv: str) -> None:
        with patch("sys.argv", ["eiga-cli", *argv]), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ArgParse().parse()

    def test_moviesda_search(self):
        args = self.parse("--tamil", "-s", "leo", "-y", "2023")
        self.assertEqual("leo", args.query)
        self.assertEqual("2023", args.year)
        self.assertFalse(args.dubbed)
        self.assertFalse(args.latest)
        self.assertTrue(args.download)

    def test_dubbed_search_and_play(self):
        args = self.parse("--tamil", "--dubbed", "--search", "Spider", "Man", "--play")
        self.assertEqual("Spider Man", args.query)
        self.assertTrue(args.dubbed)
        self.assertFalse(args.download)

    def test_latest_listing(self):
        latest = self.parse("--tamil", "--latest")
        self.assertTrue(latest.latest)
        self.assertIsNone(latest.query)
        self.assertFalse(latest.dubbed)

    def test_legacy_commands_and_missing_provider_are_rejected(self):
        self.assertRejected("list-latest")
        self.assertRejected("list-dubbed")
        self.assertRejected("-s", "leo")
        self.assertRejected("--dubbed", "-s", "leo")

    def test_unsupported_and_conflicting_flags_are_rejected(self):
        self.assertRejected("--tamil", "--dubbed", "--latest")
        self.assertRejected("--tamil", "--latest", "-s", "leo")
        self.assertRejected("--tamil", "--latest", "-y", "2023")
        self.assertRejected("--tamil", "-y", "2023")
        self.assertRejected("--tamil")
        self.assertRejected("--tamil", "--dubbed")
        self.assertRejected("--tamil", "-p", "-d")


if __name__ == "__main__":
    unittest.main()
