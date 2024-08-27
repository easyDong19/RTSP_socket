from enum import Enum

class RtspMethod(Enum):
    OPTIONS = "OPTIONS"
    DESCRIBE = "DESCRIBE"
    SETUP = "SETUP"
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    TEARDOWN = "TEARDOWN"

