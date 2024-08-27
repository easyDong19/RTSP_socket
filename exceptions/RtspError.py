class UnsupportedMethodError(Exception):
    def __init__(self, msg):
        self.msg = msg


    def __str__(self):
        return self.msg


class RtspAuthorizationError(Exception):
    def __init__(self, response, msg="인증권한이 필요합니다."):
        self.msg = msg
        self.__response = response

    def __str__(self):
        return self.msg

    def get_response(self):
        return self.__response

