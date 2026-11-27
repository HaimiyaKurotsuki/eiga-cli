"""Shared provider contract and the source-independent resolution flow.

A provider owns everything that happens before the media layer: finding movie
choices, letting the user pick one, and walking release/quality/server pages
until a final downloadable URL is reached. Downstream code only receives that
resolved link.
"""

import re
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import httpx
from InquirerPy import inquirer
from InquirerPy.base import Choice
from rich.console import Console

from src.cache import CatalogueCache
from src.config import Config
from src.scraper import Link, ScrapeError, Scraper
from src.utils import canonical_url, normalized, secure_url


console = Console()

MAX_PAGES = 80
MAX_CHOICE_PAGES = 50
MAX_RESOLVE_HOPS = 25


@dataclass(frozen=True)
class ProviderRequest:
    """One input shape for every provider; each provider interprets it."""

    query: str | None = None
    year: str | None = None
    latest: bool = False


@dataclass(frozen=True)
class ResolvedLink:
    """Final media URL plus the metadata the media layer needs."""

    url: str
    title: str
    referer: str = ""


async def choose_link(message: str, links: list[Link],
                      labels: list[str] | None = None) -> Link:
    """Keep Link objects out of InquirerPy's recursive Choice conversion."""
    names = labels if labels is not None else [link.title for link in links]
    selected = await inquirer.fuzzy(
        message=message,
        choices=[Choice(value=index, name=name) for index, name in enumerate(names)],
    ).execute_async()
    if not isinstance(selected, int) or not 0 <= selected < len(links):
        raise ValueError("No item selected.")
    return links[selected]


