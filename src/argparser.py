import argparse


class ArgParse:
    def __init__(self):
        parser = argparse.ArgumentParser(
            prog="eiga-cli",
            description="Browse, stream and download Tamil movies."
        )

        # provider selection
        parser.add_argument(
            "--tamil",
            action="store_true",
            help="Use the Tamil source (moviesda; both sources with --dubbed)"
        )

        parser.add_argument(
            "--dubbed",
            action="store_true",
            help="Search both moviesda and isaidub dubbed catalogues (requires --search)"
        )

        parser.add_argument(
            "--latest",
            action="store_true",
            help="Show latest moviesda releases"
        )

        # search
        parser.add_argument(
            "-s", "--search",
            nargs="+",
            metavar="MOVIE",
            help="Search movie"
        )

        # year
        parser.add_argument(
            "-y", "--year",
            type=str,
            metavar="YEAR",
            help="Movie year"
        )

        # play/download
        group = parser.add_mutually_exclusive_group()

        group.add_argument(
            "-p", "--play",
            action="store_true",
            help="Stream movie"
        )

        group.add_argument(
            "-d", "--download",
            action="store_true",
            help="Download movie (default)"
        )

        self.parser = parser

    def parse(self):
        args = self.parser.parse_args()
        if not args.tamil:
            self.parser.error("Choose a source with --tamil (add --dubbed for isaidub).")
        if args.dubbed and args.latest:
            self.parser.error("--tamil --dubbed --latest is not supported yet.")
        if args.latest and (args.search or args.year):
            self.parser.error("--latest cannot be combined with --search or --year.")
        if args.year and not args.search:
            self.parser.error("--year requires --search.")
        if args.dubbed and not args.search:
            self.parser.error("--dubbed requires --search.")
        if not args.search and not args.latest:
            self.parser.error("Enter --tamil --search MOVIE or --tamil --latest.")

        self.query = " ".join(args.search) if args.search else None
        self.year = args.year
        self.latest = args.latest
        self.dubbed = args.dubbed

        # Download is the default
        self.download = not args.play

        return self
