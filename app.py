import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from io import BytesIO


# =================== 页面设置 ===================
st.set_page_config(page_title="自动 CV 分析平台 Pro", layout="wide")
st.title("⚡ 自动 CV 多圈分析平台 · Pro 版本")
st.caption("支持：自动解析参数 · 自动圈数识别 · 峰值检测 · 图像下载 · 多文件分析")


# =================== 文件上传 ===================
uploaded_files = st.file_uploader(
    "请选择一个或多个 CSV 文件：", 
    type=["csv"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.stop()


# ============ 公共函数：自动解码 UTF8 / GBK ============
def safe_decode(file):
    try:
        return file.getvalue().decode("utf-8")
    except:
        return file.getvalue().decode("gbk", errors="ignore")


# ============ 处理每一个文件 ============

for uploaded_file in uploaded_files:

    st.divider()
    st.header(f"📌 文件：{uploaded_file.name}")

    # 读取文本
    file_text = safe_decode(uploaded_file)
    raw_lines = file_text.splitlines()

    # ====== 自动提取 CSV 表头参数 ======
    param_dict = {}
    param_pattern = re.compile(r"(.+?)\s*[:\t]\s*(.+)")

    for line in raw_lines:
        m = param_pattern.match(line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            param_dict[key] = value

    with st.expander("📋 仪器参数（自动解析）", expanded=False):
        st.json(param_dict)

    # 参数解析带容错
    getF = lambda k, d=0: float(param_dict.get(k, d))
    getI = lambda k, d=0: int(param_dict.get(k, d))

    init_E = getF("Init E (mV)")
    high_E = getF("High E (mV)")
    low_E = getF("Low E (mV)")
    sample_int = getF("Sample Int (mV)")
    sweep_segments = getI("Sweep Segments", 2)

    full_cycles = sweep_segments // 2
    st.success(f"✔ 识别到：{sweep_segments} 个扫描段 → {full_cycles} 圈")

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

    # ====== 自动识别扫描段 ======
    dx = np.diff(x)
    direction = np.sign(dx)
    switch_points = np.where(np.diff(direction) != 0)[0] + 1

    segments = []
    start = 0
    for p in switch_points:
        segments.append((start, p))
        start = p
    segments.append((start, len(x) - 1))

    # ====== 合并两个 segment → 一圈 ======
    cycles = []
    for i in range(0, len(segments), 2):
        if i + 1 < len(segments):
            s, _ = segments[i]
            _, e = segments[i+1]
            cycles.append((s, e))

    st.info(f"已识别到 {len(cycles)} 圈完整扫描")

    # =================== 绘制全部曲线 ===================
    st.subheader("📈 全部扫描曲线")
    fig_full, ax1 = plt.subplots()
    ax1.plot(x, y)
    ax1.set_xlabel("Potential (V)")
    ax1.set_ylabel("Current (A)")
    ax1.grid(True)
    st.pyplot(fig_full)

    # 下载 PNG
    buf_png = BytesIO()
    fig_full.savefig(buf_png, format="png")
    st.download_button("下载当前图 (PNG)", buf_png.getvalue(), file_name=f"{uploaded_file.name}_full.png")

    # =================== 绘制每一圈 ===================
    st.subheader("🔄 每一圈分析")

    for idx, (s, e) in enumerate(cycles, 1):
        st.markdown(f"### 🔸 第 {idx} 圈")

        xc = x[s:e]
        yc = y[s:e]

        fig, ax = plt.subplots()
        ax.plot(xc, yc)
        ax.set_xlabel("Potential (V)")
        ax.set_ylabel("Current (A)")
        ax.grid(True)
        st.pyplot(fig)

        # ====== 峰值检测 ======
        max_idx = np.argmax(yc)
        min_idx = np.argmin(yc)

        st.write(
            f"**峰值电流（氧化峰）**： {yc[max_idx]:.4e} A @ {xc[max_idx]:.3f} V\n\n"
            f"**谷值电流（还原峰）**： {yc[min_idx]:.4e} A @ {xc[min_idx]:.3f} V"
        )

        # 下载
        buf_png = BytesIO()
        fig.savefig(buf_png, format="png")
        st.download_button(
            f"下载第{idx}圈图 (PNG)", 
            buf_png.getvalue(), 
            file_name=f"{uploaded_file.name}_cycle_{idx}.png"
        )
