import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="시야각 실시간 분석 대시보드", layout="wide")

# 🚨 핵심 기능: 세션(메모리)에 '저장된 시나리오 보관함' 만들기
if 'saved_scenarios' not in st.session_state:
    st.session_state['saved_scenarios'] = {}

st.title("🚗 실시간 시야각 & 주행 분석기 (시나리오 저장형)")
st.markdown("데이터를 업로드하고 저장하면, 우측 사이드바에서 클릭 한 번으로 시나리오를 넘나들며 분석할 수 있습니다.")

# ---------------------------------------------------------
# 1. 사이드바: 데이터 업로드 및 '저장' 버튼 구역
# ---------------------------------------------------------
st.sidebar.header("📥 1. 새 시나리오 업로드 및 저장")
with st.sidebar.expander("여기를 눌러 데이터 업로드창 열기", expanded=True):
    ds_file = st.file_uploader("주행 데이터 (2_B1.csv)", type=['csv'])
    sac_file = st.file_uploader("시선 이동 (saccades.csv)", type=['csv'])
    blink_file = st.file_uploader("눈 깜빡임 (blinks.csv)", type=['csv'])
    
    new_scenario_name = st.text_input("📝 저장할 시나리오 이름 지정:", placeholder="예: 600m_주간_P01")
    
    if st.button("💾 현재 데이터 저장하기", use_container_width=True):
        if ds_file and sac_file and new_scenario_name:
            # 💡 업로드된 파일을 판다스 데이터프레임으로 변환하여 '메모리'에 통째로 저장
            st.session_state['saved_scenarios'][new_scenario_name] = {
                'ds': pd.read_csv(ds_file),
                'sac': pd.read_csv(sac_file),
                'blink': pd.read_csv(blink_file) if blink_file else None
            }
            st.success(f"🎉 '{new_scenario_name}' 시나리오가 성공적으로 저장되었습니다!")
        else:
            st.error("⚠️ 주행 데이터, 시선 이동 데이터, 그리고 저장할 이름을 모두 입력해주세요.")

st.sidebar.markdown("---")

# ---------------------------------------------------------
# 2. 사이드바: 저장된 시나리오 불러오기 구역
# ---------------------------------------------------------
st.sidebar.header("📁 2. 저장된 시나리오 불러오기")

if not st.session_state['saved_scenarios']:
    st.sidebar.info("아직 저장된 시나리오가 없습니다. 위에서 데이터를 업로드해주세요.")
else:
    # 저장된 시나리오 목록을 라디오 버튼으로 출력
    selected_scenario = st.sidebar.radio(
        "분석할 시나리오를 선택하세요:",
        list(st.session_state['saved_scenarios'].keys())
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ 3. 분석 레이어 및 옵션")
    show_speed = st.sidebar.checkbox("📈 차량 속도 표시", value=True)
    show_offset = st.sidebar.checkbox("↔️ 조향 편차 (차로 이탈 정도)", value=True)
    show_saccade = st.sidebar.checkbox("👁️ 시선 이동 각도 (채워진 그래프)", value=True)
    show_blink = st.sidebar.checkbox("😌 눈 깜빡임 (하단 마커)", value=True)
    show_lane_change = st.sidebar.checkbox("🚧 차선 변경 구간 하이라이트", value=True)
    time_offset = st.sidebar.slider("아이트래커 시간 오차 보정 (초)", -10.0, 10.0, 0.0, 0.1)

    # ---------------------------------------------------------
    # 3. 메인 화면: 선택된 시나리오 그래프 그리기
    # ---------------------------------------------------------
    # 메모리에서 선택된 데이터프레임 복사해오기
    data = st.session_state['saved_scenarios'][selected_scenario]
    df_ds = data['ds'].copy()
    df_sac = data['sac'].copy()
    df_blink = data['blink'].copy() if data['blink'] is not None else None
    
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

    if show_speed and ds_speed_col in df_ds.columns:
        fig.add_trace(go.Scatter(
            x=df_ds['Time_s'], y=df_ds[ds_speed_col], 
            mode='lines', name='차량 속도 (km/h)', line=dict(color='royalblue', width=2)
        ), secondary_y=False)

    if show_offset and ds_offset_col in df_ds.columns:
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
        blink_time_col = 'start timestamp [ns]' 
        if blink_time_col in df_blink.columns:
            df_blink['Time_s'] = ((df_blink[blink_time_col] - sac_start_time) / 1e9) + time_offset
            fig.add_trace(go.Scatter(
                x=df_blink['Time_s'], y=[-5] * len(df_blink), 
                mode='markers', name='눈 깜빡임 발생',
                marker=dict(symbol='line-ns', color='darkorange', size=15, line=dict(width=2)),
                hoverinfo='x+name'
            ), secondary_y=False)

    lane_changes = df_ds[df_ds[ds_lane_col].diff().abs() > 0] if ds_lane_col in df_ds.columns else []
    if show_lane_change and len(lane_changes) > 0:
        for lc_time in lane_changes['Time_s']:
            fig.add_vrect(
                x0=lc_time - 3.0, x1=lc_time + 3.0, 
                fillcolor="gold", opacity=0.15, layer="below", line_width=0,
                annotation_text="차선 변경", annotation_position="top left"
            )

    fig.update_layout(
        title=f"[{selected_scenario}] 실시간 다중 레이어 분석 차트",
        xaxis_title="주행 시간 (초)",
        height=650,
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255, 255, 255, 0.7)')
    )
    
    fig.update_yaxes(title_text="속도 (km/h) / 시야각 (deg)", secondary_y=False)
    fig.update_yaxes(title_text="조향 편차 (m)", secondary_y=True, showgrid=False)

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader(f"💡 '{selected_scenario}' 요약 통계")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 주행 시간", f"{round(df_ds['Time_s'].max(), 1)} 초")
    col2.metric("최대 시야각 발생", f"{round(df_sac[sac_amp_col].max(), 1)} deg")
    max_offset = round(df_ds[ds_offset_col].abs().max(), 2) if ds_offset_col in df_ds.columns else 0
    col3.metric("최대 조향 이탈", f"{max_offset} m")
    col4.metric("차선 변경 횟수", f"{len(lane_changes)} 회")