class Provider(ABC):
    def __init__(self, config: Config):
        self.config = config
        self.scraper = Scraper()
        self.cache = CatalogueCache(config.cache_path.parent / "catalogue")

    @abstractmethod
    async def list_movies(self, client: httpx.AsyncClient,
                          request: ProviderRequest) -> list[Link]:
        """Return the movie choices this provider offers for the request."""

    def label(self, link: Link) -> str:
        """Display text for a movie choice; overrides can tag the source."""
        return link.title

    async def resolve(self, client: httpx.AsyncClient,
                      request: ProviderRequest) -> ResolvedLink:
        """Run the full interactive flow and hand back the final media link."""
        movies = await self.list_movies(client, request)
        if not movies:
            raise ValueError("No movies found. Try another title, year or source.")
        chosen = await choose_link("Select a movie (type to filter):", movies,
                                   labels=[self.label(link) for link in movies])
        media = await self.resolve_link(client, chosen)
        return ResolvedLink(media.url, chosen.title, media.referer)

    @staticmethod
    def validate_search(query: str | None, year: str | None) -> str:
        needle = normalized(query or "")
        if not needle:
            raise ValueError("Enter a movie title.")
        if year and not re.fullmatch(r"(?:19|20)\d{2}", year):
            raise ValueError("Enter a four-digit release year.")
        if not year and not ("a" <= needle[0] <= "z"):
            raise ValueError("Add a release year for titles starting with a number or Tamil letter.")
        return needle

    async def catalogue_root(self, client: httpx.AsyncClient, home_url: str,
                             category: str) -> str:
        """Home page may redirect to the real catalogue host or link the A-Z category."""
        page = await self.scraper.fetch_page(client, home_url)
        for link in self.scraper.links(page, "a[href]"):
            if urlsplit(link.url).path == category:
                return link.url
        return page.url

    async def collect(self, client: httpx.AsyncClient, start: str,
                      query: str | None = None, referer: str = "") -> list[Link]:
        pending = deque([start])
        visited = set()
        cached = self.cache.load(start)
        if cached is not None:
            needle = normalized(query) if query else None
            return [link for link in cached if needle is None or needle in normalized(link.title)]
        movies = {}
        failures = 0
        needle = normalized(query) if query else None
        while pending and len(visited) < MAX_PAGES:
            url = pending.popleft()
            if url in visited:
                continue
            visited.add(url)
            try:
                page = await self.scraper.fetch_page(client, url, referer)
            except ScrapeError:
                if len(visited) == 1:
                    raise
                failures += 1
                continue
            for link in self.scraper.entries(page, self.config.junks):
                movies.setdefault(link.url, link)
            for page_url in self.scraper.pages(page):
                if page_url not in visited and page_url not in pending:
                    pending.append(page_url)
        if pending:
            console.print("[yellow]Search reached 80 pages. Add a year to narrow it.[/yellow]")
        if failures:
            console.print(f"[yellow]{failures} catalogue pages could not be loaded; results may be incomplete.[/yellow]")
        result = list(movies.values())
        if not failures and not pending:
            self.cache.save(start, result)
        return [link for link in result if needle is None or needle in normalized(link.title)]

    @staticmethod
    def _same_listing(url: str, first_url: str) -> bool:
        """Keep crawling within one listing: same path, or a numeric path suffix.

        Mirrors TamizhFlix's encodedPath rule: `/season/v/2` and `/season/v/page/2`
        belong to `/season/v`, but `/season/v2/` and other hosts do not.
        """
        first = urlsplit(first_url)
        candidate = urlsplit(url)
        if candidate.hostname != first.hostname:
            return False
        if candidate.path == first.path:
            return True
        prefix = first.path.rstrip("/") + "/"
        if not candidate.path.startswith(prefix):
            return False
        suffix = candidate.path[len(prefix):].rstrip("/")
        return bool(re.fullmatch(r"(?:page/)?\d+", suffix))

    @staticmethod
    def _page_label(url: str) -> str:
        """Label an unreached page from `?page=` or a path-style page segment."""
        parts = urlsplit(url)
        number = parse_qs(parts.query).get("page", [None])[0]
        if not number:
            number = next((segment for segment in reversed(parts.path.split("/")) if segment), "?")
        return number or "?"

    async def _paginated_choices(self, client: httpx.AsyncClient, first_page,
                                 first_choices: list[Link]) -> list[Link]:
        """Include episode/file choices on later pages of a release listing."""
        cache_key = first_page.url + "#release-choices"
        cached = self.cache.load(cache_key)
        if cached is not None:
            return cached
        found = {link.url: link for link in first_choices}
        pending = deque(self.scraper.pages(first_page))
        visited = {first_page.url}
        unavailable = []
        while pending and len(visited) < MAX_CHOICE_PAGES:
            url = pending.popleft()
            if url in visited or not self._same_listing(url, first_page.url):
                continue
            visited.add(url)
            try:
                page = await self.scraper.fetch_page(client, url, first_page.url)
            except ScrapeError:
                unavailable.append(url)
                continue
            if page.is_media:
                continue
            for link in self.scraper.choices(page, self.config.junks):
                found.setdefault(link.url, link)
            for next_url in self.scraper.pages(page):
                if next_url not in visited and next_url not in pending:
                    pending.append(next_url)
        if unavailable or pending:
            console.print("[yellow]Some episode pages could not be loaded. You can open them from the list.[/yellow]")
            for url in dict.fromkeys(unavailable + list(pending)):
                found.setdefault(url, Link(f"Open episode page {self._page_label(url)}",
                                           url, first_page.url))
        result = list(found.values())
        if not unavailable and not pending:
            self.cache.save(cache_key, result)
        return result

    async def resolve_link(self, client: httpx.AsyncClient, initial: Link) -> Link:
        """Walk release, quality and server choices until a media URL is reached."""
        current = initial
        visited = set()
        server_backups: list[Link] = []
        for _ in range(MAX_RESOLVE_HOPS):
            try:
                if current.url in visited:
                    raise ScrapeError(current.url, "download links form a loop")
                visited.add(current.url)
                page = await self.scraper.fetch_page(client, current.url, current.referer)
                if page.is_hls:
                    raise ScrapeError(page.url,
                                      "This server offers HLS streaming only. Choose a regular movie file.")
                if page.is_media:
                    # Defensive canonicalization protects against legacy cache entries
                    # and callers that still hand us an unencoded media URL.
                    media_url = canonical_url(page.url) or page.url
                    return Link(current.title, media_url, current.referer)
                choices = self.scraper.choices(page, self.config.junks)
                pages = self.scraper.pages(page)
                if pages and choices:
                    choices = await self._paginated_choices(client, page, choices)
                choices = [link for link in choices
                           if link.url not in visited]
                if not choices:
                    raise ScrapeError(page.url, "no release, quality, or server links found")
                if len(choices) == 1:
                    current = choices[0]
                else:
                    selected = await choose_link("Choose release, quality or server:", choices)
                    if all(re.search(r"\b(?:server|mirror)\b", link.title, re.I)
                           for link in choices):
                        server_backups.extend(reversed([link for link in choices
                                                        if link.url != selected.url]))
                    current = selected
            except ScrapeError:
                while server_backups and server_backups[-1].url in visited:
                    server_backups.pop()
                if not server_backups:
                    raise
                current = server_backups.pop()
                console.print(f"[yellow]That server failed. Trying {current.title}.[/yellow]")
        raise ScrapeError(current.url, "too many download pages")
