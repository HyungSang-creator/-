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
# [핵심 함수 1] 폴더 내 기본 파일 자동 매칭
# ---------------------------------------------------------
def find_files_in_folder(folder_path):
    ds_file_path, sac_file_path, blink_file_path, fix_file_path = None, None, None, None
    
    for filename in os.listdir(folder_path):
        lower_name = filename.lower()
        if lower_name.endswith('.csv'):
            if 'saccade' in lower_name:
                sac_file_path = os.path.join(folder_path, filename)
            elif 'blink' in lower_name:
                blink_file_path = os.path.join(folder_path, filename)
            elif 'fixation' in lower_name:
                fix_file_path = os.path.join(folder_path, filename)
            elif '_' in lower_name and 'world' not in lower_name:
                ds_file_path = os.path.join(folder_path, filename)
                
    return ds_file_path, sac_file_path, blink_file_path, fix_file_path

# ---------------------------------------------------------
# 1. 사이드바: 데이터 소스 선택
# ---------------------------------------------------------
st.sidebar.header("📁 1. 데이터 소스 선택")
data_mode = st.sidebar.radio(
    "어떤 방식으로 데이터를 분석할까요?", 
    ["💾 서버에 내장된 시나리오 불러오기", "📤 내 PC에서 직접 파일 업로드"]
)

st.sidebar.markdown("---")

df_ds, df_sac, df_blink, df_fix = None, None, None, None
data_loaded = False

if data_mode == "💾 서버에 내장된 시나리오 불러오기":
    st.sidebar.subheader("내장된 폴더 선택")
    folder_options = [item for item in os.listdir('.') if os.path.isdir(item) and not item.startswith('.') and not item == '__pycache__']
    folder_options.sort()

    if len(folder_options) > 0:
        selected_folder = st.sidebar.selectbox("분석할 시나리오 폴더 선택:", folder_options)
        ds_path, sac_path, blink_path, fix_path = find_files_in_folder(selected_folder)
        
        if ds_path and sac_path:
            df_ds = pd.read_csv(ds_path)
            df_sac = pd.read_csv(sac_path)
            df_blink = pd.read_csv(blink_path) if blink_path else None
            df_fix = pd.read_csv(fix_path) if fix_path else None
            data_loaded = True
        else:
            st.sidebar.error(f"⚠️ '{selected_folder}' 폴더에서 필수 데이터를 찾지 못했습니다.")
    else:
        st.sidebar.warning("⚠️ 깃허브 서버에 시나리오 폴더가 없습니다.")

else:
    st.sidebar.subheader("파일 업로드")
    ds_file = st.sidebar.file_uploader("주행 데이터 파일 업로드", type=['csv'])
    sac_file = st.sidebar.file_uploader("시선 이동(Saccade) 파일 업로드", type=['csv'])
    blink_file = st.sidebar.file_uploader("눈 깜빡임(Blink) 파일 업로드", type=['csv'])
    fix_file = st.sidebar.file_uploader("시선 고정(Fixations) 파일 업로드", type=['csv'])
    
    if ds_file and sac_file:
        df_ds = pd.read_csv(ds_file)
        df_sac = pd.read_csv(sac_file)
        df_blink = pd.read_csv(blink_file) if blink_file else None
        df_fix = pd.read_csv(fix_file) if fix_file else None
        data_loaded = True
    else:
        st.sidebar.info("분석할 CSV 파일들을 올려주세요.")

