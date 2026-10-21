"""Which domains count as official - the one place that decides it.

A domain is official when its **registrable** domain matches exactly:

- ``.edu``            - a university or college (any country)
- ``.ac.<cc>``        - a university in a country domain (university.ac.uk)
- ``.gov`` / ``.gov.<cc>``
- ``.int``, ``.mil``  - public bodies
- ``europa.eu``       - the European Union's own domains

The student's own ``search.trusted_domains`` are added on top (a scholarship
body such as a foundation is not a university, and only the student can say
"this one is mine").

Nothing is ever matched as a substring. ``university.edu.example.com`` has the
registrable domain ``example.com`` and is not official; ``notgov.example`` is
not a government domain. A lookalike name is exactly the thing this rule
exists to catch.
"""

from __future__ import annotations

from urllib.parse import urlsplit

#: Top-level domains that are academic or governmental.
OFFICIAL_TLDS = ("edu", "gov", "int", "mil")

#: Second-level labels that make a country domain an academic or government
#: one: "university.ac.uk", "agency.gov.jp".
OFFICIAL_SECOND_LEVEL = ("ac", "gov", "edu")

#: The European Union's own domain family.
EUROPA_SUFFIX = "europa.eu"


def registrable_domain(host: str) -> str:
    """The domain a site owns: "university.ac.uk" for "www.university.ac.uk".

    Two labels normally ("example.co.uk" is three, because "co.uk" is a
    country suffix), which is enough to compare a domain exactly.
    """
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if len(labels[-1]) == 2 and labels[-1].isalpha():
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_official_domain(host: str) -> bool:
    """True for academic and government domains, on the registrable domain.

    "scholarships.university.edu" is official; "university.edu.example.com"
    and "notgov.example" are not. Nothing is matched as a substring.
    """
    host = (host or "").split("/", 1)[0].split("?", 1)[0]
    registrable = registrable_domain(host)
    if not registrable or "." not in registrable:
        return False
    if registrable == EUROPA_SUFFIX or registrable.endswith("." + EUROPA_SUFFIX):
        return True
    labels = registrable.split(".")
    top = labels[-1]
    second = labels[-2]
    if top in OFFICIAL_TLDS:
        return True
    if second in OFFICIAL_SECOND_LEVEL and len(top) == 2 and top.isalpha():
        return True
    return False


def trusted_domains(values: object) -> set[str]:
    """The student's own trusted domains, reduced to registrable domains."""
    if not values:
        return set()
    if isinstance(values, str):
        values = [values]
    trusted: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        candidate = registrable_domain(value.strip())
        if candidate:
            trusted.add(candidate)
    return trusted


def is_known_domain(host: str, trusted: object = ()) -> bool:
    """True when the host is official, or one the student trusts.

    The trusted list is matched on the registrable domain too, so a student's
    "chevening.org" covers "www.chevening.org" but not "chevening.org.example.com".
    """
    host = (host or "").split("/", 1)[0].split("?", 1)[0]
    if is_official_domain(host):
        return True
    registrable = registrable_domain(host)
    if not registrable:
        return False
    return registrable in trusted_domains(trusted)


def host_of(url: str) -> str:
    """The host of a URL, without the scheme or a leading "www."."""
    host = (urlsplit(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host
