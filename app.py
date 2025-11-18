import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
import re
from fpdf import FPDF
import os
import matplotlib.pyplot as plt

# =========================================================
# Matplotlib 中文支持
# =========================================================
plt.rcParams['font.sans-serif'] = ['SimHei']  # 中文字体
plt.rcParams['axes.unicode_minus'] = False    # 负号正常显示

st.set_page_config(page_title="自动 CV 分析平台 Pro+", layout="wide")
st.title("⚡ 自动 CV 多圈分析平台 · Pro+ 版本")
st.caption("支持：自动解析参数 · 多圈切分 · 峰值分析 · Excel 导出 · PDF 报告 · 多文件对比")

# =========================================================
# 工具函数
# =========================================================

def safe_decode(file):
    try:
        return file.getvalue().decode("utf-8")
    except:
        return file.getvalue().decode("gbk", errors="ignore")

def save_curve_png(x, y, path, title="曲线"):
    plt.figure(figsize=(8,4))
    plt.plot(x, y, color='royalblue', linewidth=2)
    plt.xlabel("电位 (V)")
    plt.ylabel("电流 (A)")
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def generate_pdf_report(filename, params, cycles_data, full_curve_xy):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(0, 10, "Cyclic Voltammetry Report", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Instrument Parameters:", ln=True)
    for k, v in params.items():
        pdf.cell(0, 8, f"{k}: {v}", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Full CV Curve:", ln=True)
    full_png_path = f"{filename}_tmp_full.png"
    save_curve_png(full_curve_xy[0], full_curve_xy[1], full_png_path, title="完整 CV 曲线")
    if os.path.exists(full_png_path):
        pdf.image(full_png_path, w=170)

    for idx, (df_cycle, peaks) in enumerate(cycles_data):
        pdf.add_page()
        pdf.cell(0, 10, f"第 {idx+1} 圈:", ln=True)
        cycle_png_path = f"{filename}_tmp_cycle_{idx+1}.png"
        save_curve_png(df_cycle["Potential"], df_cycle["Current"], cycle_png_path, title=f"第 {idx+1} 圈曲线")
        if os.path.exists(cycle_png_path):
            pdf.image(cycle_png_path, w=170)
        pdf.ln(5)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, f"氧化峰: {peaks['ox']}", ln=True)
        pdf.cell(0, 8, f"还原峰: {peaks['red']}", ln=True)

    buf = BytesIO()
    buf.write(pdf.output(dest="S").encode("latin-1"))
    
    for path in [full_png_path] + [f"{filename}_tmp_cycle_{i+1}.png" for i in range(len(cycles_data))]:
        if os.path.exists(path):
            os.remove(path)
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

all_cycles = {}
all_cycles_peaks = {}

for uploaded_file in uploaded_files:
    st.divider()
    st.header(f"📌 文件：{uploaded_file.name}")

    file_text = safe_decode(uploaded_file)
    raw_lines = file_text.splitlines()

    # 解析参数
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

    # 找数据表头
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

    # 切分圈
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

    # Plotly 全曲线
    st.subheader("📈 交互式完整曲线（可缩放）")
    fig_plotly = go.Figure()
    fig_plotly.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(color='royalblue', width=2)))
    fig_plotly.update_layout(
        title=dict(text="完整 CV 曲线", font=dict(size=24)),
        xaxis=dict(title="电位 (V)", title_font=dict(size=18), tickfont=dict(size=14), showgrid=True, gridcolor='lightgrey'),
        yaxis=dict(title="电流 (A)", title_font=dict(size=18), tickfont=dict(size=14), showgrid=True, gridcolor='lightgrey'),
        height=600,
        margin=dict(l=80, r=40, t=80, b=60),
        legend=dict(font=dict(size=14)),
    )
    st.plotly_chart(fig_plotly, use_container_width=True)
    full_curve_xy = (x, y)

    st.subheader("🔄 每一圈分析")
    excel_output = []
    cycles_data_list = []
    save_dir = f"{uploaded_file.name}_Cycles"
    os.makedirs(save_dir, exist_ok=True)
    all_cycles[uploaded_file.name] = {}
    all_cycles_peaks[uploaded_file.name] = {}

    for idx, (s, e) in enumerate(cycles, 1):
        st.markdown(f"### 🔸 第 {idx} 圈")
        xc, yc = x[s:e], y[s:e]

        fig_cycle = go.Figure()
        fig_cycle.add_trace(go.Scatter(x=xc, y=yc, mode='lines', line=dict(color='firebrick', width=2)))
        fig_cycle.update_layout(
            title=dict(text=f"第 {idx} 圈", font=dict(size=20)),
            xaxis=dict(title="电位 (V)", title_font=dict(size=16), tickfont=dict(size=12), showgrid=True, gridcolor='lightgrey'),
            yaxis=dict(title="电流 (A)", title_font=dict(size=16), tickfont=dict(size=12), showgrid=True, gridcolor='lightgrey'),
            height=500,
            margin=dict(l=80, r=40, t=60, b=50),
        )
        st.plotly_chart(fig_cycle, use_container_width=True)

        df_cycle = pd.DataFrame({"Potential": xc, "Current": yc})
        df_cycle.to_csv(os.path.join(save_dir, f"Cycle_{idx}.csv"), index=False)

        ox_idx = np.argmax(yc)
        rd_idx = np.argmin(yc)
        ox = f"{yc[ox_idx]:.4e} A @ {xc[ox_idx]:.3f} V"
        rd = f"{yc[rd_idx]:.4e} A @ {xc[rd_idx]:.3f} V"
        st.write(f"**氧化峰:** {ox}")
        st.write(f"**还原峰:** {rd}")

        excel_output.append(df_cycle)
        cycles_data_list.append((df_cycle, {"ox": ox, "red": rd}))
        all_cycles[uploaded_file.name][idx] = df_cycle
        all_cycles_peaks[uploaded_file.name][idx] = {"ox": ox, "red": rd}

    # 下载 Excel / PDF
    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        for i, dfc in enumerate(excel_output, 1):
            dfc.to_excel(writer, sheet_name=f"Cycle_{i}", index=False)
    st.download_button(
        label="⬇ 下载 Excel",
        data=excel_buf.getvalue(),
        file_name=f"{uploaded_file.name}_Cycles.xlsx",
        key=f"{uploaded_file.name}_excel"
    )

    pdf_bytes = generate_pdf_report(uploaded_file.name, params, cycles_data_list, full_curve_xy)
    st.download_button(
        label="⬇ 下载 PDF 报告",
        data=pdf_bytes,
        file_name=f"{uploaded_file.name}_Report.pdf",
        key=f"{uploaded_file.name}_pdf"
    )

