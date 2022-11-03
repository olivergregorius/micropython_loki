class MockedResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def close(self) -> None:
        pass


def mock_post(status_code: int) -> MockedResponse:
    return MockedResponse(status_code)
