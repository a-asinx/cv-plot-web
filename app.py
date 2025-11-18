import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
import re
import numpy as np
from math import isfinite

st.set_page_config(page_title="CV 三段/多段 绘图平台（稳健版）", layout="wide")

# 中文字体设置（尽量兼容）
st.markdown("<style>body { font-family: 'SimHei', sans-serif; }</style>", unsafe_allow_html=True)
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

st.markdown("# 🔬 CV 绘图平台（稳健解析头部参数 & 数据驱动分段）\n---")
uploaded_file = st.file_uploader("📤 上传 CV 数据文件（CSV）", type=["csv"])

def extract_number(s):
    """从字符串中用正则提取第一个数字（支持科学计数），若找不到返回 None"""
    if s is None:
        return None
    m = re.search(r'[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?', str(s))
    if not m:
        return None
    try:
        return float(m.group(0))
    except:
        return None

def parse_params_from_lines(lines):
    """解析头部参数，返回一个 dict"""
    params = {}
    for line in lines:
        if not line.strip():
            continue
        # 分两种常见分隔：冒号或制表符或多个空格
        if ":" in line:
            parts = line.split(":", 1)
        elif "\t" in line:
            parts = line.split("\t", 1)
        else:
            # 尝试用多个空格分割
            parts = re.split(r'\s{2,}', line.strip(), maxsplit=1)
            if len(parts) == 1:
                continue
        key = parts[0].strip()
        val = parts[1].strip() if len(parts) > 1 else ""
        params[key] = val
    return params

def find_data_start_line(lines):
    for i, line in enumerate(lines):
        if "Potential" in line and "Current" in line:
            return i
    return None

