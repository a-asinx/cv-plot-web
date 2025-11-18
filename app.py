import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="CV 三圈闭合曲线可视化平台", layout="wide")

st.markdown("""
# 🔬 CV 三圈闭合曲线可视化平台
上传实验 CSV 数据，我将自动识别数据区间并绘制三圈闭合曲线。
---
""")

uploaded_file = st.file_uploader("📤 上传你的 CV 数据文件（CSV 格式）", type=["csv"])

if uploaded_file:
    # 尝试自动检测数据起始行
    lines = uploaded_file.read().decode("utf-8").split("\n")

    data_start = None
    for i, line in enumerate(lines):
        if "Potential" in line and "Current" in line:
            data_start = i
            break

    if data_start is None:
        st.error("❌ 未找到数据表头（Potential / Current），请检查文件格式。")
    else:
        st.success(f"找到数据表头，位于第 {data_start + 1} 行")

        # 重新读入 CSV，从数据区开始
        csv_data = "\n".join(lines[data_start:])
        df = pd.read_csv(io.StringIO(csv_data))

        # 自动识别列名
        x_col, y_col = df.columns[:2]

        st.info(f"自动识别到列名：**{x_col}**, **{y_col}**")

        x = df[x_col].astype(float)
        y = df[y_col].astype(float)

        # --- 自动寻找 turning points（峰/谷，即换向点） ---
        turning_points = []
        for i in range(1, len(x)-1):
            if (x[i] > x[i-1] and x[i] > x[i+1]) or (x[i] < x[i-1] and x[i] < x[i+1]):
                turning_points.append(i)

        turning_points = turning_points[:4]  # 只取前 4 个

        # --- 分段 ---
        segments = []
        start = 0
        for tp in turning_points:
            segments.append((start, tp))
            start = tp
        segments.append((start, len(x)-1))

        # --- 绘制整体图 ---
        st.markdown("## 📈 整体扫描图（全曲线）")

        fig_all, ax_all = plt.subplots(figsize=(7,5))
        ax_all.plot(x, y)
        ax_all.set_xlabel("Voltage (V)")
        ax_all.set_ylabel("Current (A)")
        ax_all.grid(alpha=0.3)

        st.pyplot(fig_all)

        # --- 绘制每一圈 ---
        st.markdown("## 🔍 分圈图像展示")

        cols = st.columns(3)

        for idx, (s, e) in enumerate(segments):
            fig, ax = plt.subplots(figsize=(4,4))
            ax.plot(x[s:e], y[s:e])
            ax.set_title(f"第 {idx+1} 圈")
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel("Current (A)")
            ax.grid(alpha=0.3)

            cols[idx % 3].pyplot(fig)

        st.success("🎉 数据处理完成！")
