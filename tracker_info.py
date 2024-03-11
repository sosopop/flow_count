class TrackerInfo:
    def __init__(self):
        self.history = []  # 存储历史中心点
        self.frame_count = 0  # 自上次更新以来的帧计数器
        self.in_ready = False # 入绊线候选
        self.out_ready = False # 出绊线候选