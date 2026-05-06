import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")

if 'custom_markers' not in st.session_state:
    st.session_state['custom_markers'] = {}

st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
st.markdown("서버에 저장된 시나리오를 불러오거나, 새로운 데이터를 직접 업로드하여 분석할 수 있습니다.")

# ---------------------------------------------------------
# [핵심 함수 1] 폴더 내 파일 자동 매칭
# ---------------------------------------------------------
def find_files_in_folder(folder_path):
    ds_file_path, sac_file_path, blink_file_path, fix_file_path, map_file_path = None, None, None, None, None
    for filename in os.listdir(folder_path):
        lower_name = filename.lower()
        if lower_name.endswith('.csv'):
            if 'saccade' in lower_name:
                sac_file_path = os.path.join(folder_path, filename)
            elif 'blink' in lower_name:
                blink_file_path = os.path.join(folder_path, filename)
            elif 'fixation' in lower_name:
                fix_file_path = os.path.join(folder_path, filename)
            elif 'map' in lower_name or 'name' in lower_name:
                map_file_path = os.path.join(folder_path, filename)
            elif '_' in lower_name and 'world' not in lower_name:
                ds_file_path = os.path.join(folder_path, filename)
    return ds_file_path, sac_file_path, blink_file_path, fix_file_path, map_file_path

# ---------------------------------------------------------
# 1. 사이드바: 데이터 소스 선택
# ---------------------------------------------------------
st.sidebar.header("📁 1. 데이터 소스 선택")
data_mode = st.sidebar.radio("어떤 방식으로 데이터를 분석할까요?", ["💾 서버에 내장된 시나리오 불러오기", "📤 내 PC에서 직접 파일 업로드"])
st.sidebar.markdown("---")

df_ds, df_sac, df_blink, df_fix, df_map = None, None, None, None, None
data_loaded = False
current_ds_filename = ""
selected_folder = ""

if data_mode == "💾 서버에 내장된 시나리오 불러오기":
    folder_options = [item for item in os.listdir('.') if os.path.isdir(item) and not item.startswith('.') and not item == '__pycache__']
    folder_options.sort()
    if len(folder_options) > 0:
        selected_folder = st.sidebar.selectbox("분석할 시나리오 폴더 선택:", folder_options)
        ds_path, sac_path, blink_path, fix_path, map_path = find_files_in_folder(selected_folder)
        if ds_path and sac_path:
            df_ds = pd.read_csv(ds_path)
            df_sac = pd.read_csv(sac_path)
            df_blink = pd.read_csv(blink_path) if blink_path else None
            df_fix = pd.read_csv(fix_path) if fix_path else None
            df_map = pd.read_csv(map_path) if map_path else None
            current_ds_filename = os.path.basename(ds_path)
            data_loaded = True
        else:
            st.sidebar.error("⚠️ 필수 데이터를 찾지 못했습니다.")
else:
    ds_file = st.sidebar.file_uploader("주행 데이터 파일 업로드", type=['csv'])
    sac_file = st.sidebar.file_uploader("시선 이동(Saccade) 파일 업로드", type=['csv'])
    blink_file = st.sidebar.file_uploader("눈 깜빡임(Blink) 업로드 (선택)", type=['csv'])
    fix_file = st.sidebar.file_uploader("시선 고정(Fixations) 업로드 (선택)", type=['csv'])
    map_file = st.sidebar.file_uploader("객체 이름 사전(mapping.csv) 업로드 (선택)", type=['csv'])
    if ds_file and sac_file:
        df_ds = pd.read_csv(ds_file)
        df_sac = pd.read_csv(sac_file)
        df_blink = pd.read_csv(blink_file) if blink_file else None
        df_fix = pd.read_csv(fix_file) if fix_file else None
        df_map = pd.read_csv(map_file) if map_file else None
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

    # 💡 [신규] 심층 분석 동적 그래프 전용 섹션 개편
    st.sidebar.markdown("---")
    st.sidebar.header("🧠 심층 분석 동적 그래프")
    window_size = st.sidebar.slider("산출 윈도우 크기 (과거 n초)", 1.0, 10.0, 3.0, 0.5)
    
    st.sidebar.subheader("👁️ 인지/주의력 지표")
    show_dynamic_sge = st.sidebar.checkbox("👀 동적 시선 분산도(SGE)", value=False)
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

    # 가속도 산출 (Jerk용)
    accel_col = next((col for col in df_ds.columns if 'accel' in col.lower() and 'x' in col.lower()), None)
    if accel_col:
        y_accel = df_ds[accel_col]
    else:
        y_accel = (df_ds[ds_speed_col] / 3.6).diff() / df_ds['Time_s'].diff()

    # ---------------------------------------------------------
    # 💡 동적 지표 계산 (Sliding Window)
    # ---------------------------------------------------------
    time_vals = df_ds['Time_s'].values

    # 1. 동적 SGE
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

    # 2. 동적 조향 엔트로피
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

    # 3. 동적 Jerk
    if show_dynamic_jerk:
        df_ds['Dynamic_Jerk'] = y_accel.diff() / df_ds['Time_s'].diff()

    # 4. 💡 [신규] 동적 SDLP (차로 유지 편차)
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

    # ---------------------------------------------------------
    # 차트 그리기
    # ---------------------------------------------------------
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    max_y = df_ds[ds_speed_col].max() if ds_speed_col in df_ds.columns else 100

    if show_speed:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_speed_col], mode='lines', name='속도(km/h)', line=dict(color='royalblue', width=2)), secondary_y=False)
    if show_accel:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=y_accel, mode='lines', name='가속도(m/s²)', line=dict(color='darkmagenta', width=1.5)), secondary_y=True)
    if show_offset and ds_offset_col:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_offset_col], mode='lines', name='조향 편차', line=dict(color='seagreen', width=2, dash='dot')), secondary_y=True)
    if show_saccade:
        fig.add_trace(go.Scatter(x=df_sac['Time_s'], y=df_sac[sac_amp_col], mode='lines', name='시선 이동', fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.4)', line=dict(color='crimson', width=0.5)), secondary_y=False)

    # 심층 분석 동적 레이어들 (Secondary Y축 사용)
    if show_dynamic_sge:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_SGE'], mode='lines', name='동적 SGE', line=dict(color='#FF8C00', width=2.5)), secondary_y=True)
    if show_dynamic_steer:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_Steer_Ent'], mode='lines', name='동적 조향 엔트로피', line=dict(color='#8A2BE2', width=2.5, dash='dash')), secondary_y=True)
    if show_dynamic_jerk:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_Jerk'], mode='lines', name='Jerk (m/s³)', line=dict(color='#FF1493', width=2, dash='dot')), secondary_y=True)
    if show_dynamic_sdlp:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds['Dynamic_SDLP'], mode='lines', name='동적 SDLP (m)', line=dict(color='#20B2AA', width=2.5, dash='solid')), secondary_y=True)

    # 랜드마크 및 구간 표시 (코드 생략, 이전 버전과 동일)
    # ... (테이퍼 시점, 휴머노이드 위치 등 표시 로직 유지)

    fig.update_layout(title=f"[{custom_scenario_name}] 실시간 통합 데이터 분석 차트", xaxis_title="주행 시간 (초)", height=700, hovermode="x unified")
    fig.update_yaxes(title_text="속도 / 시야각", secondary_y=False)
    fig.update_yaxes(title_text="안정성 및 심층 분석 지표", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------
    # 하단 통계 섹션 (이전 로직 유지 및 SDLP 요약 추가 가능)
    # ---------------------------------------------------------
    # ... (생략)
