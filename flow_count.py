import json
import cv2
import datetime
import time
from datetime import datetime
from ultralytics import YOLO
from display_thread import DisplayThread
from save_thread import SaveThread
from tracker_info import TrackerInfo
from datalog import DataLog
from utils import intersection_angle, color_palette


class FlowCount:
    def __init__(self, config_file):
        self.config_file = config_file
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        print(json.dumps(self.config, indent=4))
        
        self.target_area = self.config["target"] if "target" in self.config else None
        self.model_path = self.config["model"] if "model" in self.config else ""
        self.source_url = self.config["source"] if "source" in self.config else ""
        self.frame_skip = self.config["frameSkip"] if "frameSkip" in self.config else 1
        self.save_path = self.config["savePath"] if "savePath" in self.config else ""
        self.save_codec = self.config["saveCodec"] if "saveCodec" in self.config else "self"
        self.save_thread = None
        self.display_thread = None
        self.lines = self.config["lines"]
        self.show_window = self.config["showWindow"] if "showWindow" in self.config else False
        self.debug = self.config["debug"] if "debug" in self.config else False
        self.device = self.config["device"] if "device" in self.config else "cpu"
        self.in_count = 0
        self.out_count = 0
        self.cross_render = 0
        self.trackers = {}
        self.__load_model()
        self.__init_db()
        self.__init_debug_view()
    
    def __load_model(self):
        print(f"FlowCount.load_model: 加载模型 {self.model_path}")
        self.detector = YOLO(self.model_path)

    def __init_db(self):
        print(f"FlowCount.init_db: 初始化数据库")
        self.db = DataLog(self.config["db"])

    def __init_debug_view(self):
        print(f"FlowCount.init_debug_view: 初始化调试视图")
        if self.show_window:
            self.display_thread = DisplayThread(self.config_file, max_queue_size=10)
            self.display_thread.start()
        
    def run(self):
        print(f"FlowCount.run: 以配置文件 {self.config_file} 运行slave进程")
        while True:
            self.__loop()
            time.sleep(3)
        if self.db:
            self.db.close()
        if self.display_thread:
            self.display_thread.stop()

    def __loop(self):
        cap = cv2.VideoCapture(self.source_url, cv2.CAP_FFMPEG)
        current_frame = 0

        # 确定输出视频的分辨率和帧率
        self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.read_fps = cap.get(cv2.CAP_PROP_FPS)
        if not cap.isOpened() or self.frame_height == 0 or self.frame_width == 0:
            print(f"FlowCount.loop: 无法打开视频地址 {self.source_url}")
            cap.release()
            return

        # 多帧采样一次
        sample_interval = self.frame_skip if self.frame_skip else 1
            
        # 写入帧率
        self.write_fps = self.read_fps / sample_interval

        if self.save_path:
            self.save_thread = SaveThread(
                self.save_path, self.write_fps,
                self.frame_width, self.frame_height, 
                self.save_codec, max_queue_size=10)
            self.save_thread.start()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # 仅在符合帧间隔的帧上运行检测
            if current_frame % sample_interval == 0:
                if not self.__detect(frame):
                    break
                self.__show(frame)
                self.__save(frame)

            current_frame += 1

            # 更新当前帧数并打印进度
            progress = current_frame / self.read_fps
            # if self.debug:
                # print(f"FlowCount.loop: 当前进度 {progress:.2f} s", end="\r")

        # 释放资源
        cap.release()
        if self.save_thread:
            self.save_thread.stop()

    def __detect(self, frame):
        target_frame = frame
        if self.target_area:
            x1, y1, x2, y2 = self.target_area
            target_frame = frame[y1:y2, x1:x2]
        
        # 首先为所有跟踪器的计数器增加1
        for tracker in self.trackers.values():
            tracker.frame_count += 1
            
        results = self.detector.track(
            target_frame, 
            save=False, 
            imgsz=640, 
            conf=0.1, 
            iou=0.7,
            verbose=False,
            show_labels=False, 
            show_conf=False, 
            show_boxes=False, 
            classes=0, 
            tracker="bytetrack.yaml", 
            persist=True, 
            frame_rate=self.write_fps, device=self.device)
        
        if self.target_area and self.debug:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)

        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            if self.target_area:
                x1 += self.target_area[0]
                y1 += self.target_area[1]
                x2 += self.target_area[0]
                y2 += self.target_area[1]
            center = [(x1 + x2) // 2, y1]

            if box.is_track:
                box.test = True
                id = box.id.item()
                # 根据ID取余颜色表长度获取颜色
                color = color_palette[int(id) % len(color_palette)]
                if self.debug:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                tracker = self.trackers.get(id)
                if tracker is None:
                    tracker = TrackerInfo()
                    self.trackers[id] = tracker
                    
                # 重置对应目标的帧计数器
                tracker.frame_count = 0

                # 检查history最后一个点和center是否与绊线相交
                if len(tracker.history) > 0 : # and not tracker.counted:
                    last_center = tracker.history[-1]

                    if self.debug:
                        start_point = center
                        # 绘制历史轨迹
                        for i in range(len(tracker.history) - 1, 0, -1):
                            end_point = tracker.history[i]
                            # 使用获取的颜色绘制线条
                            cv2.line(frame, start_point, end_point, color, 2)
                            start_point = tracker.history[i]

                    # 判断是否移动
                    if last_center != center:
                        for i in range(0, len(self.lines) - 2, 2):
                            line = self.lines[i:i + 4]
                            x1, y1, x2, y2 = line
                            # 计算移动向量和绊线向量的夹角
                            # fix bug: 导致夹角计算错误，因此在计算时加上一个很小的偏移量，避免轨迹点与绊线重合情况下可能连续两次碰撞，用例：
                            # angle_degrees, intersected = intersection_angle([654, 97], [650, 97], [650, 0], [650, 100])
                            # angle_degrees, intersected = intersection_angle([650, 97], [649, 97], [650, 0], [650, 100])
                            angle_degrees, intersected = intersection_angle(last_center, center, [x1 + .0001, y1 + .0001], [x2 + .0001, y2 + .0001])

                            if intersected:
                                self.cross_render = self.write_fps
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
                if len(self.trackers[id].history) >= self.write_fps:
                    self.trackers[id].history.pop(0)  # 移除最早的中心点
                self.trackers[id].history.append(center)
            else:
                # print("not track")
                if self.debug:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), 1)
                pass

        # 删除4秒未更新的跟踪器
        to_delete = [id for id, tracker in self.trackers.items() if tracker.frame_count > self.write_fps * 4]
        for id in to_delete:
            tracker = self.trackers[id]
            if tracker:
                if tracker.in_ready:
                    tracker.in_ready = False
                    self.in_count += 1
                    self.db.push_data([
                            {
                                "measurement": "flow",
                                "fields": {
                                    "count": 1,
                                },
                                "tags": {
                                    "ch": self.config["name"],
                                    "direct": "in",
                                },
                                "time": datetime.utcnow().isoformat()
                            }
                        ])
                if tracker.out_ready:
                    tracker.out_ready = False
                    self.out_count += 1
                    self.db.push_data([
                            {
                                "measurement": "flow",
                                "fields": {
                                    "count": 1,
                                },
                                "tags": {
                                    "ch": self.config["name"],
                                    "direct": "out",
                                },
                                "time": datetime.utcnow().isoformat()
                            }
                        ])
            del self.trackers[id]

        if self.debug:
            show_text = True
            color = (255, 0, 0)
            for k in range(0, len(self.lines) - 2, 2):
                line = self.lines[k:k + 4]
                x1, y1, x2, y2 = line
                if self.cross_render > 0:
                    color = (255, 255, 255)
                    self.cross_render -= 1
                cv2.line(frame, (x1, y1), (x2, y2), color, 2)
                if show_text:
                    show_text = False
                    cv2.putText(frame, f'In: {self.in_count}, Out: {self.out_count}', (x1, y1 - 10), cv2.FONT_HERSHEY_PLAIN, 1, color, 1)
        
            pending_in = 0
            pending_out = 0
            
            for tracker in self.trackers.values():
                if tracker.in_ready:
                    pending_in += 1
                if tracker.out_ready:
                    pending_out += 1
    
            # 在黑色矩形背景上绘制合并后的文字
            text_in = f'In:{self.in_count}' + (f'+{pending_in}' if pending_in > 0 else '')
            text_out = f'Out:{self.out_count}' + (f'+{pending_out}' if pending_out > 0 else '')
            cv2.putText(frame, text_in, (15, 37), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 5)
            cv2.putText(frame, text_out, (15, 77), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 5)
            cv2.putText(frame, text_in, (15, 37), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1)
            cv2.putText(frame, text_out, (15, 77), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1)

        return True

    def __show(self, frame):
        if self.display_thread:
            return self.display_thread.push(frame)
        return True

    def __save(self, frame):
        if self.save_thread:
            return self.save_thread.push(frame)
        return True

