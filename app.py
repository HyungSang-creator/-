import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")
st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
st.markdown("서버에 저장된 시나리오를 불러오거나, 새로운 데이터를 직접 업로드하여 분석할 수 있습니다.")

# ---------------------------------------------------------
# [핵심 함수] 폴더 내 파일 자동 매칭 (언더바 규칙 적용)
# ---------------------------------------------------------
def find_files_in_folder(folder_path):
    ds_file_path, sac_file_path, blink_file_path = None, None, None
    
    for filename in os.listdir(folder_path):
        lower_name = filename.lower()
        if lower_name.endswith('.csv'):
            # 1. 시선 이동 데이터 찾기 ('saccade' 포함)
            if 'saccade' in lower_name:
                sac_file_path = os.path.join(folder_path, filename)
            # 2. 눈 깜빡임 데이터 찾기 ('blink' 포함)
            elif 'blink' in lower_name:
                blink_file_path = os.path.join(folder_path, filename)
            # 3. 주행 데이터 찾기 (언더바 '_'가 있고, 'world'가 포함되지 않은 파일)
            elif '_' in lower_name and 'world' not in lower_name:
                ds_file_path = os.path.join(folder_path, filename)
                
    return ds_file_path, sac_file_path, blink_file_path

# ---------------------------------------------------------
# 1. 사이드바: 데이터 소스 선택
# ---------------------------------------------------------
st.sidebar.header("📁 1. 데이터 소스 선택")
data_mode = st.sidebar.radio(
    "어떤 방식으로 데이터를 분석할까요?", 
    ["💾 서버에 내장된 시나리오 불러오기", "📤 내 PC에서 직접 파일 업로드"]
)

st.sidebar.markdown("---")

df_ds, df_sac, df_blink = None, None, None
data_loaded = False

# [모드 A] 서버 내장 데이터 불러오기
if data_mode == "💾 서버에 내장된 시나리오 불러오기":
    st.sidebar.subheader("내장된 폴더 선택")
    
    # 숨김 폴더 등을 제외하고 일반 폴더만 스캔
    folder_options = [item for item in os.listdir('.') if os.path.isdir(item) and not item.startswith('.') and not item == '__pycache__']
    folder_options.sort()

    if len(folder_options) > 0:
        selected_folder = st.sidebar.selectbox("분석할 시나리오 폴더 선택:", folder_options)
        
        # 💡 업그레이드된 스캔 함수 작동 (언더바 규칙)
        ds_path, sac_path, blink_path = find_files_in_folder(selected_folder)
        
        if ds_path and sac_path:
            df_ds = pd.read_csv(ds_path)
            df_sac = pd.read_csv(sac_path)
            df_blink = pd.read_csv(blink_path) if blink_path else None
            data_loaded = True
        else:
            st.sidebar.error(f"⚠️ '{selected_folder}' 폴더에서 필수 데이터를 찾지 못했습니다.\n폴더 안에 주행 데이터(언더바 포함 .csv)와 시선 이동(saccade) 파일이 모두 있는지 확인해주세요.")
    else:
        st.sidebar.warning("⚠️ 깃허브 서버에 시나리오 폴더가 없습니다.")

# [모드 B] 직접 파일 업로드하기
else:
    st.sidebar.subheader("파일 업로드")
    ds_file = st.sidebar.file_uploader("주행 데이터 파일 업로드", type=['csv'])
    sac_file = st.sidebar.file_uploader("시선 이동(Saccade) 파일 업로드", type=['csv'])
    blink_file = st.sidebar.file_uploader("눈 깜빡임(Blink) 파일 업로드", type=['csv'])
    
    if ds_file and sac_file:
        df_ds = pd.read_csv(ds_file)
        df_sac = pd.read_csv(sac_file)
        df_blink = pd.read_csv(blink_file) if blink_file else None
        data_loaded = True
    else:
        st.sidebar.info("분석할 CSV 파일들을 올려주세요.")

# ---------------------------------------------------------
# 2. 사이드바: 분석 옵션
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
    # 3. 메인 화면: 실시간 그래프 렌더링
    # ---------------------------------------------------------
    ds_time_col = 'time' if 'time' in df_ds.columns else 'timestamp'
    ds_speed_col = 'speedInKmPerHour' if 'speedInKmPerHour' in df_ds.columns else ('speed' if 'speed' in df_ds.columns else 'Velocity')
    ds_lane_col = 'laneNumber' if 'laneNumber' in df_ds.columns else ('Lane_ID' if 'Lane_ID' in df_ds.columns else None)
    ds_offset_col = 'offsetFromLaneCenter' if 'offsetFromLaneCenter' in df_ds.columns else None
    
    # 💡 [핵심 추가] 주행 미숙으로 인한 가짜 차로(0차로, 3차로) 인식 방지 정제 로직
    if ds_lane_col and ds_lane_col in df_ds.columns:
        # 3차로 이상(우측 갓길 이탈)은 모두 2차로로 덮어쓰기
        df_ds.loc[df_ds[ds_lane_col] >= 3, ds_lane_col] = 2
        # 0차로 이하(좌측 중앙선 침범)는 모두 1차로로 덮어쓰기
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

        # [레이어 5] 차선 변경 구간 하이라이트 (바운싱 노이즈 제거 적용)
        lane_change_count = 0
        if show_lane_change and ds_lane_col and ds_lane_col in df_ds.columns:
            # 값이 변한 모든 시간(초)을 리스트로 추출
            raw_lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0]['Time_s'].tolist()
            
            filtered_lane_changes = []
            last_lc_time = -999.0
            
            for lc_time in raw_lane_changes:
                # 이전 차선 변경 시점으로부터 5초가 지났을 때만 '새로운 차선 변경'으로 인정
                if lc_time - last_lc_time > 5.0:
                    filtered_lane_changes.append(lc_time)
                    last_lc_time = lc_time
                    
            lane_change_count = len(filtered_lane_changes)
            
            # 필터링된 진짜 차선 변경 시점에만 노란 박스 그리기
            for lc_time in filtered_lane_changes:
                fig.add_vrect(
                    x0=lc_time - 3.0, x1=lc_time + 3.0, 
                    fillcolor="gold", opacity=0.15, layer="below", line_width=0,
                    annotation_text="차선 변경", annotation_position="top left"
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
