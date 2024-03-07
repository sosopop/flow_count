import numpy as np
import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'

def lines_angle(seg1, seg2):
    vector1 = seg1[1] - seg1[0]
    vector2 = seg2[1] - seg2[0]

    if np.all(vector1 == 0) or np.all(vector2 == 0):
        return None

    vector1 = vector1 / np.linalg.norm(vector1)
    vector2 = vector2 / np.linalg.norm(vector2)
    dot_product = np.dot(vector1, vector2)
    # determinant = np.linalg.det([vector1, vector2])
    determinant = np.cross(vector1, vector2)

    angle = np.arctan2(determinant, dot_product)
    angle = np.degrees(angle)
    if angle < 0:
        return 360 + angle
    return angle
    
def on_segment(p, q, r):
    if r[0] <= max(p[0], q[0]) and r[0] >= min(p[0], q[0]) and r[1] <= max(p[1], q[1]) and r[1] >= min(p[1], q[1]):
        return True
    return False

def orientation(p, q, r):
    val = ((q[1] - p[1]) * (r[0] - q[0])) - ((q[0] - p[0]) * (r[1] - q[1]))
    if val == 0 : return 0
    return 1 if val > 0 else -1

def intersects(seg1, seg2):
    p1, q1 = seg1
    p2, q2 = seg2

    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)
    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and on_segment(p1, q1, p2) : return True
    if o2 == 0 and on_segment(p1, q1, q2) : return True
    if o3 == 0 and on_segment(p2, q2, p1) : return True
    if o4 == 0 and on_segment(p2, q2, q1) : return True
    return False

def intersection_angle(prev_center, current_center, line_start, line_end):
    # 计算移动向量
    V = np.array([prev_center, current_center], dtype=np.float32)
    # 计算绊线向量
    L = np.array([line_start, line_end], dtype=np.float32)
    return lines_angle(V, L), intersects(V, L)

def adjust_box_within_bounds(max_width, max_height, x1, y1, x2, y2, width_expansion=0.5, height_expansion=0.2):
    # 原始宽度和高度
    width = x2 - x1
    height = y2 - y1
    
    # 计算扩展量
    width_extension = width * width_expansion
    height_extension = height * height_expansion
    
    # 调整坐标并确保不超出边界
    x1 = max(int(x1 - width_extension / 2), 0)
    x2 = min(int(x2 + width_extension / 2), max_width)
    y2 = min(int(y2 + height_extension), max_height)
    
    return x1, y1, x2, y2

# 预置颜色表
color_palette = [
    (255, 0, 0),    # 红色
    (0, 255, 0),    # 绿色
    (0, 0, 255),    # 蓝色
    (255, 255, 0),  # 黄色
    (255, 0, 255),  # 粉色
    (0, 255, 255),  # 青色
    (255, 165, 0),  # 橙色
    (255, 192, 203),# 浅粉红
    # ... 更多颜色
]