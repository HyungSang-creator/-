import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import ast

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")

if 'custom_markers' not in st.session_state:
    st.session_state['custom_markers'] = {}

st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
st.markdown("서버에 저장된 시나리오를 불러오거나, 새로운 데이터를 직접 업로드하여 분석할 수 있습니다.")

# ---------------------------------------------------------
# [핵심 함수 1] 바이너리 동공 데이터 파싱
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
        
        # 타임스탬프 처리 (Pupil Labs는 보통 int64 ns 또는 float64 s 사용)
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
data_mode = st.sidebar.radio("어떤 방식으로 데이터를 분석할까요?", ["💾 서버에 내장된 시나리오 불러오기", "📤 내 PC에서 직접 파일 업로드"])
st.sidebar.markdown("---")

df_ds, df_sac, df_blink, df_fix, df_map, df_gaze = None, None, None, None, None, None
data_loaded = False
current_ds_filename = ""
selected_folder = ""

if data_mode == "💾 서버에 내장된 시나리오 불러오기":
    folder_options = [item for item in os.listdir('.') if os.path.isdir(item) and not item.startswith('.') and not item == '__pycache__']
    folder_options.sort()
    if len(folder_options) > 0:
        selected_folder = st.sidebar.selectbox("분석할 시나리오 폴더 선택:", folder_options)
        ds_p, sac_p, blink_p, fix_p, map_p, raw_p, time_p, dtype_p = find_files_in_folder(selected_folder)
        if ds_p and sac_p:
            df_ds = pd.read_csv(ds_p)
            df_sac = pd.read_csv(sac_p)
            df_blink = pd.read_csv(blink_p) if blink_p else None
            df_fix = pd.read_csv(fix_p) if fix_p else None
            df_map = pd.read_csv(map_p) if map_p else None
            if raw_p and time_p and dtype_p:
                df_gaze = load_eye_state(dtype_p, raw_p, time_p)
            current_ds_filename = os.path.basename(ds_p)
            data_loaded = True
        else:
            st.sidebar.error("⚠️ 필수 데이터를 찾지 못했습니다.")
else:
    ds_file = st.sidebar.file_uploader("주행 데이터 파일 (.csv)", type=['csv'])
    sac_file = st.sidebar.file_uploader("시선 이동(Saccade) 파일 (.csv)", type=['csv'])
    blink_file = st.sidebar.file_uploader("눈 깜빡임(Blink) 업로드 (선택)", type=['csv'])
    fix_file = st.sidebar.file_uploader("시선 고정(Fixations) 업로드 (선택)", type=['csv'])
    map_file = st.sidebar.file_uploader("객체 이름 사전(mapping.csv) 업로드 (선택)", type=['csv'])
    
    st.sidebar.caption("👇 동공 분석용 바이너리 3종 세트 (선택)")
    dtype_file = st.sidebar.file_uploader("eye_state.dtype", type=['dtype', 'txt', ''])
    raw_file = st.sidebar.file_uploader("eye_state.raw", type=['raw', ''])
    time_file = st.sidebar.file_uploader("eye_state.time", type=['time', ''])
    
    if ds_file and sac_file:
        df_ds = pd.read_csv(ds_file)
        df_sac = pd.read_csv(sac_file)
        df_blink = pd.read_csv(blink_file) if blink_file else None
        df_fix = pd.read_csv(fix_file) if fix_file else None
        df_map = pd.read_csv(map_file) if map_file else None
        if dtype_file and raw_file and time_file:
            df_gaze = load_eye_state(dtype_file, raw_file, time_file)
        current_ds_filename = ds_file.name
        data_loaded = True

