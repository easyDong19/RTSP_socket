from enum import Enum


class TransportProtocol(Enum):
    RTPnAVP = "RTP/AVP"
    RTPnAVPnTCP = "RTP/AVP/TCP"
    RTPnAVPnUDP = "RTP/AVP/UDP"


class NetworkType(Enum):
    UNICAST = "unicast"
    MULTICAST = "multicast"
