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

# ---------------------------------------------------------
# [설명 섹션] 대시보드 상단에 전처리 가이드 추가
# ---------------------------------------------------------
def show_preprocessing_guide():
    with st.expander("👁️ 동공 데이터가 '이상하게' 보였던 이유와 해결책 (연구자 가이드)", expanded=False):
        st.markdown("""
        ### 1. 왜 원시 데이터(Raw Data)는 엉망인가요?
        * **눈 깜빡임(Blink):** 눈을 감으면 센서는 동공을 못 찾아 크기를 **0mm**로 기록합니다. 그래프가 갑자기 바닥으로 수직 낙하하는 이유입니다.
        * **센서 노이즈:** 안구의 미세한 떨림이나 조명 반사로 인해 초당 수십 번씩 크기가 미세하게 변합니다.

        ### 2. 대시보드의 해결 방법 (슬라이더의 역할)
        1.  **아웃라이어 제거:** 1.5mm 미만(깜빡임 포함)이나 9.0mm 초과(오류) 데이터를 자동으로 삭제합니다.
        2.  **선형 보간(Interpolation):** 삭제되어 비어버린 공간을 앞뒤 데이터를 사용하여 부드러운 선으로 메꿉니다.
        3.  **스무딩(Smoothing - 슬라이더 조절):** 메꿔진 데이터들을 다시 한번 **이동 평균(Moving Average)**을 내어 자잘한 떨림을 없앱니다.
        
        **💡 연구 팁:** 슬라이더를 높일수록 자잘한 노이즈가 사라지고, 운전자가 패닉에 빠지거나 집중했을 때 나타나는 **'동공 확장 산봉우리(TEPR)'**가 명확히 보입니다.
        """)

