"""
백테스트 결과 시각화 모듈

자산 곡선, 낙폭, 거래 분포 등을 차트로 시각화합니다.
"""

import os
from typing import Optional, List, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

from .result import BacktestResult

# matplotlib 백엔드 설정 (GUI 없는 환경용)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import matplotlib.font_manager as fm


class BacktestVisualizer:
    """백테스트 결과 시각화"""

    # 한글 폰트 설정
    FONT_PATHS = [
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/nanum/NanumGothic.ttf',
        '/System/Library/Fonts/AppleGothic.ttf',
        'C:/Windows/Fonts/malgun.ttf'
    ]

    def __init__(self, result: BacktestResult, figsize: Tuple[int, int] = (14, 10)):
        """
        Args:
            result: 백테스트 결과
            figsize: 그림 크기
        """
        self.result = result
        self.figsize = figsize
        self._setup_font()
        self._setup_style()

    def _setup_font(self):
        """한글 폰트 설정"""
        for font_path in self.FONT_PATHS:
            if os.path.exists(font_path):
                font_prop = fm.FontProperties(fname=font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
                break
        plt.rcParams['axes.unicode_minus'] = False

    def _setup_style(self):
        """차트 스타일 설정"""
        plt.style.use('seaborn-v0_8-whitegrid')
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'
        plt.rcParams['axes.edgecolor'] = '#333333'
        plt.rcParams['axes.labelcolor'] = '#333333'
        plt.rcParams['xtick.color'] = '#333333'
        plt.rcParams['ytick.color'] = '#333333'

    def plot_equity_curve(
        self,
        benchmark: Optional[pd.Series] = None,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> plt.Figure:
        """
        자산 곡선 차트

        Args:
            benchmark: 벤치마크 수익률 시리즈 (선택)
            save_path: 저장 경로 (선택)
            show: 화면 표시 여부
        """
        fig, axes = plt.subplots(2, 1, figsize=self.figsize, height_ratios=[3, 1])

        equity_curve = self.result.get_equity_curve()
        drawdown_curve = self.result.get_drawdown_curve()

        if len(equity_curve) == 0:
            return fig

        # 상단: 자산 곡선
        ax1 = axes[0]
        ax1.plot(equity_curve.index, equity_curve.values / 1e6,
                 label='포트폴리오', color='#2196F3', linewidth=2)

        if benchmark is not None:
            ax1.plot(benchmark.index, benchmark.values / 1e6,
                    label='벤치마크', color='#9E9E9E', linewidth=1.5, linestyle='--')

        ax1.axhline(y=self.result.initial_capital / 1e6, color='#333333',
                   linestyle=':', alpha=0.5, label='초기 자본')

        ax1.set_ylabel('자산 (백만원)')
        ax1.set_title(f'{self.result.strategy_name} - 자산 곡선\n'
                     f'총 수익률: {self.result.total_return:.2f}% | '
                     f'샤프비율: {self.result.sharpe_ratio:.2f} | '
                     f'MDD: {self.result.max_drawdown:.2f}%',
                     fontsize=12, fontweight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        # 하단: 낙폭
        ax2 = axes[1]
        ax2.fill_between(drawdown_curve.index, 0, drawdown_curve.values,
                        color='#F44336', alpha=0.4)
        ax2.plot(drawdown_curve.index, drawdown_curve.values, color='#D32F2F', linewidth=1)
        ax2.axhline(y=self.result.max_drawdown, color='#B71C1C', linestyle='--',
                   label=f'최대 낙폭: {self.result.max_drawdown:.2f}%')
        ax2.set_ylabel('낙폭 (%)')
        ax2.set_xlabel('날짜')
        ax2.legend(loc='lower left')
        ax2.grid(True, alpha=0.3)

        # X축 날짜 포맷
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()

        return fig

    def plot_returns_distribution(
        self,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> plt.Figure:
        """수익률 분포 차트"""
        fig, axes = plt.subplots(2, 2, figsize=self.figsize)

        daily_returns = self.result.get_daily_returns()
        trades_df = self.result.get_trades_df()

        # 1. 일간 수익률 히스토그램
        ax1 = axes[0, 0]
        ax1.hist(daily_returns, bins=50, color='#2196F3', alpha=0.7, edgecolor='white')
        ax1.axvline(x=daily_returns.mean(), color='#F44336', linestyle='--',
                   label=f'평균: {daily_returns.mean():.2f}%')
        ax1.axvline(x=0, color='#333333', linestyle='-', alpha=0.5)
        ax1.set_xlabel('일간 수익률 (%)')
        ax1.set_ylabel('빈도')
        ax1.set_title('일간 수익률 분포')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. 월별 수익률
        ax2 = axes[0, 1]
        if self.result.monthly_returns:
            months = list(self.result.monthly_returns.keys())
            returns = list(self.result.monthly_returns.values())
            colors = ['#4CAF50' if r >= 0 else '#F44336' for r in returns]
            ax2.bar(range(len(months)), returns, color=colors, alpha=0.7)
            ax2.axhline(y=0, color='#333333', linestyle='-', alpha=0.5)
            ax2.set_xlabel('월')
            ax2.set_ylabel('수익률 (%)')
            ax2.set_title('월별 수익률')

            # X축 레이블 간소화
            if len(months) > 12:
                step = len(months) // 12
                ax2.set_xticks(range(0, len(months), step))
                ax2.set_xticklabels([months[i][:7] for i in range(0, len(months), step)], rotation=45)
            else:
                ax2.set_xticks(range(len(months)))
                ax2.set_xticklabels([m[:7] for m in months], rotation=45)
        ax2.grid(True, alpha=0.3)

        # 3. 거래 손익 분포
        ax3 = axes[1, 0]
        if not trades_df.empty and 'net_pnl_pct' in trades_df.columns:
            pnl_pct = trades_df['net_pnl_pct'].dropna()
            colors = ['#4CAF50' if p >= 0 else '#F44336' for p in pnl_pct]
            ax3.bar(range(len(pnl_pct)), pnl_pct, color=colors, alpha=0.7)
            ax3.axhline(y=0, color='#333333', linestyle='-', alpha=0.5)
            ax3.set_xlabel('거래 번호')
            ax3.set_ylabel('수익률 (%)')
            ax3.set_title(f'거래별 수익률 (승률: {self.result.win_rate:.1f}%)')
        ax3.grid(True, alpha=0.3)

        # 4. 누적 거래 수익
        ax4 = axes[1, 1]
        if not trades_df.empty and 'net_pnl' in trades_df.columns:
            cumulative_pnl = trades_df['net_pnl'].cumsum() / 1e6
            ax4.plot(cumulative_pnl.values, color='#2196F3', linewidth=2)
            ax4.fill_between(range(len(cumulative_pnl)), 0, cumulative_pnl.values,
                            alpha=0.3, color='#2196F3')
            ax4.axhline(y=0, color='#333333', linestyle='-', alpha=0.5)
            ax4.set_xlabel('거래 번호')
            ax4.set_ylabel('누적 손익 (백만원)')
            ax4.set_title('누적 거래 손익')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()

        return fig

    def plot_metrics_summary(
        self,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> plt.Figure:
        """성과 지표 요약 차트"""
        fig = plt.figure(figsize=(14, 8))
        gs = GridSpec(2, 3, figure=fig)

        # 1. 주요 지표 게이지
        ax1 = fig.add_subplot(gs[0, :2])
        metrics = {
            '총 수익률': (self.result.total_return, -20, 50, '%'),
            '연환산 수익률': (self.result.annual_return, -10, 30, '%'),
            '샤프 비율': (self.result.sharpe_ratio, -1, 3, ''),
            '승률': (self.result.win_rate, 0, 100, '%'),
            '손익비': (self.result.profit_factor, 0, 3, ''),
        }

        y_pos = np.arange(len(metrics))
        values = [v[0] for v in metrics.values()]
        names = list(metrics.keys())

        colors = []
        for name, (val, min_v, max_v, _) in metrics.items():
            mid = (min_v + max_v) / 2
            if val >= mid:
                colors.append('#4CAF50')
            elif val >= min_v:
                colors.append('#FFC107')
            else:
                colors.append('#F44336')

        bars = ax1.barh(y_pos, values, color=colors, alpha=0.7, edgecolor='white')
        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(names)
        ax1.set_xlabel('값')
        ax1.set_title('주요 성과 지표', fontsize=12, fontweight='bold')
        ax1.axvline(x=0, color='#333333', linestyle='-', alpha=0.5)

        # 값 레이블
        for i, (bar, (val, _, _, unit)) in enumerate(zip(bars, metrics.values())):
            ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    f'{val:.2f}{unit}', va='center', fontsize=10)

        ax1.grid(True, alpha=0.3, axis='x')

        # 2. 리스크 지표 파이 차트
        ax2 = fig.add_subplot(gs[0, 2])
        risk_labels = ['MDD', '변동성', 'VaR 95%']
        risk_values = [
            abs(self.result.max_drawdown),
            self.result.volatility,
            abs(self.result.var_95) if self.result.var_95 else 0
        ]

        if sum(risk_values) > 0:
            colors = ['#F44336', '#FF9800', '#FFC107']
            ax2.pie(risk_values, labels=risk_labels, autopct='%1.1f%%',
                   colors=colors, startangle=90)
            ax2.set_title('리스크 구성', fontsize=12, fontweight='bold')

        # 3. 거래 통계 테이블
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.axis('off')

        trade_stats = [
            ['총 거래', f'{self.result.total_trades}회'],
            ['승리/패배', f'{self.result.winning_trades}/{self.result.losing_trades}'],
            ['최대 연승', f'{self.result.consecutive_wins}회'],
            ['최대 연패', f'{self.result.consecutive_losses}회'],
            ['평균 보유', f'{self.result.avg_holding_days:.1f}일'],
        ]

        table = ax3.table(cellText=trade_stats, colLabels=['지표', '값'],
                         loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)
        ax3.set_title('거래 통계', fontsize=12, fontweight='bold', y=0.9)

        # 4. 손익 통계 테이블
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.axis('off')

        pnl_stats = [
            ['평균 이익', f'{self.result.avg_profit:,.0f}원'],
            ['평균 손실', f'{self.result.avg_loss:,.0f}원'],
            ['최대 이익', f'{self.result.largest_win:,.0f}원'],
            ['최대 손실', f'{self.result.largest_loss:,.0f}원'],
            ['총 수수료', f'{self.result.total_commission:,.0f}원'],
        ]

        table = ax4.table(cellText=pnl_stats, colLabels=['지표', '값'],
                         loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)
        ax4.set_title('손익 통계', fontsize=12, fontweight='bold', y=0.9)

        # 5. 고급 지표 테이블
        ax5 = fig.add_subplot(gs[1, 2])
        ax5.axis('off')

        adv_stats = [
            ['소르티노', f'{self.result.sortino_ratio:.2f}'],
            ['칼마', f'{self.result.calmar_ratio:.2f}'],
            ['왜도', f'{self.result.skewness:.2f}'],
            ['첨도', f'{self.result.kurtosis:.2f}'],
            ['CVaR 95%', f'{self.result.cvar_95:.2f}%'],
        ]

        table = ax5.table(cellText=adv_stats, colLabels=['지표', '값'],
                         loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)
        ax5.set_title('고급 지표', fontsize=12, fontweight='bold', y=0.9)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()

        return fig

    def plot_full_report(
        self,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> List[plt.Figure]:
        """전체 보고서 생성"""
        figs = []

        # 1. 자산 곡선
        fig1 = self.plot_equity_curve()
        figs.append(fig1)

        # 2. 수익률 분포
        fig2 = self.plot_returns_distribution()
        figs.append(fig2)

        # 3. 지표 요약
        fig3 = self.plot_metrics_summary()
        figs.append(fig3)

        if save_path:
            # PDF로 저장
            from matplotlib.backends.backend_pdf import PdfPages
            with PdfPages(save_path) as pdf:
                for fig in figs:
                    pdf.savefig(fig, bbox_inches='tight')

        if show:
            plt.show()

        return figs

    def save_html_report(self, save_path: str):
        """HTML 보고서 생성"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>백테스트 결과 - {self.result.strategy_name}</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #2196F3; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .metric-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 8px; color: white; text-align: center; }}
        .metric-card.positive {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .metric-card.negative {{ background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ font-size: 12px; opacity: 0.9; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; font-weight: bold; }}
        tr:hover {{ background: #fafafa; }}
        .footer {{ margin-top: 30px; text-align: center; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 백테스트 결과: {self.result.strategy_name}</h1>
        <p>기간: {self.result.start_date} ~ {self.result.end_date} | 실행 시간: {self.result.execution_time:.2f}초</p>

        <div class="metrics-grid">
            <div class="metric-card {'positive' if self.result.total_return >= 0 else 'negative'}">
                <div class="metric-value">{self.result.total_return:.2f}%</div>
                <div class="metric-label">총 수익률</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self.result.sharpe_ratio:.2f}</div>
                <div class="metric-label">샤프 비율</div>
            </div>
            <div class="metric-card negative">
                <div class="metric-value">{self.result.max_drawdown:.2f}%</div>
                <div class="metric-label">최대 낙폭</div>
            </div>
            <div class="metric-card {'positive' if self.result.win_rate >= 50 else 'negative'}">
                <div class="metric-value">{self.result.win_rate:.1f}%</div>
                <div class="metric-label">승률</div>
            </div>
        </div>

        <h2>💰 자본 변동</h2>
        <table>
            <tr><th>항목</th><th>금액</th></tr>
            <tr><td>초기 자본</td><td>{self.result.initial_capital:,.0f}원</td></tr>
            <tr><td>최종 자본</td><td>{self.result.final_capital:,.0f}원</td></tr>
            <tr><td>순이익</td><td>{self.result.final_capital - self.result.initial_capital:,.0f}원</td></tr>
            <tr><td>총 수수료</td><td>{self.result.total_commission:,.0f}원</td></tr>
        </table>

        <h2>📈 성과 지표</h2>
        <table>
            <tr><th>지표</th><th>값</th><th>설명</th></tr>
            <tr><td>연환산 수익률</td><td>{self.result.annual_return:.2f}%</td><td>1년 기준 환산 수익률</td></tr>
            <tr><td>변동성</td><td>{self.result.volatility:.2f}%</td><td>연간 수익률 표준편차</td></tr>
            <tr><td>소르티노 비율</td><td>{self.result.sortino_ratio:.2f}</td><td>하방 위험 대비 수익률</td></tr>
            <tr><td>칼마 비율</td><td>{self.result.calmar_ratio:.2f}</td><td>MDD 대비 수익률</td></tr>
            <tr><td>VaR (95%)</td><td>{self.result.var_95:.2f}%</td><td>일간 최대 예상 손실</td></tr>
        </table>

        <h2>🔄 거래 통계</h2>
        <table>
            <tr><th>지표</th><th>값</th></tr>
            <tr><td>총 거래</td><td>{self.result.total_trades}회</td></tr>
            <tr><td>승리 거래</td><td>{self.result.winning_trades}회</td></tr>
            <tr><td>패배 거래</td><td>{self.result.losing_trades}회</td></tr>
            <tr><td>손익비</td><td>{self.result.profit_factor:.2f}</td></tr>
            <tr><td>평균 보유 기간</td><td>{self.result.avg_holding_days:.1f}일</td></tr>
            <tr><td>최대 연승</td><td>{self.result.consecutive_wins}회</td></tr>
            <tr><td>최대 연패</td><td>{self.result.consecutive_losses}회</td></tr>
        </table>

        <div class="footer">
            생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Hantu Quant Backtest Engine
        </div>
    </div>
</body>
</html>
"""
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)


def visualize_backtest(
    result: BacktestResult,
    save_dir: str = None,
    show: bool = False
) -> List[plt.Figure]:
    """백테스트 결과 시각화 편의 함수"""
    visualizer = BacktestVisualizer(result)

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        visualizer.plot_equity_curve(save_path=f"{save_dir}/equity_curve.png")
        visualizer.plot_returns_distribution(save_path=f"{save_dir}/returns_dist.png")
        visualizer.plot_metrics_summary(save_path=f"{save_dir}/metrics_summary.png")
        visualizer.save_html_report(f"{save_dir}/report.html")

    return visualizer.plot_full_report(show=show)
