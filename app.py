import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import ast

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")

# ---------------------------------------------------------
# [설명 섹션] 대시보드 상단에 전처리 가이드 추가
# ---------------------------------------------------------
def show_preprocessing_guide():
    with st.expander("👁️ 동공 데이터가 '이상하게' 보였던 이유와 해결책 (연구자 가이드)", expanded=False):
        st.markdown("""
        ### 1. 왜 원시 데이터(Raw Data)는 엉망인가요?
        *   **눈 깜빡임(Blink):** 눈을 감으면 센서는 동공을 못 찾아 크기를 **0mm**로 기록합니다. 그래프가 갑자기 바닥으로 수직 낙하하는 이유입니다.
        *   **센서 노이즈:** 안구의 미세한 떨림이나 조명 반사로 인해 초당 수십 번씩 크기가 미세하게 변합니다.

        ### 2. 대시보드의 해결 방법 (슬라이더의 역할)
        1.  **아웃라이어 제거:** 1.5mm 미만(깜빡임 포함)이나 9.0mm 초과(오류) 데이터를 자동으로 삭제합니다.
        2.  **선형 보간(Interpolation):** 삭제되어 비어버린 공간을 앞뒤 데이터를 사용하여 부드러운 선으로 메꿉니다.
        3.  **스무딩(Smoothing - 슬라이더 조절):** 메꿔진 데이터들을 다시 한번 **이동 평균(Moving Average)**을 내어 자잘한 떨림을 없앱니다.
        
        **💡 연구 팁:** 슬라이더를 높일수록 자잘한 노이즈가 사라지고, 운전자가 패닉에 빠지거나 집중했을 때 나타나는 **'동공 확장 산봉우리(TEPR)'**가 명확히 보입니다.
        """)

st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
show_preprocessing_guide()

# ---------------------------------------------------------
# [핵심 함수 1] 바이너리 동공 데이터 파싱 및 전처리
# ---------------------------------------------------------
def load_eye_state(dtype_source, raw_source, time_source):
    try:
        if isinstance(dtype_source, str):
            with open(dtype_source, 'r') as f: dt_str = f.read()
            with open(raw_source, 'rb') as f: raw_bytes = f.read()
            with open(time_source, 'rb') as f: time_bytes = f.read()
        else:
            dt_str = dtype_source.getvalue().decode('utf-8')
            raw_bytes = raw_source.getvalue()
            time_bytes = time_source.getvalue()
            
        dt_list = ast.literal_eval(dt_str)
        dt = np.dtype(dt_list)
        data_arr = np.frombuffer(raw_bytes, dtype=dt)
        
        time_arr = np.frombuffer(time_bytes, dtype=np.int64)
        if 0 < time_arr.max() < 1e12:
            time_arr = np.frombuffer(time_bytes, dtype=np.float64)
            
        df = pd.DataFrame(data_arr)
        df['timestamp'] = time_arr
        return df
    except Exception as e:
        st.error(f"⚠️ 동공 바이너리 파싱 실패: {e}")
        return None

# ---------------------------------------------------------
# [핵심 함수 2] 폴더 내 파일 자동 매칭
# ---------------------------------------------------------
def find_files_in_folder(folder_path):
    ds_path, sac_path, blink_path, fix_path, map_path = None, None, None, None, None
    raw_path, time_path, dtype_path = None, None, None
    for filename in os.listdir(folder_path):
        lower_name = filename.lower()
        full_path = os.path.join(folder_path, filename)
        if lower_name.endswith('.csv'):
            if 'saccade' in lower_name: sac_path = full_path
            elif 'blink' in lower_name: blink_path = full_path
            elif 'fixation' in lower_name: fix_path = full_path
            elif 'map' in lower_name or 'name' in lower_name: map_path = full_path
            elif '_' in lower_name and 'world' not in lower_name: ds_path = full_path
        elif 'eye_state' in lower_name:
            if lower_name.endswith('.raw'): raw_path = full_path
            elif lower_name.endswith('.time'): time_path = full_path
            elif lower_name.endswith('.dtype'): dtype_path = full_path
    return ds_path, sac_path, blink_path, fix_path, map_path, raw_path, time_path, dtype_path

# ---------------------------------------------------------
# 1. 사이드바: 데이터 소스 선택
# ---------------------------------------------------------
st.sidebar.header("📁 1. 데이터 소스 선택")
data_mode = st.sidebar.radio("데이터 방식:", ["💾 서버 시나리오", "📤 직접 업로드"])

df_ds, df_sac, df_blink, df_fix, df_map, df_gaze = None, None, None, None, None, None
data_loaded = False
current_ds_filename = ""

if data_mode == "💾 서버 시나리오":
    folder_options = [item for item in os.listdir('.') if os.path.isdir(item) and not item.startswith('.') and not item == '__pycache__']
    if folder_options:
        selected_folder = st.sidebar.selectbox("폴더 선택:", folder_options)
        ds_p, sac_p, blink_p, fix_p, map_p, raw_p, time_p, dtype_p = find_files_in_folder(selected_folder)
        if ds_p and sac_p:
            df_ds, df_sac = pd.read_csv(ds_p), pd.read_csv(sac_p)
            df_blink = pd.read_csv(blink_p) if blink_p else None
            df_fix = pd.read_csv(fix_p) if fix_p else None
            df_map = pd.read_csv(map_p) if map_p else None
            if raw_p and time_p and dtype_p:
                df_gaze = load_eye_state(dtype_p, raw_p, time_p)
            current_ds_filename = os.path.basename(ds_p)
            data_loaded = True