if uploaded_file:
    try:
        text = uploaded_file.read().decode("utf-8", errors="ignore")
        lines = text.splitlines()

        # 解析头部参数（尽可能多）
        params = parse_params_from_lines(lines[:50])  # 通常前 50 行包含参数
        # 尝试提取关键参数
        init_E_mV = extract_number(params.get("Init E (mV)") or params.get("Init E") or params.get("Init E (V)"))
        high_E_mV = extract_number(params.get("High E (mV)") or params.get("High E") or params.get("High E (V)"))
        low_E_mV  = extract_number(params.get("Low E (mV)") or params.get("Low E") or params.get("Low E (V)"))
        sample_int_mV = extract_number(params.get("Sample Int (mV)") or params.get("Sample Int") or params.get("Sample Interval"))
        sweep_segments_raw = params.get("Sweep Segments") or params.get("Sweep Segment") or params.get("Sweep Segments ")
        sweep_segments = None
        if sweep_segments_raw is not None:
            try:
                sweep_segments = int(re.search(r'\d+', sweep_segments_raw).group(0))
            except:
                sweep_segments = None

        st.write("#### 解析到的头部参数（若为 None 则未解析到）")
        st.write({
            "Init E (mV)": init_E_mV,
            "High E (mV)": high_E_mV,
            "Low E (mV)": low_E_mV,
            "Sample Int (mV)": sample_int_mV,
            "Sweep Segments": sweep_segments
        })

        # 找到数据起始行并读取数据
        data_start = find_data_start_line(lines)
        if data_start is None:
            st.error("未在文件中找到 'Potential' 和 'Current' 的表头。请确认文件格式。")
            st.stop()

        csv_data = "\n".join(lines[data_start:])
        df = pd.read_csv(io.StringIO(csv_data))
        df.columns = [c.strip() for c in df.columns]
        x_col, y_col = df.columns[:2]

        x = pd.to_numeric(df[x_col], errors='coerce').values
        y = pd.to_numeric(df[y_col], errors='coerce').values

        # 移除含 NaN 的行
        valid = np.isfinite(x) & np.isfinite(y)
        x = x[valid]
        y = y[valid]

        if len(x) < 5:
            st.error("读取到的数据点过少，无法处理。")
            st.stop()

        # ---- 尝试基于头部参数分段（优先） ----
        segments = []
        used_method = None
        try:
            if (high_E_mV is not None) and (low_E_mV is not None) and (sample_int_mV is not None) and (sweep_segments is not None):
                # 所有必须参数存在 -> 计算每段点数（头部以 mV 给出）
                # points_per_seg 是基于 mV 单位计算
                points_per_seg = int(round(abs(high_E_mV - low_E_mV) / sample_int_mV)) + 1
                st.info(f"基于头部参数估算到每段点数 = {points_per_seg}")
                start = 0
                for i in range(sweep_segments):
                    end = start + points_per_seg
                    # 防止越界
                    if end > len(x):
                        end = len(x)
                    segments.append((start, end))
                    start = end
                used_method = "header"
                # 如果最后一个 segment 没有实际数据或 segments 数量不合理，降级
                if len(segments) < 1 or segments[0][1]-segments[0][0] < 3:
                    raise ValueError("头部估算的分段结果不合理，改用数据驱动方法")
            else:
                raise ValueError("头部参数不完整，改用数据驱动方法")
        except Exception as e:
            # 头部参数解析失败 -> 使用数据驱动方法（根据电位方向变化/转折点）
            used_method = "data-driven"
            st.warning(f"头部解析分段失败或不完整，改为数据驱动分段：{e}")

            # 计算电位一阶差分方向
            dx = np.diff(x)
            # 视为正扫（+1）或反扫（-1）或 0
            dir_sign = np.sign(dx)
            # 找到方向翻转点（从上升变为下降或反之）
            flips = np.where(np.diff(dir_sign) != 0)[0] + 1

            # 若没有明显翻转，尝试更宽松的检测拐点（极值）
            if len(flips) == 0:
                # 使用 second derivative sign changes as fallback
                flips = np.where(np.sign(np.diff(np.sign(np.diff(x)))) != 0)[0] + 1

            # 根据翻转点构造 segments
            seg_starts = [0] + flips.tolist()
            seg_ends = flips.tolist() + [len(x)]
            segments = list(zip(seg_starts, seg_ends))

            # 如果 segments 过多，合并近邻小段
            if len(segments) > 10:
                # 合并小段：把长度小于 3 的段合并到前一段
                new_segments = []
                for (s,e) in segments:
                    if new_segments and (e-s) < 3:
                        prev_s, prev_e = new_segments.pop()
                        new_segments.append((prev_s, e))
                    else:
                        new_segments.append((s,e))
                segments = new_segments

        st.success(f"使用 `{used_method}` 方法分段，检测到 {len(segments)} 段。")

        # ---- 绘图 ----
        st.markdown("## 📈 整体曲线")
        fig_all, ax_all = plt.subplots(figsize=(8,5))
        ax_all.plot(x, y, linewidth=1)
        ax_all.set_xlabel("Potential (V)")
        ax_all.set_ylabel("Current (A)")
        ax_all.grid(alpha=0.3)
        st.pyplot(fig_all)

        st.markdown("## 🔍 分段（每段独立显示）")
        # 用三列显示
        ncols = 3
        cols = st.columns(ncols)
        for idx, (s, e) in enumerate(segments):
            fig, ax = plt.subplots(figsize=(4,3))
            ax.plot(x[s:e], y[s:e])
            ax.set_title(f"段 {idx+1} [{s}:{e}] ({e-s} pts)")
            ax.set_xlabel("Potential (V)")
            ax.set_ylabel("Current (A)")
            ax.grid(alpha=0.3)
            cols[idx % ncols].pyplot(fig)

        st.info("✅ 分段绘图完成。若分段数与实际 Sweep Segments 不一致，请上传带有完整头部参数的文件或告知我你的期望分段数。")

    except Exception as err:
        st.error("程序运行时发生了意外错误，请查看下方异常信息以便调试：")
        st.exception(err)
