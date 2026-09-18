class WalletException(Exception):
    """
    Base wallet exception.
    """
    pass


class InsufficientBalance(WalletException):
    """
    Raised when wallet balance is not enough.
    """
    pass


class InactiveWallet(WalletException):
    """
    Raised when wallet is disabled.
    """
    pass


class InvalidAmount(WalletException):
    """
    Raised when amount is invalid.
    """
    pass


class InvalidIdempotencyKey(WalletException):
    """
    Raised when idempotency key is reused with
    different payload.
    """
    pass