# ---------------------------------------------------------
# 2. 사이드바: 분석 옵션 및 레이어
# ---------------------------------------------------------
if data_loaded:
    if data_mode == "💾 서버에 내장된 시나리오 불러오기":
        custom_scenario_name = selected_folder
    else:
        custom_scenario_name = os.path.splitext(current_ds_filename)[0] if current_ds_filename else "업로드된 시나리오"

    st.sidebar.header("⚙️ 2. 분석 레이어 및 옵션")
    show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
    show_accel = st.sidebar.checkbox("🚀 차량 가속도 표시 (m/s²)", value=False)
    show_offset = st.sidebar.checkbox("↔️ 조향 편차 (차로 이탈 정도)", value=True)
    show_saccade = st.sidebar.checkbox("👁️ 시선 이동 각도 (채워진 그래프)", value=True)
    show_blink = st.sidebar.checkbox("😌 눈 깜빡임 (하단 마커)", value=True)
    show_lane_change = st.sidebar.checkbox("🚧 차로 변경 궤적 하이라이트", value=True)
    time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -10.0, 10.0, 0.0, 0.1)

    st.sidebar.markdown("---")
    st.sidebar.header("🧠 심층 분석 동적 그래프")
    window_size = st.sidebar.slider("산출 윈도우 크기 (과거 n초)", 1.0, 10.0, 3.0, 0.5)
    smoothing_level = st.sidebar.slider("📉 데이터 스무딩 강도 (노이즈 제거)", 1, 20, 5, help="값이 클수록 그래프가 부드러워지며 경향성이 뚜렷해집니다.")
    
    st.sidebar.subheader("👁️ 인지/주의력 지표")
    show_dynamic_sge = st.sidebar.checkbox("👀 동적 시선 분산도(SGE)", value=False)
    show_dynamic_pupil = st.sidebar.checkbox("👁️ 동적 동공 크기(TEPR)", value=False)
    show_blink_sup = st.sidebar.checkbox("🚫 눈 깜빡임 억제 구간 표시", value=False)
    show_dynamic_steer = st.sidebar.checkbox("🔄 동적 조향 엔트로피", value=False)
    
    st.sidebar.subheader("🚗 차량 거동 안정성")
    show_dynamic_jerk = st.sidebar.checkbox("🚨 동적 가속도 변화율(Jerk)", value=False)
    show_dynamic_sdlp = st.sidebar.checkbox("↔️ 동적 차로 유지 편차(SDLP)", value=False)

    ds_dist_col = next((col for col in df_ds.columns if 'distance' in col.lower() or 'dist' in col.lower() or 'mileage' in col.lower()), None)
    
    st.sidebar.markdown("---")
    st.sidebar.header("🚨 3. 시나리오 구간 자동 감지")
    
    show_zones = st.sidebar.checkbox("🚧 이벤트 구간 배경 표시", value=True)
    show_humanoid_pos = st.sidebar.checkbox("🤖 휴머노이드 위치선 표시", value=True)
    show_taper_pos = st.sidebar.checkbox("🛣️ 테이퍼(2500m) 시점선 표시", value=True)
    
    scenario_id = current_ds_filename.split('_')[0] if '_' in current_ds_filename else current_ds_filename[0]
    if scenario_id not in ['0', '1', '2', '3']:
        scenario_id = '1'
        
    humanoid_positions = {'0': None, '1': 1000.0, '2': 1600.0, '3': 2200.0}
    actual_h_pos = humanoid_positions.get(scenario_id)
    
    st.sidebar.info(f"✅ 감지된 시나리오: **S{scenario_id}**")
    if actual_h_pos:
        st.sidebar.success(f"🤖 휴머노이드 물리적 위치: **{actual_h_pos}m**")
    else:
        st.sidebar.warning("🤖 휴머노이드: **없음 (S0)**")
        
    st.sidebar.caption("🗺️ 공사 구간: 1000m(주의) ➔ 2500m(완화/테이퍼) ➔ 2720m(작업) ➔ 3270m(종결)")

    # ---------------------------------------------------------
    # 4. 객체 감지 및 표시 (토글)
    # ---------------------------------------------------------
    objects_to_draw = []
    humanoid_gaze_stats = []
    fix_id_col, fix_time_col = None, None
    
    if df_fix is not None:
        fix_id_col = next((col for col in df_fix.columns if 'fixation id' in col.lower() or 'target' in col.lower() or 'object' in col.lower()), None)
        fix_time_col = next((col for col in df_fix.columns if 'start' in col.lower() or 'time' in col.lower()), None)
        dur_col = next((c for c in df_fix.columns if 'duration' in c.lower()), None)
        end_col = next((c for c in df_fix.columns if 'end' in c.lower() and 'time' in c.lower()), None)

        if fix_id_col and fix_time_col:
            valid_ids = [int(x) for x in df_fix[fix_id_col].dropna().unique() if str(x).strip() and int(x) > 0]
            st.sidebar.markdown("---")
            st.sidebar.header("🎯 4. 객체 감지 및 표시 (토글)")
            
            if df_map is not None:
                mapping_dict = {int(row.iloc[0]): str(row.iloc[1]) for _, row in df_map.iterrows()}
                for obj_id in valid_ids:
                    if obj_id in mapping_dict:
                        obj_name = mapping_dict[obj_id]
                        if "휴머노이드" in obj_name:
                            fix_rows = df_fix[df_fix[fix_id_col] == obj_id]
                            if not fix_rows.empty:
                                raw_dur = 0.0
                                if dur_col:
                                    raw_val = fix_rows[dur_col].sum()
                                    raw_dur = raw_val / 1000.0 if raw_val > 10 else raw_val
                                elif end_col:
                                    diff = fix_rows[end_col].max() - fix_rows[fix_time_col].min()
                                    raw_dur = diff / 1e9 if diff > 1e12 else diff
                                order = 1 if obj_name == "휴머노이드" else (int(obj_name.split("-")[1]) + 1 if "-" in obj_name else 99)
                                humanoid_gaze_stats.append((order, raw_dur))
                        if "-" not in obj_name:
                            if st.sidebar.checkbox(f"🔴 {obj_name}", value=True):
                                objects_to_draw.append((obj_id, obj_name))
            else:
                st.sidebar.caption("⚠️ mapping.csv 파일이 없습니다.")
                selected_ids = st.sidebar.multiselect("분석할 객체 번호 선택:", sorted(valid_ids))
                for sid in selected_ids:
                    custom_name = st.sidebar.text_input(f"ID {sid} 표시 이름:", value=f"객체 {sid}")
                    objects_to_draw.append((sid, custom_name))
            humanoid_gaze_stats.sort(key=lambda x: x[0])

    # ---------------------------------------------------------
    # 데이터 전처리 및 분석 로직
    # ---------------------------------------------------------
    ds_time_col = 'time' if 'time' in df_ds.columns else 'timestamp'
    ds_speed_col = 'speedInKmPerHour' if 'speedInKmPerHour' in df_ds.columns else ('speed' if 'speed' in df_ds.columns else 'Velocity')
    ds_lane_col = 'laneNumber' if 'laneNumber' in df_ds.columns else ('Lane_ID' if 'Lane_ID' in df_ds.columns else None)
    ds_offset_col = 'offsetFromLaneCenter' if 'offsetFromLaneCenter' in df_ds.columns else None
    steer_col = next((col for col in df_ds.columns if 'steer' in col.lower()), None)
    sac_time_col = 'start timestamp [ns]' if 'start timestamp [ns]' in df_sac.columns else 'start timestamp'
    sac_amp_col = 'amplitude [deg]' if 'amplitude [deg]' in df_sac.columns else 'amplitude'
    
    ds_start_time = df_ds[ds_time_col].min()
    df_ds['Time_s'] = df_ds[ds_time_col] - ds_start_time
    sac_start_time = df_sac[sac_time_col].min()
    is_ns = df_sac[sac_time_col].max() > 1e12
    df_sac['Time_s'] = ((df_sac[sac_time_col] - sac_start_time) / 1e9) + time_offset if is_ns else (df_sac[sac_time_col] - sac_start_time) + time_offset

    if df_fix is not None and fix_time_col is not None:
        is_fix_ns = df_fix[fix_time_col].max() > 1e12
        df_fix['Time_s'] = ((df_fix[fix_time_col] - sac_start_time) / 1e9) + time_offset if is_fix_ns else (df_fix[fix_time_col] - sac_start_time) + time_offset

    # 💡 [신규] 원시 바이너리 기반 동공 크기 산출 로직
    if df_gaze is not None and 'pupil_diameter_left_mm' in df_gaze.columns and 'pupil_diameter_right_mm' in df_gaze.columns:
        is_gaze_ns = df_gaze['timestamp'].max() > 1e12
        df_gaze['Time_s'] = ((df_gaze['timestamp'] - sac_start_time) / 1e9) + time_offset if is_gaze_ns else (df_gaze['timestamp'] - sac_start_time) + time_offset
        
        # 좌/우 동공 평균 및 유효하지 않은 값(0) 제외
        df_gaze['Pupil_Avg'] = df_gaze[['pupil_diameter_left_mm', 'pupil_diameter_right_mm']].replace(0, np.nan).mean(axis=1)
        df_gaze = df_gaze.dropna(subset=['Pupil_Avg']).copy()
        
        if smoothing_level > 1:
            df_gaze['Pupil_Smooth'] = df_gaze['Pupil_Avg'].rolling(window=smoothing_level*5, min_periods=1).mean()
        else:
            df_gaze['Pupil_Smooth'] = df_gaze['Pupil_Avg']

    lane_change_count = 0
    filtered_lane_changes = []
    
    if ds_lane_col in df_ds.columns:
        df_ds.loc[df_ds[ds_lane_col]
