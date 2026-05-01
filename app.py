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

# 기기 간 시간 오차 수동 보정 (동기화 미세 조정용)
st.sidebar.markdown("---")
st.sidebar.header("⏱️ 3. 시간 동기화 보정")
time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -100.0, 100.0, 0.0, 0.1)
st.sidebar.info("DS와 아이트래커의 시작 시간이 다를 경우, 이 슬라이더를 움직여 그래프의 시점을 완벽하게 일치시킬 수 있습니다.")

if ds_file and sac_file:
    # 데이터 로드
    df_ds = pd.read_csv(ds_file)
    df_sac = pd.read_csv(sac_file)
    
    # ⚠️ 컬럼명 매핑 (실제 데이터에 맞게 자동 탐색 또는 지정)
    # DS 시간 컬럼 찾기 (time 또는 timestamp)
    ds_time_col = 'time' if 'time' in df_ds.columns else 'timestamp'
    # DS 속도 컬럼 찾기
    ds_speed_col = 'speed' if 'speed' in df_ds.columns else 'Velocity'
    # DS 차로 컬럼 찾기
    ds_lane_col = 'laneNumber' if 'laneNumber' in df_ds.columns else 'Lane_ID'
    
    # 시간 단위 통일 (DS는 초, 아이트래커는 나노초->초 변환 후 오차 보정)
    df_ds['Time_s'] = df_ds[ds_time_col]
    df_sac['Time_s'] = (df_sac['start timestamp'] / 1e9) + time_offset

    # 그래프 생성 (Plotly Graph Objects 사용)
    fig = go.Figure()

    # [레이어 1] 차량 속도 (Line)
    if show_speed and ds_speed_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
            mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2)
        ))

    # [레이어 2] 시야각 (Saccade Amplitude - Scatter)
    if show_saccade and 'amplitude [deg]' in df_sac.columns:
        fig.add_trace(go.Scatter(
            x=df_sac['Time_s'], y=df_sac['amplitude [deg]'], 
            mode='markers', name='시선 이동 각도 (deg)',
            marker=dict(size=8, color='crimson', symbol='diamond', opacity=0.7)
        ))

    # [레이어 3] 눈 깜빡임 (Blink - Vertical Lines)
    if show_blink and blink_file:
        df_blink = pd.read_csv(blink_file)
        df_blink['Time_s'] = (df_blink['start timestamp'] / 1e9) + time_offset
        for _, row in df_blink.iterrows():
            fig.add_vline(x=row['Time_s'], line_width=1, line_dash="dash", line_color="orange", opacity=0.5)
        # 범례 표시용 더미 트레이스
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='orange', dash='dash'), name='눈 깜빡임 발생'))

    # [레이어 4] 차선 변경 구간 하이라이트 (Background V-Rect)
    if show_lane_change and ds_lane_col in df_ds.columns:
        lane_changes = df_ds[df_ds[ds_lane_col].diff() > 0]
        for lc_time in lane_changes['Time_s']:
            # 차선 변경 시점 기준 앞뒤 3초를 노란색 배경으로 칠함
            fig.add_vrect(
                x0=lc_time - 3.0, x1=lc_time + 3.0, 
                fillcolor="gold", opacity=0.2, layer="below", line_width=0,
                annotation_text="차선 변경 구간", annotation_position="top left"
            )

    # 그래프 레이아웃 설정
    fig.update_layout(
        title="실시간 다중 레이어 분석 차트 (마우스로 드래그하여 확대/축소 가능)",
        xaxis_title="주행 시간 (초)",
        yaxis_title="수치 (속도 km/h / 시야각 deg)",
        height=600,
        hovermode="x unified", # 마우스를 올리면 그 시간대의 모든 데이터가 툴팁으로 표시됨
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )

    st.plotly_chart(fig, use_container_width=True)

    # 하단 데이터 요약 표
    st.markdown("---")
    st.subheader("💡 현재 데이터 요약")
    col1, col2, col3 = st.columns(3)
    col1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max() - df_ds['Time_s'].min(), 1)} 초")
    col2.metric("최대 시야각 발생", f"{round(df_sac['amplitude [deg]'].max(), 1)} deg")
    col3.metric("차선 변경 횟수", f"{len(df_ds[df_ds[ds_lane_col].diff() > 0])} 회")

else:
    st.info("👈 좌측 메뉴에서 2_B1.csv 파일과 saccades.csv 파일을 업로드하면 그래프가 나타납니다.")
