import time

from rtsp_server.RtspSocket import RtspSocket
from enums.rtsp_method import RtspMethod
from enums.setup_types import NetworkType


def connect_with_ipcamera(camera_ip, camera_port, camera_username, camera_pwd, end_point, rtp_client_port):
    socket_instance = RtspSocket(camera_ip, camera_port, camera_username, camera_pwd, NetworkType.UNICAST,
                                 rtp_client_port, "10005", end_point)
    describe_func = socket_instance.send_rtsp_request(RtspMethod.DESCRIBE)
    describe_func()

    setup_func = socket_instance.send_rtsp_request(RtspMethod.SETUP)
    setup_func()

    return socket_instance


if __name__ == '__main__':
    rtp_client_port1 = 10004

    s1 = connect_with_ipcamera('192.168.0.140', 554, 'admin', 'safeai1234', 'ch_100', rtp_client_port1)

    while True:
        send_play = s1.send_rtsp_request(RtspMethod.PLAY)
        send_play()
        time.sleep(50)
