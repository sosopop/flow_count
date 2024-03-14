import queue
import subprocess
import time
from threading import Thread

class SaveThread(Thread):
    def __init__(self, path, fps, width, height, codec, ffmpegVerbose=False, max_queue_size=10):
        super().__init__()
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.stop_flag = False
        self.path = path
        self.fps = fps
        self.width = width
        self.height = height
        self.current_frame = 0
        self.ffmpegVerbose = ffmpegVerbose

        if codec == "intel":
            self.codec = 'h264_qsv'
        elif codec == "amd":
            self.codec = 'h264_amf'
        elif self.codec == "nvidia":
            self.codec = 'h264_nvenc'
        else:
            self.codec = 'libx264'

        # 设置FFmpeg命令 intel加速
        self.command = ['ffmpeg',
                        '-y',
                        '-f', 'rawvideo',
                        '-vcodec', 'rawvideo',
                        '-pix_fmt', 'bgr24',
                        '-s', '{}x{}'.format(self.width, self.height),
                        '-r', str(self.fps),
                        '-i', '-',
                        '-vf', 'scale=640:-1',  # 设置宽度为640，高度自适应
                        '-b:v', '1M',  # 设置视频比特率为1Mbps
                        '-c:v', self.codec,
                        '-preset', 'fast',  # 选择适合的预设
                        '-pix_fmt', 'yuv420p',
                        '-f', 'flv',
                        self.path]
        
        # # 设置FFmpeg命令 intel加速
        # self.command = ['ffmpeg',
        #                 '-y',
        #                 '-f', 'rawvideo',
        #                 '-vcodec', 'rawvideo',
        #                 '-pix_fmt', 'bgr24',
        #                 '-s', '{}x{}'.format(self.width, self.height),
        #                 '-r', str(self.fps),
        #                 '-i', '-',
        #                 '-vf', 'scale=640:-1',  # 设置宽度为640，高度自适应
        #                 '-b:v', '1M',  # 设置视频比特率为1Mbps
        #                 '-c:v', 'h264_qsv',  # 使用Intel QSV硬件编码器
        #                 '-preset', 'fast',  # 选择适合的预设
        #                 '-pix_fmt', 'yuv420p',
        #                 '-f', 'flv',
        #                 self.path]
        
        # # 设置FFmpeg命令 nvidia加速
        # self.command = ['ffmpeg',
        #                 '-y',
        #                 '-f', 'rawvideo',
        #                 '-vcodec', 'rawvideo',
        #                 '-pix_fmt', 'bgr24',
        #                 '-s', '{}x{}'.format(self.width, self.height),
        #                 '-r', str(self.fps),
        #                 '-i', '-',
        #                 '-vf', 'scale=640:-1',  # 设置宽度为640，高度自适应
        #                 '-c:v', 'h264_nvenc',  # 使用NVIDIA硬件编码器
        #                 '-preset', 'fast',  # 选择适合的预设
        #                 '-pix_fmt', 'yuv420p',
        #                 '-f', 'flv',
        #                 self.path]
        
        # # 设置FFmpeg命令 AMD加速
        # self.command = ['ffmpeg',
        #                 '-y',
        #                 '-f', 'rawvideo',
        #                 '-vcodec', 'rawvideo',
        #                 '-pix_fmt', 'bgr24',
        #                 '-s', '{}x{}'.format(self.width, self.height),
        #                 '-r', str(self.fps),
        #                 '-i', '-',
        #                 '-vf', 'scale=640:-1',  # 设置宽度为640,高度自适应
        #                 '-c:v', 'h264_amf',  # 使用AMD AMF硬件编码器
        #                 '-usage', 'lowlatency',  # 低延迟使用模式
        #                 '-profile:v', 'main',  # H.264配置文件
        #                 '-rc', 'cbr',  # 恒定比特率控制
        #                 '-pix_fmt', 'yuv420p',
        #                 '-f', 'flv',
        #                 self.path]
        
    def run(self):
        while not self.stop_flag:
            print(f"正在启动推流进程 {self.path}")
            # 启动FFmpeg进程
            if self.ffmpegVerbose:
                process = subprocess.Popen(self.command, stdin=subprocess.PIPE)
            else:
                process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            while not self.stop_flag:
                try:
                    frame = self.frame_queue.get(block=True, timeout=0.01)
                    # 将帧写入到FFmpeg进程的标准输入
                    process.stdin.write(frame.tobytes())
                except queue.Empty:
                    time.sleep(0.01)
                    continue
                except Exception as e:
                    print(f"推流进程 {self.path} 发生异常: {e}")
                    # FFmpeg进程已关闭，重新启动新的进程
                    break

            process.stdin.close()
            process.terminate()
            process.wait()
            print(f"推流进程已退出 {self.path}")
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