"""Provider registry: CLI flags choose which source resolves a request."""

from src.config import Config
from src.providers.base import Provider, ProviderRequest, ResolvedLink, choose_link
from src.providers.dubbed import DubbedProvider
from src.providers.isaidub import IsaidubProvider
from src.providers.moviesda import MoviesdaProvider


def get_provider(config: Config, *, dubbed: bool = False,
                 english: bool = False) -> Provider:
    """`--tamil` selects moviesda, `--english` isaidub, `--dubbed` merges both."""
    if english:
        if dubbed:
            raise ValueError("--dubbed cannot be combined with --english.")
        return IsaidubProvider(config)
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
