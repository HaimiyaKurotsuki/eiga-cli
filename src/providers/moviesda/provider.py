"""Moviesda provider: Tamil catalogue search and latest releases."""

import httpx

from src.providers.base import Provider, ProviderRequest
from src.scraper import Link, ScrapeError
from src.utils import secure_url


class MoviesdaProvider(Provider):
    """Handles `--tamil` and `--tamil --latest`."""

    async def list_movies(self, client: httpx.AsyncClient,
                          request: ProviderRequest) -> list[Link]:
        if request.latest:
            page = await self.scraper.fetch_page(client, self.config.moviesda_home_endpoint)
            return self.scraper.latest(page)

        needle = self.validate_search(request.query, request.year)
        root = await self.catalogue_root(client, self.config.moviesda_home_endpoint,
                                         self.config.moviesda_atoz_path)
        path = (self.config.endpoint("moviesda_by_year", year=request.year) if request.year
                else self.config.endpoint("moviesda_by_letter", first=needle[0]))
        start = secure_url(root, path)
        if start is None:
            raise ScrapeError(root, "invalid catalogue path")
        return await self.collect(client, start, request.query, root)

    async def dubbed_movies(self, client: httpx.AsyncClient,
                            request: ProviderRequest) -> list[Link]:
        """List moviesda's dubbed catalogue, filtered by the search query."""
        self.validate_search(request.query, request.year)
        root = await self.catalogue_root(client, self.config.moviesda_home_endpoint,
                                         self.config.moviesda_atoz_path)
        start = secure_url(root, self.config.dubbed_movies_path)
        if start is None:
            raise ScrapeError(root, "invalid dubbed catalogue path")
        return await self.collect(client, start, request.query, root)