# ---------------------------------------------------------
# 2. 사이드바: 분석 옵션 및 마커
# ---------------------------------------------------------
if data_loaded:
    custom_scenario_name = st.sidebar.text_input(
        "📝 차트 제목(시나리오 이름) 변경:", 
        value=selected_folder if data_mode == "💾 서버에 내장된 시나리오 불러오기" else "새로운 분석 시나리오"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ 2. 분석 레이어 및 옵션")
    show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
    show_offset = st.sidebar.checkbox("↔️ 조향 편차 (차로 이탈 정도)", value=True)
    show_saccade = st.sidebar.checkbox("👁️ 시선 이동 각도 (채워진 그래프)", value=True)
    show_blink = st.sidebar.checkbox("😌 눈 깜빡임 (하단 마커)", value=True)
    show_lane_change = st.sidebar.checkbox("🚧 차선 변경 구간 하이라이트", value=True)
    time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -10.0, 10.0, 0.0, 0.1)

    # ---------------------------------------------------------
    # 💡 [핵심 추가] Fixations 기반 객체 선택 및 이름 변경 UI
    # ---------------------------------------------------------
    selected_ids = []
    custom_labels = {}
    fix_id_col, fix_time_col = None, None
    
    if df_fix is not None:
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 3. 감지된 객체 표시 (Fixations)")
        
        # fixation id 및 시간 열 유연하게 찾기
        fix_id_col = next((col for col in df_fix.columns if 'fixation id' in col.lower() or 'target' in col.lower() or 'object' in col.lower()), None)
        fix_time_col = next((col for col in df_fix.columns if 'start' in col.lower() or 'time' in col.lower()), None)
        
        if fix_id_col and fix_time_col:
            # 유효한 숫자형 ID만 추출 (빈칸, NaN 제외)
            unique_ids = df_fix[fix_id_col].dropna().unique()
            # 0이나 -1 같은 더미 데이터 제외하고 오름차순 정렬
            valid_ids = sorted([int(x) for x in unique_ids if str(x).strip() and int(x) > 0])
            
            selected_ids = st.sidebar.multiselect("분석할 객체 번호를 선택하세요 (다중 선택):", valid_ids)
            
            if selected_ids:
                st.sidebar.caption("👇 선택한 객체의 표시 이름을 변경하세요")
                for sid in selected_ids:
                    custom_labels[sid] = st.sidebar.text_input(f"ID {sid} 표시 이름:", value=f"객체 {sid}")
        else:
            st.sidebar.warning("Fixations 파일에서 'fixation id' 열을 찾을 수 없습니다.")

    # ---------------------------------------------------------
    # 📌 수동 마커 기능
    # ---------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("📌 4. 수동 커스텀 마커")
    
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
            fig.add_trace(go.Scatter(
                x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
                mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2)
            ), secondary_y=False)

        if show_offset and ds_offset_col and ds_offset_col in df_ds.columns:
            fig.add_trace(go.Scatter(
                x=df_ds['Time_s'], y=df_ds[ds_offset_col], 
                mode='lines', name='조향 편차 (m)', line=dict(color='seagreen', width=2, dash='dot')
            ), secondary_y=True)

        if show_saccade and sac_amp_col in df_sac.columns:
            fig.add_trace(go.Scatter(
                x=df_sac['Time_s'], y=df_sac[sac_amp_col], 
                mode='lines', name='시선 이동 각도 (deg)',
                fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.4)', 
                line=dict(color='crimson', width=0.5) 
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
                    marker=dict(symbol='line-ns', color='darkorange', size=15, line=dict(width=2)),
                    hoverinfo='x+name'
                ), secondary_y=False)

        lane_change_count = 0
        if show_lane_change and ds_lane_col and ds_lane_col in df_ds.columns:
            raw_lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0]['Time_s'].tolist()
            filtered_lane_changes = []
            last_lc_time = -999.0
            for lc_time in raw_lane_changes:
                if lc_time - last_lc_time > 5.0:
                    filtered_lane_changes.append(lc_time)
                    last_lc_time = lc_time
            lane_change_count = len(filtered_lane_changes)
            for lc_time in filtered_lane_changes:
                fig.add_vrect(
                    x0=lc_time - 3.0, x1=lc_time + 3.0, 
                    fillcolor="gold", opacity=0.15, layer="below", line_width=0,
                    annotation_text="차선 변경", annotation_position="top left"
                )

        # ---------------------------------------------------------
        # 💡 [핵심 추가] 사용자가 선택한 객체(Fixations)만 그래프에 표시
        # ---------------------------------------------------------
        if df_fix is not None and fix_id_col and fix_time_col and selected_ids:
            for sid in selected_ids:
                # 선택한 객체를 처음 바라본 순간의 데이터 한 줄을 가져옴
                first_occurrence = df_fix[df_fix[fix_id_col] == sid].iloc[0]
                raw_t = first_occurrence[fix_time_col]
                
                # 아이트래커 기준 시간을 메인 그래프의 시간에 맞춰 보정
                is_ns_fix = raw_t > 1e12
                if is_ns_fix:
                    adj_time = ((raw_t - sac_start_time) / 1e9) + time_offset
                else:
                    adj_time = (raw_t - sac_start_time) + time_offset
                
                # 그래프 위에 지정한 이름으로 빨간 점선 긋기
                fig.add_vline(
                    x=adj_time, line_width=2, line_dash="dash", line_color="red",
                    annotation_text=f"🎯 {custom_labels[sid]}", annotation_position="bottom right",
                    annotation_font=dict(color="red", size=14, family="Arial Black")
                )

        # 수동 마커 렌더링
        for marker in st.session_state['custom_markers'][custom_scenario_name]:
            fig.add_vline(
                x=marker['time'], line_width=2, line_dash="dash", line_color="purple",
                annotation_text=f"📌 {marker['label']}", annotation_position="top right",
                annotation_font=dict(color="purple", size=14, family="Arial Black")
            )

        fig.update_layout(
            title=f"[{custom_scenario_name}] 실시간 다중 레이어 분석 차트",
            xaxis_title="주행 시간 (초)",
            height=650,
            hovermode="x unified",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255, 255, 255, 0.7)')
        )
        
        fig.update_yaxes(title_text="속도 (km/h) / 시야각 (deg)", secondary_y=False)
        fig.update_yaxes(title_text="조향 편차 (m)", secondary_y=True, showgrid=False)

        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader(f"💡 '{custom_scenario_name}' 요약 통계")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max(), 1)} 초")
        col2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
        max_offset = round(df_ds[ds_offset_col].abs().max(), 2) if ds_offset_col and ds_offset_col in df_ds.columns else 0
        col3.metric("최대 조향 이탈", f"{max_offset} m")
        col4.metric("차선 변경 횟수", f"{lane_change_count} 회")
    else:
        st.error("⚠️ 데이터 구조(컬럼명)를 인식할 수 없습니다. 원본 파일 형식을 확인해주세요.")
