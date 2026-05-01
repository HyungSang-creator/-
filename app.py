import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")
st.title("🚗 원시 데이터 기반 실시간 시야각 & 주행 분석기")
st.markdown("주행 데이터(DS)와 시선 데이터(Eye-tracker)를 업로드하면 타임라인에 실시간으로 동기화하여 분석합니다.")

# 1. 사이드바: 데이터 업로드 및 레이어 컨트롤
st.sidebar.header("📁 1. 데이터 업로드")
ds_file = st.sidebar.file_uploader("주행 데이터 (2_B1.csv)", type=['csv'])
sac_file = st.sidebar.file_uploader("시선 이동 (saccades.csv)", type=['csv'])
blink_file = st.sidebar.file_uploader("눈 깜빡임 (blinks.csv)", type=['csv'])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. 분석 레이어 선택")
show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
show_saccade = st.sidebar.checkbox("👁️ 시선 이동(Saccade) 표시", value=True)
show_blink = st.sidebar.checkbox("😌 눈 깜빡임(Blink) 표시", value=True)
show_lane_change = st.sidebar.checkbox("🚧 차선 변경 구간 하이라이트", value=True)

st.sidebar.markdown("---")
st.sidebar.header("⏱️ 3. 시간 동기화 보정")
time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -100.0, 100.0, 0.0, 0.1)
st.sidebar.info("DS와 아이트래커의 시작 시간이 다를 경우, 이 슬라이더를 움직여 보정하세요.")

if ds_file and sac_file:
    # 1. 데이터 읽기
    df_ds = pd.read_csv(ds_file)
    df_sac = pd.read_csv(sac_file)
    
    # 2. 🚨 에러 해결 핵심: 실제 파일에 적힌 정확한 컬럼명 사용
    ds_time_col = 'time'
    ds_speed_col = 'speedInKmPerHour'
    ds_lane_col = 'laneNumber'
    
    sac_time_col = 'start timestamp [ns]'
    sac_amp_col = 'amplitude [deg]'
    
   # 3. 시간 단위 통일 및 영점(0초) 맞추기
    # DS 데이터를 0초부터 시작하도록 맞춤
    ds_start_time = df_ds[ds_time_col].min()
    df_ds['Time_s'] = df_ds[ds_time_col] - ds_start_time

    # 아이트래커 데이터를 0초부터 시작하도록 맞춤 (나노초 영점)
    sac_start_time = df_sac[sac_time_col].min()
    df_sac['Time_s'] = ((df_sac[sac_time_col] - sac_start_time) / 1e9) + time_offset

    # 4. 그래프 생성 (Plotly)
    fig = go.Figure()

    # [레이어 1] 차량 속도 (Line)
    if show_speed and ds_speed_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
            mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2)
        ))

    # [레이어 2] 시야각 (Scatter)
    if show_saccade and sac_amp_col in df_sac.columns:
        fig.add_trace(go.Scatter(
            x=df_sac['Time_s'], y=df_sac[sac_amp_col], 
            mode='markers', name='시선 이동 각도 (deg)',
            marker=dict(size=8, color='crimson', symbol='diamond', opacity=0.7)
        ))

    # [레이어 3] 눈 깜빡임 (Vertical Lines)
    if show_blink and blink_file:
        df_blink = pd.read_csv(blink_file)
        blink_time_col = 'start timestamp [ns]' 
        
        if blink_time_col in df_blink.columns:
            # 눈 깜빡임 데이터도 아이트래커 기준 영점을 빼서 맞춤
            df_blink['Time_s'] = ((df_blink[blink_time_col] - sac_start_time) / 1e9) + time_offset
            for _, row in df_blink.iterrows():
                fig.add_vline(x=row['Time_s'], line_width=1, line_dash="dash", line_color="orange", opacity=0.5)
            # 범례 표시용
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='orange', dash='dash'), name='눈 깜빡임 발생'))

    # 4. 그래프 생성 (Plotly)
    fig = go.Figure()

    # [레이어 1] 차량 속도 (Line)
    if show_speed and ds_speed_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
            mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2)
        ))

    # [레이어 2] 시야각 (Scatter)
    if show_saccade and sac_amp_col in df_sac.columns:
        fig.add_trace(go.Scatter(
            x=df_sac['Time_s'], y=df_sac[sac_amp_col], 
            mode='markers', name='시선 이동 각도 (deg)',
            marker=dict(size=8, color='crimson', symbol='diamond', opacity=0.7)
        ))

    # [레이어 3] 눈 깜빡임 (Vertical Lines)
    if show_blink and blink_file:
        df_blink = pd.read_csv(blink_file)
        blink_time_col = 'start timestamp [ns]' # blinks 파일도 동일한 컬럼 구조
        
        if blink_time_col in df_blink.columns:
            df_blink['Time_s'] = (df_blink[blink_time_col] / 1e9) + time_offset
            for _, row in df_blink.iterrows():
                fig.add_vline(x=row['Time_s'], line_width=1, line_dash="dash", line_color="orange", opacity=0.5)
            # 범례 표시용
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='orange', dash='dash'), name='눈 깜빡임 발생'))

    # [레이어 4] 차선 변경 구간 하이라이트 (1->2차로, 2->1차로 모두 감지)
    if show_lane_change and ds_lane_col in df_ds.columns:
        # 차로 번호가 변경되는 모든 순간 찾기
        lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0]
        
        for lc_time in lane_changes['Time_s']:
            fig.add_vrect(
                x0=lc_time - 3.0, x1=lc_time + 3.0, 
                fillcolor="gold", opacity=0.2, layer="below", line_width=0,
                annotation_text="차선 변경", annotation_position="top left"
            )

    fig.update_layout(
        title="실시간 다중 레이어 분석 차트 (드래그하여 확대)",
        xaxis_title="주행 시간 (초)",
        yaxis_title="수치 (속도 km/h / 시야각 deg)",
        height=600,
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )

    st.plotly_chart(fig, use_container_width=True)

    # 5. 요약 통계
    st.markdown("---")
    st.subheader("💡 현재 데이터 요약")
    col1, col2, col3 = st.columns(3)
    col1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max() - df_ds['Time_s'].min(), 1)} 초")
    col2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
    col3.metric("차선 변경 횟수", f"{len(lane_changes)} 회")

else:
    st.info("👈 좌측 메뉴에서 2_B1.csv 파일과 saccades.csv 파일을 업로드하면 그래프가 나타납니다.")
