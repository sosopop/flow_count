import cv2
from ultralytics import YOLO
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import ASYNCHRONOUS
from utils import intersection_angle, color_palette
import queue
from threading import Thread

class CrowdCount:
    def __init__(self, config):
        # self.input_video = config["source"]
        # self.output_video = config["output"]
        # self.model_path = config["model"]
        # self.db_config = config["db"]
        # self.gates_config = config["gates"]
        # self.target_area = config["target_area"]
        self.config = config
        self.detector = YOLO(self.config["model"])
        self.trackers = {}
        # self.gates = []
        self.db_client = None
        self.db_write_api = None
        self.fps = 30
        self.initialize_database()
        self.initialize_gates()

    def initialize_database(self):
        self.db_client = InfluxDBClient(url=self.db_config['url'], token=self.db_config['token'], org=self.db_config['org'])
        self.db_write_api = self.db_client.write_api(write_options=ASYNCHRONOUS)

    def initialize_gates(self):
        for config in self.gates_config:
            self.gates.append(GateInfo(config))

    def push_data(self, data):
        self.db_write_api.write(bucket=self.db_config['bucket'], record=data)

    def detect_person(self, frame):
        show_frame = frame
        target_frame = show_frame
        if self.target_area:
            x1, y1, x2, y2 = self.target_area
            target_frame = frame[y1:y2, x1:x2]
        
        # 首先为所有跟踪器的计数器增加1
        for tracker in self.trackers.values():
            tracker.frame_count += 1
            
        results = self.detector.track(target_frame, save=False, imgsz=640, conf=0.1, iou=0.7, verbose=False, show_labels=False, show_conf=False, show_boxes=False, classes=0, tracker="bytetrack.yaml", persist=True, frame_rate=self.fps)
        if self.target_area:
            cv2.rectangle(show_frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            if self.target_area:
                x1 += self.target_area[0]
                y1 += self.target_area[1]
                x2 += self.target_area[0]
                y2 += self.target_area[1]
            # x1, y1, x2, y2 = adjust_box_within_bounds(show_frame.shape[1], show_frame.shape[0], x1, y1, x2, y2)
            center = [(x1 + x2) // 2, y1]
            # 显示置信度
            # cv2.putText(show_frame, f'{box.conf.item():.2f}', (x1 + 30, y1), cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 0), 2)
            # cv2.rectangle(show_frame, (x1, y1), (x2, y2), (0,0,0), 2)

            if box.is_track:
                box.test = True
                id = box.id.item()
                # 根据ID取余颜色表长度获取颜色
                color = color_palette[int(id) % len(color_palette)]
                cv2.rectangle(show_frame, (x1, y1), (x2, y2), color, 2)
                # cv2.putText(show_frame, str(int(id)), (x1, y1), cv2.FONT_HERSHEY_PLAIN, 1, color, 2)

                tracker = self.trackers.get(id)
                if tracker is None:
                    tracker = TrackerInfo()
                    self.trackers[id] = tracker
                    
                # 重置对应目标的帧计数器
                tracker.frame_count = 0

                # 检查history最后一个点和center是否与绊线相交
                if len(tracker.history) > 0 : # and not tracker.counted:
                    last_center = tracker.history[-1]
                                
                    start_point = center
                    # 绘制历史轨迹
                    for i in range(len(tracker.history) - 1, 0, -1):
                        end_point = tracker.history[i]
                        # 使用获取的颜色绘制线条
                        cv2.line(show_frame, start_point, end_point, color, 2)
                        start_point = tracker.history[i]

                    # 判断是否移动
                    if last_center != center:
                        for gate in self.gates:
                            for i in range(0, len(gate.lines) - 2, 2):
                                line = gate.lines[i:i + 4]
                                x1, y1, x2, y2 = line
                                # 计算移动向量和绊线向量的夹角
                                # fix bug: 导致夹角计算错误，因此在计算时加上一个很小的偏移量，避免轨迹点与绊线重合情况下可能连续两次碰撞，用例：
                                # angle_degrees, intersected = intersection_angle([654, 97], [650, 97], [650, 0], [650, 100])
                                # angle_degrees, intersected = intersection_angle([650, 97], [649, 97], [650, 0], [650, 100])
                                angle_degrees, intersected = intersection_angle(last_center, center, [x1 + .0001, y1 + .0001], [x2 + .0001, y2 + .0001])

                                if intersected:
                                    gate.cross_render = self.fps
                                    tracker.gate = gate
                                    if angle_degrees < 180:
                                        if tracker.out_ready:
                                            # 如果已经碰触出绊线，重置出绊线候选
                                            tracker.out_ready = False
                                        else:
                                            # 碰触入绊线，进入出绊线候选
                                            tracker.in_ready = True
                                    else:
                                        if tracker.in_ready:
                                            # 如果已经碰触入绊线，重置入绊线候选
                                            tracker.in_ready = False
                                        else:
                                            # 碰触出绊线，进入入绊线候选
                                            tracker.out_ready = True
                                    #bugfix 去掉break，一次碰撞触发多个绊线都需要处理
                                    #break

                # 保持历史记录长度最多为1秒
                if len(self.trackers[id].history) >= self.fps:
                    self.trackers[id].history.pop(0)  # 移除最早的中心点
                self.trackers[id].history.append(center)
            else:
                # print("not track")
                cv2.rectangle(show_frame, (x1, y1), (x2, y2), (0, 0, 0), 1)
                pass

        # 删除4秒未更新的跟踪器
        to_delete = [id for id, tracker in self.trackers.items() if tracker.frame_count > self.fps * 4]
        for id in to_delete:
            tracker = self.trackers[id]
            if tracker.gate:
                gate = tracker.gate
                tracker.gate = None
                if tracker.in_ready:
                    tracker.in_ready = False
                    gate.in_count += 1
                    self.push_data(
                        Point(self.db_config['measurement'])
                        .tag("ch", gate.name)
                        .tag("direct", "in")
                        # field字段必须存在
                        .field("count", 1)
                        .time(datetime.utcnow(), WritePrecision.NS))
                if tracker.out_ready:
                    tracker.out_ready = False
                    gate.out_count += 1
                    self.push_data(
                        Point(self.db_config['measurement'])
                        .tag("ch", gate.name)
                        .tag("direct", "out")
                        # field字段必须存在
                        .field("count", 1)
                        .time(datetime.utcnow(), WritePrecision.NS)
                    )
            del self.trackers[id]

        total_in = 0
        total_out = 0

        for i in range(0, len(self.gates)):
            gate = self.gates[i]
            show_text = True
            color = color_palette[int(i) % len(color_palette)]
            for k in range(0, len(gate.lines) - 2, 2):
                line = gate.lines[k:k + 4]
                x1, y1, x2, y2 = line
                if gate.cross_render > 0:
                    color = (255, 255, 255)
                    gate.cross_render -= 1
                cv2.line(show_frame, (x1, y1), (x2, y2), color, 2)
                if show_text:
                    show_text = False
                    cv2.putText(show_frame, f'In: {gate.in_count}, Out: {gate.out_count}', (x1, y1 - 10), cv2.FONT_HERSHEY_PLAIN, 1, color, 1)
                    # cv2.putText(show_frame, f'Out: {gate.out_count}', (x1, y1 - 25), cv2.FONT_HERSHEY_PLAIN, 1, color, 1)
            
            total_in += gate.in_count
            total_out += gate.out_count

        pending_in = 0
        pending_out = 0
        
        for tracker in self.trackers.values():
            if tracker.in_ready:
                pending_in += 1
            if tracker.out_ready:
                pending_out += 1
  
        # 在黑色矩形背景上绘制合并后的文字
        text_in = f'In:{total_in}' + (f'+{pending_in}' if pending_in > 0 else '')
        text_out = f'Out:{total_out}' + (f'+{pending_out}' if pending_out > 0 else '')
        cv2.putText(show_frame, text_in, (15, 37), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 5)
        cv2.putText(show_frame, text_out, (15, 77), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 5)
        cv2.putText(show_frame, text_in, (15, 37), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1)
        cv2.putText(show_frame, text_out, (15, 77), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1)


    def process_videos(self):
        cap = cv2.VideoCapture(self.input_video)
        # 获取视频的总帧数
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        current_frame = 0

        # 确定输出视频的分辨率和帧率
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        # 多帧采样一次
        sample_interval = int(self.fps / 8)
        if sample_interval < 1:
            sample_interval = 1
        # 写入帧率
        self.fps = self.fps / sample_interval

        # 创建视频写入对象
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.output_video, fourcc, self.fps, (frame_width, frame_height))

        self.display_thread = DisplayThread(self.input_video, out, max_queue_size=10)
        self.display_thread.start()

        seek_frame = 800
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            # if seek_frame > 0:
            #     seek_frame -= 1
            #     continue
            # 仅在符合帧间隔的帧上运行检测
            if current_frame % sample_interval == 0:
                self.detect_person(frame)
                # out.write(frame)
                if self.display_thread.push(frame) == False:
                    break

            # 更新当前帧数并打印进度
            current_frame += 1
            progress = (current_frame / total_frames) * 100
            print(f"Processing video: {progress:.2f}% complete", end="\r")

        if self.display_thread:
            self.display_thread.stop_display()
            self.display_thread.join()

        # 释放资源
        cap.release()
        out.release()

    def run(self):
        self.process_videos()
        if self.db_client:
            self.db_client.close()
        print("Processing complete.")

class TrackerInfo:
    def __init__(self):
        self.history = []  # 存储历史中心点
        self.frame_count = 0  # 自上次更新以来的帧计数器
        self.in_ready = False # 入绊线候选
        self.out_ready = False # 出绊线候选
        self.gate = None # 绊线通道

class GateInfo:
    def __init__(self, config):
        self.name = config["name"]
        self.tags = config["tags"]
        self.lines = config["lines"]
        self.in_count = 0
        self.out_count = 0
        self.cross_render = 0

class DisplayThread(Thread):
    def __init__(self, name, videoOut, max_queue_size=10):
        super().__init__()
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.stop_flag = False
        self.videoOut = videoOut
        self.name = name

    def run(self):
        while not self.stop_flag:
            try:
                frame = self.frame_queue.get_nowait()
                cv2.imshow(self.name, frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):  # 按'q'退出
                    self.stop_display()
                if self.videoOut:
                    self.videoOut.write(frame)
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

    def stop_display(self):
        self.stop_flag = True
        cv2.destroyWindow(self.name)
