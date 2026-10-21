"""Finding scholarship links on a page the student trusts (G134).

Discovery never invents a scholarship: every candidate comes from an `<a href>`
printed on a fetched page, filtered to the same site.
"""

from __future__ import annotations

from scholarpath.discovery import (
    KEYWORDS,
    MAX_CANDIDATES,
    Candidate,
    Discovery,
    _same_site,
    candidate_links,
)

BASE = "https://www.university.edu/scholarships"


def _html(links: list[tuple[str, str]]) -> str:
    body = "".join(f'<li><a href="{href}">{label}</a></li>' for href, label in links)
    return f"<html><head><title>Scholarships</title></head><body><ul>{body}</ul></body></html>"


def test_relative_scholarship_links_are_resolved() -> None:
    found = candidate_links(_html([("engineering-scholarship", "Engineering scholarship")]), BASE)
    assert [candidate.url for candidate in found] == [
        "https://www.university.edu/engineering-scholarship"
    ]


def test_off_site_links_are_dropped() -> None:
    page = _html(
        [
            ("https://other-site.example/scholarship", "Another scholarship"),
            ("/funding/merit-award", "Merit award"),
        ]
    )
    found = candidate_links(page, BASE)
    assert [candidate.url for candidate in found] == [
        "https://www.university.edu/funding/merit-award"
    ]


def test_subdomains_of_the_same_site_are_kept() -> None:
    assert _same_site("scholarships.university.edu", "www.university.edu")
    assert _same_site("university.edu", "www.university.edu")
    assert not _same_site("notuniversity.edu", "university.edu")


def test_navigation_links_without_scholarship_words_are_dropped() -> None:
    page = _html(
        [
            ("/about", "About us"),
            ("/contact", "Contact"),
            ("/scholarships/phd", "PhD scholarship"),
        ]
    )
    found = candidate_links(page, BASE)
    assert [candidate.label for candidate in found] == ["PhD scholarship"]


def test_a_keyword_in_the_visible_label_is_enough() -> None:
    found = candidate_links(_html([("/node/42", "Vice-Chancellor's bursary")]), BASE)
    assert [candidate.url for candidate in found] == ["https://www.university.edu/node/42"]
    assert found[0].label == "Vice-Chancellor's bursary"


def test_duplicates_and_the_page_itself_are_dropped() -> None:
    page = _html(
        [
            ("/funding/grant", "Grant"),
            ("/funding/grant#apply", "Grant again"),
            ("/scholarships", "Scholarships"),
        ]
    )
    found = candidate_links(page, BASE)
    assert [candidate.url for candidate in found] == [
        "https://www.university.edu/funding/grant"
    ]


def test_document_links_are_skipped() -> None:
    page = _html([("/files/scholarship-form.pdf", "Scholarship form")])
    assert candidate_links(page, BASE) == []


def test_mail_and_script_links_are_ignored() -> None:
    page = _html(
        [
            ("mailto:scholarships@university.edu", "Email the scholarship office"),
            ("javascript:void(0)", "Scholarship help"),
        ]
    )
    assert candidate_links(page, BASE) == []


def test_the_list_is_capped() -> None:
    page = _html([(f"/scholarship-{index}", f"Scholarship {index}") for index in range(40)])
    found = candidate_links(page, BASE)
    assert len(found) == MAX_CANDIDATES


def test_visible_keyword_links_come_before_url_only_matches() -> None:
    page = _html(
        [
            ("/scholarship-news", "Latest news"),
            ("/node/7", "Chevening scholarship"),
        ]
    )
    found = candidate_links(page, BASE)
    assert found[0].label == "Chevening scholarship"


def test_a_name_is_always_available_for_the_student() -> None:
    page = _html([("/funding/merit-based-award", "")])
    found = candidate_links(page, BASE)
    assert found and found[0].label == "Merit Based Award"


def test_source_url_is_kept_on_every_candidate() -> None:
    found = candidate_links(_html([("/funding", "Funding")]), BASE)
    assert all(candidate.source_url == BASE for candidate in found)


def test_keywords_are_scholarship_words() -> None:
    assert "scholarship" in KEYWORDS
    assert "bursary" in KEYWORDS
    assert all(word == word.casefold() for word in KEYWORDS)


def test_discovery_reports_empty_honestly() -> None:
    result = Discovery(
        source_url=BASE, final_url=BASE, title="Scholarships", candidates=()
    )
    assert result.empty
    candidate = Candidate(url=BASE + "/x", label="X", source_url=BASE)
    assert not Discovery(
        source_url=BASE, final_url=BASE, title="", candidates=(candidate,)
    ).empty
