"""Centralized selectors and URLs for CNKI automation."""

SEARCH_URL = "https://kns.cnki.net/kns8s/search"
ADVANCED_SEARCH_URL = "https://kns.cnki.net/kns/AdvSearch?classid=7NS01R8M"
JOURNAL_HOME_URL = "https://navi.cnki.net/knavi"
EXPORT_API_URL = "https://kns.cnki.net/dm8/API/GetExport"

CAPTCHA_SELECTOR = "#tcaptcha_transform_dy"
SEARCH_INPUT_SELECTOR = "input.search-input"
SEARCH_BUTTON_SELECTOR = "input.search-btn"
RESULT_ROWS_SELECTOR = ".result-table-list tbody tr"
RESULT_COUNT_SELECTOR = ".pagerTitleCell"
PAGE_MARK_SELECTOR = ".countPageMark"
PAPER_TITLE_SELECTOR = ".brief h1"
PAPER_SECTION_SELECTOR = ".brief"
JOURNAL_TITLE_LINK_SELECTOR = 'a[href*="knavi/detail"]'
JOURNAL_SEARCH_BUTTON_SELECTOR = "input.researchbtn"

KNOWN_JOURNAL_TAGS = [
    "北大核心",
    "CSSCI",
    "CSCD",
    "SCI",
    "EI",
    "CAS",
    "JST",
    "WJCI",
    "AMI",
    "Scopus",
    "卓越期刊",
    "网络首发",
]
