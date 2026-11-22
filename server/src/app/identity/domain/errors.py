class InvalidPhoneError(ValueError):
    pass


class InvalidCredentialsError(Exception):
    """Unknown phone, wrong password or inactive account: one error so the client cannot tell them apart."""


class AccountLockedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("account locked")
        self.retry_after_seconds = retry_after_seconds


class UserNotFoundError(Exception):
    pass
