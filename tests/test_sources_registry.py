"""The sources registry: the list of portals the catalog may read.

No network here: the registry is data, and this file checks that it is
readable, strict and honest.
"""

from __future__ import annotations

import pytest

from scholarpath.registry import (
    TRUST_LEVELS,
    RegistryError,
    Source,
    default_registry_path,
    load_registry,
    parse_registry,
    registry_in_use,
    render_registry,
    user_registry_path,
    write_user_registry,
)

MINIMAL = """
version = 1

[[source]]
name = "Example Portal"
base_url = "https://example.gov/scholarships/"
country = "Wonderland"
trust_level = "government"
allowed_path_prefixes = ["/scholarships/"]
crawl_depth = 1
"""


def test_the_shipped_registry_is_readable() -> None:
    sources = load_registry(default_registry_path())
    assert sources, "the shipped registry must not be empty"
    for source in sources:
        assert source.name
        assert source.base_url.startswith("https://")
        assert source.country
        assert source.trust_level in TRUST_LEVELS
        assert source.allowed_path_prefixes
        assert 0 <= source.crawl_depth <= 5


def test_the_shipped_registry_holds_the_expected_portals() -> None:
    names = {source.name for source in load_registry(default_registry_path())}
    assert "Chevening Scholarships" in names
    assert "DAAD Scholarships (Germany)" in names
    assert "Fulbright Program (U.S. Department of State)" in names
    assert "Erasmus+ (European Commission)" in names
    assert "MEXT - Study in Japan (Ministry of Education)" in names
    assert "Commonwealth Scholarships in the UK (FCDO)" in names
    assert "Korea GKS - Study in Korea" in names
    assert "Turkiye Scholarships (Turkiye Burslari)" in names


def test_every_shipped_portal_is_on_its_own_domain() -> None:
    for source in load_registry(default_registry_path()):
        assert source.domain, source.name
        assert "." in source.domain, source.name
        assert source.domain not in ("localhost", "127.0.0.1")


def test_a_missing_prefix_is_refused() -> None:
    with pytest.raises(RegistryError) as excinfo:
        parse_registry(
            MINIMAL.replace('allowed_path_prefixes = ["/scholarships/"]', "")
        )
    assert "allowed_path_prefixes" in str(excinfo.value)


def test_an_unknown_trust_level_is_refused() -> None:
    with pytest.raises(RegistryError) as excinfo:
        parse_registry(MINIMAL.replace('trust_level = "government"', 'trust_level = "maybe"'))
    assert "trust_level" in str(excinfo.value)


def test_a_non_http_base_url_is_refused() -> None:
    with pytest.raises(RegistryError) as excinfo:
        parse_registry(
            MINIMAL.replace("https://example.gov", "file:///etc/passwd")
        )
    assert "http" in str(excinfo.value)


def test_credentials_in_a_base_url_are_refused() -> None:
    with pytest.raises(RegistryError) as excinfo:
        parse_registry(
            MINIMAL.replace("https://example.gov", "https://user:secret@example.gov")
        )
    assert "credential" in str(excinfo.value)


def test_an_unreasonable_crawl_depth_is_refused() -> None:
    with pytest.raises(RegistryError) as excinfo:
        parse_registry(MINIMAL.replace("crawl_depth = 1", "crawl_depth = 99"))
    assert "crawl_depth" in str(excinfo.value)


def test_the_same_portal_twice_is_refused() -> None:
    duplicate = """
[[source]]
name = "Example Portal again"
base_url = "https://example.gov/scholarships/"
country = "Wonderland"
trust_level = "official"
allowed_path_prefixes = ["/scholarships/"]
crawl_depth = 1
"""
    with pytest.raises(RegistryError) as excinfo:
        parse_registry(MINIMAL + duplicate)
    assert "twice" in str(excinfo.value)


def test_broken_toml_is_refused_with_the_reason() -> None:
    with pytest.raises(RegistryError) as excinfo:
        parse_registry("version = 1\n[[source]\nname = ")
    assert "Invalid TOML" in str(excinfo.value)


def test_an_empty_registry_is_refused() -> None:
    with pytest.raises(RegistryError):
        parse_registry("version = 1\n")


def test_an_unknown_version_is_refused() -> None:
    with pytest.raises(RegistryError) as excinfo:
        parse_registry(MINIMAL.replace("version = 1", "version = 99"))
    assert "version" in str(excinfo.value)


def test_path_prefixes_are_normalised_to_start_with_a_slash() -> None:
    source = parse_registry(
        MINIMAL.replace('allowed_path_prefixes = ["/scholarships/"]', 'allowed_path_prefixes = ["scholarships/"]')
    )[0]
    assert source.allowed_path_prefixes == ("/scholarships/",)


def test_a_source_only_allows_its_own_paths() -> None:
    source = parse_registry(MINIMAL)[0]
    assert source.allows_path("/scholarships/apply") is True
    assert source.allows_path("/other/") is False
    assert source.allows_url("https://example.gov/scholarships/apply") is True
    assert source.allows_url("https://example.gov/other") is False
    assert source.allows_url("https://elsewhere.gov/scholarships/") is False
    assert source.allows_url("javascript:alert(1)") is False


def test_the_user_copy_lives_next_to_the_config(tmp_path) -> None:
    path = user_registry_path(tmp_path)
    assert path.parent == tmp_path
    assert path.name == "sources_registry.toml"


def test_the_user_copy_is_written_from_the_shipped_default(tmp_path) -> None:
    path = write_user_registry(path=tmp_path / "sources_registry.toml")
    assert path.exists()
    sources = parse_registry(path.read_text(encoding="utf-8"))
    assert sources == load_registry(default_registry_path())


def test_the_user_copy_is_used_when_it_exists(tmp_path) -> None:
    path = tmp_path / "sources_registry.toml"
    path.write_text(MINIMAL, encoding="utf-8")
    sources = load_registry(path)
    assert [source.name for source in sources] == ["Example Portal"]
    loaded, used_path, is_user_copy = registry_in_use(path)
    assert is_user_copy is True
    assert used_path == path
    assert loaded[0].name == "Example Portal"


def test_a_broken_user_copy_is_not_replaced_by_the_default(tmp_path) -> None:
    path = tmp_path / "sources_registry.toml"
    path.write_text("version = 1\n[[source]]\nname = 'x'\n", encoding="utf-8")
    with pytest.raises(RegistryError):
        load_registry(path)


def test_a_registry_can_be_rendered_back_to_text() -> None:
    source = Source(
        name="Example Portal",
        base_url="https://example.gov/scholarships/",
        country="Wonderland",
        trust_level="government",
        allowed_path_prefixes=("/scholarships/",),
        crawl_depth=2,
    )
    text = render_registry([source])
    assert "[[source]]" in text
    assert parse_registry(text) == [source]
