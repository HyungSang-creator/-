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
data_mode = st.sidebar.radio(
    "어떤 방식으로 데이터를 분석할까요?", 
    ["💾 서버에 내장된 시나리오 불러오기", "📤 내 PC에서 직접 파일 업로드"]
)

st.sidebar.markdown("---")

df_ds, df_sac, df_blink, df_fix, df_map = None, None, None, None, None
data_loaded = False

if data_mode == "💾 서버에 내장된 시나리오 불러오기":
    st.sidebar.subheader("내장된 폴더 선택")
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
            data_loaded = True
        else:
            st.sidebar.error(f"⚠️ '{selected_folder}' 폴더에서 필수 데이터를 찾지 못했습니다.")
    else:
        st.sidebar.warning("⚠️ 깃허브 서버에 시나리오 폴더가 없습니다.")

else:
    st.sidebar.subheader("파일 업로드")
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
        data_loaded = True
    else:
        st.sidebar.info("분석할 CSV 파일들을 올려주세요.")

# ---------------------------------------------------------
# 2. 사이드바: 분석 옵션 및 레이어
# ---------------------------------------------------------
if data_loaded:
    custom_scenario_name = st.sidebar.text_input(
        "📝 차트 제목 변경:", 
        value=selected_folder if data_mode == "💾 서버에 내장된 시나리오 불러오기" else "새로운 분석 시나리오"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ 2. 분석 레이어 및 옵션")
    show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
    show_accel = st.sidebar.checkbox("🚀 차량 가속도 표시 (m/s²)", value=False)
    show_offset = st.sidebar.checkbox("↔️ 조향 편차 (차로 이탈 정도)", value=True)
    show_saccade = st.sidebar.checkbox("👁️ 시선 이동 각도 (채워진 그래프)", value=True)
    show_blink = st.sidebar.checkbox("😌 눈 깜빡임 (하단 마커)", value=True)
    show_lane_change = st.sidebar.checkbox("🚧 차선 변경 구간 하이라이트", value=True)
    time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -10.0, 10.0, 0.0, 0.1)

    # ---------------------------------------------------------
    # 3. 주의 구간 (이벤트 존) 설정
    # ---------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("🚨 3. 주의 구간 (이벤트 존) 설정")
    
    ds_dist_col = next((col for col in df_ds.columns if 'distance' in col.lower() or 'dist' in col.lower() or 'mileage' in col.lower()), None)
    
    caution_mode = st.sidebar.radio("주의 구간 시작 기준", ["사용 안 함", "특정 시간(초) 기준", "이동 거리(m) 기준"])
    caution_start_time = None
    
    if caution_mode == "특정 시간(초) 기준":
        caution_start_time = st.sidebar.number_input("🚨 주의 구간 시작 시간 (초)", min_value=0.0, max_value=1000.0, value=60.0)
    elif caution_mode == "이동 거리(m) 기준":
        if ds_dist_col:
            caution_dist_input = st.sidebar.number_input(f"🚨 주의 구간 시작 거리 (m)", min_value=0.0, max_value=10000.0, value=500.0)
            st.sidebar.caption(f"감지된 거리 열: `{ds_dist_col}`")
            over_dist_df = df_ds[df_ds[ds_dist_col] >= caution_dist_input]
            temp_time_col = 'time' if 'time' in df_ds.columns else 'timestamp'
            
            if not over_dist_df.empty:
                ds_start_time_raw = df_ds[temp_time_col].min()
                raw_caution_time = over_dist_df[temp_time_col].iloc[0]
                caution_start_time = raw_caution_time - ds_start_time_raw
            else:
                st.sidebar.warning("⚠️ 주행 데이터가 입력한 거리에 도달하지 못했습니다.")
        else:
            st.sidebar.error("⚠️ 거리(Distance) 열이 없어 기준 설정이 불가합니다.")

    # ---------------------------------------------------------
    # 4. 객체 감지 및 표시 (토글)
    # ---------------------------------------------------------
    objects_to_draw = []
    fix_id_col, fix_time_col = None, None
    
    if df_fix is not None:
        fix_id_col = next((col for col in df_fix.columns if 'fixation id' in col.lower() or 'target' in col.lower() or 'object' in col.lower()), None)
        fix_time_col = next((col for col in df_fix.columns if 'start' in col.lower() or 'time' in col.lower()), None)
        
        if fix_id_col and fix_time_col:
            unique_ids = df_fix[fix_id_col].dropna().unique()
            valid_ids = [int(x) for x in unique_ids if str(x).strip() and int(x) > 0]
            
            st.sidebar.markdown("---")
            st.sidebar.header("🎯 4. 객체 감지 및 표시 (토글)")
            
            if df_map is not None:
                st.sidebar.caption("✅ 매핑 파일이 감지되어 객체 이름이 자동 변환되었습니다.")
                mapping_dict = {int(row.iloc[0]): str(row.iloc[1]) for _, row in df_map.iterrows()}
                
                for obj_id in valid_ids:
                    if obj_id in mapping_dict:
                        obj_name = mapping_dict[obj_id]
                        if st.sidebar.checkbox(f"🔴 {obj_name} (ID: {obj_id})", value=True):
                            objects_to_draw.append((obj_id, obj_name))
            else:
                st.sidebar.caption("⚠️ mapping.csv 파일이 없습니다. 수동으로 선택하세요.")
                selected_ids = st.sidebar.multiselect("분석할 객체 번호 선택:", sorted(valid_ids))
                for sid in selected_ids:
                    custom_name = st.sidebar.text_input(f"ID {sid} 표시 이름:", value=f"객체 {sid}")
                    objects_to_draw.append((sid, custom_name))

    # ---------------------------------------------------------
    # 5. 수동 커스텀 마커
    # ---------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("📌 5. 수동 커스텀 마커")
    
    if custom_scenario_name not in st.session_state['custom_markers']:
        st.session_state['custom_markers'][custom_scenario_name] = []
        
    marker_time = st.sidebar.number_input("📍 마커 시간 (초)", min_value=0.0, max_value=1000.0, value=10.0, step=0.1)
    marker_label = st.sidebar.text_input("🏷️ 마커 이름", value="")
    
    col_m1, col_m2 = st.sidebar.columns(2)
    if col_m1.button("➕ 수동 마커 추가"):
        if marker_label:
            st.session_state['custom_markers'][custom_scenario_name].append({'time': marker_time, 'label': marker_label})
    if col_m2.button("🗑️ 모두 지우기"):
        st.session_state['custom_markers'][custom_scenario_name] = []

    # ---------------------------------------------------------
    # 메인 화면: 실시간 그래프 렌더링
    # ---------------------------------------------------------
    ds_time_col = 'time' if 'time' in df_ds.columns else 'timestamp'
    ds_speed_col = 'speedInKmPerHour' if 'speedInKmPerHour' in df_ds.columns else ('speed' if 'speed' in df_ds.columns else 'Velocity')
    ds_lane_col = 'laneNumber' if 'laneNumber' in df_ds.columns else ('Lane_ID' if 'Lane_ID' in df_ds.columns else None)
    ds_offset_col = 'offsetFromLaneCenter' if 'offsetFromLaneCenter' in df_ds.columns else None
    
    if ds_lane_col and ds_lane_col in df_ds.columns:
        df_ds.loc[df_ds[ds_lane_col] >= 3, ds_lane_col] = 2
        df_ds.loc[df_ds[ds_lane_col] <= 0, ds_lane_col] = 1

    sac_time_col = 'start timestamp [ns]' if 'start timestamp [ns]' in df_sac.columns else 'start timestamp'
    sac_amp_col = 'amplitude [deg]' if 'amplitude [deg]' in df_sac.columns else 'amplitude'
    
    if ds_time_col in df_ds.columns and sac_time_col in df_sac.columns:
        ds_start_time = df_ds[ds_time_col].min()
        df_ds['Time_s'] = df_ds[ds_time_col] - ds_start_time

        sac_start_time = df_sac[sac_time_col].min()
        is_ns = df_sac[sac_time_col].max() > 1e12
        if is_ns:
            df_sac['Time_s'] = ((df_sac[sac_time_col] - sac_start_time) / 1e9) + time_offset
        else:
            df_sac['Time_s'] = (df_sac[sac_time_col] - sac_start_time) + time_offset

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        if show_speed and ds_speed_col in df_ds.columns:
            if ds_dist_col:
                hovertemplate = '%{y:.1f} <br>📍 위치: %{customdata:.1f} m'
                custom_data = df_ds[ds_dist_col]
            else:
                hovertemplate = '%{y:.1f}'
                custom_data = None
                
            fig.add_trace(go.Scatter(
                x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
                mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2),
                customdata=custom_data, hovertemplate=hovertemplate
            ), secondary_y=False)

        if show_accel:
            accel_col = next((col for col in df_ds.columns if 'accel' in col.lower() and 'x' in col.lower()), None)
            
            if accel_col:
                y_accel = df_ds[accel_col]
            else:
                y_accel = (df_ds[ds_speed_col] / 3.6).diff() / df_ds['Time_s'].diff()
                
            fig.add_trace(go.Scatter(
                x=df_ds['Time_s'], y=y_accel, 
                mode='lines', name='가속도 (m/s²)', line=dict(color='darkmagenta', width=1.5)
            ), secondary_y=True)

        if show_offset and ds_offset_col and ds_offset_col in df_ds.columns:
            fig.add_trace(go.Scatter(
                x=df_ds['Time_s'], y=df_ds[ds_offset_col], 
                mode='lines', name='조향 편차 (m)', line=dict(color='seagreen', width=2, dash='dot')
            ), secondary_y=True)

        if show_saccade and sac_amp_col in df_sac.columns:
            fig.add_trace(go.Scatter(
                x=df_sac['Time_s'], y=df_sac[sac_amp_col], 
                mode='lines', name='시선 이동 각도 (deg)',
                fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.4)', line=dict(color='crimson', width=0.5) 
            ), secondary_y=False)

        if show_blink and df_blink is not None:
            blink_time_col = 'start timestamp [ns]' if 'start timestamp [ns]' in df_blink.columns else 'start timestamp'
            if blink_time_col in df_blink.columns:
                if is_ns:
                    df_blink['Time_s'] = ((df_blink[blink_time_col] - sac_start_time) / 1e9) + time_offset
                else:
                    df_blink['Time_s'] = (df_blink[blink_time_col] - sac_start_time) + time_offset
                    
                fig.add_trace(go.Scatter(
                    x=df_blink['Time_s'], y=[-5] * len(df_blink), 
                    mode='markers', name='눈 깜빡임 발생',
                    marker=dict(symbol='line-ns', color='darkorange', size=15, line=dict(width=2)), hoverinfo='x+name'
                ), secondary_y=False)

        # 차선 변경 필터링 (통계 출력용 분리)
        lane_change_count = 0
        filtered_lane_changes = []
        if ds_lane_col and ds_lane_col in df_ds.columns:
            raw_lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0]['Time_s'].tolist()
            last_lc_time = -999.0
            for lc_time in raw_lane_changes:
                if lc_time - last_lc_time > 5.0:
                    filtered_lane_changes.append(lc_time)
                    last_lc_time = lc_time
            lane_change_count = len(filtered_lane_changes)
            
            if show_lane_change:
                for lc_time in filtered_lane_changes:
                    fig.add_vrect(x0=lc_time-3.0, x1=lc_time+3.0, fillcolor="gold", opacity=0.15, layer="below", line_width=0, annotation_text="차선 변경", annotation_position="top left")

        if caution_mode == "이동 거리(m) 기준" and caution_start_time is not None and ds_dist_col:
            base_m = caution_dist_input
            work_zones = [
                {"name": "🟢 주의구간", "start": base_m, "end": base_m + 1500, "color": "lightgreen"},
                {"name": "🟡 완화구간", "start": base_m + 1500, "end": base_m + 1720, "color": "orange"},
                {"name": "🔴 완충구간", "start": base_m + 1720, "end": base_m + 2270, "color": "red"},
                {"name": "⚫ 작업구역", "start": base_m + 2270, "end": base_m + 3070, "color": "black"}
            ]
            
            for zone in work_zones:
                start_df = df_ds[df_ds[ds_dist_col] >= zone["start"]]
                end_df = df_ds[df_ds[ds_dist_col] >= zone["end"]]
                
                z_start_time = start_df.iloc[0]['Time_s'] if not start_df.empty else df_ds['Time_s'].max()
                z_end_time = end_df.iloc[0]['Time_s'] if not end_df.empty else df_ds['Time_s'].max()
                
                if z_start_time < z_end_time:
                    fig.add_vrect(
                        x0=z_start_time, x1=z_end_time, 
                        fillcolor=zone["color"], opacity=0.1, layer="below", line_width=1,
                        annotation_text=zone["name"], annotation_position="top left", annotation_font=dict(size=12, color="gray")
                    )

        if df_fix is not None and objects_to_draw:
            for obj_id, obj_name in objects_to_draw:
                first_occurrence = df_fix[df_fix[fix_id_col] == obj_id].iloc[0]
                raw_t = first_occurrence[fix_time_col]
                
                is_ns_fix = raw_t > 1e12
                adj_time = ((raw_t - sac_start_time) / 1e9) + time_offset if is_ns_fix else (raw_t - sac_start_time) + time_offset
                
                closest_ds_row = df_ds.iloc[(df_ds['Time_s'] - adj_time).abs().argsort()[:1]]
                
                dist_str = f"<br><span style='font-size:11px; font-family:Arial;'>({closest_ds_row[ds_dist_col].values[0]:.1f}m 지점)</span>" if ds_dist_col and not closest_ds_row.empty else ""
                
                fig.add_vline(
                    x=adj_time, line_width=2, line_dash="dash", line_color="red",
                    annotation_text=f"🎯 {obj_name} 인지 {dist_str}", annotation_position="bottom right",
                    annotation_font=dict(color="red", size=14, family="Arial Black")
                )

        for marker in st.session_state['custom_markers'][custom_scenario_name]:
            fig.add_vline(
                x=marker['time'], line_width=2, line_dash="dash", line_color="purple",
                annotation_text=f"📌 {marker['label']}", annotation_position="top right",
                annotation_font=dict(color="purple", size=14, family="Arial Black")
            )

        fig.update_layout(
            title=f"[{custom_scenario_name}] 실시간 다중 레이어 분석 차트", xaxis_title="주행 시간 (초)",
            height=650, hovermode="x unified", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255, 255, 255, 0.7)')
        )
        
        fig.update_yaxes(title_text="속도 (km/h) / 시야각 (deg)", secondary_y=False)
        fig.update_yaxes(title_text="가속도 & 조향 편차", secondary_y=True, showgrid=False)

        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader(f"💡 '{custom_scenario_name}' 요약 통계")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        total_blinks = len(df_blink) if df_blink is not None else 0
        max_offset = round(df_ds[ds_offset_col].abs().max(), 2) if ds_offset_col and ds_offset_col in df_ds.columns else 0
        
        col1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max(), 1)} 초")
        col2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
        col3.metric("최대 조향 이탈", f"{max_offset} m")
        col4.metric("👀 총 눈 깜빡임", f"{total_blinks} 회")
        col5.metric("차선 변경 횟수", f"{lane_change_count} 회")
        
        # 💡 [신규 기능 4] 차선 변경 상세 통계 (±3초 구간 기준)
        if lane_change_count > 0 and ds_dist_col:
            st.markdown("#### 🚧 첫 번째 차선 변경 상세 분석 (기준: 변경 시점 ±3초)")
            lc_col1, lc_col2, lc_col3, lc_col4 = st.columns(4)
            
            first_lc = filtered_lane_changes[0]
            start_t = max(0, first_lc - 3.0)
            end_t = first_lc + 3.0
            
            start_row = df_ds.iloc[(df_ds['Time_s'] - start_t).abs().argsort()[:1]]
            end_row = df_ds.iloc[(df_ds['Time_s'] - end_t).abs().argsort()[:1]]
            
            start_dist = start_row[ds_dist_col].values[0]
            end_dist = end_row[ds_dist_col].values[0]
            
            lc_col1.metric("시작 지점 (시간 / 거리)", f"{start_t:.1f}초 / {start_dist:.1f}m")
            lc_col2.metric("종료 지점 (시간 / 거리)", f"{end_t:.1f}초 / {end_dist:.1f}m")
            lc_col3.metric("변경 소요 시간", f"{end_t - start_t:.1f}초")
            lc_col4.metric("변경 중 이동 거리", f"{end_dist - start_dist:.1f}m")

    else:
        st.error("⚠️ 데이터 구조(컬럼명)를 인식할 수 없습니다. 원본 파일 형식을 확인해주세요.")
