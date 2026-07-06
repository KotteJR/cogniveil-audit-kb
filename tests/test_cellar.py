from fetch.http_utils import (
    cellar_url_for_celex,
    normalize_fetch_url,
    rewrite_eurlex_to_cellar,
)


def test_rewrite_eurlex_to_cellar_oj() -> None:
    assert rewrite_eurlex_to_cellar(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689"
    ) == "https://publications.europa.eu/resource/oj/L_202401689"


def test_rewrite_eurlex_to_cellar_celex() -> None:
    assert rewrite_eurlex_to_cellar(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1689"
    ) == "https://publications.europa.eu/resource/celex/32024R1689"


def test_rewrite_eurlex_non_eurlex_returns_none() -> None:
    assert rewrite_eurlex_to_cellar("https://example.com/?uri=CELEX:1") is None


def test_normalize_fetch_url_upgrades_http() -> None:
    assert (
        normalize_fetch_url("http://example.com/doc.pdf")
        == "https://example.com/doc.pdf"
    )


def test_cellar_url_for_celex() -> None:
    assert cellar_url_for_celex("32006L0043") == (
        "https://publications.europa.eu/resource/celex/32006L0043"
    )