# =========================================================
# 多文件多圈自定义对比
# =========================================================
st.divider()
st.header("📊 多文件多圈自定义对比（可缩放）")

file_names = list(all_cycles.keys())
selected_files = st.multiselect("选择文件用于叠加：", file_names)

cycle_selection = {}
if selected_files:
    for f in selected_files:
        max_cycle = len(all_cycles[f])
        cycle_selection[f] = st.number_input(f"{f} 选择圈数", 1, max_cycle, 1, key=f"{f}_cycle_input")

    fig_compare = go.Figure()
    compare_data = {}
    for f in selected_files:
        sel_cycle = cycle_selection[f]
        df_sel = all_cycles[f][sel_cycle]
        peaks_sel = all_cycles_peaks[f][sel_cycle]
        compare_data[f] = (df_sel, peaks_sel)
        fig_compare.add_trace(go.Scatter(x=df_sel["Potential"], y=df_sel["Current"], mode='lines', name=f"{f} Cycle {sel_cycle}"))

    fig_compare.update_layout(
        title="Multi-file Multi-cycle Comparison",
        xaxis_title="电位 (V)",
        yaxis_title="电流 (A)",
        height=600,
        legend=dict(font=dict(size=14)),
    )
    st.plotly_chart(fig_compare, use_container_width=True)

    if st.button("⬇ 导出对比数据 Excel/PNG"):
        export_buf = BytesIO()
        with pd.ExcelWriter(export_buf, engine="openpyxl") as writer:
            for f, (df_sel, peaks_sel) in compare_data.items():
                df_sel.to_excel(writer, sheet_name=f"{f}_数据", index=False)
            peak_summary = []
            for f, (df_sel, peaks_sel) in compare_data.items():
                peak_summary.append({"文件": f, "氧化峰": peaks_sel["ox"], "还原峰": peaks_sel["red"]})
            df_peak = pd.DataFrame(peak_summary)
            df_peak.to_excel(writer, sheet_name="峰值分析", index=False)
        st.download_button(
            label="⬇ 下载对比数据 Excel",
            data=export_buf.getvalue(),
            file_name="多文件多圈对比数据.xlsx",
            key="compare_excel"
        )

        # 对比曲线 PNG
        compare_png_path = "多文件多圈对比曲线.png"
        plt.figure(figsize=(8,4))
        for f, (df_sel, peaks_sel) in compare_data.items():
            plt.plot(df_sel["Potential"], df_sel["Current"], label=f"{f} Cycle {cycle_selection[f]}")
        plt.xlabel("电位 (V)")
        plt.ylabel("电流 (A)")
        plt.title("多文件多圈对比曲线")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(compare_png_path)
        plt.close()
        with open(compare_png_path, "rb") as f:
            png_bytes = f.read()
        st.download_button(
            label="⬇ 下载对比曲线 PNG",
            data=png_bytes,
            file_name="多文件多圈对比曲线.png",
            key="compare_png"
        )
        if os.path.exists(compare_png_path):
            os.remove(compare_png_path)
