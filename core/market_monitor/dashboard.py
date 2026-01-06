"""
실시간 모니터링 대시보드

시장 현황을 시각화하고 실시간으로 모니터링할 수 있는 대시보드 시스템
"""

import numpy as np
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
import time

from ..utils.logging import get_logger
from .market_monitor import MarketMonitor, MarketSnapshot, MarketStatus
from .anomaly_detector import AnomalyDetector, AnomalyAlert, AnomalySeverity
from .alert_system import AlertSystem

# 시각화 라이브러리 (선택적)
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import seaborn as sns
    from matplotlib.animation import FuncAnimation
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.io as pio
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

logger = get_logger(__name__)

class DashboardTheme(Enum):
    """대시보드 테마"""
    LIGHT = "light"
    DARK = "dark"
    PROFESSIONAL = "professional"

class ChartType(Enum):
    """차트 유형"""
    LINE = "line"
    CANDLESTICK = "candlestick"
    BAR = "bar"
    HEATMAP = "heatmap"
    SCATTER = "scatter"
    PIE = "pie"

@dataclass
class DashboardConfig:
    """대시보드 설정"""
    # 업데이트 설정
    update_interval: int = 30           # 업데이트 간격 (초)
    auto_refresh: bool = True           # 자동 새로고침
    
    # 데이터 설정
    max_data_points: int = 1000         # 최대 데이터 포인트 수
    historical_hours: int = 24          # 표시할 과거 데이터 시간
    
    # 시각화 설정
    theme: DashboardTheme = DashboardTheme.PROFESSIONAL
    chart_height: int = 400             # 차트 높이
    chart_width: int = 800              # 차트 너비
    
    # 알림 설정
    show_alerts: bool = True            # 알림 표시
    max_alerts_display: int = 20        # 최대 알림 표시 개수
    
    # 성능 설정
    enable_real_time_charts: bool = True
    chart_animation: bool = False       # 차트 애니메이션 (성능 영향)
    
    # 레이아웃 설정
    columns: int = 3                    # 대시보드 컬럼 수
    show_grid: bool = True              # 그리드 표시
    
    # 출력 설정
    output_dir: str = "dashboard_output"
    save_charts: bool = True            # 차트 저장 여부
    chart_format: str = "html"          # 차트 포맷 (html, png, svg)

@dataclass
class DashboardMetrics:
    """대시보드 지표"""
    timestamp: datetime
    
    # 시장 지표
    market_status: MarketStatus
    kospi_index: float
    kosdaq_index: float
    kospi_change: float
    kosdaq_change: float
    
    # 거래 지표
    total_trading_value: float
    advance_decline_ratio: float
    volatility_index: float
    
    # 종목 통계
    total_stocks: int
    rising_stocks: int
    declining_stocks: int
    high_volume_stocks: int
    
    # 알림 지표
    total_alerts: int
    critical_alerts: int
    high_alerts: int
    
    # 시스템 지표
    monitoring_uptime: float
    data_processing_time: float
    alert_response_time: float

