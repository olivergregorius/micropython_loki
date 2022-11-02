import time


class MockedResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def mock_post(status_code: int):
    return MockedResponse(status_code)
