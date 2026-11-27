"""Provider registry: CLI flags choose which source resolves a request."""

from src.config import Config
from src.providers.base import Provider, ProviderRequest, ResolvedLink, choose_link
from src.providers.dubbed import DubbedProvider
from src.providers.isaidub import IsaidubProvider
from src.providers.moviesda import MoviesdaProvider


def get_provider(config: Config, *, dubbed: bool = False) -> Provider:
    """`--tamil` selects moviesda; `--dubbed` merges moviesda and isaidub."""
    return DubbedProvider(config) if dubbed else MoviesdaProvider(config)


__all__ = [
    "get_provider",
    "Provider",
    "ProviderRequest",
    "ResolvedLink",
    "choose_link",
    "MoviesdaProvider",
    "IsaidubProvider",
    "DubbedProvider",
]
