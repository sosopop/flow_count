import cv2
import queue
import time
from threading import Thread

class SaveThread(Thread):
    def __init__(self, path, fps, max_queue_size=10):
        super().__init__()
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.stop_flag = False
        self.path = path
        self.fps = fps
        self.current_frame = 0

    def run(self):
        while not self.stop_flag:
            try:
                frame = self.frame_queue.get_nowait()
            except queue.Empty:
                # 暂停0.01秒
                time.sleep(0.01)
                continue

    def push(self, frame):
        if self.stop_flag:
            return False
        try:
            self.frame_queue.put(frame, block=True)  # 尝试将帧放入队列，如满则等待直到有空间
        except queue.Full:
            # 队列满时的处理逻辑可以根据需要添加，例如：跳过帧、记录日志等
            pass
        return True

    def stop(self):
        self.stop_flag = True
        self.join()
