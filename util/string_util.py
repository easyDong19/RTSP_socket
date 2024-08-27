import re

def get_status_code(response: str) -> int:
    match = re.search(r'RTSP/\d.\d (\d{3})', response)
    return int(match.group(1)) if match else None