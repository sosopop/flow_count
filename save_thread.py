import queue
import subprocess
import time
from threading import Thread

class SaveThread(Thread):
    def __init__(self, path, fps, width, height, max_queue_size=10):
        super().__init__()
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.stop_flag = False
        self.path = path
        self.fps = fps
        self.width = width
        self.height = height
        self.current_frame = 0

        # 设置FFmpeg命令
        self.command = ['ffmpeg',
                        '-y',
                        '-f', 'rawvideo',
                        '-vcodec', 'rawvideo',
                        '-pix_fmt', 'bgr24',
                        '-s', '{}x{}'.format(self.width, self.height),
                        '-r', str(self.fps),
                        '-i', '-',
                        '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p',
                        '-preset', 'ultrafast',
                        '-f', 'flv',
                        self.path]

    def run(self):
        while not self.stop_flag:
            # 启动FFmpeg进程
            process = subprocess.Popen(self.command, stdin=subprocess.PIPE)

            while not self.stop_flag:
                try:
                    frame = self.frame_queue.get_nowait()
                    # 将帧写入到FFmpeg进程的标准输入
                    process.stdin.write(frame.tobytes())
                except queue.Empty:
                    time.sleep(0.01)
                    continue
                except BrokenPipeError:
                    # FFmpeg进程已关闭，重新启动新的进程
                    break

            process.stdin.close()
            process.wait()
            self.frame_queue.queue.clear()

    def push(self, frame):
        if self.stop_flag:
            return False
        try:
            self.frame_queue.put_nowait(frame)  # 尝试将帧放入队列，不等待
        except queue.Full:
            # 队列满时的处理逻辑可以根据需要添加，例如：跳过帧、记录日志等
            return False
        return True

    def stop(self):
        self.stop_flag = True
        self.join()