import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re


st.set_page_config(page_title="自动 CV 分析平台", layout="centered")
st.title("🔬 自动 CV 曲线多圈分析平台")
st.write("上传 CSV 文件后，将自动解析仪器参数并分割所有扫描圈。")


# ============ 文件上传 ============
uploaded_file = st.file_uploader("请上传 CSV 文件：", type=["csv"])

if uploaded_file:
    # 读取全部文本行
    raw_lines = uploaded_file.getvalue().decode("utf-8").splitlines()

    # ====== 自动提取 CSV 表头参数 ======
    param_dict = {}
    param_pattern = re.compile(r"(.+?)\s*[:\t]\s*(.+)")

    for line in raw_lines:
        m = param_pattern.match(line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            param_dict[key] = value

    # 显示读取的参数
    st.subheader("📌 自动识别的仪器参数")
    st.json(param_dict)

    # 解析关键参数（带容错处理）
    try:
        init_E = float(param_dict.get("Init E (mV)", 0))
        high_E = float(param_dict.get("High E (mV)", 0))
        low_E = float(param_dict.get("Low E (mV)", 0))
        sample_int = float(param_dict.get("Sample Int (mV)", 5))
        sweep_segments = int(param_dict.get("Sweep Segments", 2))
    except:
        st.error("❌ 参数格式解析失败，请检查文件！")
        st.stop()

    # 一圈包含两个 segment
    full_cycles = sweep_segments // 2
    st.success(f"✔ 自动识别到 **{sweep_segments} 个扫描段** → **{full_cycles} 圈完整扫描**")

    # ====== 查找数据表头行 ======
    header_line = None
    for i, line in enumerate(raw_lines):
        if "Potential" in line and "Current" in line:
            header_line = i
            break

    if header_line is None:
        st.error("❌ 未找到 Potential / Current 表头！")
        st.stop()

    # ====== 读取数据 ======
    df = pd.read_csv(uploaded_file, skiprows=header_line)
    df.columns = df.columns.str.strip()

    x_col = [c for c in df.columns if "Potential" in c][0]
    y_col = [c for c in df.columns if "Current" in c][0]

    x = df[x_col].dropna().values
    y = df[y_col].dropna().values

    # ====== 自动识别电压方向变化（切分 segment）======
    dx = np.diff(x)
    direction = np.sign(dx)
    switch_points = np.where(np.diff(direction) != 0)[0] + 1

    segments = []
    start = 0
    for p in switch_points:
        segments.append((start, p))
        start = p
    segments.append((start, len(x)-1))

    st.write(f"自动检测到 {len(segments)} 个电压段（Segment）")

    # ====== 根据 Sweep Segments 精确匹配 ======
    if len(segments) != sweep_segments:
        st.warning("⚠ 自动识别的 Segment 数量与 Sweep Segments 不一致，但仍继续匹配。")

    # ====== 合并两个 Segment → 一圈 ======
    cycles = []
    for i in range(0, len(segments), 2):
        if i + 1 < len(segments):
            s1, _ = segments[i]
            _, e2 = segments[i + 1]
            cycles.append((s1, e2))

    st.success(f"✔ 最终识别到 {len(cycles)} 圈")

    # ====== 绘制整体图像 ======
    st.subheader("📈 全部扫描曲线")
    fig_full, ax_full = plt.subplots()
    ax_full.plot(x, y)
    ax_full.set_xlabel("Potential (V)")
    ax_full.set_ylabel("Current (A)")
    ax_full.grid(True)
    st.pyplot(fig_full)

    # ====== 绘制每一圈 ======
    st.subheader("🔄 每一圈图像")
    for idx, (s, e) in enumerate(cycles, start=1):
        st.markdown(f"### 第 {idx} 圈")
        fig, ax = plt.subplots()
        ax.plot(x[s:e], y[s:e])
        ax.set_xlabel("Potential (V)")
        ax.set_ylabel("Current (A)")
        ax.grid(True)
        st.pyplot(fig)
