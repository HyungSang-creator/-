import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")
st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
st.markdown("주행 데이터(DS)와 시선 데이터(Eye-tracker)를 업로드하면 타임라인에 실시간으로 동기화하여 분석합니다.")

# 1. 사이드바: 데이터 업로드
st.sidebar.header("📁 1. 데이터 업로드")
ds_file = st.sidebar.file_uploader("주행 데이터 (2_B1.csv)", type=['csv'])
sac_file = st.sidebar.file_uploader("시선 이동 (saccades.csv)", type=['csv'])
blink_file = st.sidebar.file_uploader("눈 깜빡임 (blinks.csv)", type=['csv'])

# 2. 사이드바: 분석 레이어 선택 (조향 편차 추가됨)
st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. 분석 레이어 선택")
show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
show_offset = st.sidebar.checkbox("↔️ 조향 편차 (차로 이탈 정도)", value=True)
show_saccade = st.sidebar.checkbox("👁️ 시선 이동 각도 (채워진 그래프)", value=True)
show_blink = st.sidebar.checkbox("😌 눈 깜빡임 (세로줄)", value=True)
show_lane_change = st.sidebar.checkbox("🚧 차선 변경 구간 하이라이트", value=True)

# 3. 사이드바: 시간 동기화
st.sidebar.markdown("---")
st.sidebar.header("⏱️ 3. 시간 동기화 보정")
time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -10.0, 10.0, 0.0, 0.1)

if ds_file and sac_file:
    # 데이터 읽기
    df_ds = pd.read_csv(ds_file)
    df_sac = pd.read_csv(sac_file)
    
    # 정확한 컬럼명 세팅
    ds_time_col = 'time'
    ds_speed_col = 'speedInKmPerHour'
    ds_lane_col = 'laneNumber'
    ds_offset_col = 'offsetFromLaneCenter' # 조향 편차 컬럼
    
    sac_time_col = 'start timestamp [ns]'
    sac_amp_col = 'amplitude [deg]'
    
    # 시간 단위 통일 및 영점(0초) 맞추기
    ds_start_time = df_ds[ds_time_col].min()
    df_ds['Time_s'] = df_ds[ds_time_col] - ds_start_time

    sac_start_time = df_sac[sac_time_col].min()
    df_sac['Time_s'] = ((df_sac[sac_time_col] - sac_start_time) / 1e9) + time_offset

    # 🚨 이중 Y축을 지원하는 그래프 뼈대 생성
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # [레이어 1] 차량 속도 (좌측 Y축)
    if show_speed and ds_speed_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
            mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2)
        ), secondary_y=False)

    # [레이어 2] 조향 편차 (우측 보조 Y축, 단위가 작아서 따로 분리)
    if show_offset and ds_offset_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_offset_col], 
            mode='lines', name='조향 편차 (m)', line=dict(color='seagreen', width=2, dash='dot')
        ), secondary_y=True)

    # [레이어 3] 시야각 (좌측 Y축, 점 대신 채워진 선 그래프로 변경)
    if show_saccade and sac_amp_col in df_sac.columns:
        fig.add_trace(go.Scatter(
            x=df_sac['Time_s'], y=df_sac[sac_amp_col], 
            mode='lines', name='시선 이동 각도 (deg)',
            fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.2)', # 반투명 빨간색 채우기
            line=dict(color='crimson', width=2)
        ), secondary_y=False)

    # [레이어 4] 눈 깜빡임 (깔끔한 한 줄 세로선)
    if show_blink and blink_file:
        df_blink = pd.read_csv(blink_file)
        blink_time_col = 'start timestamp [ns]' 
        
        if blink_time_col in df_blink.columns:
            df_blink['Time_s'] = ((df_blink[blink_time_col] - sac_start_time) / 1e9) + time_offset
            for _, row in df_blink.iterrows():
                fig.add_vline(x=row['Time_s'], line_width=1.5, line_dash="dash", line_color="darkorange", opacity=0.8)
            # 범례 표시용
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='darkorange', dash='dash'), name='눈 깜빡임 발생'), secondary_y=False)

    # [레이어 5] 차선 변경 구간 하이라이트
    if show_lane_change and ds_lane_col in df_ds.columns:
        lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0]
        for lc_time in lane_changes['Time_s']:
            fig.add_vrect(
                x0=lc_time - 3.0, x1=lc_time + 3.0, 
                fillcolor="gold", opacity=0.15, layer="below", line_width=0,
                annotation_text="차선 변경", annotation_position="top left"
            )

    # 그래프 디자인 최종 정리
    fig.update_layout(
        title="실시간 다중 레이어 분석 차트 (드래그하여 확대/축소)",
        xaxis_title="주행 시간 (초)",
        height=600,
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255, 255, 255, 0.7)')
    )
    
    # Y축 이름 설정
    fig.update_yaxes(title_text="속도 (km/h) / 시야각 (deg)", secondary_y=False)
    fig.update_yaxes(title_text="조향 편차 (m)", secondary_y=True, showgrid=False)

    st.plotly_chart(fig, use_container_width=True)

    # 요약 통계
    st.markdown("---")
    st.subheader("💡 현재 데이터 요약")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max(), 1)} 초")
    col2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
    
    max_offset = round(df_ds[ds_offset_col].abs().max(), 2) if ds_offset_col in df_ds.columns else 0
    col3.metric("최대 조향 이탈", f"{max_offset} m")
    
    lane_change_count = len(lane_changes) if 'lane_changes' in locals() else 0
    col4.metric("차선 변경 횟수", f"{lane_change_count} 회")

else:
    st.info("👈 좌측 메뉴에서 파일을 업로드하면 프로토타입 디자인의 그래프가 나타납니다.")