st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
st.markdown("서버에 저장된 시나리오를 불러오거나, 새로운 데이터를 직접 업로드하여 분석할 수 있습니다.")
show_preprocessing_guide()

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
    custom_scenario_name = selected_folder if data_mode == "💾 서버에 내장된 시나리오 불러오기" else (os.path.splitext(current_ds_filename)[0] if current_ds_filename else "업로드된 시나리오")
    # 💡 [핵심] 시나리오 간 캐싱 간섭을 막기 위한 고유 키 생성
    scen_key = custom_scenario_name.replace(" ", "_").replace(".", "_")

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
    smoothing_level = st.sidebar.slider("📉 데이터 스무딩 강도 (노이즈 제거)", 1, 20, 5, help="이 수치를 높이면 미세한 센서 떨림과 깜빡임 후유증을 지웁니다. 동공 크기의 거시적인 흐름을 보고 싶다면 10 이상으로 설정하세요.")
    
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

    # 동공 크기 전처리
    if df_gaze is not None and 'pupil_diameter_left_mm' in df_gaze.columns and 'pupil_diameter_right_mm' in df_gaze.columns:
        is_gaze_ns = df_gaze['timestamp'].max() > 1e12
        df_gaze['Time_s'] = ((df_gaze['timestamp'] - sac_start_time) / 1e9) + time_offset if is_gaze_ns else (df_gaze['timestamp'] - sac_start_time) + time_offset
        
        df_gaze['Pupil_Avg'] = df_gaze[['pupil_diameter_left_mm', 'pupil_diameter_right_mm']].mean(axis=1)
        df_gaze.loc[(df_gaze['Pupil_Avg'] < 1.5) | (df_gaze['Pupil_Avg'] > 9.0), 'Pupil_Avg'] = np.nan
        df_gaze['Pupil_Interp'] = df_gaze['Pupil_Avg'].interpolate(method='linear')
        
        smooth_win = max(10, smoothing_level * 10)
        df_gaze['Pupil_Smooth'] = df_gaze['Pupil_Interp'].rolling(window=smooth_win, min_periods=1).mean()
        df_gaze = df_gaze.dropna(subset=['Pupil_Smooth']).copy()

    lane_change_count = 0
    filtered_lane_changes = []
    
    if ds_lane_col in df_ds.columns:
        df_ds.loc[df_ds[ds_lane_col] >= 3, ds_lane_col] = 2
        df_ds.loc[df_ds[ds_lane_col] <= 0, ds_lane_col] = 1
        
        raw_lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0]['Time_s'].tolist()
        last_lc_time = -999.0
        
        for lc_time in raw_lane_changes:
            if lc_time - last_lc_time > 5.0:
                filtered_lane_changes.append(lc_time)
                last_lc_time = lc_time
                
        lane_change_count = len(filtered_lane_changes)

    accel_col = next((col for col in df_ds.columns if 'accel' in col.lower() and 'x' in col.lower()), None)
    if accel_col:
        y_accel = df_ds[accel_col]
    else:
        y_accel = (df_ds[ds_speed_col] / 3.6).diff() / df_ds['Time_s'].diff()

    # 동적 지표 계산
    time_vals = df_ds['Time_s'].values

    if show_dynamic_sge and df_fix is not None and fix_id_col in df_fix.columns:
        sge_vals = []
        fix_t = df_fix['Time_s'].values; fix_i = df_fix[fix_id_col].values
        for ct in time_vals:
            mask = (fix_t >= ct - window_size) & (fix_t <= ct)
            w_ids = fix_i[mask]
            if len(w_ids) > 0:
                _, counts = np.unique(w_ids, return_counts=True)
                p = counts / counts.sum(); sge_vals.append(-np.sum(p * np.log2(p)))
            else: sge_vals.append(0.0)
        df_ds['Dynamic_SGE'] = sge_vals

    if show_dynamic_steer:
        target_steer_col = steer_col if steer_col else ds_offset_col
        if target_steer_col:
            s_data = df_ds[target_steer_col].fillna(0).values
            x_1 = pd.Series(s_data).shift(1); x_2 = pd.Series(s_data).shift(2); x_3 = pd.Series(s_data).shift(3)
            pred = x_1 + (x_1 - x_2) + 0.5 * ((x_1 - x_2) - (x_2 - x_3))
            err_vals = (s_data - pred).values
            ent_vals = []
            for ct in time_vals:
                mask = (time_vals >= ct - window_size) & (time_vals <= ct) & ~np.isnan(err_vals)
                w_err = err_vals[mask]
                if len(w_err) > 10:
                    bins = np.histogram_bin_edges(w_err, bins=9)
                    p_s, _ = np.histogram(w_err, bins=bins)
                    p_s = p_s[p_s > 0] / sum(p_s); ent_vals.append(-np.sum(p_s * np.log2(p_s)))
                else: ent_vals.append(0.0)
            df_ds['Dynamic_Steer_Ent'] = ent_vals

    if show_dynamic_jerk:
        df_ds['Dynamic_Jerk'] = y_accel.diff() / df_ds['Time_s'].diff()

    if show_dynamic_sdlp and ds_offset_col:
        sdlp_vals = []
        offset_data = df_ds[ds_offset_col].values
        for ct in time_vals:
            mask = (time_vals >= ct - window_size) & (time_vals <= ct)
            w_offset = offset_data[mask]
            if len(w_offset) > 1:
                sdlp_vals.append(np.std(w_offset))
            else: sdlp_vals.append(0.0)
        df_ds['Dynamic_SDLP'] = sdlp_vals

    if smoothing_level > 1:
        if 'Dynamic_SGE' in df_ds.columns:
            df_ds['Dynamic_SGE'] = df_ds['Dynamic_SGE'].rolling(window=smoothing_level, min_periods=1).mean()
        if 'Dynamic_Steer_Ent' in df_ds.columns:
            df_ds['Dynamic_Steer_Ent'] = df_ds['Dynamic_Steer_Ent'].rolling(window=smoothing_level, min_periods=1).mean()
        if 'Dynamic_Jerk' in df_ds.columns:
            df_ds['Dynamic_Jerk'] = df_ds['Dynamic_Jerk'].rolling(window=smoothing_level, min_periods=1).mean()
        if 'Dynamic_SDLP' in df_ds.columns:
            df_ds['Dynamic_SDLP'] = df_ds['Dynamic_SDLP'].rolling(window=smoothing_level, min_periods=1).mean()

    # ---------------------------------------------------------
    # 차트 그리기
    # ---------------------------------------------------------
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    max_y = df_ds[ds_speed_col].max() if ds_speed_col in df_ds.columns else 100

    if show_speed and ds_speed_col in df_ds.columns:
        hovertemplate = '%{y:.1f} <br>📍 위치: %{customdata:.1f} m' if ds_dist_col else '%{y:.1f}'
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_speed_col], mode='lines', name='속도(km/h)', line=dict(color='royalblue', width=2), customdata=df_ds[ds_dist_col] if ds_dist_col else None, hovertemplate=hovertemplate), secondary_y=False)

    if show_accel:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=y_accel, mode='lines', name='가속도(m/s²)', line=dict(color='darkmagenta', width=1.5)), secondary_y=True)

    if show_offset and ds_offset_col in df_ds.columns:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_offset_col], mode='lines', name='조향 편차', line=dict(color='seagreen', width=2, dash='dot')), secondary_y=True)

    if show_saccade and sac_amp_col in df_sac.columns:
        fig.add_trace(go.Scatter(x=df_sac['Time_s'], y=df_sac[sac_amp_col], mode='lines', name='시선 이동', fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.4)', line=dict(color='crimson', width=0.5)), secondary_y=False)

    if show_dynamic_sge and 'Dynamic_SGE' in df_ds.columns:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_SGE'], mode='lines', name='동적 SGE', line=dict(color='#FF8C00', width=2.5)), secondary_y=True)
    if show_dynamic_steer and 'Dynamic_Steer_Ent' in df_ds.columns:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_Steer_Ent'], mode='lines', name='동적 조향 엔트로피', line=dict(color='#8A2BE2', width=2.5, dash='solid')), secondary_y=True)
    if show_dynamic_jerk and 'Dynamic_Jerk' in df_ds.columns:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_Jerk'], mode='lines', name='Jerk (m/s³)', line=dict(color='#FF1493', width=2, dash='dot')), secondary_y=True)
    if show_dynamic_sdlp and 'Dynamic_SDLP' in df_ds.columns:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_SDLP'], mode='lines', name='동적 SDLP (m)', line=dict(color='#20B2AA', width=2.5, dash='solid')), secondary_y=True)

    if show_dynamic_pupil and df_gaze is not None and 'Pupil_Smooth' in df_gaze.columns:
        plot_gaze = df_gaze if len(df_gaze) < 50000 else df_gaze.iloc[::10, :]
        fig.add_trace(go.Scatter(x=plot_gaze['Time_s'], y=plot_gaze['Pupil_Smooth'], mode='lines', name='동공 크기 (TEPR, mm)', line=dict(color='#00BFFF', width=2.5)), secondary_y=True)

    if show_blink and df_blink is not None:
        blink_time_col = 'start timestamp [ns]' if 'start timestamp [ns]' in df_blink.columns else 'start timestamp'
        if blink_time_col in df_blink.columns:
            df_blink['Time_s'] = ((df_blink[blink_time_col] - sac_start_time) / 1e9) + time_offset if is_ns else (df_blink[blink_time_col] - sac_start_time) + time_offset
            fig.add_trace(go.Scatter(x=df_blink['Time_s'], y=[-5] * len(df_blink), mode='markers', name='눈 깜빡임 발생', marker=dict(symbol='line-ns', color='darkorange', size=15, line=dict(width=2)), hoverinfo='x+name'), secondary_y=False)

            if show_blink_sup:
                b_times = df_blink.sort_values('Time_s')['Time_s'].values
                for i in range(1, len(b_times)):
                    if b_times[i] - b_times[i-1] >= 5.0:
                        fig.add_vrect(x0=b_times[i-1], x1=b_times[i], fillcolor="black", opacity=0.15, layer="below", line_width=0, annotation_text="깜빡임 억제", annotation_position="top left", annotation_font_size=10, annotation_font_color="gray")

    if show_lane_change and lane_change_count > 0:
        for lc in filtered_lane_changes:
            fig.add_vrect(x0=lc-3.0, x1=lc+3.0, fillcolor="gold", opacity=0.15, layer="below", line_width=0, annotation_text="차로 변경")

    if show_zones and ds_dist_col:
        work_zones = [
            {"name": "🟢 주의구간", "start": 1000.0, "end": 2500.0, "color": "rgba(144, 238, 144, 0.15)"},
            {"name": "🟡 완화구간 (테이퍼)", "start": 2500.0, "end": 2720.0, "color": "rgba(255, 165, 0, 0.15)"},
            {"name": "🔴 작업구간", "start": 2720.0, "end": 3270.0, "color": "rgba(255, 0, 0, 0.15)"},
            {"name": "⚫ 종결구간", "start": 3270.0, "end": 3300.0, "color": "rgba(128, 128, 128, 0.15)"}
        ]
        for zone in work_zones:
            start_df = df_ds[df_ds[ds_dist_col] >= zone["start"]]
            end_df = df_ds[df_ds[ds_dist_col] >= zone["end"]]
            if not start_df.empty:
                z_start_time = start_df.iloc[0]['Time_s']
                z_end_time = end_df.iloc[0]['Time_s'] if not end_df.empty else df_ds['Time_s'].max()
                if z_start_time < z_end_time:
                    fig.add_trace(go.Scatter(
                        x=[z_start_time, z_end_time, z_end_time, z_start_time, z_start_time], 
                        y=[0, 0, max_y*1.1, max_y*1.1, 0], 
                        fill='toself', fillcolor=zone["color"], mode='lines', line=dict(width=0),
                        name=zone["name"], hoveron='fills', hoverinfo='text',
                        text=f"<b>{zone['name']}</b><br>{zone['start']}m ~ {zone['end']}m", showlegend=False
                    ), secondary_y=False)

    if show_humanoid_pos and actual_h_pos is not None and ds_dist_col:
        h_df = df_ds[df_ds[ds_dist_col] >= actual_h_pos]
        if not h_df.empty:
            h_pass_time = h_df.iloc[0]['Time_s']
            fig.add_trace(go.Scatter(
                x=[h_pass_time, h_pass_time], y=[0, max_y], mode='lines', 
                line=dict(color='purple', width=3, dash='solid'),
                name="휴머노이드 물리적 위치", 
                hovertemplate=f"<b>🤖 휴머노이드 물리적 위치</b><br>거리: {actual_h_pos}m<extra></extra>", showlegend=False
            ), secondary_y=False)

    if show_taper_pos and ds_dist_col:
        taper_df = df_ds[df_ds[ds_dist_col] >= 2500.0]
        if not taper_df.empty:
            taper_time = taper_df.iloc[0]['Time_s']
            fig.add_trace(go.Scatter(
                x=[taper_time, taper_time], y=[0, max_y], mode='lines', 
                line=dict(color='black', width=1.5, dash='solid'),
                name="테이퍼 시점", 
                hovertemplate="<b>🚧 테이퍼 시점 (차로 감소 시작)</b><br>위치: 2500.0m<extra></extra>", showlegend=False
            ), secondary_y=False)

    if df_fix is not None and objects_to_draw:
        for obj_id, obj_name in objects_to_draw:
            first_row = df_fix[df_fix[fix_id_col] == obj_id].iloc[0]
            raw_t = first_row[fix_time_col]
            adj_time = ((raw_t - sac_start_time) / 1e9) + time_offset if raw_t > 1e12 else (raw_t - sac_start_time) + time_offset
            
            close_row = df_ds.iloc[(df_ds['Time_s'] - adj_time).abs().argsort()[:1]]
            dist_txt = f"({close_row[ds_dist_col].values[0]:.1f}m 지점)" if ds_dist_col and not close_row.empty else ""
            line_color = 'red' if "휴머노이드" in obj_name else 'royalblue'
            
            fig.add_trace(go.Scatter(
                x=[adj_time, adj_time], y=[0, max_y], mode='lines', 
                line=dict(color=line_color, width=2, dash='dash' if "휴머노이드" in obj_name else 'dot'),
                name=obj_name, hovertemplate=f"<b>🎯 {obj_name} 인지 시점</b><br>인지 위치: {dist_txt}<extra></extra>", showlegend=False
            ), secondary_y=False)

    fig.update_layout(title=f"[{custom_scenario_name}] 실시간 통합 데이터 분석 차트", xaxis_title="주행 시간 (초)", height=700, hovermode="x unified", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255, 255, 255, 0.7)'))
    fig.update_yaxes(title_text="속도 (km/h) / 시야각 (deg)", secondary_y=False)
    fig.update_yaxes(title_text="안정성 및 심층 분석 지표", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------
    # [💡 딥 추출] 평가용 기준 데이터 (t_a, t_b) 전역 추출
    # ---------------------------------------------------------
    eval_ta, eval_tb, eval_va, eval_vb, eval_dista, eval_distb = None, None, None, None, None, None
    
    # 1. mapping.csv에서 휴머노이드 ID 자동 추출 (UI 체크 무관)
    humanoid_auto_id = None
    if df_map is not None:
        for _, row in df_map.iterrows():
            if "휴머노이드" in str(row.iloc[1]):
                humanoid_auto_id = int(row.iloc[0])
                break
                
    # 2. t_a 추출
    if humanoid_auto_id is not None and df_fix is not None and fix_id_col is not None:
        h_fixes = df_fix[df_fix[fix_id_col] == humanoid_auto_id]
        if not h_fixes.empty:
            raw_ta = h_fixes.iloc[0][fix_time_col]
            eval_ta = ((raw_ta - sac_start_time) / 1e9) + time_offset if raw_ta > 1e12 else (raw_ta - sac_start_time) + time_offset
            
    # 3. t_b 추출
    if lane_change_count > 0:
        eval_tb = filtered_lane_changes[0]
        
    # 4. v_a, v_b, dist_a, dist_b 매핑
    if eval_ta is not None and ds_dist_col:
        row_a = df_ds.iloc[(df_ds['Time_s'] - eval_ta).abs().argsort()[:1]]
        if not row_a.empty:
            eval_va = row_a[ds_speed_col].values[0]
            eval_dista = row_a[ds_dist_col].values[0]
            
    if eval_tb is not None and ds_dist_col:
        row_b = df_ds.iloc[(df_ds['Time_s'] - eval_tb).abs().argsort()[:1]]
        if not row_b.empty:
            eval_vb = row_b[ds_speed_col].values[0]
            eval_distb = row_b[ds_dist_col].values[0]

    # ---------------------------------------------------------
    # 통계 섹션
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader(f"💡 '{custom_scenario_name}' 요약 통계")
                
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max(), 1)} 초")
    c2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
    c3.metric("최대 조향 이탈", f"{round(df_ds[ds_offset_col].abs().max(), 2)} m" if ds_offset_col else "0 m")
    c4.metric("👀 총 눈 깜빡임", f"{len(df_blink) if df_blink is not None else 0} 회")
    c5.metric("차로 변경 횟수", f"{lane_change_count} 회")
    
    perception_dist_str = "-"
    if eval_dista is not None and actual_h_pos is not None:
        perception_dist = max(0.0, actual_h_pos - eval_dista)
        perception_dist_str = f"{perception_dist:.1f} m"
    c6.metric("🤖 최초 인지 거리", perception_dist_str)
    
    refix_count = len(humanoid_gaze_stats)
    if refix_count == 0:
        refix_str = "미인지"
    elif refix_count == 1:
        refix_str = "1회 (단번)"
    else:
        refix_str = f"{refix_count}회 (혼란)"
    c7.metric("🤖 로봇 재주시", refix_str)
    
    if humanoid_gaze_stats:
        st.markdown("#### 👀 휴머노이드 누적 주시 시간 분석 (다중 인지 포함)")
        gaze_html = '<div style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 5px; margin-bottom: 20px;">'
        total_dur = 0.0
        for order, dur in humanoid_gaze_stats:
            total_dur += dur
            gaze_html += f'<div style="background-color: #f0f2f6; padding: 12px 18px; border-radius: 8px; border: 1px solid #dcdede;"><p style="font-size: 13px; margin: 0; color: #555;">{order}차 주시</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #e74c3c;">{dur:.2f}초</p></div>'
        gaze_html += f'<div style="background-color: #ffeaea; padding: 12px 18px; border-radius: 8px; border: 1.5px solid #ffb3b3;"><p style="font-size: 13px; margin: 0; color: #c0392b; font-weight: bold;">총 누적 주시 시간</p><p style="font-size: 18px; font-weight: 900; margin: 0; color: #c0392b;">{total_dur:.2f}초</p></div></div>'
        st.markdown(gaze_html, unsafe_allow_html=True)

    if lane_change_count > 0 and ds_dist_col:
        st.markdown("#### 🚧 첫 번째 차로 변경 상세 분석 (기준: 변경 시점 ±3초)")
        first_lc = filtered_lane_changes[0]
        st_t, ed_t = max(0, first_lc - 3.0), first_lc + 3.0
        st_dist = df_ds.iloc[(df_ds['Time_s'] - st_t).abs().argsort()[:1]][ds_dist_col].values[0]
        ed_dist = df_ds.iloc[(df_ds['Time_s'] - ed_t).abs().argsort()[:1]][ds_dist_col].values[0]
        
        lc_html = f'<div style="display: flex; justify-content: space-between; text-align: center; background-color: #f8f9fb; padding: 20px; border-radius: 10px; border: 1px solid #e6e6e9; margin-top: 10px;"><div style="flex: 1; padding: 0 10px;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">시작 지점 (시간 / 거리)</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #1f77b4;">{st_t:.1f}초 / {st_dist:.1f}m</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #ccc;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">종료 지점 (시간 / 거리)</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #1f77b4;">{ed_t:.1f}초 / {ed_dist:.1f}m</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #ccc;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">변경 소요 시간</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #2ca02c;">{ed_t - st_t:.1f}초</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #ccc;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">변경 중 이동 거리</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #2ca02c;">{ed_dist - st_dist:.1f}m</p></div></div>'
        st.markdown(lc_html, unsafe_allow_html=True)
        
        if eval_distb is not None:
            st.markdown("#### 🛡️ 테이퍼 구간 진입 전 여유 마진 분석 (2500m 테이퍼 시점 기준)")
            taper_df_stat = df_ds[df_ds[ds_dist_col] >= 2500.0]
            margin_time = taper_df_stat.iloc[0]['Time_s'] - eval_tb if not taper_df_stat.empty else 0.0
            margin_dist = max(0.0, 2500.0 - eval_distb)
            
            margin_html = f'''
            <div style="display: flex; justify-content: space-between; text-align: center; background-color: #f4f6f9; padding: 20px; border-radius: 10px; border: 1px solid #d3d9e2; margin-top: 10px;">
                <div style="flex: 1; padding: 0 10px;">
                    <p style="font-size: 14px; margin-bottom: 5px; color: #555;">차로 변경 ➔ 테이퍼 시점 여유 시간</p>
                    <p style="font-size: 18px; font-weight: bold; margin: 0; color: #2c3e50;">{margin_time:.2f} 초</p>
                </div>
                <div style="flex: 1; padding: 0 10px; border-left: 1px solid #d3d9e2;">
                    <p style="font-size: 14px; margin-bottom: 5px; color: #555;">차로 변경 ➔ 테이퍼 시점 여유 거리</p>
                    <p style="font-size: 18px; font-weight: bold; margin: 0; color: #2c3e50;">{margin_dist:.2f} m</p>
                </div>
            </div>
            '''
            st.markdown(margin_html, unsafe_allow_html=True)
                    
        if eval_ta is not None and eval_tb is not None:
            st.markdown("#### ⏱️ 인지 반응 분석 (휴머노이드 인지 ➔ 차로 변경)")
            st.caption("차량이 전방의 휴머노이드를 최초로 발견(인지)했을 때의 거리 간격을 도출하고, 인지 후 차로를 변경하기까지 소요된 운전자의 반응 시간과 이동 거리를 분석합니다.")
            
            if eval_tb > eval_ta:
                react_time = eval_tb - eval_ta
                react_dist = abs(eval_distb - eval_dista)
                
                view_html = ""
                if actual_h_pos is not None:
                    view_dist = max(0, actual_h_pos - eval_dista)
                    view_html = f'<div style="flex: 1; padding: 0 10px; border-right: 1px solid #fce79a;"><p style="font-size: 14px; margin-bottom: 5px; color: #8a6d3b;">최초 인지 거리 (가시거리)</p><p style="font-size: 18px; font-weight: bold; margin: 0; color: #c0392b;">{view_dist:.1f} m</p></div>'
                
                react_html = f'<div style="display: flex; justify-content: space-between; text-align: center; background-color: #fff9e6; padding: 20px; border-radius: 10px; border: 1px solid #fce79a; margin-top: 10px;">{view_html}<div style="flex: 1; padding: 0 10px;"><p style="font-size: 14px; margin-bottom: 5px; color: #8a6d3b;">인지 ➔ 차로 변경 소요 시간</p><p style="font-size: 18px; font-weight: bold; margin: 0; color: #d35400;">{react_time:.2f} 초</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #fce79a;"><p style="font-size: 14px; margin-bottom: 5px; color: #8a6d3b;">인지 ➔ 차로 변경 이동 거리</p><p style="font-size: 18px; font-weight: bold; margin: 0; color: #d35400;">{react_dist:.2f} m</p></div></div>'
                st.markdown(react_html, unsafe_allow_html=True)
            else:
                st.warning("⚠️ 차로 변경이 휴머노이드 인지보다 먼저 발생했습니다. (반응 속도 역전)")

    # ---------------------------------------------------------
    # 💡 심층 주행 & 인지 부하 분석 (SSM & Workload)
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🧠 심층 주행 & 인지 부하 분석 (SSM & Workload)")
    
    with st.expander("🛠️ 인지적 작업 부하 및 안정성 지표 상세 보기", expanded=True):
        col_w1, col_w2 = st.columns(2)
        
        with col_w1:
            st.markdown("#### 1. 차로 유지 편차 (SDLP) 및 조향 엔트로피")
            with st.container(border=True):
                sdlp_val = df_ds[ds_offset_col].std() if ds_offset_col and not df_ds[ds_offset_col].isnull().all() else 0.0
                st.markdown(f"**🔹 차로 유지 편차 (SDLP)**")
                st.info(f"**계산 결과 (SDLP):** {sdlp_val:.3f} m")
                
                st.divider()
                
                target_steer_col = steer_col if steer_col else ds_offset_col
                st.markdown(f"**🔹 조향 엔트로피 (Steering Entropy)**")
                if target_steer_col and not df_ds[target_steer_col].isnull().all():
                    s_data = df_ds[target_steer_col].fillna(0)
                    x_1 = s_data.shift(1); x_2 = s_data.shift(2); x_3 = s_data.shift(3)
                    pred = x_1 + (x_1 - x_2) + 0.5 * ((x_1 - x_2) - (x_2 - x_3))
                    error = (s_data - pred).dropna()
                    if len(error) > 10:
                        bins = np.histogram_bin_edges(error, bins=9)
                        p_steer, _ = np.histogram(error, bins=bins)
                        p_steer = p_steer[p_steer > 0] / sum(p_steer)
                        steering_entropy = -sum(p_steer * np.log2(p_steer))
                        st.success(f"**계산 결과 (조향 엔트로피):** {steering_entropy:.3f}")
                    else: st.warning("데이터 부족")
                else: st.warning("조향 데이터 없음")

            st.markdown("#### 2. 가속도 변화율 (Jerk)")
            with st.container(border=True):
                jerk = y_accel.diff() / df_ds['Time_s'].diff()
                max_jerk = jerk.abs().max()
                harsh_ratio = (jerk.abs() > 2.0).sum() / len(jerk.dropna()) * 100
                st.warning(f"**최대 저크 (Max Jerk):** {max_jerk:.2f} $m/s^3$\n\n**급조작(위험) 비율:** {harsh_ratio:.2f} %")

        with col_w2:
            st.markdown("#### 3. 누적 시선 분산도 (전체 Gaze Entropy)")
            with st.container(border=True):
                if df_fix is not None and fix_id_col in df_fix.columns:
                    p_gaze = df_fix[fix_id_col].value_counts(normalize=True).values
                    p_gaze = p_gaze[p_gaze > 0]
                    gaze_entropy = -sum(p_gaze * np.log2(p_gaze))
                    prob_str = ", ".join([f"{p*100:.1f}%" for p in p_gaze[:5]]) + (f" ... (외 {len(p_gaze)-5}개)" if len(p_gaze)>5 else "")
                    st.markdown(f"- **실제 대입 데이터:** 총 {len(p_gaze)}개 타겟의 확률 분포 $p_i$ = [{prob_str}]")
                    st.info(f"**계산 결과 (전체 구간 SGE):** {gaze_entropy:.3f}")
                else: st.warning("시선 고정 데이터 없음")
            
            st.markdown("#### 4. 동공 확장(TEPR) & 재주시(Re-fixation)")
            with st.container(border=True):
                st.markdown("- **동공 확장(TEPR):** 자율신경계 반응으로, 인지 부하가 급증할 때 동공이 확장됩니다. (메인 차트 동적 꺾은선 지원)")
                st.markdown("- **눈 깜빡임 억제:** 정보 처리에 고도로 집중하거나 긴장 시(터널 비전) 깜빡임이 중단됩니다. (5초 이상 억제 시 메인 차트에 검은색 구간 표출)")
                st.markdown("- **재주시 횟수:** 로봇을 발견 후 단번에 이해하지 못하고 반복해서 시선을 옮긴 횟수를 뜻합니다. 2회 이상 발생 시 해당 배치가 운전자에게 시각적 혼란을 야기했음을 의미합니다.")

            st.markdown("#### 5. 충돌 예상 시간(TTC) 및 정지 거리 지수(SDI)")
            with st.container(border=True):
                st.markdown("- **기준점:** 휴머노이드 인지 시점($t_a$) 및 차로 변경 시점($t_b$)에서 2500m 테이퍼까지 남은 여유 거리 기준 산출")
                
                if eval_ta is not None and eval_tb is not None:
                    v_a_ms = eval_va / 3.6
                    v_b_ms = eval_vb / 3.6
                    
                    target_taper = 2500.0
                    rem_dist_a = max(0.001, target_taper - eval_dista)
                    rem_dist_b = max(0.001, target_taper - eval_distb)
                    
                    ttc_a = rem_dist_a / max(0.001, v_a_ms)
                    ttc_b = rem_dist_b / max(0.001, v_b_ms)
                    
                    tr, f, g = 2.5, 0.8, 9.81
                    stop_dist_a = v_a_ms * tr + (v_a_ms**2)/(2*g*f)
                    stop_dist_b = v_b_ms * tr + (v_b_ms**2)/(2*g*f)
                    
                    sdi_a = stop_dist_a / rem_dist_a
                    sdi_b = stop_dist_b / rem_dist_b
                    
                    c_s1, c_s2 = st.columns(2)
                    with c_s1:
                        st.markdown("**🔵 인지 시점 기준 ($t_a$)**")
                        st.info(f"**TTC:** {ttc_a:.2f} 초\n\n**SDI:** {sdi_a:.3f}")
                    with c_s2:
                        st.markdown("**🟠 차로 변경 기준 ($t_b$)**")
                        st.info(f"**TTC:** {ttc_b:.2f} 초\n\n**SDI:** {sdi_b:.3f}")
                else:
                    st.warning("휴머노이드 인지 및 차로 변경 데이터가 모두 필요합니다.")

    # ---------------------------------------------------------
    # 6. 시나리오 안전성 평가 (SSD & 구간 속도)
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🛑 시나리오 안전성 평가 (이중 SSD & 구간 속도)")
    
    with st.expander("🛠️ SSD 이중 검증 및 구간 속도 결과 보기", expanded=True):
        col_ssd1, col_ssd2 = st.columns(2)
        f_val, s_val, tr_val = 0.8, 0.0, 2.5
        
        ui_va = eval_va if eval_va is not None else 90.0
        ui_vb = eval_vb if eval_vb is not None else 90.0
        ui_da = max(0.0, 2500.0 - eval_dista) if eval_dista is not None else 1500.0
        ui_db = max(0.0, 2500.0 - eval_distb) if eval_distb is not None else 1350.0
        
        # 💡 [핵심] scen_key를 삽입하여 시나리오 변경 시 입력창 강제 업데이트
        with col_ssd1:
            st.markdown("### 🔵 [초기 안전성] 인지 시점 기준")
            st.caption("로봇을 발견한 최초 순간, 물리적으로 테이퍼 전까지 멈출 수 있는 제동 거리가 확보되는지 검증합니다.")
            v_val_a = st.number_input("인지 시점 속도 V_a (km/h)", value=float(ui_va), format="%.2f", key=f"va_{scen_key}")
            d_val_a = st.number_input("인지 시점 여유거리 D_a (m)", value=float(ui_da), format="%.2f", key=f"da_{scen_key}")
            
            ssd_a = (v_val_a**2) / (254 * (f_val + s_val)) + tr_val * (v_val_a / 3.6)
            st.latex(r"SSD_a = \frac{V_a^2}{254 \times (f + s)} + t_r \times \frac{V_a}{3.6}")
            st.latex(fr"= \frac{{{v_val_a:.1f}^2}}{{254 \times 0.8}} + 2.5 \times \frac{{{v_val_a:.1f}}}{{3.6}} = {ssd_a:.2f}m")
            st.info(f"판정: **{'🟢 Safety' if ssd_a <= d_val_a else '🔴 Danger'}** (남은 {d_val_a:.1f}m 대비 필요 {ssd_a:.1f}m)")

        with col_ssd2:
            st.markdown("### 🟠 [실행 안전성] 차로 변경 시점 기준")
            st.caption("실제 회피 기동(차로 변경)을 시작하는 순간의 주행 상태가 안전 마진을 만족하는지 검증합니다.")
            v_val_b = st.number_input("변경 시점 속도 V_b (km/h)", value=float(ui_vb), format="%.2f", key=f"vb_{scen_key}")
            d_val_b = st.number_input("변경 시점 여유거리 D_b (m)", value=float(ui_db), format="%.2f", key=f"db_{scen_key}")
            
            ssd_b = (v_val_b**2) / (254 * (f_val + s_val)) + tr_val * (v_val_b / 3.6)
            st.latex(r"SSD_b = \frac{V_b^2}{254 \times (f + s)} + t_r \times \frac{V_b}{3.6}")
            st.latex(fr"= \frac{{{v_val_b:.1f}^2}}{{254 \times 0.8}} + 2.5 \times \frac{{{v_val_b:.1f}}}{{3.6}} = {ssd_b:.2f}m")
            st.info(f"판정: **{'🟢 Safety' if ssd_b <= d_val_b else '🔴 Danger'}** (남은 {d_val_b:.1f}m 대비 필요 {ssd_b:.1f}m)")

        st.divider()
        st.markdown("### 🏁 2. 구간 속도 (SMS)")
        st.caption("💡 참고: 구간 속도는 휴머노이드 최초 인지 시점(t_a)부터 차로 변경 시작 시점(t_b)까지 이동한 구간의 평균 속도입니다.")
        
        ui_l = abs(eval_distb - eval_dista) if (eval_dista is not None and eval_distb is not None) else 150.0
        l_val = st.number_input("구간 길이 L (m)", value=float(ui_l), format="%.2f", key=f"l_{scen_key}")
        
        if eval_ta is not None and eval_tb is not None and eval_tb > eval_ta:
            sms_val = (l_val / (eval_tb - eval_ta)) * 3.6
            st.latex(fr"SMS = \frac{{{l_val:.1f}}}{{{eval_tb:.2f} - {eval_ta:.2f}}} \times 3.6 = {sms_val:.2f} km/h")
            st.info(f"판정 결과: **{sms_val:.2f} km/h** ➔ **{'🟢 Safety' if sms_val <= 80 else '🔴 Danger'}**")
        else: 
            st.error("시간 데이터가 불충분하거나 오류가 있습니다.")
