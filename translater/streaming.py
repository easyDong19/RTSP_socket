import os
import gi
import threading

from typing import Final, List

from util.translater_util import get_server_date, ensure_directory_exists

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

# 1초 = 10억 나노초
NANO: Final[int] = 1000000000


def write_m3u8_playlist(ts_files: List, m3u8_file_name: str, output_url: str, duration_sec: int) -> None:
    with open(m3u8_file_name, 'w') as m3u8:
        m3u8.write("#EXTM3U\n")
        dir = os.path.dirname(output_url)
        for ts_file in ts_files:
            duration = duration_sec
            if duration is not None:
                m3u8.write(f"#EXTINF:{duration:.6f},\n")
                m3u8.write(f"{dir}/{ts_file}\n")
        m3u8.write("#EXT-X-ENDLIST\n")


def start_streaming(udp_port: str, output_url: str, m3u8_filename: str, duration_sec: int = 10, segment_count: int = 3):
    pipeline = Gst.parse_launch(
        f"udpsrc port={udp_port} caps=\"application/x-rtp\" ! "
        "rtpjitterbuffer ! rtph264depay ! h264parse ! queue ! "
        f"hlssink2 location={output_url} target-duration={duration_sec} max-files=0 name=combine_to_hls"
    )

    def update_m3u8_file():
        ts_files = sorted([f for f in os.listdir(os.path.dirname(output_url)) if f.endswith(".ts")])
        write_m3u8_playlist(ts_files[-segment_count:], m3u8_filename, output_url, duration_sec)

    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def on_message(bus, message):
        if message.type == Gst.MessageType.ELEMENT:
            if message.has_name("splitmuxsink-fragment-closed"):
                print("세그먼트 작성 완료")
                update_m3u8_file()
        elif message.type == Gst.MessageType.EOS:
            update_m3u8_file()
            loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error received: {err}, {debug}")
            loop.quit()

    bus.connect("message", on_message)

    pipeline.set_state(Gst.State.PLAYING)

    # 이벤트루프를 만들고, pipeline에서 event받을 때까지 기다림
    # 이 코드가 없으면 함수를 한번 실행하고 바로 메인스레드로 넘어가서 프로그램이 종료됨
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        # 프로세스에 올려둔 파이프라인 초기화하고 반납
        pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':

    rtp_1_rtp = 'output_1'
    rtp_2_rtp = 'output_2'
    output_1_dir_path = f"../{rtp_1_rtp}"
    output_2_dir_path = f"../{rtp_2_rtp}"

    output1_m3u8_path = f"../public/m3u8/{rtp_1_rtp}"
    output2_m3u8_path = f"../public/m3u8/{rtp_2_rtp}"

    server_date = get_server_date()

    output_1_today_log = f"{output_1_dir_path}/{server_date}"
    output_2_today_log = f"{output_2_dir_path}/{server_date}"

    ensure_directory_exists(output_1_today_log)
    ensure_directory_exists(output_2_today_log)

    ensure_directory_exists(output1_m3u8_path)
    ensure_directory_exists(output2_m3u8_path)

    ts_name = f"{server_date}_%05d.ts"

    streams = [
        {"port": 10004, "output": f"{output_1_today_log}/{ts_name}",
         "m3u8": f"{output1_m3u8_path}/{server_date}.m3u8"},
        {"port": 10006, "output": f"{output_2_today_log}/{ts_name}",
         "m3u8": f"{output2_m3u8_path}/{server_date}.m3u8"},
    ]

    # 개별 thread로 처리안하고 main스레드에서 처리하면 위의 GLib.MainLoop가 무한 대기하기 때문에 처음 연결된 RTP만 받아짐
    threads = []
    for stream in streams:
        t = threading.Thread(target=start_streaming, args=(stream["port"], stream["output"], stream["m3u8"]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("parents thread finshed")