class ChartGenerator:
    """차트 생성기"""
    
    def __init__(self, config: DashboardConfig):
        self._config = config
        self._logger = logger
        
        # 테마 설정
        self._setup_theme()
    
    def _setup_theme(self):
        """테마 설정"""
        if MATPLOTLIB_AVAILABLE:
            if self._config.theme == DashboardTheme.DARK:
                plt.style.use('dark_background')
            elif self._config.theme == DashboardTheme.PROFESSIONAL:
                sns.set_style("whitegrid")
        
        if PLOTLY_AVAILABLE:
            if self._config.theme == DashboardTheme.DARK:
                pio.templates.default = "plotly_dark"
            elif self._config.theme == DashboardTheme.PROFESSIONAL:
                pio.templates.default = "plotly_white"
    
    def create_market_overview_chart(self, snapshots: List[MarketSnapshot]) -> Optional[str]:
        """시장 개요 차트 생성"""
        try:
            if not snapshots or not PLOTLY_AVAILABLE:
                return None
            
            # 데이터 준비
            timestamps = [s.timestamp for s in snapshots]
            kospi_values = [s.kospi_index for s in snapshots]
            kosdaq_values = [s.kosdaq_index for s in snapshots]
            
            # 서브플롯 생성
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('KOSPI 지수', 'KOSDAQ 지수', '상승/하락 비율', '거래대금'),
                specs=[[{"secondary_y": False}, {"secondary_y": False}],
                       [{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            # KOSPI 지수
            fig.add_trace(
                go.Scatter(x=timestamps, y=kospi_values, name='KOSPI', line=dict(color='blue')),
                row=1, col=1
            )
            
            # KOSDAQ 지수
            fig.add_trace(
                go.Scatter(x=timestamps, y=kosdaq_values, name='KOSDAQ', line=dict(color='red')),
                row=1, col=2
            )
            
            # 상승/하락 비율
            ad_ratios = [s.advance_decline_ratio for s in snapshots]
            fig.add_trace(
                go.Scatter(x=timestamps, y=ad_ratios, name='상승/하락 비율', line=dict(color='green')),
                row=2, col=1
            )
            
            # 거래대금
            trading_values = [s.total_trading_value / 1e12 for s in snapshots]  # 조원 단위
            fig.add_trace(
                go.Scatter(x=timestamps, y=trading_values, name='거래대금(조원)', line=dict(color='orange')),
                row=2, col=2
            )
            
            # 레이아웃 설정
            fig.update_layout(
                title="시장 개요",
                height=self._config.chart_height * 2,
                showlegend=True
            )
            
            # 차트 저장
            return self._save_chart(fig, "market_overview")
            
        except Exception as e:
            self._logger.error(f"시장 개요 차트 생성 실패: {e}", exc_info=True)
            return None
    
    def create_volatility_heatmap(self, current_snapshot: MarketSnapshot) -> Optional[str]:
        """변동성 히트맵 생성"""
        try:
            if not current_snapshot.stock_snapshots or not PLOTLY_AVAILABLE:
                return None
            
            # 상위 변동성 종목 선별 (최대 25개)
            stocks = sorted(
                current_snapshot.stock_snapshots,
                key=lambda x: abs(x.price_change_rate),
                reverse=True
            )[:25]
            
            # 5x5 그리드로 배치
            grid_size = 5
            z_values = []
            text_values = []
            
            for i in range(grid_size):
                z_row = []
                text_row = []
                for j in range(grid_size):
                    idx = i * grid_size + j
                    if idx < len(stocks):
                        stock = stocks[idx]
                        z_row.append(stock.price_change_rate * 100)
                        text_row.append(f"{stock.stock_name}<br>{stock.price_change_rate:.1%}")
                    else:
                        z_row.append(0)
                        text_row.append("")
                
                z_values.append(z_row)
                text_values.append(text_row)
            
            # 히트맵 생성
            fig = go.Figure(data=go.Heatmap(
                z=z_values,
                text=text_values,
                texttemplate="%{text}",
                textfont={"size": 10},
                colorscale='RdYlGn',
                zmid=0,
                hoverongaps=False
            ))
            
            fig.update_layout(
                title="종목별 변동성 히트맵",
                height=self._config.chart_height,
                xaxis={'showticklabels': False},
                yaxis={'showticklabels': False}
            )
            
            return self._save_chart(fig, "volatility_heatmap")
            
        except Exception as e:
            self._logger.error(f"변동성 히트맵 생성 실패: {e}", exc_info=True)
            return None
    
    def create_volume_analysis_chart(self, current_snapshot: MarketSnapshot) -> Optional[str]:
        """거래량 분석 차트 생성"""
        try:
            if not current_snapshot.stock_snapshots or not PLOTLY_AVAILABLE:
                return None
            
            # 고거래량 종목 선별
            high_volume_stocks = sorted(
                [s for s in current_snapshot.stock_snapshots if s.volume_ratio > 1.5],
                key=lambda x: x.volume_ratio,
                reverse=True
            )[:20]
            
            if not high_volume_stocks:
                return None
            
            stock_names = [s.stock_name[:8] for s in high_volume_stocks]  # 이름 길이 제한
            volume_ratios = [s.volume_ratio for s in high_volume_stocks]
            price_changes = [s.price_change_rate * 100 for s in high_volume_stocks]
            
            # 서브플롯 생성
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=('거래량 급증 종목', '거래량 vs 가격 변동'),
                specs=[[{"secondary_y": False}, {"secondary_y": True}]]
            )
            
            # 거래량 비율 막대 차트
            fig.add_trace(
                go.Bar(x=stock_names, y=volume_ratios, name='거래량 비율', marker_color='skyblue'),
                row=1, col=1
            )
            
            # 거래량 vs 가격 변동 산점도
            fig.add_trace(
                go.Scatter(
                    x=volume_ratios,
                    y=price_changes,
                    mode='markers',
                    text=stock_names,
                    name='종목별 위치',
                    marker=dict(size=8, color=price_changes, colorscale='RdYlGn', showscale=True)
                ),
                row=1, col=2
            )
            
            # 레이아웃 설정
            fig.update_layout(
                title="거래량 분석",
                height=self._config.chart_height,
                showlegend=True
            )
            
            fig.update_xaxes(tickangle=45, row=1, col=1)
            fig.update_xaxes(title_text="거래량 비율", row=1, col=2)
            fig.update_yaxes(title_text="거래량 비율", row=1, col=1)
            fig.update_yaxes(title_text="가격 변동률(%)", row=1, col=2)
            
            return self._save_chart(fig, "volume_analysis")
            
        except Exception as e:
            self._logger.error(f"거래량 분석 차트 생성 실패: {e}", exc_info=True)
            return None
    
    def create_alert_timeline(self, alerts: List[AnomalyAlert]) -> Optional[str]:
        """알림 타임라인 생성"""
        try:
            if not alerts or not PLOTLY_AVAILABLE:
                return None
            
            # 최근 24시간 알림만 표시
            recent_alerts = [
                alert for alert in alerts
                if alert.timestamp > datetime.now() - timedelta(hours=24)
            ]
            
            if not recent_alerts:
                return None
            
            # 심각도별 색상 매핑
            color_map = {
                AnomalySeverity.CRITICAL: 'red',
                AnomalySeverity.HIGH: 'orange', 
                AnomalySeverity.MEDIUM: 'yellow',
                AnomalySeverity.LOW: 'lightblue'
            }
            
            # 데이터 준비
            timestamps = [alert.timestamp for alert in recent_alerts]
            severities = [alert.severity.value for alert in recent_alerts]
            titles = [alert.title for alert in recent_alerts]
            colors = [color_map.get(alert.severity, 'gray') for alert in recent_alerts]
            
            # 타임라인 차트 생성
            fig = go.Figure()
            
            # 각 심각도별로 별도 트레이스 생성
            for severity in AnomalySeverity:
                severity_alerts = [a for a in recent_alerts if a.severity == severity]
                if severity_alerts:
                    fig.add_trace(go.Scatter(
                        x=[a.timestamp for a in severity_alerts],
                        y=[severity.value] * len(severity_alerts),
                        mode='markers',
                        marker=dict(
                            size=12,
                            color=color_map.get(severity, 'gray'),
                            symbol='circle'
                        ),
                        text=[a.title for a in severity_alerts],
                        name=severity.value.upper(),
                        hovertemplate='<b>%{text}</b><br>시간: %{x}<br>심각도: %{y}<extra></extra>'
                    ))
            
            # 레이아웃 설정
            fig.update_layout(
                title="알림 타임라인 (최근 24시간)",
                xaxis_title="시간",
                yaxis_title="심각도",
                height=self._config.chart_height // 2,
                hovermode='closest'
            )
            
            return self._save_chart(fig, "alert_timeline")
            
        except Exception as e:
            self._logger.error(f"알림 타임라인 생성 실패: {e}", exc_info=True)
            return None
    
    def create_market_status_gauge(self, current_snapshot: MarketSnapshot) -> Optional[str]:
        """시장 상태 게이지 생성"""
        try:
            if not PLOTLY_AVAILABLE:
                return None
            
            # 시장 상태를 숫자로 변환
            status_values = {
                MarketStatus.ABNORMAL: 0,
                MarketStatus.DECLINING: 1,
                MarketStatus.VOLATILE: 2,
                MarketStatus.SIDEWAYS: 3,
                MarketStatus.NORMAL: 4,
                MarketStatus.RISING: 5
            }
            
            current_value = status_values.get(current_snapshot.market_status, 3)
            
            # 게이지 차트 생성
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=current_value,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "시장 상태"},
                delta={'reference': 3},  # NORMAL 기준
                gauge={
                    'axis': {'range': [None, 5]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 1], 'color': "red"},      # ABNORMAL
                        {'range': [1, 2], 'color': "orange"},   # DECLINING
                        {'range': [2, 3], 'color': "yellow"},   # VOLATILE
                        {'range': [3, 4], 'color': "lightgreen"}, # NORMAL
                        {'range': [4, 5], 'color': "green"}     # RISING
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': current_value
                    }
                }
            ))
            
            fig.update_layout(
                title="실시간 시장 상태",
                height=self._config.chart_height // 2,
                font={'size': 12}
            )
            
            return self._save_chart(fig, "market_status_gauge")
            
        except Exception as e:
            self._logger.error(f"시장 상태 게이지 생성 실패: {e}", exc_info=True)
            return None
    
    def _save_chart(self, fig, filename: str) -> Optional[str]:
        """차트 저장"""
        try:
            if not self._config.save_charts:
                return None
            
            # 출력 디렉토리 생성
            os.makedirs(self._config.output_dir, exist_ok=True)
            
            # 타임스탬프 추가
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            full_filename = f"{filename}_{timestamp}"
            
            if self._config.chart_format == "html":
                filepath = os.path.join(self._config.output_dir, f"{full_filename}.html")
                fig.write_html(filepath)
            elif self._config.chart_format == "png":
                filepath = os.path.join(self._config.output_dir, f"{full_filename}.png")
                fig.write_image(filepath)
            elif self._config.chart_format == "svg":
                filepath = os.path.join(self._config.output_dir, f"{full_filename}.svg")
                fig.write_image(filepath)
            else:
                filepath = os.path.join(self._config.output_dir, f"{full_filename}.html")
                fig.write_html(filepath)
            
            self._logger.info(f"차트 저장 완료: {filepath}")
            return filepath
            
        except Exception as e:
            self._logger.error(f"차트 저장 실패: {e}", exc_info=True)
            return None

