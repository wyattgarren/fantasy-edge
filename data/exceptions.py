class SleeperAPIError(Exception):
    """Base error for all Sleeper API failures."""


class UserNotFoundError(SleeperAPIError):
    """Raised when a Sleeper username does not exist."""


class LeagueNotFoundError(SleeperAPIError):
    """Raised when a league_id does not exist or is not accessible."""


class SleeperUnavailableError(SleeperAPIError):
    """Raised when Sleeper is unreachable or erroring after a retry."""
