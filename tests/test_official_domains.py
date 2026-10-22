"""Which domains count as official (G141).

The rule works on the *registrable* domain and matches exactly: a domain is
never recognised by a substring of its host.
"""

from __future__ import annotations

from scholarpath.websearch import (
    format_results,
    is_official_domain,
    parse_results,
    registrable_domain,
)


def test_the_registrable_domain_is_found() -> None:
    assert registrable_domain("www.university.edu") == "university.edu"
    assert registrable_domain("scholarships.university.ac.uk") == "university.ac.uk"
    assert registrable_domain("blog.example.com") == "example.com"
    assert registrable_domain("example.co.uk") == "example.co.uk"
    assert registrable_domain("") == ""


def test_academic_and_government_domains_are_official() -> None:
    assert is_official_domain("university.edu")
    assert is_official_domain("scholarships.university.edu")
    assert is_official_domain("university.ac.uk")
    assert is_official_domain("university.ac.jp")
    assert is_official_domain("gov.uk")
    assert is_official_domain("www.gov.uk")
    assert is_official_domain("scholarship.gov.in")
    assert is_official_domain("europa.eu")


def test_other_domains_are_not_official() -> None:
    assert not is_official_domain("chevening.org")
    assert not is_official_domain("blog.example.com")
    assert not is_official_domain("university.example")
    assert not is_official_domain("notgov.example")
    assert not is_official_domain("example.co.uk")


def test_government_conventions_outside_gov_count_as_official() -> None:
    """Governments do not all use "gov": Korea says "go.kr" (G178)."""
    assert is_official_domain("www.studyinkorea.go.kr")
    assert is_official_domain("studyinkorea.go.kr")
    assert is_official_domain("www.mofa.go.jp")
    assert is_official_domain("www.gov.go.id")
    assert is_official_domain("www.gc.ca")
    assert is_official_domain("www.gouv.fr")
    assert is_official_domain("www.gob.mx")
    assert is_official_domain("www.gob.pe")
    assert is_official_domain("www.admin.ch")
    assert is_official_domain("www.gv.at")
    assert is_official_domain("www.govt.nz")


def test_a_lookalike_of_a_government_domain_is_not_official() -> None:
    assert not is_official_domain("studyinkorea.go.kr.example.com")
    assert not is_official_domain("www.studyinkorea.go.kr.fake.net")
    assert not is_official_domain("go.kr.example.com")
    assert not is_official_domain("notgo.kr")
    assert not is_official_domain("www.gc.ca.example.org")


def test_the_match_is_on_the_registrable_domain_only() -> None:
    """A host that merely contains an official-looking part is not official."""
    assert not is_official_domain("university.edu.example.com")
    assert not is_official_domain("gov.uk.example.net")
    assert not is_official_domain("myuniversity.edu.example.org")
    assert not is_official_domain("example.com/university.edu")


def test_a_user_trusted_domain_is_marked_as_trusted() -> None:
    page = (
        "<a class='result-link' href='https://www.chevening.org/scholarships'>Chevening</a>"
        "<a class='result-link' href='https://blog.example.com/scholarship'>Blog</a>"
    )
    results = parse_results(page, trusted_domains=["chevening.org"])
    assert results[0].trusted is True
    assert results[0].official_looking is False
    assert results[1].trusted is False


def test_a_trusted_domain_is_matched_exactly() -> None:
    page = (
        "<a class='result-link' href='https://chevening.org.evil.example/x'>Fake</a>"
        "<a class='result-link' href='https://notchevening.org/x'>Other</a>"
    )
    results = parse_results(page, trusted_domains=["chevening.org"])
    assert all(result.trusted is False for result in results)


def test_trusted_domains_are_listed_first() -> None:
    page = (
        "<a class='result-link' href='https://blog.example.com/scholarship'>Blog</a>"
        "<a class='result-link' href='https://chevening.org/x'>Chevening</a>"
    )
    results = parse_results(page, trusted_domains=["chevening.org"])
    assert results[0].trusted is True


def test_the_block_says_which_kind_of_domain_it_is() -> None:
    results = parse_results(
        "<a class='result-link' href='https://university.edu/x'>University</a>"
        "<a class='result-link' href='https://blog.example.com/x'>Blog</a>"
    )
    block = format_results("uk scholarship", results)
    assert "official government or university domain" in block
    assert "third-party site, not an official domain" in block


def test_a_government_portal_is_not_called_third_party() -> None:
    """The Korean government portal is official, whatever the label says."""
    results = parse_results(
        "<a class='result-link' href='https://www.studyinkorea.go.kr/plan/scholarship.do'>"
        "Study in Korea</a>"
        "<a class='result-link' href='https://koreaadmit.com/x'>Admit</a>"
    )
    assert results[0].official_looking is True
    assert results[0].url.startswith("https://www.studyinkorea.go.kr")
    block = format_results("korea scholarship", results)
    assert "third-party site" in block
    assert "Study in Korea - https://www.studyinkorea.go.kr" in block
