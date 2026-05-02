import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")
st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
st.markdown("좌측 메뉴에서 폴더를 선택하고, 발표에 맞게 시나리오 이름을 자유롭게 변경해보세요.")

# 1. 사이드바: 시나리오(폴더) 선택
st.sidebar.header("📁 1. 시나리오 데이터 선택")

# Scenario_1 부터 Scenario_12 까지 폴더 목록 자동 생성
folder_options = [f"Scenario_{i}" for i in range(1, 13)]

selected_folder = st.sidebar.selectbox("분석할 원본 폴더 번호 선택:", folder_options)

# 💡 핵심 추가 기능: 사이트 내에서 시나리오 이름 직접 변경
st.sidebar.markdown("---")
custom_scenario_name = st.sidebar.text_input(
    "📝 차트에 표시될 시나리오 이름 변경:", 
    value=f"시나리오 {selected_folder.split('_')[1]}" # 기본값 세팅 (예: 시나리오 1)
)
st.sidebar.caption("여기에 입력한 이름이 우측 차트 제목과 통계표에 즉시 반영됩니다. (예: Base, 600m 주간 등)")

# 2. 분석 레이어 선택
st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. 분석 레이어 선택")
show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
show_offset = st.sidebar.checkbox("↔️ 조향 편차 (차로 이탈 정도)", value=True)
show_saccade = st.sidebar.checkbox("👁️ 시선 이동 각도 (채워진 그래프)", value=True)
show_blink = st.sidebar.checkbox("😌 눈 깜빡임 (하단 마커)", value=True)
show_lane_change = st.sidebar.checkbox("🚧 차선 변경 구간 하이라이트", value=True)

# 3. 시간 동기화 보정
st.sidebar.markdown("---")
st.sidebar.header("⏱️ 3. 시간 동기화 보정")
time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -10.0, 10.0, 0.0, 0.1)

# 데이터 파일 경로 자동 생성
ds_path = os.path.join(selected_folder, "2_B1.csv")
sac_path = os.path.join(selected_folder, "saccades.csv")
blink_path = os.path.join(selected_folder, "blinks.csv")

# 파일 존재 여부 확인 후 실행
if os.path.exists(ds_path) and os.path.exists(sac_path):
    df_ds = pd.read_csv(ds_path)
    df_sac = pd.read_csv(sac_path)
    
    ds_time_col = 'time'
    ds_speed_col = 'speedInKmPerHour'
    ds_lane_col = 'laneNumber'
    ds_offset_col = 'offsetFromLaneCenter'
    
    sac_time_col = 'start timestamp [ns]'
    sac_amp_col = 'amplitude [deg]'
    
    # 시간 단위 통일 및 영점 맞추기
    ds_start_time = df_ds[ds_time_col].min()
    df_ds['Time_s'] = df_ds[ds_time_col] - ds_start_time

    sac_start_time = df_sac[sac_time_col].min()
    df_sac['Time_s'] = ((df_sac[sac_time_col] - sac_start_time) / 1e9) + time_offset

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # [레이어 1] 차량 속도
    if show_speed and ds_speed_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
            mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2)
        ), secondary_y=False)

    # [레이어 2] 조향 편차
    if show_offset and ds_offset_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_offset_col], 
            mode='lines', name='조향 편차 (m)', line=dict(color='seagreen', width=2, dash='dot')
        ), secondary_y=True)

    # [레이어 3] 시야각
    if show_saccade and sac_amp_col in df_sac.columns:
        fig.add_trace(go.Scatter(
            x=df_sac['Time_s'], y=df_sac[sac_amp_col], 
            mode='lines', name='시선 이동 각도 (deg)',
            fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.4)', 
            line=dict(color='crimson', width=0.5) 
        ), secondary_y=False)

    # [레이어 4] 눈 깜빡임
    if show_blink and os.path.exists(blink_path):
        df_blink = pd.read_csv(blink_path)
        blink_time_col = 'start timestamp [ns]' 
        
        if blink_time_col in df_blink.columns:
            df_blink['Time_s'] = ((df_blink[blink_time_col] - sac_start_time) / 1e9) + time_offset
            
            fig.add_trace(go.Scatter(
                x=df_blink['Time_s'], y=[-5] * len(df_blink), 
                mode='markers', name='눈 깜빡임 발생',
                marker=dict(symbol='line-ns', color='darkorange', size=15, line=dict(width=2)),
                hoverinfo='x+name'
            ), secondary_y=False)

    # [레이어 5] 차선 변경 구간 하이라이트
    if show_lane_change and ds_lane_col in df_ds.columns:
        lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0]
        for lc_time in lane_changes['Time_s']:
            fig.add_vrect(
                x0=lc_time - 3.0, x1=lc_time + 3.0, 
                fillcolor="gold", opacity=0.15, layer="below", line_width=0,
                annotation_text="차선 변경", annotation_position="top left"
            )

    # 💡 사용자가 입력한 이름을 차트 제목에 반영
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

    # 💡 통계표 제목에도 사용자가 입력한 이름 반영
    st.markdown("---")
    st.subheader(f"💡 '{custom_scenario_name}' 요약 통계")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max(), 1)} 초")
    col2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
    
    max_offset = round(df_ds[ds_offset_col].abs().max(), 2) if ds_offset_col in df_ds.columns else 0
    col3.metric("최대 조향 이탈", f"{max_offset} m")
    
    lane_change_count = len(lane_changes) if 'lane_changes' in locals() else 0
    col4.metric("차선 변경 횟수", f"{lane_change_count} 회")

else:
    st.warning(f"⚠️ '{selected_folder}' 폴더에 데이터가 없습니다. 깃허브에 '2_B1.csv'와 'saccades.csv' 파일을 업로드해주세요.")
