import hashlib
import socket
import re
import time

from enums.rtsp_method import RtspMethod
from enums.setup_types import NetworkType, TransportProtocol
from typing import Optional, Dict, List
from string import Template

from exceptions.RtspError import RtspAuthorizationError, UnsupportedMethodError
from util.string_util import get_status_code


class RtspSocket:
    def __init__(self, camera_ip: str, camera_port: str, camera_username: str, camera_pwd: str,
                 network_type: NetworkType, rtp_port: str, rtcp_port: str,
                 end_point: Optional[str] = None):
        self.__camera_ip = camera_ip
        self.__camera_port = camera_port
        self.__camera_username = camera_username
        self.__camera_pwd = camera_pwd
        self.__CSeq = 1

        self.__network_type = network_type
        self.__rtp_port = rtp_port
        self.__rtcp_port = rtcp_port

        # 프로토콜 호출 후 얻는 파라미터 값
        self.__auth_header: str = ""
        self.__method_list: List[str] = []
        self.__session: str = ""
        self.__transport_protocol: str = ""

        self.__url = f'rtsp://{self.__camera_ip}:{self.__camera_port}/{end_point}' if end_point is not None \
            else f'rtsp://{self.__camera_ip}:{self.__camera_port}'

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.sock.connect((self.__camera_ip, self.__camera_port))
            self.__set_available_method_list()
        except socket.error as e:
            raise ConnectionError(f"소켓 연결 오류 : {e}")

    """
    RTSP 프로토콜 메시지 생성 
    """

    def __create_msg(self, method: RtspMethod, header_keyword: Optional[List[dict[str, str]]] = None) -> str:

        header_keyword = header_keyword or []
        header_msg = ''.join(f'{key}: {value}\r\n' for item in header_keyword for key, value in item.items())

        request_template = Template(
            "$method $url RTSP/1.0\r\n"
            "CSeq: $cseq\r\n"
            "Accept: application/sdp\r\n"
            "$header_msg"
            "$auth_header"
            "\r\n"
        )

        request_msg = request_template.substitute(
            method=method.value,
            url=self.__url,
            cseq=self.__CSeq,
            header_msg=header_msg,
            auth_header=self.__auth_header
        )
        self.__CSeq += 1
        print(request_msg)

        return request_msg

    """
    milesight 제품일 경우
    digest 인증을 받아서 헤더에 실어야
    describe 명령어 실행 가능
    """

    def __set_auth_header(self, method: RtspMethod, realm: str, nonce: str) -> None:

        def __create_digest_response() -> str:
            ha_1 = hashlib.md5(f"{self.__camera_username}:{realm}:{self.__camera_pwd}".encode('utf-8')).hexdigest()
            ha_2 = hashlib.md5(f"{method.value}:{self.__url}".encode('utf-8')).hexdigest()
            response = hashlib.md5(f"{ha_1}:{nonce}:{ha_2}".encode('utf-8')).hexdigest()
            return response

        digest_response = __create_digest_response()
        auth_header = (
            'Authorization: Digest '
            f'username="{self.__camera_username}", realm="{realm}", nonce="{nonce}", uri="{self.__url}", response="{digest_response}"\r\n'
        )

        self.__auth_header = auth_header

    """
    OPTIONS : 
    사용할 수 있는 RTSP 명령어를 반환 
    """

    def __set_available_method_list(self, buffer=1024) -> None:
        request_msg = self.__create_msg(RtspMethod.OPTIONS)
        self.sock.sendall(request_msg.encode('utf-8'))
        response = self.sock.recv(buffer).decode('utf-8')
        self.__method_list = re.search(r'Public:\s*(.*)', response).group(1).strip().split(',')

    """
    만약 전송방식이 여러개인 IP 카메라가 나온다면
    각각을 딕셔너리로 저장해야 하나, 대부분 하나의 전송 방식만 선택해서 생략
    example) 
    m=video 0 RTP/AVP 96
    m=application 0 RTP/AVP/UDP 98
    """

    def __set_available_transport_protocol(self, response: str) -> None:
        pattern = re.compile(r"m=\w+ \d+ (RTP/\w+) \d+")
        matches = pattern.findall(response)
        ret = set(matches)
        self.__transport_protocol = ret.pop()

    """
    DESCRIBE : 
    미디어에 대한 정보를 요청 
    """

    def __send_describe(self, buffer=2048) -> None:
        request_msg = self.__create_msg(RtspMethod.DESCRIBE)

        try:
            self.sock.sendall(request_msg.encode('utf-8'))
            response = self.sock.recv(buffer).decode('utf-8')

            if get_status_code(response) == 401:
                raise RtspAuthorizationError(response)

        except RtspAuthorizationError as e:
            error_response = e.get_response()
            realm = re.search(r'realm="([^"]+)"', error_response).group(1)
            nonce = re.search(r'nonce="([^"]+)"', error_response).group(1)

            self.__set_auth_header(RtspMethod.DESCRIBE, realm, nonce)
            re_request_msg = self.__create_msg(RtspMethod.DESCRIBE)
            self.sock.sendall(re_request_msg.encode('utf-8'))
            response = self.sock.recv(buffer).decode('utf-8')

            self.__set_available_transport_protocol(response)

    """
    SETUP : 
    단일 미디어가 어떻게 전송되어야 하는지 규정
    이 요청이 수행되고 난 후에야 PLAY 요청 가능  
    """

    def __send_setup(self, buffer=2048) -> None:
        header_keyword = [{
            'Transport': f"{self.__transport_protocol};{self.__network_type.value};client_port={str(self.__rtp_port) + '-' + str(self.__rtcp_port)}"
        }]
        request_msg = self.__create_msg(RtspMethod.SETUP, header_keyword)
        self.sock.sendall(request_msg.encode('utf-8'))
        response = self.sock.recv(buffer).decode('utf-8')

        pattern = re.compile(r"Session: (\S+)")
        session_value = pattern.search(response).group(1)
        self.__session = session_value

    """
    PLAY :
    미디어 스트림 재생
    주기적으로 요청을 안보내면 세션이 끊김
    """

    def __send_play(self, buffer=2048) -> None:
        header_keyword = [{
            'Session': f"{self.__session}"
        }]
        request_msg = self.__create_msg(RtspMethod.PLAY, header_keyword)
        self.sock.sendall(request_msg.encode('utf-8'))
        response = self.sock.recv(buffer).decode('utf-8')

        if get_status_code(response) == 200:
            print("재생이 시작됩니다.")

    """
    PAUSE :
    미디어 스트림 일시 정지
    다시 PLAY 요청하면 이어서 재생 가능 
    """

    def __send_pause(self, buffer=2048) -> None:
        header_keyword = [{
            'Session': f"{self.__session}"
        }]
        request_msg = self.__create_msg(RtspMethod.PAUSE, header_keyword)
        self.sock.sendall(request_msg.encode('utf-8'))
        response = self.sock.recv(buffer).decode('utf-8')

        if get_status_code(response) == 200: print("재생이 일시 중지됩니다.")

    """
    TEARDOWN : 
    모든 미디어 스트림 중지
    서버 상 모든 세션 관련된 데이터 할당 해제
    """

    def __send_teardown(self, buffer=2048) -> None:
        header_keyword = [{
            'Session': f"{self.__session}"
        }]
        request_msg = self.__create_msg(RtspMethod.TEARDOWN, header_keyword)
        self.sock.sendall(request_msg.encode('utf-8'))
        response = self.sock.recv(buffer).decode('utf-8')

        if get_status_code(response) == 200: print("스트림이 종료됩니다.")

    def send_rtsp_request(self, method: RtspMethod):
        send_method = {
            'DESCRIBE': self.__send_describe,
            'SETUP': self.__send_setup,
            'PLAY': self.__send_play,
            'PAUSE': self.__send_pause,
            'TEARDOWN': self.__send_teardown,
        }

        try:
            if method.value not in self.__method_list:
                raise UnsupportedMethodError("사용할 수 없는 메서드 입니다.")

            send_func = send_method[method.value]
            return send_func

        except UnsupportedMethodError as e:
            print(e)

    def close_socket(self) -> None:
        print("소켓 연결을 종료합니다.")
        self.sock.close()


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

    # s1 = connect_with_IPcamera('1.234.209.77', 2500, 'admin', 'safeai1234', 'ch_100', rtp_client_port1)
    s1 = connect_with_ipcamera('192.168.0.140', 554, 'admin', 'safeai1234', 'ch_100', rtp_client_port1)

    while True:
        send_play = s1.send_rtsp_request(RtspMethod.PLAY)
        send_play()
        time.sleep(50)
