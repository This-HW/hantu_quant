#!/usr/bin/env python3
"""
백테스트 결과 보고서 생성 모듈
텍스트, JSON, HTML 형식으로 보고서 생성
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from core.utils.log_utils import get_logger
from core.backtesting.models import BacktestResult, Trade
from core.backtesting.performance_analyzer import PerformanceAnalyzer

logger = get_logger(__name__)


class BacktestReporter:
    """백테스트 보고서 생성기"""

    def __init__(self, result: BacktestResult, trades: List[Trade]):
        """초기화

        Args:
            result: 백테스트 결과
            trades: 거래 내역 리스트
        """
        self.logger = logger
        self.result = result
        self.trades = trades
        self.analyzer = PerformanceAnalyzer()

    def generate_summary(self) -> Dict:
        """핵심 지표 요약 생성

        Returns:
            Dict: 핵심 지표 요약
        """
        try:
            # 거래 분포 분석
            trade_dist = self.analyzer.analyze_trade_distribution(self.trades)

            summary = {
                'strategy_name': self.result.strategy_name,
                'period': {
                    'start': self.result.start_date,
                    'end': self.result.end_date
                },
                'performance': {
                    'total_return': self.result.total_return,
                    'sharpe_ratio': self.result.sharpe_ratio,
                    'max_drawdown': self.result.max_drawdown,
                    'win_rate': self.result.win_rate
                },
                'trades': {
                    'total': self.result.total_trades,
                    'winning': self.result.winning_trades,
                    'losing': self.result.losing_trades,
                    'avg_holding_days': self.result.avg_holding_days
                },
                'risk_metrics': {
                    'profit_factor': self.result.profit_factor,
                    'avg_win': self.result.avg_win,
                    'avg_loss': self.result.avg_loss,
                    'best_trade': self.result.best_trade,
                    'worst_trade': self.result.worst_trade
                },
                'trade_distribution': trade_dist
            }

            return summary

        except Exception as e:
            self.logger.error(f"요약 생성 중 오류: {e}", exc_info=True)
            return {}

    def generate_text_report(self) -> str:
        """텍스트 보고서 생성

        Returns:
            str: 텍스트 형식 보고서
        """
        try:
            lines = []
            lines.append("=" * 80)
            lines.append("백테스트 결과 보고서".center(80))
            lines.append("=" * 80)
            lines.append("")

            # 기본 정보
            lines.append(f"전략명: {self.result.strategy_name}")
            lines.append(f"기간: {self.result.start_date} ~ {self.result.end_date}")
            lines.append(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")

            # 성과 지표
            lines.append("-" * 80)
            lines.append("[성과 지표]")
            lines.append("-" * 80)
            lines.append(f"총 수익률:        {self.result.total_return:>10.2%}")
            lines.append(f"Sharpe Ratio:     {self.result.sharpe_ratio:>10.2f}")
            lines.append(f"최대 손실폭:      {self.result.max_drawdown:>10.2%}")
            lines.append(f"승률:            {self.result.win_rate:>10.1%}")
            lines.append("")

            # 거래 통계
            lines.append("-" * 80)
            lines.append("[거래 통계]")
            lines.append("-" * 80)
            lines.append(f"총 거래 수:      {self.result.total_trades:>10}건")
            lines.append(f"승리 거래:       {self.result.winning_trades:>10}건")
            lines.append(f"손실 거래:       {self.result.losing_trades:>10}건")
            lines.append(f"평균 보유일:     {self.result.avg_holding_days:>10.1f}일")
            lines.append("")

            # 수익/손실 분석
            lines.append("-" * 80)
            lines.append("[수익/손실 분석]")
            lines.append("-" * 80)
            lines.append(f"평균 수익:       {self.result.avg_return:>10.2%}")
            lines.append(f"평균 이익:       {self.result.avg_win:>10.2%}")
            lines.append(f"평균 손실:       {self.result.avg_loss:>10.2%}")
            lines.append(f"Profit Factor:   {self.result.profit_factor:>10.2f}")
            lines.append(f"최고 거래:       {self.result.best_trade:>10.2%}")
            lines.append(f"최악 거래:       {self.result.worst_trade:>10.2%}")
            lines.append("")

            # 거래 분포
            trade_dist = self.analyzer.analyze_trade_distribution(self.trades)
            if trade_dist['total_trades'] > 0:
                lines.append("-" * 80)
                lines.append("[거래 분포 분석]")
                lines.append("-" * 80)
                lines.append(f"최대 연속 승:    {trade_dist['max_consecutive_wins']:>10}회")
                lines.append(f"최대 연속 패:    {trade_dist['max_consecutive_losses']:>10}회")
                lines.append("")

            # 거래 내역 테이블
            if self.trades:
                lines.append("-" * 80)
                lines.append("[거래 내역]")
                lines.append("-" * 80)
                lines.append(self._format_trade_table(self.trades[:20]))  # 최근 20건
                if len(self.trades) > 20:
                    lines.append(f"\n... 외 {len(self.trades) - 20}건 생략 ...")
                lines.append("")

            lines.append("=" * 80)

            return "\n".join(lines)

        except Exception as e:
            self.logger.error(f"텍스트 보고서 생성 중 오류: {e}", exc_info=True)
            return "보고서 생성 실패"

    def generate_json_report(self) -> str:
        """JSON 보고서 생성

        Returns:
            str: JSON 형식 보고서
        """
        try:
            summary = self.generate_summary()

            # 거래 내역 추가
            trades_data = []
            for trade in self.trades:
                trades_data.append({
                    'stock_code': trade.stock_code,
                    'stock_name': trade.stock_name,
                    'entry_date': trade.entry_date,
                    'entry_price': trade.entry_price,
                    'exit_date': trade.exit_date,
                    'exit_price': trade.exit_price,
                    'quantity': trade.quantity,
                    'return_pct': trade.return_pct,
                    'holding_days': trade.holding_days,
                    'exit_reason': trade.exit_reason
                })

            report = {
                'summary': summary,
                'trades': trades_data,
                'generated_at': datetime.now().isoformat()
            }

            return json.dumps(report, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"JSON 보고서 생성 중 오류: {e}", exc_info=True)
            return json.dumps({'error': str(e)})

    def save_report(self, filepath: str, format: str = 'text') -> None:
        """보고서 파일 저장

        Args:
            filepath: 저장할 파일 경로
            format: 보고서 형식 ('text', 'json', 'html')
        """
        try:
            # 디렉토리 생성
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            # 형식별 보고서 생성
            if format == 'text':
                content = self.generate_text_report()
            elif format == 'json':
                content = self.generate_json_report()
            elif format == 'html':
                content = self.generate_html_report()
            else:
                raise ValueError(f"지원하지 않는 형식: {format}")

            # 파일 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"보고서 저장 완료: {filepath}")

        except Exception as e:
            self.logger.error(f"보고서 저장 중 오류: {e}", exc_info=True)
            raise

    def _format_trade_table(self, trades: List[Trade]) -> str:
        """거래 내역 테이블 포맷팅

        Args:
            trades: 거래 내역 리스트

        Returns:
            str: 포맷팅된 테이블
        """
        try:
            if not trades:
                return "거래 내역 없음"

            lines = []

            # 헤더
            header = (
                f"{'종목코드':^8} | {'종목명':^12} | {'진입일':^10} | "
                f"{'청산일':^10} | {'진입가':>10} | {'청산가':>10} | "
                f"{'수익률':>8} | {'보유일':>6} | {'사유':^10}"
            )
            lines.append(header)
            lines.append("-" * len(header))

            # 거래 내역
            for trade in trades:
                exit_date = trade.exit_date if trade.exit_date else '-'
                exit_price = f"{trade.exit_price:,.0f}" if trade.exit_price else '-'
                return_pct = f"{trade.return_pct:+.2%}" if trade.return_pct is not None else '-'
                holding_days = f"{trade.holding_days}" if trade.holding_days is not None else '-'
                exit_reason = trade.exit_reason if trade.exit_reason else '-'

                # 수익률에 따른 포맷팅 (색상은 터미널에서만 지원)
                if trade.return_pct is not None:
                    if trade.return_pct > 0:
                        return_str = f"{return_pct:>8}"
                    else:
                        return_str = f"{return_pct:>8}"
                else:
                    return_str = f"{'-':>8}"

                row = (
                    f"{trade.stock_code:^8} | {trade.stock_name:^12} | "
                    f"{trade.entry_date:^10} | {exit_date:^10} | "
                    f"{trade.entry_price:>10,.0f} | {exit_price:>10} | "
                    f"{return_str} | {holding_days:>6} | {exit_reason:^10}"
                )
                lines.append(row)

            return "\n".join(lines)

        except Exception as e:
            self.logger.error(f"거래 테이블 포맷팅 중 오류: {e}", exc_info=True)
            return "테이블 생성 실패"

    def generate_html_report(self) -> str:
        """HTML 보고서 생성

        Returns:
            str: HTML 형식 보고서
        """
        try:
            html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>백테스트 결과 보고서 - {self.result.strategy_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            text-align: center;
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .section {{
            margin: 30px 0;
        }}
        .section h2 {{
            color: #4CAF50;
            border-left: 4px solid #4CAF50;
            padding-left: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .metric {{
            display: inline-block;
            width: 48%;
            margin: 10px 1%;
            padding: 15px;
            background-color: #f9f9f9;
            border-left: 4px solid #4CAF50;
        }}
        .metric-label {{
            font-weight: bold;
            color: #666;
        }}
        .metric-value {{
            font-size: 24px;
            color: #333;
            margin-top: 5px;
        }}
        .positive {{
            color: #4CAF50;
        }}
        .negative {{
            color: #f44336;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>백테스트 결과 보고서</h1>

        <div class="section">
            <p><strong>전략명:</strong> {self.result.strategy_name}</p>
            <p><strong>기간:</strong> {self.result.start_date} ~ {self.result.end_date}</p>
            <p><strong>생성일시:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="section">
            <h2>성과 지표</h2>
            <div class="metric">
                <div class="metric-label">총 수익률</div>
                <div class="metric-value {'positive' if self.result.total_return > 0 else 'negative'}">
                    {self.result.total_return:.2%}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value">{self.result.sharpe_ratio:.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">최대 손실폭</div>
                <div class="metric-value negative">{self.result.max_drawdown:.2%}</div>
            </div>
            <div class="metric">
                <div class="metric-label">승률</div>
                <div class="metric-value">{self.result.win_rate:.1%}</div>
            </div>
        </div>

        <div class="section">
            <h2>거래 통계</h2>
            <table>
                <tr>
                    <th>항목</th>
                    <th>값</th>
                </tr>
                <tr>
                    <td>총 거래 수</td>
                    <td>{self.result.total_trades}건</td>
                </tr>
                <tr>
                    <td>승리 거래</td>
                    <td>{self.result.winning_trades}건</td>
                </tr>
                <tr>
                    <td>손실 거래</td>
                    <td>{self.result.losing_trades}건</td>
                </tr>
                <tr>
                    <td>평균 보유일</td>
                    <td>{self.result.avg_holding_days:.1f}일</td>
                </tr>
                <tr>
                    <td>Profit Factor</td>
                    <td>{self.result.profit_factor:.2f}</td>
                </tr>
            </table>
        </div>

        <div class="section">
            <h2>거래 내역 (최근 20건)</h2>
            {self._format_trade_html_table(self.trades[:20])}
        </div>
    </div>
</body>
</html>
            """
            return html

        except Exception as e:
            self.logger.error(f"HTML 보고서 생성 중 오류: {e}", exc_info=True)
            return f"<html><body><h1>보고서 생성 실패: {e}</h1></body></html>"

    def _format_trade_html_table(self, trades: List[Trade]) -> str:
        """거래 내역 HTML 테이블 포맷팅

        Args:
            trades: 거래 내역 리스트

        Returns:
            str: HTML 테이블
        """
        if not trades:
            return "<p>거래 내역 없음</p>"

        rows = []
        for trade in trades:
            exit_date = trade.exit_date if trade.exit_date else '-'
            exit_price = f"{trade.exit_price:,.0f}" if trade.exit_price else '-'
            return_pct = f"{trade.return_pct:+.2%}" if trade.return_pct is not None else '-'
            holding_days = f"{trade.holding_days}" if trade.holding_days is not None else '-'
            exit_reason = trade.exit_reason if trade.exit_reason else '-'

            color_class = ''
            if trade.return_pct is not None:
                color_class = 'positive' if trade.return_pct > 0 else 'negative'

            rows.append(f"""
                <tr>
                    <td>{trade.stock_code}</td>
                    <td>{trade.stock_name}</td>
                    <td>{trade.entry_date}</td>
                    <td>{exit_date}</td>
                    <td>{trade.entry_price:,.0f}</td>
                    <td>{exit_price}</td>
                    <td class="{color_class}">{return_pct}</td>
                    <td>{holding_days}</td>
                    <td>{exit_reason}</td>
                </tr>
            """)

        table = f"""
        <table>
            <tr>
                <th>종목코드</th>
                <th>종목명</th>
                <th>진입일</th>
                <th>청산일</th>
                <th>진입가</th>
                <th>청산가</th>
                <th>수익률</th>
                <th>보유일</th>
                <th>사유</th>
            </tr>
            {''.join(rows)}
        </table>
        """
        return table