class MetricsCollector:
    """지표 수집기"""
    
    def __init__(self):
        self._logger = logger
        self._metrics_history = []
        self._start_time = datetime.now()
    
    def collect_metrics(self, market_monitor: MarketMonitor, 
                       anomaly_detector: AnomalyDetector,
                       alert_system: AlertSystem) -> DashboardMetrics:
        """지표 수집"""
        try:
            current_snapshot = market_monitor.get_current_snapshot()
            if not current_snapshot:
                return self._create_default_metrics()
            
            # 최근 알림 조회
            recent_alerts = anomaly_detector.get_recent_alerts(24)
            
            # 알림 시스템 통계
            alert_stats = alert_system.get_alert_statistics(1)
            
            # 변동성 지수 계산
            volatility_index = self._calculate_volatility_index(current_snapshot)
            
            # 시스템 지표 계산
            uptime = (datetime.now() - self._start_time).total_seconds() / 3600  # 시간 단위
            
            metrics = DashboardMetrics(
                timestamp=datetime.now(),
                market_status=current_snapshot.market_status,
                kospi_index=current_snapshot.kospi_index,
                kosdaq_index=current_snapshot.kosdaq_index,
                kospi_change=current_snapshot.kospi_change,
                kosdaq_change=current_snapshot.kosdaq_change,
                total_trading_value=current_snapshot.total_trading_value,
                advance_decline_ratio=current_snapshot.advance_decline_ratio,
                volatility_index=volatility_index,
                total_stocks=current_snapshot.total_stocks,
                rising_stocks=current_snapshot.rising_stocks,
                declining_stocks=current_snapshot.declining_stocks,
                high_volume_stocks=len(current_snapshot.high_volume_stocks),
                total_alerts=len(recent_alerts),
                critical_alerts=len([a for a in recent_alerts if a.severity == AnomalySeverity.CRITICAL]),
                high_alerts=len([a for a in recent_alerts if a.severity == AnomalySeverity.HIGH]),
                monitoring_uptime=uptime,
                data_processing_time=0.5,  # Mock 값
                alert_response_time=alert_stats.get('overall_success_rate', 0) * 100
            )
            
            # 히스토리에 추가
            self._metrics_history.append(metrics)
            
            # 오래된 데이터 정리 (최대 1000개)
            if len(self._metrics_history) > 1000:
                self._metrics_history = self._metrics_history[-1000:]
            
            return metrics
            
        except Exception as e:
            self._logger.error(f"지표 수집 실패: {e}", exc_info=True)
            return self._create_default_metrics()
    
    def _calculate_volatility_index(self, snapshot: MarketSnapshot) -> float:
        """변동성 지수 계산"""
        try:
            if not snapshot.stock_snapshots:
                return 0.0
            
            # 가격 변동률의 표준편차 계산
            price_changes = [abs(s.price_change_rate) for s in snapshot.stock_snapshots]
            volatility = np.std(price_changes) * 100  # 백분율
            
            return volatility
            
        except:
            return 0.0
    
    def _create_default_metrics(self) -> DashboardMetrics:
        """기본 지표 생성"""
        return DashboardMetrics(
            timestamp=datetime.now(),
            market_status=MarketStatus.NORMAL,
            kospi_index=0,
            kosdaq_index=0,
            kospi_change=0,
            kosdaq_change=0,
            total_trading_value=0,
            advance_decline_ratio=1.0,
            volatility_index=0,
            total_stocks=0,
            rising_stocks=0,
            declining_stocks=0,
            high_volume_stocks=0,
            total_alerts=0,
            critical_alerts=0,
            high_alerts=0,
            monitoring_uptime=0,
            data_processing_time=0,
            alert_response_time=0
        )
    
    def get_metrics_history(self, hours: int = 24) -> List[DashboardMetrics]:
        """지표 히스토리 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [m for m in self._metrics_history if m.timestamp > cutoff_time]

class MonitoringDashboard:
    """실시간 모니터링 대시보드"""
    
    def __init__(self, config: DashboardConfig = None, data_dir: str = "data/dashboard"):
        """
        초기화
        
        Args:
            config: 대시보드 설정
            data_dir: 대시보드 데이터 저장 디렉토리
        """
        self._logger = logger
        self._config = config or DashboardConfig()
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self._config.output_dir, exist_ok=True)
        
        # 컴포넌트들
        self._market_monitor = None
        self._anomaly_detector = None
        self._alert_system = None
        
        # 대시보드 컴포넌트
        self._chart_generator = ChartGenerator(self._config)
        self._metrics_collector = MetricsCollector()
        
        # 업데이트 상태
        self._is_running = False
        self._update_thread = None
        self._stop_event = threading.Event()
        
        # 현재 상태
        self._current_metrics = None
        self._chart_paths = {}
        
        self._logger.info("모니터링 대시보드 초기화 완료")
    
    def set_components(self, market_monitor: MarketMonitor, 
                      anomaly_detector: AnomalyDetector,
                      alert_system: AlertSystem):
        """컴포넌트 설정"""
        self._market_monitor = market_monitor
        self._anomaly_detector = anomaly_detector
        self._alert_system = alert_system
        
        self._logger.info("대시보드 컴포넌트 설정 완료")
    
    def start(self):
        """대시보드 시작"""
        if self._is_running:
            self._logger.warning("대시보드가 이미 실행 중입니다")
            return
        
        if not all([self._market_monitor, self._anomaly_detector, self._alert_system]):
            self._logger.error("필수 컴포넌트가 설정되지 않았습니다")
            return
        
        self._is_running = True
        self._stop_event.clear()
        
        if self._config.auto_refresh:
            self._update_thread = threading.Thread(target=self._update_loop)
            self._update_thread.start()
        
        # 초기 업데이트
        self.update_dashboard()
        
        self._logger.info("모니터링 대시보드 시작")
    
    def stop(self):
        """대시보드 중지"""
        if not self._is_running:
            return
        
        self._is_running = False
        self._stop_event.set()
        
        if self._update_thread:
            self._update_thread.join()
        
        self._logger.info("모니터링 대시보드 중지")
    
    def update_dashboard(self):
        """대시보드 업데이트"""
        try:
            # 지표 수집
            self._current_metrics = self._metrics_collector.collect_metrics(
                self._market_monitor, self._anomaly_detector, self._alert_system
            )
            
            # 차트 생성
            self._update_charts()
            
            # HTML 대시보드 생성
            self._generate_html_dashboard()
            
            # 메트릭 저장
            self._save_metrics()
            
            self._logger.debug("대시보드 업데이트 완료")
            
        except Exception as e:
            self._logger.error(f"대시보드 업데이트 실패: {e}", exc_info=True)
    
    def _update_loop(self):
        """업데이트 루프"""
        while self._is_running and not self._stop_event.is_set():
            try:
                self.update_dashboard()
                self._stop_event.wait(self._config.update_interval)
                
            except Exception as e:
                self._logger.error(f"대시보드 업데이트 루프 오류: {e}", exc_info=True)
                time.sleep(60)
    
    def _update_charts(self):
        """차트 업데이트"""
        try:
            # 현재 스냅샷 조회
            current_snapshot = self._market_monitor.get_current_snapshot()
            if not current_snapshot:
                return
            
            # 최근 스냅샷들 조회
            recent_snapshots = self._market_monitor.get_recent_snapshots(self._config.historical_hours)
            
            # 최근 알림들 조회
            recent_alerts = self._anomaly_detector.get_recent_alerts(24)
            
            # 차트 생성
            charts = {}
            
            # 1. 시장 개요
            if recent_snapshots:
                chart_path = self._chart_generator.create_market_overview_chart(recent_snapshots)
                if chart_path:
                    charts['market_overview'] = chart_path
            
            # 2. 변동성 히트맵
            chart_path = self._chart_generator.create_volatility_heatmap(current_snapshot)
            if chart_path:
                charts['volatility_heatmap'] = chart_path
            
            # 3. 거래량 분석
            chart_path = self._chart_generator.create_volume_analysis_chart(current_snapshot)
            if chart_path:
                charts['volume_analysis'] = chart_path
            
            # 4. 알림 타임라인
            if recent_alerts:
                chart_path = self._chart_generator.create_alert_timeline(recent_alerts)
                if chart_path:
                    charts['alert_timeline'] = chart_path
            
            # 5. 시장 상태 게이지
            chart_path = self._chart_generator.create_market_status_gauge(current_snapshot)
            if chart_path:
                charts['market_status_gauge'] = chart_path
            
            self._chart_paths = charts
            
        except Exception as e:
            self._logger.error(f"차트 업데이트 실패: {e}", exc_info=True)
    
    def _generate_html_dashboard(self):
        """HTML 대시보드 생성"""
        try:
            if not self._current_metrics:
                return
            
            # HTML 템플릿
            html_content = self._create_html_template()
            
            # 파일 저장
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dashboard_{timestamp}.html"
            filepath = os.path.join(self._config.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 최신 대시보드로 링크 생성
            latest_path = os.path.join(self._config.output_dir, "dashboard_latest.html")
            with open(latest_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self._logger.info(f"HTML 대시보드 생성: {filepath}")
            
        except Exception as e:
            self._logger.error(f"HTML 대시보드 생성 실패: {e}", exc_info=True)
    
    def _create_html_template(self) -> str:
        """HTML 템플릿 생성"""
        metrics = self._current_metrics
        
        # 상태별 색상
        status_colors = {
            MarketStatus.NORMAL: "green",
            MarketStatus.RISING: "darkgreen",
            MarketStatus.DECLINING: "red",
            MarketStatus.VOLATILE: "orange",
            MarketStatus.SIDEWAYS: "blue",
            MarketStatus.ABNORMAL: "darkred"
        }
        
        status_color = status_colors.get(metrics.market_status, "gray")
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>한투 퀀트 - 실시간 모니터링 대시보드</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .metrics-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .metric-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .metric-value {{
                    font-size: 2em;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                .metric-label {{
                    color: #666;
                    font-size: 0.9em;
                }}
                .status-indicator {{
                    display: inline-block;
                    width: 20px;
                    height: 20px;
                    border-radius: 50%;
                    margin-right: 10px;
                }}
                .charts-section {{
                    margin-top: 30px;
                }}
                .chart-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                }}
                .chart-container {{
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .last-updated {{
                    text-align: center;
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 20px;
                }}
                .positive {{ color: #d32f2f; }}
                .negative {{ color: #1976d2; }}
                .neutral {{ color: #666; }}
            </style>
            <script>
                // 자동 새로고침
                setTimeout(function() {{
                    location.reload();
                }}, {self._config.update_interval * 1000});
            </script>
        </head>
        <body>
            <div class="header">
                <h1>🚀 한투 퀀트 실시간 모니터링 대시보드</h1>
                <p>시장 상황을 실시간으로 모니터링하고 이상 상황을 감지합니다</p>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">시장 상태</div>
                    <div class="metric-value">
                        <span class="status-indicator" style="background-color: {status_color};"></span>
                        {metrics.market_status.value.upper()}
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">KOSPI 지수</div>
                    <div class="metric-value {'positive' if metrics.kospi_change > 0 else 'negative' if metrics.kospi_change < 0 else 'neutral'}">
                        {metrics.kospi_index:,.0f}
                    </div>
                    <div class="metric-label">({metrics.kospi_change:+.2%})</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">KOSDAQ 지수</div>
                    <div class="metric-value {'positive' if metrics.kosdaq_change > 0 else 'negative' if metrics.kosdaq_change < 0 else 'neutral'}">
                        {metrics.kosdaq_index:,.0f}
                    </div>
                    <div class="metric-label">({metrics.kosdaq_change:+.2%})</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">상승/하락 비율</div>
                    <div class="metric-value">{metrics.advance_decline_ratio:.2f}</div>
                    <div class="metric-label">상승 {metrics.rising_stocks} / 하락 {metrics.declining_stocks}</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">거래대금</div>
                    <div class="metric-value">{metrics.total_trading_value/1e12:.1f}조원</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">변동성 지수</div>
                    <div class="metric-value">{metrics.volatility_index:.2f}%</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">전체 알림 (24시간)</div>
                    <div class="metric-value">{metrics.total_alerts}</div>
                    <div class="metric-label">긴급: {metrics.critical_alerts}, 높음: {metrics.high_alerts}</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">시스템 가동시간</div>
                    <div class="metric-value">{metrics.monitoring_uptime:.1f}시간</div>
                </div>
            </div>
            
            <div class="charts-section">
                <h2>📊 실시간 차트</h2>
                <div class="chart-grid">
        """
        
        # 차트 섹션 추가
        for chart_name, chart_path in self._chart_paths.items():
            if chart_path and os.path.exists(chart_path):
                chart_title = {
                    'market_overview': '시장 개요',
                    'volatility_heatmap': '변동성 히트맵',
                    'volume_analysis': '거래량 분석',
                    'alert_timeline': '알림 타임라인',
                    'market_status_gauge': '시장 상태'
                }.get(chart_name, chart_name)
                
                # HTML 파일인 경우 iframe으로 포함
                if chart_path.endswith('.html'):
                    html += f"""
                    <div class="chart-container">
                        <h3>{chart_title}</h3>
                        <iframe src="{os.path.basename(chart_path)}" width="100%" height="400" frameborder="0"></iframe>
                    </div>
                    """
                else:
                    # 이미지 파일인 경우 img 태그 사용
                    html += f"""
                    <div class="chart-container">
                        <h3>{chart_title}</h3>
                        <img src="{os.path.basename(chart_path)}" style="width: 100%; height: auto;" alt="{chart_title}">
                    </div>
                    """
        
        # HTML 마무리
        html += f"""
                </div>
            </div>
            
            <div class="last-updated">
                마지막 업데이트: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                <br>
                자동 새로고침: {self._config.update_interval}초 간격
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _save_metrics(self):
        """지표 저장"""
        try:
            if not self._current_metrics:
                return
            
            # 일별 파일로 저장
            date_str = self._current_metrics.timestamp.strftime('%Y%m%d')
            filename = f"metrics_{date_str}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            # 기존 데이터 로드
            metrics_data = []
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    metrics_data = json.load(f)
            
            # 새 지표 추가
            metric_dict = asdict(self._current_metrics)
            metric_dict['timestamp'] = self._current_metrics.timestamp.isoformat()
            metric_dict['market_status'] = self._current_metrics.market_status.value
            
            metrics_data.append(metric_dict)
            
            # 파일 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"지표 저장 실패: {e}", exc_info=True)
    
    def get_dashboard_status(self) -> Dict[str, Any]:
        """대시보드 상태 조회"""
        return {
            'is_running': self._is_running,
            'auto_refresh': self._config.auto_refresh,
            'update_interval': self._config.update_interval,
            'last_update': self._current_metrics.timestamp.isoformat() if self._current_metrics else None,
            'available_charts': list(self._chart_paths.keys()),
            'components_connected': all([self._market_monitor, self._anomaly_detector, self._alert_system]),
            'config': asdict(self._config)
        }
    
    def export_dashboard_data(self, days: int = 7) -> str:
        """대시보드 데이터 내보내기"""
        try:
            # 데이터 수집
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'export_period_days': days,
                'dashboard_config': asdict(self._config),
                'metrics_history': []
            }
            
            # 최근 지표 데이터 수집
            metrics_history = self._metrics_collector.get_metrics_history(days * 24)
            for metrics in metrics_history:
                metric_dict = asdict(metrics)
                metric_dict['timestamp'] = metrics.timestamp.isoformat()
                metric_dict['market_status'] = metrics.market_status.value
                export_data['metrics_history'].append(metric_dict)
            
            # 파일 저장
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dashboard_export_{timestamp}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            self._logger.info(f"대시보드 데이터 내보내기 완료: {filepath}")
            return filepath
            
        except Exception as e:
            self._logger.error(f"대시보드 데이터 내보내기 실패: {e}", exc_info=True)
            return ""

# 전역 인스턴스
_monitoring_dashboard = None

def get_monitoring_dashboard() -> MonitoringDashboard:
    """모니터링 대시보드 싱글톤 인스턴스 반환"""
    global _monitoring_dashboard
    if _monitoring_dashboard is None:
        _monitoring_dashboard = MonitoringDashboard()
    return _monitoring_dashboard 