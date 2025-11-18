import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("三圈闭合曲线数据可视化平台")
st.write("上传 CSV 文件，自动识别三圈闭合曲线并生成图像。")

# 用户上传 CSV 文件
uploaded_file = st.file_uploader("上传数据文件（CSV）", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # 自动检测列
    x_col, y_col = df.columns[:2]

    st.success(f"检测到 X 列：{x_col}，Y 列：{y_col}")

    x = df[x_col]
    y = df[y_col]

    # 识别电压扫描方向变化（峰值处换方向）
    turning_points = []
    for i in range(1, len(x)-1):
        if (x[i] > x[i-1] and x[i] > x[i+1]) or (x[i] < x[i-1] and x[i] < x[i+1]):
            turning_points.append(i)

    # Turning points 会是每圈的分界点
    # 三圈完整闭合曲线 ≈ 4 个拐点（start->peak->end->peak->end）
    # 这里取前 4 个 turning points，如果更多则精简
    turning_points = turning_points[:4]

    # 自动分割
    segments = []
    start = 0
    for tp in turning_points:
        segments.append((start, tp))
        start = tp
    segments.append((start, len(x)-1))

    # 绘制整体图
    st.subheader("整体扫描图")
    fig_all, ax_all = plt.subplots()
    ax_all.plot(x, y)
    ax_all.set_xlabel("Voltage (X)")
    ax_all.set_ylabel("Current (Y)")
    st.pyplot(fig_all)

    # 绘制每一圈图
    st.subheader("拆分后的每一圈图像")

    for idx, (s, e) in enumerate(segments):
        fig, ax = plt.subplots()
        ax.plot(x[s:e], y[s:e])
        ax.set_title(f"第 {idx+1} 圈")
        ax.set_xlabel("Voltage")
        ax.set_ylabel("Current")
        st.pyplot(fig)

    st.success("处理完成！")
