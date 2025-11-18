import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from io import BytesIO
import re
from fpdf import FPDF


st.set_page_config(page_title="自动 CV 分析平台 Pro+", layout="wide")
st.title("⚡ 自动 CV 多圈分析平台 · Pro+ 版本")
st.caption("支持：自动解析参数 · 多圈切分 · 峰值分析 · Excel 导出 · PDF 报告 · 多曲线对比 · 交互缩放")


# =========================================================
# 工具函数
# =========================================================

def safe_decode(file):
    """自动 UTF-8 / GBK 识别"""
    try:
        return file.getvalue().decode("utf-8")
    except:
        return file.getvalue().decode("gbk", errors="ignore")


def generate_pdf_report(filename, params, cycles_data, full_fig_png, cycle_figs_png):
    """生成 PDF 分析报告"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)

    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(0, 10, "Cyclic Voltammetry Report", ln=True)

    # 参数
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Instrument Parameters:", ln=True)
    for k, v in params.items():
        pdf.cell(0, 8, f"{k}: {v}", ln=True)

    # 全图
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Full CV Curve:", ln=True)
    full_path = "/tmp/full.png"
    with open(full_path, "wb") as f:
        f.write(full_fig_png)
    pdf.image(full_path, w=170)

    # 每圈
    for idx, (png, info) in enumerate(cycle_figs_png):
        pdf.add_page()
        pdf.cell(0, 10, f"Cycle {idx+1}:", ln=True)
        path = f"/tmp/cycle_{idx}.png"
        with open(path, "wb") as f:
            f.write(png)
        pdf.image(path, w=170)
        pdf.ln(5)

        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, f"Oxidation Peak: {info['ox']}", ln=True)
        pdf.cell(0, 8, f"Reduction Peak: {info['red']}", ln=True)

    # 输出 PDF
    buf = BytesIO()
    buf.write(pdf.output(dest="S").encode("latin-1"))
    return buf.getvalue()


# =========================================================
# 文件上传
# =========================================================

uploaded_files = st.file_uploader(
    "请选择一个或多个 CSV 文件：",
    type=["csv"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.stop()


# =========================================================
# 主循环：处理每一个文件
# =========================================================

all_cycles_for_compare = {}   # 保存用于多曲线叠加

for uploaded_file in uploaded_files:

    st.divider()
    st.header(f"📌 文件：{uploaded_file.name}")

    file_text = safe_decode(uploaded_file)
    raw_lines = file_text.splitlines()

    # ------------------- 解析参数 -------------------
    params = {}
    pat = re.compile(r"(.+?)\s*[:\t]\s*(.+)")
    for line in raw_lines:
        m = pat.match(line)
        if m:
            params[m.group(1).strip()] = m.group(2).strip()

    with st.expander("📋 仪器参数（自动识别）"):
        st.json(params)

    # 参数解析
    getF = lambda k, d=0: float(params.get(k, d))
    getI = lambda k, d=0: int(params.get(k, d))

    sweep_segments = getI("Sweep Segments", 2)
    full_cycles = sweep_segments // 2

    # ------------------- 找数据表头 -------------------
    header_line = None
    for i, line in enumerate(raw_lines):
        if "Potential" in line and "Current" in line:
            header_line = i
            break

    df = pd.read_csv(uploaded_file, skiprows=header_line)
    df.columns = df.columns.str.strip()

    x_col = [c for c in df.columns if "Potential" in c][0]
    y_col = [c for c in df.columns if "Current" in c][0]
    x = df[x_col].values
    y = df[y_col].values

    # ------------------- 切分 segment -------------------
    dx = np.diff(x)
    direction = np.sign(dx)
    switch = np.where(np.diff(direction) != 0)[0] + 1

    segments = [(0, switch[0])] if len(switch) else []
    for a, b in zip(switch, np.append(switch[1:], len(x) - 1)):
        segments.append((a, b))

    # 合并成周期
    cycles = []
    for i in range(0, len(segments), 2):
        if i + 1 < len(segments):
            cycles.append((segments[i][0], segments[i+1][1]))

    st.success(f"✔ 共识别到 {len(cycles)} 圈")

    # =========================================================
    # ① 交互式 Plotly 全曲线（可缩放）
    # =========================================================
    st.subheader("📈 交互式完整曲线（可缩放）")

    fig_plotly = go.Figure()
    fig_plotly.add_trace(go.Scatter(x=x, y=y, mode='lines', name="Full Curve"))
    fig_plotly.update_layout(
        xaxis_title="Potential (V)",
        yaxis_title="Current (A)",
        title="Full CV Curve",
        height=500
    )
    st.plotly_chart(fig_plotly, use_container_width=True)

    # 保存用于 PDF
    buf_full = BytesIO()
    plt.figure()
    plt.plot(x, y)
    plt.savefig(buf_full, format="png")
    buf_full_png = buf_full.getvalue()

    # =========================================================
    # ② 每一圈分析
    # =========================================================
    st.subheader("🔄 每一圈分析")

    excel_output = []
    cycle_figs = []  # 用于 PDF

    for idx, (s, e) in enumerate(cycles, 1):

        st.markdown(f"### 🔸 第 {idx} 圈")
        xc, yc = x[s:e], y[s:e]

        # ---- matplotlib 图 ----
        fig, ax = plt.subplots()
        ax.plot(xc, yc)
        ax.grid(True)
        ax.set_xlabel("Potential (V)")
        ax.set_ylabel("Current (A)")
        st.pyplot(fig)

        # 保存 PNG
        buf = BytesIO()
        fig.savefig(buf, format="png")
        cycle_png = buf.getvalue()

        # 峰值检测
        ox_idx = np.argmax(yc)
        rd_idx = np.argmin(yc)
        ox = f"{yc[ox_idx]:.4e} A @ {xc[ox_idx]:.3f} V"
        rd = f"{yc[rd_idx]:.4e} A @ {xc[rd_idx]:.3f} V"

        st.write(f"**Oxidation Peak:** {ox}")
        st.write(f"**Reduction Peak:** {rd}")

        excel_output.append(pd.DataFrame({
            "Cycle": idx,
            "Potential": xc,
            "Current": yc
        }))

        cycle_figs.append((cycle_png, {"ox": ox, "red": rd}))

        # 保存用于叠加比较
        all_cycles_for_compare.setdefault(uploaded_file.name, {})[idx] = (xc, yc)

    # =========================================================
    # ③ 下载 Excel
    # =========================================================
    st.subheader("📥 导出结果")

    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        for i, dfc in enumerate(excel_output, 1):
            dfc.to_excel(writer, sheet_name=f"Cycle_{i}", index=False)

    st.download_button(
        "⬇ 下载 Excel",
        excel_buf.getvalue(),
        file_name=f"{uploaded_file.name}_Cycles.xlsx"
    )

    # =========================================================
    # ④ 下载 PDF 报告
    # =========================================================
    pdf_bytes = generate_pdf_report(uploaded_file.name, params, excel_output, buf_full_png, cycle_figs)

    st.download_button(
        "⬇ 下载 PDF 报告",
        pdf_bytes,
        file_name=f"{uploaded_file.name}_Report.pdf"
    )


# =========================================================
# ⑤ 多文件多曲线叠加
# =========================================================

st.divider()
st.header("📊 多曲线叠加比较（可缩放）")

file_names = list(all_cycles_for_compare.keys())

select_files = st.multiselect("选择文件用于叠加：", file_names)

if select_files:
    cycle_num = st.number_input("选择叠加的圈数（通常 1 为第一圈）", 1, 10, 1)

    fig_c = go.Figure()
    for fname in select_files:
        if cycle_num in all_cycles_for_compare[fname]:
            xc, yc = all_cycles_for_compare[fname][cycle_num]
            fig_c.add_trace(go.Scatter(x=xc, y=yc, mode='lines', name=f"{fname} - Cycle {cycle_num}"))

    fig_c.update_layout(
        xaxis_title="Potential (V)",
        yaxis_title="Current (A)",
        title="Multi-file Cycle Comparison (Interactive)",
        height=600
    )
    st.plotly_chart(fig_c, use_container_width=True)
