"""eiga-cli entry point, including the installed console-script command."""

import asyncio
import sys
from urllib.request import Request

import httpx
from rich.console import Console

from src.argparser import ArgParse
from src.config import Config
from src.media import Media
from src.providers import ProviderRequest, get_provider
from src.scraper import ScrapeError


console = Console()


async def run(args: ArgParse, config: Config) -> int:
    provider = get_provider(config, dubbed=args.dubbed, english=args.english)
    request = ProviderRequest(query=args.query, year=args.year, latest=args.latest,
                              english=args.english)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30,
                                 headers=config.headers) as client:
        resolved = await provider.resolve(client, request)
        headers = dict(config.headers)
        if resolved.referer:
            headers["Referer"] = resolved.referer
        cookie_request = Request(resolved.url)
        client.cookies.jar.add_cookie_header(cookie_request)
        cookie = cookie_request.get_header("Cookie")
        if cookie:
            headers["Cookie"] = cookie
    media = Media(resolved.url, resolved.title, config.download_path, headers)
    return 0 if media.process(args.download) else 1


def main() -> int:
    try:
        args = ArgParse().parse()  # --help exits before any network request.
        config = Config()
        if not config.fetch_config():
            console.print("[yellow]Remote config unavailable; using saved domains.[/yellow]")
        return asyncio.run(run(args, config))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        return 130
    except (ScrapeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
