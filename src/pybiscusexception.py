
class PybiscusInternalException(Exception):

    def __init__(self, message: str):
        super().__init__(message)

class PybiscusValueException(Exception):

    def __init__(self, message: str):
        super().__init__(message)
