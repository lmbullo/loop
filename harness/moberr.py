"""One error type for the transport-neutral mobile API."""


class ApiError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status = status
        self.text = text
