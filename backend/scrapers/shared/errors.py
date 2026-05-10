class InformationFetchError(Exception):
    """Raised when fetching data from the UVic/Kuali API fails."""

class ParseError(Exception):
    """Raised when parsing fetched data fails."""