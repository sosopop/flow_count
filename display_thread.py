import cv2
import queue
import time
from threading import Thread

class DisplayThread(Thread):
    def __init__(self, name, max_queue_size=10):
        super().__init__()
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.stop_flag = False
        self.name = name

    def run(self):
        while not self.stop_flag:
            try:
                frame = self.frame_queue.get_nowait()
                cv2.imshow(self.name, frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):  # 按'q'退出
                    self.stop_display()
            except queue.Empty:
                cv2.waitKey(1)  # 空队列时暂停显示
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
        cv2.destroyWindow(self.name)
        time.sleep(0.1)
        self.join()
