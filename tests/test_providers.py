import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from src.config import Config
from src.providers import (
    DubbedProvider,
    IsaidubProvider,
    MoviesdaProvider,
    ProviderRequest,
    choose_link,
    get_provider,
)
from src.providers.dubbed.provider import TaggedLink
from src.scraper import Link, Page, ScrapeError


def test_config(directory: str) -> Config:
    root = Path(directory)
    return Config(root / "missing", root / "cache")


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_picker_returns_original_link_instead_of_dictionary(self):
        links = [Link("First", "https://site.example/first"),
                 Link("Second", "https://site.example/second")]
        with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
            fuzzy.return_value.execute_async = AsyncMock(return_value=1)
            selected = await choose_link("Choose:", links)
        self.assertIs(selected, links[1])
        self.assertEqual([0, 1], [choice.value for choice in fuzzy.call_args.kwargs["choices"]])

    async def test_provider_resolve_returns_selected_title_and_final_url(self):
        chosen = Link("Movie", "https://site.example/movie")
        media = Link("Movie", "https://site.example/file.mp4", chosen.url)
        with tempfile.TemporaryDirectory() as directory:
            provider = MoviesdaProvider(test_config(directory))
            with patch("src.providers.base.inquirer.fuzzy") as fuzzy, \
                 patch.object(provider, "list_movies", new=AsyncMock(return_value=[chosen])), \
                 patch.object(provider, "resolve_link", new=AsyncMock(return_value=media)) as resolver:
                fuzzy.return_value.execute_async = AsyncMock(return_value=0)
                resolved = await provider.resolve(None, ProviderRequest(query="movie"))
        self.assertIs(resolver.await_args.args[1], chosen)
        self.assertEqual("Movie", resolved.title)
        self.assertEqual(media.url, resolved.url)
        self.assertEqual(chosen.url, resolved.referer)

    async def test_empty_provider_results_raise_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = MoviesdaProvider(test_config(directory))
            with patch.object(provider, "list_movies", new=AsyncMock(return_value=[])):
                with self.assertRaisesRegex(ValueError, "No movies found"):
                    await provider.resolve(None, ProviderRequest(query="missing"))

    async def test_multiple_servers_use_original_link(self):
        def handler(request):
            if request.url.path == "/start":
                return httpx.Response(200, text="""<div class=dlink>
                    <a href='/server1'>Server 1</a><a href='/server2'>Server 2</a></div>""")
            return httpx.Response(200, headers={"Content-Type": "video/mp4"}, content=b"x")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                    fuzzy.return_value.execute_async = AsyncMock(return_value=1)
                    media = await MoviesdaProvider(test_config(directory)).resolve_link(
                        client, Link("Movie", "https://site.example/start"))
        self.assertEqual("https://site.example/server2", media.url)
        self.assertEqual([0, 1], [choice.value for choice in fuzzy.call_args.kwargs["choices"]])

    async def test_failed_server_uses_another_server(self):
        def handler(request):
            if request.url.path == "/start":
                return httpx.Response(200, text="""<div class=dlink>
                    <a href='/server1'>Download Server 1</a>
                    <a href='/server2'>Download Server 2</a></div>""")
            if request.url.path == "/server1":
                return httpx.Response(404)
            return httpx.Response(200, headers={"Content-Type": "video/mp4"}, content=b"x")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                    fuzzy.return_value.execute_async = AsyncMock(return_value=0)
                    media = await MoviesdaProvider(test_config(directory)).resolve_link(
                        client, Link("Movie", "https://site.example/start"))
        self.assertEqual("https://site.example/server2", media.url)

    async def test_series_episodes_include_later_pages(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if request.url.path == "/show":
                return httpx.Response(200, text="<div class=f><a href='/season'>Season 01</a></div>")
            if request.url.path == "/season":
                number = request.url.params.get("page", "1")
                if number == "1":
                    body = """<div class=f><a href='/episode4'>Epi 4</a></div>
                        <div class=f><a href='/episode3'>Epi 3</a></div>
                        <div class=pagination><a href='?page=2'>2</a></div>"""
                elif number == "2":
                    body = """<div class=f><a href='/episode2'>Epi 2</a></div>
                        <div class=pagination><a href='?page=3'>3</a></div>"""
                else:
                    body = "<div class=f><a href='/episode1'>Epi 1</a></div>"
                return httpx.Response(200, text=body)
            if request.url.path == "/episode1":
                return httpx.Response(302, headers={"Location": "https://cdn.example/episode1.mp4"})
            raise AssertionError("Unexpected URL or attempted media download")

        with tempfile.TemporaryDirectory() as directory:
            config = test_config(directory)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                    fuzzy.return_value.execute_async = AsyncMock(return_value=3)
                    media = await MoviesdaProvider(config).resolve_link(
                        client, Link("Show", "https://site.example/show"))
                    again = await MoviesdaProvider(config).resolve_link(
                        client, Link("Show", "https://site.example/show"))
        self.assertEqual("https://cdn.example/episode1.mp4", media.url)
        self.assertEqual(media.url, again.url)
        self.assertIn("https://site.example/season?page=2", calls)
        self.assertIn("https://site.example/season?page=3", calls)
        self.assertEqual(1, calls.count("https://site.example/season?page=2"))
        self.assertEqual(4, len(fuzzy.call_args.kwargs["choices"]))

    async def test_older_movie_gateway_chain_reaches_redirected_file(self):
        steps = {
            "/nanban": "<div class=f><a href='/format'>Mp4 HQ (Single Part)</a></div>",
            "/format": "<div class=dlink><a href='/download'>Nanban (2012) Single Part</a></div>",
            "/download": "<div class=dlink><a href='/gateway1'>Download Server 1</a></div>",
            "/gateway1": "<div class=dlink><a href='/gateway2'>Download Server 1</a></div>",
            "/gateway2": "<div class=dlink><a href='/final'>Download Server 1</a></div>",
        }

        def handler(request):
            if request.url.path == "/final":
                return httpx.Response(302, headers={
                    "Location": "https://cdn.example/Nanban%20%282012%29.mp4?signature=abc"})
            if request.url.path in steps:
                return httpx.Response(200, text=steps[request.url.path])
            raise AssertionError("The movie file should not be fetched")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                media = await MoviesdaProvider(test_config(directory)).resolve_link(
                    client, Link("Nanban (2012)", "https://site.example/nanban"))
        self.assertEqual("https://cdn.example/Nanban%20%282012%29.mp4?signature=abc", media.url)

    async def test_isaidub_search_discovers_other_host_and_later_page(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            path = request.url.path
            if request.url.host == "isaiidub.com":
                return httpx.Response(200, text="""
                    <a href='https://catalogue.example/tamil-atoz-dubbed-movies/'>Tamil A-Z Dubbed Movies</a>""")
            if request.url.query:
                return httpx.Response(200, text="<div class=f><a href='/virus/'>Virus (1999)</a></div>")
            return httpx.Response(200, text="""
                <div class=f><a href='/other/'>Other (1999)</a></div>
                <div class=pagination><a href='?page=2'>2</a></div>""")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await IsaidubProvider(test_config(directory)).list_movies(
                    client, ProviderRequest(query="virus"))
        self.assertEqual("https://catalogue.example/virus/", result[0].url)
        self.assertIn("https://catalogue.example/tamil-atoz-dubbed-movies/v?page=2", calls)

    async def test_isaidub_without_query_lists_the_dubbed_endpoint(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            path = request.url.path
            if path == "/":
                return httpx.Response(200, text="<a href='/tamil-atoz-dubbed-movies/'>A-Z</a>")
            return httpx.Response(200, text="<div class=f><a href='/movie/'>Dubbed Movie</a></div>")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                provider = IsaidubProvider(test_config(directory))
                result = await provider.list_movies(client, ProviderRequest())
        self.assertEqual("https://isaiidub.com/movie/", result[0].url)
        self.assertIn("https://isaiidub.com/tamil-dubbed-movies/", calls)

    async def test_english_search_uses_shared_pagination_and_verifies_year(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if request.url.host == "isaiidub.com":
                return httpx.Response(200, text="""
                    <a href='https://catalogue.example/movie/hollywood-movies-in-english/'>English Movies</a>""")
            if request.url.query:
                return httpx.Response(200, text="""
                    <div class=f><a href='/avatar-2009-hd/'>Avatar (2009) HD</a></div>""")
            return httpx.Response(200, text="""
                <div class=f><a href='/avatar-2022/'>Avatar (2022)</a>
                <a href='/avatar-2009/'>Avatar (2009)</a></div>
                <div class=pagination><a href='?page=2'>2</a></div>""")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await IsaidubProvider(test_config(directory)).list_movies(
                    client, ProviderRequest(query="avatar", year="2009", english=True))
        self.assertEqual(["https://catalogue.example/avatar-2009/",
                          "https://catalogue.example/avatar-2009-hd/"],
                         [link.url for link in result])
        self.assertIn("https://catalogue.example/movie/hollywood-movies-in-english/", calls)
        self.assertIn("https://catalogue.example/movie/hollywood-movies-in-english/?page=2", calls)

    async def test_english_catalogue_path_comes_from_config(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if request.url.path == "/":
                return httpx.Response(200, text="<html></html>")
            return httpx.Response(200, text="<div class=f><a href='/avatar/'>Avatar</a></div>")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local.json"
            local.write_text(json.dumps({
                "endpoints": {"isaidub_english_movies": "/english/hollywood/"},
            }))
            config = Config(local, root / "cache.json")
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await IsaidubProvider(config).list_movies(
                    client, ProviderRequest(query="avatar", english=True))
        self.assertIn("https://isaiidub.com/english/hollywood/", calls)
        self.assertEqual("https://isaiidub.com/avatar/", result[0].url)

    def test_provider_registry_selects_english_source(self):
        with tempfile.TemporaryDirectory() as directory:
            config = test_config(directory)
            self.assertIsInstance(get_provider(config, english=True), IsaidubProvider)
            self.assertIsInstance(get_provider(config), MoviesdaProvider)
            with self.assertRaisesRegex(ValueError, "cannot be combined"):
                get_provider(config, english=True, dubbed=True)

    async def test_moviesda_latest_uses_the_home_endpoint(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(200, text="""
                <div class=latest><strong>New Release</strong>
                  <a class=green href='/new-release/'>Download Now</a></div>""")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await MoviesdaProvider(test_config(directory)).list_movies(
                    client, ProviderRequest(latest=True))
        self.assertEqual("https://moviesda.ski/new-release/", result[0].url)
        self.assertEqual(["https://moviesda.ski/home.html"], calls)

    async def test_isaidub_rejects_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = IsaidubProvider(test_config(directory))
            with self.assertRaisesRegex(ValueError, "only supported by the moviesda provider"):
                await provider.list_movies(None, ProviderRequest(latest=True))

    async def test_dubbed_provider_merges_both_sources_with_source_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = DubbedProvider(test_config(directory))
            with patch.object(provider.moviesda, "dubbed_movies", new=AsyncMock(
                    return_value=[Link("Indian Dub", "https://moviesda.ski/indian/")])), \
                 patch.object(provider.isaidub, "list_movies", new=AsyncMock(
                     return_value=[Link("Overseas Dub", "https://isaiidub.com/overseas/")])):
                movies = await provider.list_movies(
                    None, ProviderRequest(query="dub", year="2026"))
        self.assertEqual(2, len(movies))
        self.assertEqual(["[Moviesda] Indian Dub", "[Isaidub] Overseas Dub"],
                         [provider.label(movie) for movie in movies])

    async def test_dubbed_provider_keeps_duplicate_titles_from_both_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = DubbedProvider(test_config(directory))
            with patch.object(provider.moviesda, "dubbed_movies", new=AsyncMock(
                    return_value=[Link("Virus", "https://moviesda.ski/virus/")])), \
                 patch.object(provider.isaidub, "list_movies", new=AsyncMock(
                     return_value=[Link("Virus", "https://isaiidub.com/virus/")])):
                movies = await provider.list_movies(None, ProviderRequest(query="virus"))
        self.assertEqual(["https://moviesda.ski/virus/", "https://isaiidub.com/virus/"],
                         [movie.url for movie in movies])

    async def test_dubbed_provider_warns_and_keeps_working_source(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = DubbedProvider(test_config(directory))
            failure = ScrapeError("https://isaiidub.com/", "offline")
            with patch.object(provider.moviesda, "dubbed_movies", new=AsyncMock(
                    return_value=[Link("Indian Dub", "https://moviesda.ski/indian/")])), \
                 patch.object(provider.isaidub, "list_movies", new=AsyncMock(
                     side_effect=failure)), \
                 patch("src.providers.dubbed.provider.console") as console:
                movies = await provider.list_movies(None, ProviderRequest(query="dub"))
        self.assertEqual("https://moviesda.ski/indian/", movies[0].url)
        self.assertEqual(1, len(provider.warnings))
        self.assertIn("Isaidub", provider.warnings[0])
        console.print.assert_called_once()

    async def test_dubbed_provider_uses_the_configured_moviesda_dubbed_endpoint(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if request.url.host == "moviesda.ski":
                if request.url.path == "/home.html":
                    return httpx.Response(200, text="<a href='/tamil-atoz-movies/'>A-Z</a>")
                return httpx.Response(200, text="<div class=f><a href='/indian/'>Indian Dub</a></div>")
            if request.url.path == "/":
                return httpx.Response(200, text="<a href='/tamil-atoz-dubbed-movies/'>A-Z</a>")
            return httpx.Response(200, text="<div class=f><a href='/overseas/'>Overseas Dub</a></div>")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                movies = await DubbedProvider(test_config(directory)).list_movies(
                    client, ProviderRequest(query="dub"))
        self.assertIn("https://moviesda.ski/tamil-dubbed-movies/", calls)
        self.assertIn("https://isaiidub.com/tamil-atoz-dubbed-movies/d", calls)
        self.assertEqual([movie.url for movie in movies],
                         ["https://moviesda.ski/indian/", "https://isaiidub.com/overseas/"])

    async def test_dubbed_picker_shows_source_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = DubbedProvider(test_config(directory))
            with patch.object(provider, "list_movies", new=AsyncMock(return_value=[
                    TaggedLink("Indian", "https://a.example", "", "Moviesda")])), \
                 patch.object(provider, "resolve_link", new=AsyncMock(
                     return_value=Link("Indian", "https://cdn.example/file.mp4"))), \
                 patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                fuzzy.return_value.execute_async = AsyncMock(return_value=0)
                resolved = await provider.resolve(None, ProviderRequest(query="dub"))
        self.assertEqual("https://cdn.example/file.mp4", resolved.url)
        self.assertEqual(["[Moviesda] Indian"],
                         [choice.name for choice in fuzzy.call_args.kwargs["choices"]])

    async def test_dubbed_provider_rejects_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = DubbedProvider(test_config(directory))
            with self.assertRaisesRegex(ValueError, "only supported by the moviesda provider"):
                await provider.list_movies(None, ProviderRequest(latest=True))

    async def test_resolver_follows_choices_to_verified_media(self):
        def handler(request):
            if request.url.path == "/start":
                return httpx.Response(200, text="<div class=folder><a href='/quality'>720p</a></div>")
            if request.url.path == "/quality":
                return httpx.Response(200, text="<div class=dlink><a href='/file'>Download server</a></div>")
            return httpx.Response(200, headers={"Content-Type": "video/mp4"}, content=b"x")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                media = await MoviesdaProvider(test_config(directory)).resolve_link(
                    client, Link("Movie", "https://site.example/start"))
        self.assertEqual("https://site.example/file", media.url)
        self.assertEqual("https://site.example/quality", media.referer)

    async def test_first_page_failure_propagates(self):
        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                    httpx.Response(503))) as client:
                with self.assertRaises(ScrapeError):
                    await MoviesdaProvider(test_config(directory)).list_movies(
                        client, ProviderRequest(query="leo"))

    async def test_complete_catalogue_is_reused_for_repeat_search(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(200, text="<div class=f><a href='/leo/'>Leo (2023)</a></div>")

        with tempfile.TemporaryDirectory() as directory:
            provider = MoviesdaProvider(test_config(directory))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                first = await provider.collect(client, "https://site.example/catalogue", "leo")
                second = await provider.collect(client, "https://site.example/catalogue", "leo")
        self.assertEqual(first, second)
        self.assertEqual(1, len(calls))

    async def test_path_style_pagination_collects_all_episodes_and_labels_failures(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            path = request.url.path
            if path == "/show":
                return httpx.Response(200, text="<div class=f><a href='/season/v'>Season 01</a></div>")
            if path == "/season/v":
                return httpx.Response(200, text="""<div class=dlink>
                    <a href='/ep1'>Epi 1</a><a href='/ep1'>Epi 1 duplicate</a></div>
                    <div class=pagination><a href='/season/v/2'>2</a>
                    <a href='/season/v2'>3</a></div>""")
            if path == "/season/v/2":
                return httpx.Response(200, text="""<div class=dlink><a href='/ep2'>Epi 2</a></div>
                    <div class=pagination><a href='/season/v/3'>3</a></div>""")
            if path == "/season/v/3":
                return httpx.Response(503)
            if path == "/ep2":
                return httpx.Response(302, headers={"Location": "https://cdn.example/ep2.mp4"})
            raise AssertionError(f"Unexpected request: {request.url}")

        with tempfile.TemporaryDirectory() as directory:
            config = test_config(directory)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                    fuzzy.return_value.execute_async = AsyncMock(return_value=1)
                    media = await MoviesdaProvider(config).resolve_link(
                        client, Link("Show", "https://site.example/show"))
                    labels = [choice.name for choice in fuzzy.call_args.kwargs["choices"]]
        self.assertEqual("https://cdn.example/ep2.mp4", media.url)
        self.assertIn("https://site.example/season/v/2", calls)
        self.assertIn("https://site.example/season/v/3", calls)
        self.assertNotIn("https://site.example/season/v2", calls)
        self.assertIn("Open episode page 3", labels)
        self.assertEqual(1, labels.count("Epi 1"))
        self.assertEqual(3, len(labels))

    async def test_pagination_triggered_by_choices_without_folder_entries(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if request.url.path == "/start" and not request.url.query:
                return httpx.Response(200, text="""<div class=dlink><a href='/e1'>Epi 1</a></div>
                    <div class=pagination><a href='?page=2'>2</a></div>""")
            if request.url.path == "/start" and request.url.query:
                return httpx.Response(200, text="<div class=dlink><a href='/e2'>Epi 2</a></div>")
            if request.url.path == "/e2":
                return httpx.Response(302, headers={"Location": "https://cdn.example/e2.mp4"})
            raise AssertionError(f"Unexpected request: {request.url}")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                    fuzzy.return_value.execute_async = AsyncMock(return_value=1)
                    media = await MoviesdaProvider(test_config(directory)).resolve_link(
                        client, Link("Show", "https://site.example/start"))
                    labels = [choice.name for choice in fuzzy.call_args.kwargs["choices"]]
        self.assertEqual("https://cdn.example/e2.mp4", media.url)
        self.assertIn("https://site.example/start?page=2", calls)
        self.assertEqual(["Epi 1", "Epi 2"], labels)

    async def test_complete_paginated_choices_are_cached(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            path = request.url.path
            if path == "/show":
                return httpx.Response(200, text="<div class=f><a href='/season/v'>Season 01</a></div>")
            if path == "/season/v":
                return httpx.Response(200, text="""<div class=dlink><a href='/ep1'>Epi 1</a></div>
                    <div class=pagination><a href='/season/v/2'>2</a></div>""")
            if path == "/season/v/2":
                return httpx.Response(200, text="<div class=dlink><a href='/ep2'>Epi 2</a></div>")
            if path == "/ep2":
                return httpx.Response(302, headers={"Location": "https://cdn.example/ep2.mp4"})
            raise AssertionError(f"Unexpected request: {request.url}")

        with tempfile.TemporaryDirectory() as directory:
            provider = MoviesdaProvider(test_config(directory))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                    fuzzy.return_value.execute_async = AsyncMock(return_value=1)
                    first = await provider.resolve_link(client, Link("Show", "https://site.example/show"))
                    second = await provider.resolve_link(client, Link("Show", "https://site.example/show"))
        self.assertEqual(first.url, second.url)
        self.assertEqual(1, calls.count("https://site.example/season/v/2"))

    async def test_hls_server_is_rejected_and_backup_server_is_used(self):
        def handler(request):
            if request.url.path == "/start":
                return httpx.Response(200, text="""<div class=dlink>
                    <a href='/hls'>Download Server 1</a><a href='/file'>Download Server 2</a></div>""")
            if request.url.path == "/hls":
                return httpx.Response(200, headers={"Content-Type": "application/vnd.apple.mpegurl"},
                                      text="#EXTM3U\n#EXT-X-ENDLIST\n")
            if request.url.path == "/file":
                return httpx.Response(200, headers={"Content-Type": "video/mp4"}, content=b"x")
            raise AssertionError(f"Unexpected request: {request.url}")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch("src.providers.base.inquirer.fuzzy") as fuzzy:
                    fuzzy.return_value.execute_async = AsyncMock(return_value=0)
                    media = await MoviesdaProvider(test_config(directory)).resolve_link(
                        client, Link("Movie", "https://site.example/start"))
        self.assertEqual("https://site.example/file", media.url)

    async def test_hls_only_server_reports_clear_error(self):
        def handler(request):
            if request.url.path == "/start":
                return httpx.Response(200, text="<div class=dlink><a href='/hls'>HLS server</a></div>")
            return httpx.Response(200, headers={"Content-Type": "application/x-mpegurl"},
                                  text="#EXTM3U\n")

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaisesRegex(ScrapeError, "HLS streaming only"):
                    await MoviesdaProvider(test_config(directory)).resolve_link(
                        client, Link("Movie", "https://site.example/start"))

    async def test_resolve_canonicalizes_legacy_raw_space_media_url(self):
        raw_page = Page("https://cdn.example/Tamil 2026 Movies/Epi 04).mp4?htag=a&etag=b",
                        None, "video/mp4")
        with tempfile.TemporaryDirectory() as directory:
            provider = MoviesdaProvider(test_config(directory))
            async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda _: httpx.Response(200))) as client:
                with patch.object(provider.scraper, "fetch_page",
                                  new=AsyncMock(return_value=raw_page)):
                    media = await provider.resolve_link(client, Link("Movie", "https://site.example/start"))
        self.assertEqual(
            "https://cdn.example/Tamil%202026%20Movies/Epi%2004).mp4?htag=a&etag=b",
            media.url,
        )


if __name__ == "__main__":
    unittest.main()
