import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
import re
from fpdf import FPDF
import os
import matplotlib.pyplot as plt

st.set_page_config(page_title="自动 CV 分析", layout="wide")
st.title("⚡ 电化学工作站 CV 多圈分析")
st.caption("2025.11.18")


# =========================================================
# 工具函数
# =========================================================

def safe_decode(file):
    """自动 UTF-8 / GBK 识别"""
    try:
        return file.getvalue().decode("utf-8")
    except:
        return file.getvalue().decode("gbk", errors="ignore")


def save_curve_png(x, y, path, title="Curve"):
    """使用 matplotlib 保存曲线 PNG"""
    plt.figure(figsize=(8,4))
    plt.plot(x, y, color='royalblue', linewidth=2)
    plt.xlabel("Potential (V)")
    plt.ylabel("Current (A)")
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def generate_pdf_report(filename, params, cycles_data, full_curve_xy):
    """生成 PDF 报告"""
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
    full_png_path = os.path.join(filename + "_tmp_full.png")
    save_curve_png(full_curve_xy[0], full_curve_xy[1], full_png_path, title="Full CV Curve")
    pdf.image(full_png_path, w=170)

    # 每圈
    for idx, (df_cycle, peaks) in enumerate(cycles_data):
        pdf.add_page()
        pdf.cell(0, 10, f"Cycle {idx+1}:", ln=True)
        cycle_png_path = os.path.join(filename + f"_tmp_cycle_{idx+1}.png")
        save_curve_png(df_cycle["Potential"], df_cycle["Current"], cycle_png_path, title=f"Cycle {idx+1}")
        pdf.image(cycle_png_path, w=170)
        pdf.ln(5)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, f"Oxidation Peak: {peaks['ox']}", ln=True)
        pdf.cell(0, 8, f"Reduction Peak: {peaks['red']}", ln=True)

    buf = BytesIO()
    buf.write(pdf.output(dest="S").encode("latin-1"))
    # 删除临时文件
    os.remove(full_png_path)
    for idx in range(len(cycles_data)):
        os.remove(filename + f"_tmp_cycle_{idx+1}.png")
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
# 主循环
# =========================================================

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

    # ------------------- 切分圈
    dx = np.diff(x)
    direction = np.sign(dx)
    switch = np.where(np.diff(direction) != 0)[0] + 1
    segments = [(0, switch[0])] if len(switch) else []
    for a, b in zip(switch, np.append(switch[1:], len(x) - 1)):
        segments.append((a, b))
    cycles = []
    for i in range(0, len(segments), 2):
        if i + 1 < len(segments):
            cycles.append((segments[i][0], segments[i+1][1]))
    st.success(f"✔ 共识别到 {len(cycles)} 圈")

    # =========================================================
    # Plotly 全曲线显示
    # =========================================================
    st.subheader("📈 交互式完整曲线（可缩放）")
    fig_plotly = go.Figure()
    fig_plotly.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(color='royalblue', width=2)))
    fig_plotly.update_layout(
        title=dict(text="Full CV Curve", font=dict(size=24)),
        xaxis=dict(title="Potential (V)", title_font=dict(size=18),
                   tickfont=dict(size=14), showgrid=True, gridcolor='lightgrey'),
        yaxis=dict(title="Current (A)", title_font=dict(size=18),
                   tickfont=dict(size=14), showgrid=True, gridcolor='lightgrey'),
        height=600,
        margin=dict(l=80, r=40, t=80, b=60),
        legend=dict(font=dict(size=14)),
    )
    st.plotly_chart(fig_plotly, use_container_width=True)

    full_curve_xy = (x, y)

    # =========================================================
    # 每圈分析
    # =========================================================
    st.subheader("🔄 每一圈分析")
    excel_output = []
    cycles_data_list = []

    save_dir = f"{uploaded_file.name}_Cycles"
    os.makedirs(save_dir, exist_ok=True)

    for idx, (s, e) in enumerate(cycles, 1):
        st.markdown(f"### 🔸 第 {idx} 圈")
        xc, yc = x[s:e], y[s:e]

        # Plotly 每圈交互显示
        fig_cycle = go.Figure()
        fig_cycle.add_trace(go.Scatter(x=xc, y=yc, mode='lines', line=dict(color='firebrick', width=2)))
        fig_cycle.update_layout(
            title=dict(text=f"Cycle {idx}", font=dict(size=20)),
            xaxis=dict(title="Potential (V)", title_font=dict(size=16),
                       tickfont=dict(size=12), showgrid=True, gridcolor='lightgrey'),
            yaxis=dict(title="Current (A)", title_font=dict(size=16),
                       tickfont=dict(size=12), showgrid=True, gridcolor='lightgrey'),
            height=500,
            margin=dict(l=80, r=40, t=60, b=50),
        )
        st.plotly_chart(fig_cycle, use_container_width=True)

        # 保存每圈 CSV
        df_cycle = pd.DataFrame({"Potential": xc, "Current": yc})
        df_cycle.to_csv(os.path.join(save_dir, f"Cycle_{idx}.csv"), index=False)

        # 峰值
        ox_idx = np.argmax(yc)
        rd_idx = np.argmin(yc)
        ox = f"{yc[ox_idx]:.4e} A @ {xc[ox_idx]:.3f} V"
        rd = f"{yc[rd_idx]:.4e} A @ {xc[rd_idx]:.3f} V"
        st.write(f"**Oxidation Peak:** {ox}")
        st.write(f"**Reduction Peak:** {rd}")

        excel_output.append(df_cycle)
        cycles_data_list.append((df_cycle, {"ox": ox, "red": rd}))

    # =========================================================
    # 下载 Excel
    # =========================================================
    st.subheader("📥 导出结果")
    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        for i, dfc in enumerate(excel_output, 1):
            dfc.to_excel(writer, sheet_name=f"Cycle_{i}", index=False)
    st.download_button("⬇ 下载 Excel", excel_buf.getvalue(), file_name=f"{uploaded_file.name}_Cycles.xlsx")

    # =========================================================
    # 下载 PDF
    # =========================================================
    pdf_bytes = generate_pdf_report(uploaded_file.name, params, cycles_data_list, full_curve_xy)
    st.download_button("⬇ 下载 PDF 报告", pdf_bytes, file_name=f"{uploaded_file.name}_Report.pdf")