else:
    # 업로드 로직 동일...
    ds_file = st.sidebar.file_uploader("주행 데이터 (.csv)", type=['csv'])
    sac_file = st.sidebar.file_uploader("시선 이동 (.csv)", type=['csv'])
    dtype_file = st.sidebar.file_uploader("eye_state.dtype", type=['dtype', 'txt', ''])
    raw_file = st.sidebar.file_uploader("eye_state.raw", type=['raw', ''])
    time_file = st.sidebar.file_uploader("eye_state.time", type=['time', ''])
    if ds_file and sac_file:
        df_ds, df_sac = pd.read_csv(ds_file), pd.read_csv(sac_file)
        if dtype_file and raw_file and time_file:
            df_gaze = load_eye_state(dtype_file, raw_file, time_file)
        current_ds_filename = ds_file.name
        data_loaded = True

# ---------------------------------------------------------
# 2. 사이드바: 분석 옵션 및 스무딩 슬라이더 (설명 강화)
# ---------------------------------------------------------
if data_loaded:
    st.sidebar.markdown("---")
    st.sidebar.header("🧠 데이터 정제 및 스무딩")
    
    # 슬라이더에 상세 설명(help) 주입
    smoothing_level = st.sidebar.slider(
        "📉 노이즈 제거 강도", 
        1, 20, 5, 
        help="""이 수치를 높이면 미세한 센서 떨림과 깜빡임 후유증을 지웁니다. 
        동공 크기의 '거시적인 흐름(확장/축소)'을 보고 싶다면 10 이상으로 설정하세요."""
    )
    
    time_offset = st.sidebar.slider("시간 오차 보정 (초)", -5.0, 5.0, 0.0)

    show_speed = st.sidebar.checkbox("📈 속도 표시", value=True)
    show_offset = st.sidebar.checkbox("↔️ 조향 편차", value=True)
    show_dynamic_pupil = st.sidebar.checkbox("👁️ 동적 동공 크기(TEPR) - 전처리 적용", value=True)

    # ---------------------------------------------------------
    # 데이터 전처리 로직 (보간/스무딩)
    # ---------------------------------------------------------
    ds_time_col = 'time' if 'time' in df_ds.columns else 'timestamp'
    ds_speed_col = 'speedInKmPerHour' if 'speedInKmPerHour' in df_ds.columns else 'speed'
    ds_offset_col = 'offsetFromLaneCenter' if 'offsetFromLaneCenter' in df_ds.columns else None
    sac_time_col = 'start timestamp [ns]' if 'start timestamp [ns]' in df_sac.columns else 'start timestamp'
    sac_amp_col = 'amplitude [deg]' if 'amplitude [deg]' in df_sac.columns else 'amplitude'
    
    ds_start_time = df_ds[ds_time_col].min()
    df_ds['Time_s'] = df_ds[ds_time_col] - ds_start_time
    sac_start_time = df_sac[sac_time_col].min()
    is_ns = df_sac[sac_time_col].max() > 1e12
    df_sac['Time_s'] = ((df_sac[sac_time_col] - sac_start_time) / 1e9) + time_offset if is_ns else (df_sac[sac_time_col] - sac_start_time) + time_offset

    # 💡 동공 전처리 핵심 (보간 + 슬라이더 기반 스무딩)
    if df_gaze is not None and 'pupil_diameter_left_mm' in df_gaze.columns:
        df_gaze['Time_s'] = ((df_gaze['timestamp'] - sac_start_time) / 1e9) + time_offset if is_ns else (df_gaze['timestamp'] - sac_start_time) + time_offset
        
        # 좌우 평균 구하기 및 아웃라이어(깜빡임)를 NaN으로 처리
        df_gaze['Pupil_Avg'] = df_gaze[['pupil_diameter_left_mm', 'pupil_diameter_right_mm']].mean(axis=1)
        df_gaze.loc[(df_gaze['Pupil_Avg'] < 1.5) | (df_gaze['Pupil_Avg'] > 9.0), 'Pupil_Avg'] = np.nan
        
        # 선형 보간 (비어있는 NaN 구간을 앞뒤 값으로 채움)
        df_gaze['Pupil_Interp'] = df_gaze['Pupil_Avg'].interpolate(method='linear')
        
        # 슬라이더 강도에 따른 이동 평균(Smoothing)
        # 동공 데이터는 초당 데이터가 많아 슬라이더 값의 10배 정도 가중치를 줌
        win = max(1, smoothing_level * 10)
        df_gaze['Pupil_Smooth'] = df_gaze['Pupil_Interp'].rolling(window=win, min_periods=1).mean()
        
        # 최종 NaN 제거
        df_gaze = df_gaze.dropna(subset=['Pupil_Smooth']).copy()

    # ---------------------------------------------------------
    # 차트 렌더링
    # ---------------------------------------------------------
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    if show_speed:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_speed_col], name='속도(km/h)', line=dict(color='royalblue', width=2)), secondary_y=False)
    
    if show_offset and ds_offset_col:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_offset_col], name='조향 편차', line=dict(color='seagreen', width=1.5, dash='dot')), secondary_y=True)

    if show_dynamic_pupil and df_gaze is not None:
        # 데이터가 너무 많으면 성능을 위해 5개당 1개만 샘플링
        plot_g = df_gaze.iloc[::5, :]
        fig.add_trace(go.Scatter(x=plot_g['Time_s'], y=plot_g['Pupil_Smooth'], name='동공 크기(보간+스무딩)', line=dict(color='#00BFFF', width=2.5)), secondary_y=True)

    fig.update_layout(title="통합 데이터 분석 차트 (스무딩 적용)", xaxis_title="시간 (초)", height=600, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.success(f"현재 데이터 정제 강도: {smoothing_level} | 데이터가 튄다면 슬라이더를 더 높여보세요.")
