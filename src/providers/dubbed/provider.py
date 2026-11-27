"""Combined dubbed provider: one movie picker fed by both dubbed catalogues."""

import asyncio
from dataclasses import dataclass

import httpx
from rich.console import Console

from src.logger import Logger
from src.providers.base import Provider, ProviderRequest
from src.providers.isaidub import IsaidubProvider
from src.providers.moviesda import MoviesdaProvider
from src.scraper import Link, ScrapeError


console = Console()


@dataclass(frozen=True)
class TaggedLink(Link):
    """A movie link tagged with its source for the picker."""

    source: str = ""


class DubbedProvider(Provider):
    """`--tamil --dubbed` searches moviesda and isaidub and merges the results.

    Moviesda carries Indian-language dubs (malayalam, bollywood, ...); isaidub
    carries overseas dubs (hollywood, china, japan, ...). The old `list-dubbed`
    command covered both, so the flag must query both sources as well.
    """

    def __init__(self, config):
        super().__init__(config)
        self.moviesda = MoviesdaProvider(config)
        self.isaidub = IsaidubProvider(config)
        self.warnings: list[str] = []

    def label(self, link: Link) -> str:
        source = getattr(link, "source", "")
        return f"[{source}] {link.title}" if source else link.title

    async def list_movies(self, client: httpx.AsyncClient,
                          request: ProviderRequest) -> list[Link]:
        if request.latest:
            raise ValueError("--latest is only supported by the moviesda provider.")
        self.validate_search(request.query, request.year)

        results = await asyncio.gather(
            self.moviesda.dubbed_movies(client, request),
            self.isaidub.list_movies(client, request),
            return_exceptions=True,
        )
        self.warnings = []
        movies: list[Link] = []
        for source, result in zip(("Moviesda", "Isaidub"), results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, ScrapeError):
                message = (f"{source} dubbed catalogue could not be loaded; "
                           "showing results from the other source.")
                Logger.log(f"{source} dubbed catalogue failed: {result}")
                self.warnings.append(message)
                console.print(f"[yellow]{message}[/yellow]")
                continue
            if isinstance(result, Exception):
                raise result
            movies.extend(TaggedLink(link.title, link.url, link.referer, source)
                          for link in result)
        return movies
