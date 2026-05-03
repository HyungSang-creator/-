import streamlit as st
import pandas as pd
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
    custom_scenario_name = st.sidebar.text_input("📝 차트 제목 변경:", value="새로운 분석 시나리오")
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ 2. 분석 레이어 및 옵션")
    show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
    show_accel = st.sidebar.checkbox("🚀 차량 가속도 표시 (m/s²)", value=False)
    show_offset = st.sidebar.checkbox("↔️ 조향 편차 (차로 이탈 정도)", value=True)
    show_saccade = st.sidebar.checkbox("👁️ 시선 이동 각도 (채워진 그래프)", value=True)
    show_blink = st.sidebar.checkbox("😌 눈 깜빡임 (하단 마커)", value=True)
    show_lane_change = st.sidebar.checkbox("🚧 차선 변경 궤적 하이라이트", value=True)
    time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -10.0, 10.0, 0.0, 0.1)

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
    # 메인 화면 그래프 렌더링 세팅
    # ---------------------------------------------------------
    ds_time_col = 'time' if 'time' in df_ds.columns else 'timestamp'
    ds_speed_col = 'speedInKmPerHour' if 'speedInKmPerHour' in df_ds.columns else ('speed' if 'speed' in df_ds.columns else 'Velocity')
    ds_lane_col = 'laneNumber' if 'laneNumber' in df_ds.columns else ('Lane_ID' if 'Lane_ID' in df_ds.columns else None)
    ds_offset_col = 'offsetFromLaneCenter' if 'offsetFromLaneCenter' in df_ds.columns else None
    sac_time_col = 'start timestamp [ns]' if 'start timestamp [ns]' in df_sac.columns else 'start timestamp'
    sac_amp_col = 'amplitude [deg]' if 'amplitude [deg]' in df_sac.columns else 'amplitude'
    
    ds_start_time = df_ds[ds_time_col].min()
    df_ds['Time_s'] = df_ds[ds_time_col] - ds_start_time
    sac_start_time = df_sac[sac_time_col].min()
    is_ns = df_sac[sac_time_col].max() > 1e12
    df_sac['Time_s'] = ((df_sac[sac_time_col] - sac_start_time) / 1e9) + time_offset if is_ns else (df_sac[sac_time_col] - sac_start_time) + time_offset

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

    # ---------------------------------------------------------
    # 차트 그리기
    # ---------------------------------------------------------
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    max_y = df_ds[ds_speed_col].max() if ds_speed_col in df_ds.columns else 100

    if show_speed and ds_speed_col in df_ds.columns:
        hovertemplate = '%{y:.1f} <br>📍 위치: %{customdata:.1f} m' if ds_dist_col else '%{y:.1f}'
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_speed_col], mode='lines', name='속도(km/h)', line=dict(color='royalblue', width=2), customdata=df_ds[ds_dist_col] if ds_dist_col else None, hovertemplate=hovertemplate), secondary_y=False)

    if show_accel:
        accel_col = next((col for col in df_ds.columns if 'accel' in col.lower() and 'x' in col.lower()), None)
        y_accel = df_ds[accel_col] if accel_col else (df_ds[ds_speed_col] / 3.6).diff() / df_ds['Time_s'].diff()
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=y_accel, mode='lines', name='가속도(m/s²)', line=dict(color='darkmagenta', width=1.5)), secondary_y=True)

    if show_offset and ds_offset_col in df_ds.columns:
        fig.add_trace(go.Scatter(x=df_ds['Time_s'], y=df_ds[ds_offset_col], mode='lines', name='조향 편차', line=dict(color='seagreen', width=2, dash='dot')), secondary_y=True)

    if show_saccade and sac_amp_col in df_sac.columns:
        fig.add_trace(go.Scatter(x=df_sac['Time_s'], y=df_sac[sac_amp_col], mode='lines', name='시선 이동', fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.4)', line=dict(color='crimson', width=0.5)), secondary_y=False)

    if show_blink and df_blink is not None:
        blink_time_col = 'start timestamp [ns]' if 'start timestamp [ns]' in df_blink.columns else 'start timestamp'
        if blink_time_col in df_blink.columns:
            df_blink['Time_s'] = ((df_blink[blink_time_col] - sac_start_time) / 1e9) + time_offset if is_ns else (df_blink[blink_time_col] - sac_start_time) + time_offset
            fig.add_trace(go.Scatter(x=df_blink['Time_s'], y=[-5] * len(df_blink), mode='markers', name='눈 깜빡임 발생', marker=dict(symbol='line-ns', color='darkorange', size=15, line=dict(width=2)), hoverinfo='x+name'), secondary_y=False)

    if show_lane_change and lane_change_count > 0:
        for lc in filtered_lane_changes:
            fig.add_vrect(x0=lc-3.0, x1=lc+3.0, fillcolor="gold", opacity=0.15, layer="below", line_width=0, annotation_text="차선 변경")

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
                hovertemplate="<b>🚧 테이퍼 시점 (차선 감소 시작)</b><br>위치: 2500.0m<extra></extra>", showlegend=False
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

    fig.update_layout(title=f"[{custom_scenario_name}] 실시간 다중 레이어 분석 차트", xaxis_title="주행 시간 (초)", height=650, hovermode="x unified", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255, 255, 255, 0.7)'))
    fig.update_yaxes(title_text="속도 (km/h) / 시야각 (deg)", secondary_y=False)
    fig.update_yaxes(title_text="가속도 & 조향 편차", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------
    # 통계 섹션
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader(f"💡 '{custom_scenario_name}' 요약 통계")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max(), 1)} 초")
    c2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
    c3.metric("최대 조향 이탈", f"{round(df_ds[ds_offset_col].abs().max(), 2)} m" if ds_offset_col else "0 m")
    c4.metric("👀 총 눈 깜빡임", f"{len(df_blink) if df_blink is not None else 0} 회")
    c5.metric("차선 변경 횟수", f"{lane_change_count} 회")
    
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
        st.markdown("#### 🚧 첫 번째 차선 변경 상세 분석 (기준: 변경 시점 ±3초)")
        first_lc = filtered_lane_changes[0]
        st_t, ed_t = max(0, first_lc - 3.0), first_lc + 3.0
        st_dist = df_ds.iloc[(df_ds['Time_s'] - st_t).abs().argsort()[:1]][ds_dist_col].values[0]
        ed_dist = df_ds.iloc[(df_ds['Time_s'] - ed_t).abs().argsort()[:1]][ds_dist_col].values[0]
        
        lc_html = f'<div style="display: flex; justify-content: space-between; text-align: center; background-color: #f8f9fb; padding: 20px; border-radius: 10px; border: 1px solid #e6e6e9; margin-top: 10px;"><div style="flex: 1; padding: 0 10px;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">시작 지점 (시간 / 거리)</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #1f77b4;">{st_t:.1f}초 / {st_dist:.1f}m</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #ccc;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">종료 지점 (시간 / 거리)</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #1f77b4;">{ed_t:.1f}초 / {ed_dist:.1f}m</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #ccc;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">변경 소요 시간</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #2ca02c;">{ed_t - st_t:.1f}초</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #ccc;"><p style="font-size: 14px; margin-bottom: 5px; color: #555;">변경 중 이동 거리</p><p style="font-size: 16px; font-weight: bold; margin: 0; color: #2ca02c;">{ed_dist - st_dist:.1f}m</p></div></div>'
        st.markdown(lc_html, unsafe_allow_html=True)
        
        taper_df_stat = df_ds[df_ds[ds_dist_col] >= 2500.0]
        if not taper_df_stat.empty:
            st.markdown("#### 🛡️ 테이퍼 구간 진입 전 여유 마진 분석 (2500m 테이퍼 시점 기준)")
            taper_time_stat = taper_df_stat.iloc[0]['Time_s']
            lc_exact_dist = df_ds.iloc[(df_ds['Time_s'] - first_lc).abs().argsort()[:1]][ds_dist_col].values[0]
            
            margin_time = taper_time_stat - first_lc
            margin_dist = max(0.0, 2500.0 - lc_exact_dist)
            
            margin_html = f'''
            <div style="display: flex; justify-content: space-between; text-align: center; background-color: #f4f6f9; padding: 20px; border-radius: 10px; border: 1px solid #d3d9e2; margin-top: 10px;">
                <div style="flex: 1; padding: 0 10px;">
                    <p style="font-size: 14px; margin-bottom: 5px; color: #555;">차선 변경 ➔ 테이퍼 시점 여유 시간</p>
                    <p style="font-size: 18px; font-weight: bold; margin: 0; color: #2c3e50;">{margin_time:.2f} 초</p>
                </div>
                <div style="flex: 1; padding: 0 10px; border-left: 1px solid #d3d9e2;">
                    <p style="font-size: 14px; margin-bottom: 5px; color: #555;">차선 변경 ➔ 테이퍼 시점 여유 거리</p>
                    <p style="font-size: 18px; font-weight: bold; margin: 0; color: #2c3e50;">{margin_dist:.2f} m</p>
                </div>
            </div>
            '''
            st.markdown(margin_html, unsafe_allow_html=True)

        humanoid_id = None
        if df_fix is not None:
            for oid, oname in objects_to_draw:
                if "휴머노이드" in oname:
                    humanoid_id = oid
                    break
                    
        if humanoid_id is not None:
            st.markdown("#### ⏱️ 인지 반응 분석 (휴머노이드 인지 ➔ 차선 변경)")
            raw_ta = df_fix[df_fix[fix_id_col] == humanoid_id].iloc[0][fix_time_col]
            ta = ((raw_ta - sac_start_time) / 1e9) + time_offset if raw_ta > 1e12 else (raw_ta - sac_start_time) + time_offset
            tb = first_lc
            
            if tb > ta:
                dist_ta = df_ds.iloc[(df_ds['Time_s'] - ta).abs().argsort()[:1]][ds_dist_col].values[0]
                dist_tb = df_ds.iloc[(df_ds['Time_s'] - tb).abs().argsort()[:1]][ds_dist_col].values[0]
                react_time = tb - ta
                react_dist = abs(dist_tb - dist_ta)
                
                view_html = ""
                if actual_h_pos is not None:
                    view_dist = max(0, actual_h_pos - dist_ta)
                    view_html = f'<div style="flex: 1; padding: 0 10px; border-right: 1px solid #fce79a;"><p style="font-size: 14px; margin-bottom: 5px; color: #8a6d3b;">최초 인지 시점의 전방 거리</p><p style="font-size: 18px; font-weight: bold; margin: 0; color: #c0392b;">{view_dist:.1f} m</p></div>'
                
                react_html = f'<div style="display: flex; justify-content: space-between; text-align: center; background-color: #fff9e6; padding: 20px; border-radius: 10px; border: 1px solid #fce79a; margin-top: 10px;">{view_html}<div style="flex: 1; padding: 0 10px;"><p style="font-size: 14px; margin-bottom: 5px; color: #8a6d3b;">인지 ➔ 차선 변경 소요 시간</p><p style="font-size: 18px; font-weight: bold; margin: 0; color: #d35400;">{react_time:.2f} 초</p></div><div style="flex: 1; padding: 0 10px; border-left: 1px solid #fce79a;"><p style="font-size: 14px; margin-bottom: 5px; color: #8a6d3b;">인지 ➔ 차선 변경 이동 거리</p><p style="font-size: 18px; font-weight: bold; margin: 0; color: #d35400;">{react_dist:.2f} m</p></div></div>'
                st.markdown(react_html, unsafe_allow_html=True)
            else:
                st.warning("⚠️ 차선 변경이 휴머노이드 인지보다 먼저 발생했습니다. (반응 속도 역전)")

    # ---------------------------------------------------------
    # 5. SSD & 구간 속도 평가
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🛑 시나리오 안전성 평가 (SSD & 구간 속도)")
    with st.expander("🛠️ 교통 안전성 평가 데이터 및 결과 보기", expanded=True):
        auto_ta, auto_tb, auto_v, auto_l, auto_d = 0.0, 6.0, 90.0, 150.0, 120.0
        
        target_id_ssd = None
        if objects_to_draw:
            for oid, oname in objects_to_draw:
                if "휴머노이드" in oname:
                    target_id_ssd = oid
                    break
            if target_id_ssd is None:
                target_id_ssd, _ = objects_to_draw[0]

        if df_fix is not None and target_id_ssd is not None and lane_change_count > 0 and ds_dist_col:
            raw_t = df_fix[df_fix[fix_id_col] == target_id_ssd].iloc[0][fix_time_col]
            auto_ta = ((raw_t - sac_start_time) / 1e9) + time_offset if raw_t > 1e12 else (raw_t - sac_start_time) + time_offset
            auto_tb = filtered_lane_changes[0]
            auto_v = df_ds.iloc[(df_ds['Time_s'] - auto_tb).abs().argsort()[:1]][ds_speed_col].values[0]
            dist_b = df_ds.iloc[(df_ds['Time_s'] - auto_tb).abs().argsort()[:1]][ds_dist_col].values[0]
            dist_a = df_ds.iloc[(df_ds['Time_s'] - auto_ta).abs().argsort()[:1]][ds_dist_col].values[0]
            auto_l = abs(dist_b - dist_a)
            auto_d = max(0.0, 2500.0 - dist_b) # 💡 테이퍼 여유 거리(안전거리) 자동 세팅

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📥 추출된 주행 파라미터")
            v_val = st.number_input("차로변경 시점 속도 V (km/h)", value=float(auto_v), format="%.2f")
            d_val = st.number_input("테이퍼 시점과의 거리 D (m)", value=float(auto_d), format="%.2f")
            l_val = st.number_input("구간 길이 L (m) [t_a ~ t_b 이동거리]", value=float(auto_l), format="%.2f")
            ta_val = st.number_input("휴머노이드 인지 시점 t_a (초)", value=float(auto_ta), format="%.2f")
            tb_val = st.number_input("차로 변경 시작 시점 t_b (초)", value=float(auto_tb), format="%.2f")
        with c2:
            st.markdown("#### 📊 평가 결과")
            ssd_val = (v_val**2) / (254 * (0.8 + 0.0)) + 2.5 * (v_val / 3.6)
            st.markdown("**1. 안전정지거리 (SSD)**")
            st.info(f"계산 결과: **{ssd_val:.2f} m** ➔ **{'🟢 Safety' if ssd_val <= d_val else '🔴 Danger'}**")
            st.markdown("**2. 구간 속도**")
            if tb_val > ta_val:
                sms_val = (l_val / (tb_val - ta_val)) * 3.6
                st.info(f"계산 결과: **{sms_val:.2f} km/h** ➔ **{'🟢 Safety' if sms_val <= 80 else '🔴 Danger'}**")
            else:
                st.error("시간 오류: 인지 시점(t_a)이 변경 시점(t_b)보다 빠를 수 없습니다.")
