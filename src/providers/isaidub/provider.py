"""Isaidub provider: dubbed catalogue search, English movies and dubbed listings."""

import re

import httpx

from src.providers.base import Provider, ProviderRequest
from src.scraper import Link, ScrapeError
from src.utils import secure_url


class IsaidubProvider(Provider):
    """Handles `--tamil --dubbed` and `--english`, with a search query."""

    async def list_movies(self, client: httpx.AsyncClient,
                          request: ProviderRequest) -> list[Link]:
        if request.latest:
            # Rejected by the CLI; keep the provider explicit for direct callers.
            raise ValueError("--latest is only supported by the moviesda provider.")
        if request.english:
            return await self.english_movies(client, request)

        root = await self.catalogue_root(client, self.config.isaidub + "/",
                                         self.config.isaidub_atoz_dubbed_path)
        if request.query:
            needle = self.validate_search(request.query, request.year)
            path = (self.config.endpoint("isaidub_by_year_dubbed", year=request.year) if request.year
                    else self.config.endpoint("isaidub_by_letter_dubbed", first=needle[0]))
        else:
            path = self.config.dubbed_movies_path
        start = secure_url(root, path)
        if start is None:
            raise ScrapeError(root, "invalid dubbed catalogue path")
        return await self.collect(client, start, request.query, root)

    async def english_movies(self, client: httpx.AsyncClient,
                             request: ProviderRequest) -> list[Link]:
        """Search isaidub's English catalogue with the shared scraping flow."""
        self.validate_search(request.query, request.year)
        path = self.config.isaidub_english_movies_path
        root = await self.catalogue_root(client, self.config.isaidub + "/", path)
        start = secure_url(root, path)
        if start is None:
            raise ScrapeError(root, "invalid English catalogue path")
        movies = await self.collect(client, start, request.query, root)
        if request.year:
            # The catalogue has no year-based URL, so verify the year in titles.
            pattern = re.compile(rf"(?<!\d){re.escape(request.year)}(?!\d)")
            movies = [link for link in movies if pattern.search(link.title)]
        return movies
