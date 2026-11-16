"""The failures of a check that the app can name, whichever AI ran it."""


class ReviewError(Exception):
    """A failure the app can name. `code` selects the message shown."""
    def __init__(self, code, detail=''):
        super().__init__(detail or code)
        self.code, self.detail = code, detail
