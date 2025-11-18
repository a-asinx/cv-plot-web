import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ==========================
# 网页标题
# ==========================
st.set_page_config(page_title="CV 三圈自动识别绘图平台", layout="centered")

st.title("🔬 CV 电化学三圈自动识别与绘图平台")
st.write("上传你的 CSV 数据文件，我将自动识别表头、自动分割三圈并绘图。")


# ==========================
# 文件上传
# ==========================
uploaded_file = st.file_uploader("请上传 CSV 数据文件：", type=["csv"])

if uploaded_file:

    # ==========================
    # 自动查找表头
    # ==========================
    lines = uploaded_file.getvalue().decode("utf-8").splitlines()

    header_line = None
    for i, line in enumerate(lines):
        if ("Potential" in line and "Current" in line) or ("Potential(V)" in line):
            header_line = i
            break

    if header_line is None:
        st.error("❌ 未找到 Potential / Current 表头，请检查文件格式！")
        st.stop()

    st.success(f"✔ 表头已自动识别：位于第 {header_line + 1} 行")

    # ==========================
    # 读取数据
    # ==========================
    df = pd.read_csv(uploaded_file, skiprows=header_line)
    df.columns = df.columns.str.strip()

    # 匹配列名
    x_col = [c for c in df.columns if "Potential" in c][0]
    y_col = [c for c in df.columns if "Current" in c][0]

    st.write(f"**识别电位列：** `{x_col}`")
    st.write(f"**识别电流列：** `{y_col}`")

    x = df[x_col].dropna().values
    y = df[y_col].dropna().values

    # ==========================
    # 自动识别方向变化（确定扫描段）
    # ==========================
    dx = np.diff(x)
    direction = np.sign(dx)
    switch_points = np.where(np.diff(direction) != 0)[0] + 1

    segments = []
    start = 0
    for p in switch_points:
        segments.append((start, p))
        start = p
    segments.append((start, len(x)-1))

    # 合并两段为一整圈
    cycles = []
    for i in range(0, len(segments), 2):
        if i + 1 < len(segments):
            s1, _ = segments[i]
            _, e2 = segments[i + 1]
            cycles.append((s1, e2))

    st.success(f"✔ 自动识别到 {len(cycles)} 圈完整扫描")

    # ==========================
    # 绘制整体图像
    # ==========================
    st.subheader("📈 全部扫描曲线")

    fig_full, ax_full = plt.subplots()
    ax_full.plot(x, y)
    ax_full.set_xlabel("Potential (V)")
    ax_full.set_ylabel("Current (A)")
    ax_full.grid(True)
    st.pyplot(fig_full)

    # ==========================
    # 每一圈独立绘图
    # ==========================
    st.subheader("🔄 每一圈扫描曲线")

    for idx, (s, e) in enumerate(cycles, start=1):
        st.markdown(f"### 第 {idx} 圈")
        fig, ax = plt.subplots()
        ax.plot(x[s:e], y[s:e])
        ax.set_xlabel("Potential (V)")
        ax.set_ylabel("Current (A)")
        ax.grid(True)
        st.pyplot(fig)

