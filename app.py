import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from tkinter import Tk
from tkinter.filedialog import askopenfilename

# ================================
# 1. 选择文件
# ================================
Tk().withdraw()
file_path = askopenfilename(
    title="请选择 CSV 数据文件",
    filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
)

if not file_path:
    raise ValueError("未选择文件！")

print("你选择的文件是:", file_path)


# ================================
# 2. 自动查找真正的数据表头所在行
# ================================
header_line = None

with open(file_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        # 更宽松匹配，防止表头格式变化
        if ("Potential" in line and "Current" in line) or ("Potential(V)" in line):
            header_line = i
            break

if header_line is None:
    raise ValueError("❌ 未找到表头 Potential/Current ，请检查文件内容")


print(f"✔ 已识别表头在第 {header_line+1} 行")


# ================================
# 3. 正式读取数据
# ================================
df = pd.read_csv(file_path, skiprows=header_line)

# 去掉空白字符
df.columns = df.columns.str.strip()

# 只保留需要的数据列
possible_x = [c for c in df.columns if "Potential" in c]
possible_y = [c for c in df.columns if "Current" in c]

if not possible_x or not possible_y:
    raise ValueError("❌ 未检测到 Potential 或 Current 列，请检查文件格式")

x_col = possible_x[0]
y_col = possible_y[0]

df = df[[x_col, y_col]].dropna()

print(f"✔ 使用电位列: {x_col}, 电流列: {y_col}")

x = df[x_col].values
y = df[y_col].values


# ================================
# 4. 自动识别电压方向变化（确定扫描段）
# ================================
dx = np.diff(x)
direction = np.sign(dx)  # +1 上升, -1 下降

# 找方向变化点
switch_points = np.where(np.diff(direction) != 0)[0] + 1

# 每次方向变化，表示一次“半圈”
segments = []
start = 0
for p in switch_points:
    segments.append((start, p))
    start = p
segments.append((start, len(x)-1))


# ================================
# 5. 合并两个半圈为一整圈
# ================================
cycles = []
for i in range(0, len(segments), 2):
    if i + 1 < len(segments):
        s1, _ = segments[i]
        _, e2 = segments[i + 1]
        cycles.append((s1, e2))

print(f"✔ 自动识别到 {len(cycles)} 圈扫描")


# ================================
# 6. 绘制整体图像
# ================================
plt.figure(figsize=(7, 5))
plt.plot(x, y)
plt.title("Full Cyclic Voltammetry Scan")
plt.xlabel("Potential (V)")
plt.ylabel("Current (A)")
plt.grid(True)
plt.show()


# ================================
# 7. 绘制每一圈
# ================================
for idx, (s, e) in enumerate(cycles, start=1):
    plt.figure(figsize=(6, 4))
    plt.plot(x[s:e], y[s:e])
    plt.title(f"Cycle {idx}")
    plt.xlabel("Potential (V)")
    plt.ylabel("Current (A)")
    plt.grid(True)
    plt.show()
