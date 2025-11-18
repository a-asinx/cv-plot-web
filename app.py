import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
import re

st.set_page_config(page_title="CV 三段/三圈绘图平台", layout="wide")

# ---- 中文字体设置 ----
st.markdown("<style>body { font-family: 'SimHei', sans-serif; }</style>", unsafe_allow_html=True)
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

st.markdown("# 🔬 CV 三段（三圈）自动绘图平台\n---")
uploaded_file = st.file_uploader("📤 上传 CV 数据文件（CSV）", type=["csv"])

if uploaded_file:

    # 读整个文本以解析参数
    text = uploaded_file.read().decode("utf-8")
    lines = text.split("\n")

    # ---- 提取参数区（表头） ----
    params = {}
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            params[key.strip()] = value.strip()
        elif "\t" in line:
            key, value = line.split("\t", 1)
            params[key.strip()] = value.strip()

    # ---- 从参数中解析数值 ----
    def get_param(name, default=None):
        if name not in params:
            return default
        try:
            return float(params[name])
        except:
            return params[name]

    init_E = get_param("Init E (mV)")
    high_E = get_param("High E (mV)")
    low_E = get_param("Low E (mV)")
    sample_int = get_param("Sample Int (mV)")
    sweep_seg = int(get_param("Sweep Segments", 3))

    st.info(f"""
    **自动参数识别成功：**

    - 起始电位 Init E：{init_E} mV  
    - 高电位 High E：{high_E} mV  
    - 低电位 Low E：{low_E} mV  
    - 步进 Sample Interval：{sample_int} mV  
    - 扫描段数 Sweep Segments：{sweep_seg}
    """)

    # ---- 寻找数据开始行 ----
    data_start = None
    for i, line in enumerate(lines):
        if "Potential" in line and "Current" in line:
            data_start = i
            break

    if data_start is None:
        st.error("❌ 未找到数据表头！")
    else:
        csv_data = "\n".join(lines[data_start:])
        df = pd.read_csv(io.StringIO(csv_data))

        x_col, y_col = df.columns[:2]
        x = df[x_col].astype(float)
        y = df[y_col].astype(float)

        # ---- 自动根据参数计算每段点数 ----
        points_per_seg = int(abs(high_E - low_E) / sample_int) + 1

        st.success(f"每段大致点数估计：{points_per_seg} 点")

        # 分段
        segments = []
        start = 0
        for i in range(sweep_seg):
            end = start + points_per_seg
            segments.append((start, end))
            start = end

        # ---- 整体图 ----
        st.markdown("## 📈 整体曲线")
        fig_all, ax = plt.subplots(figsize=(7,5))
        ax.plot(x, y)
        ax.set_xlabel("电位 (V)")
        ax.set_ylabel("电流 (A)")
        ax.grid(alpha=0.3)
        st.pyplot(fig_all)

        # ---- 单段图 ----
        st.markdown("## 🔍 各段曲线")
        cols = st.columns(3)

        for idx, (s, e) in enumerate(segments):
            fig, ax = plt.subplots(figsize=(4,4))
            ax.plot(x[s:e], y[s:e])
            ax.set_title(f"第 {idx+1} 段")
            ax.set_xlabel("电位 (V)")
            ax.set_ylabel("电流 (A)")
            ax.grid(alpha=0.3)
            cols[idx % 3].pyplot(fig)

        st.success("🎉 绘图完成！")
