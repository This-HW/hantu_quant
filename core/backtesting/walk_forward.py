#!/usr/bin/env python3
"""
Walk-Forward Analysis 모듈
Rolling window 방식으로 전략을 Out-of-Sample 검증
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import statistics

from core.utils.log_utils import get_logger
from core.backtesting.strategy_backtester import StrategyBacktester, BacktestResult

logger = get_logger(__name__)


@dataclass
class WalkForwardConfig:
    """Walk-Forward Analysis 설정

    Attributes:
        train_window_days: 학습 윈도우 크기 (일). 기본 180일(6개월).
            충분한 학습 데이터를 위해 최소 90일 이상 권장.
        test_window_days: 테스트 윈도우 크기 (일). 기본 30일(1개월).
            train_window_days의 1/6~1/3이 적절.
        step_days: 윈도우 이동 간격 (일). 기본 30일.
            test_window_days와 동일하면 겹침 없이 진행.
        min_train_trades: 학습 구간 최소 거래 수. 기본 20건.
            통계적 유의성을 위해 최소 15건 이상 권장.
        purge_days: 학습/테스트 구간 사이 데이터 격리 기간 (일). 기본 5일.
            Look-ahead bias 방지용. 보유 기간과 동일하게 설정 권장.
    """
    train_window_days: int = 180  # 6개월
    test_window_days: int = 30    # 1개월
    step_days: int = 30           # 1개월씩 이동
    min_train_trades: int = 20    # 최소 학습 거래수
    purge_days: int = 5           # 데이터 격리 기간


@dataclass
class WindowResult:
    """단일 윈도우 백테스트 결과"""
    window_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_result: BacktestResult
    test_result: BacktestResult
    overfitting_ratio: float  # test_sharpe / train_sharpe


@dataclass
class WalkForwardResult:
    """Walk-Forward Analysis 종합 결과"""
    config: WalkForwardConfig
    windows: List[WindowResult]
    avg_train_sharpe: float
    avg_test_sharpe: float
    avg_train_return: float
    avg_test_return: float
    overall_overfitting_ratio: float  # > 0.5 is good
    consistency_score: float          # std of test returns (lower is better)
    total_windows: int
    valid_windows: int                # windows with sufficient trades


class WalkForwardAnalyzer:
    """Walk-Forward Analysis 수행 엔진"""

    def __init__(self, config: Optional[WalkForwardConfig] = None):
        """
        Args:
            config: Walk-Forward 설정 (기본값 사용 시 None)
        """
        self.config = config or WalkForwardConfig()
        self.backtester = StrategyBacktester()

        # 입력 검증
        if self.config.train_window_days <= 0:
            raise ValueError(f"train_window_days must be > 0, got {self.config.train_window_days}")
        if self.config.test_window_days <= 0:
            raise ValueError(f"test_window_days must be > 0, got {self.config.test_window_days}")
        if self.config.step_days <= 0:
            raise ValueError(f"step_days must be > 0, got {self.config.step_days}")

        logger.info(
            f"WalkForwardAnalyzer 초기화: "
            f"train={self.config.train_window_days}일, "
            f"test={self.config.test_window_days}일, "
            f"step={self.config.step_days}일, "
            f"min_trades={self.config.min_train_trades}"
        )

    def run(
        self,
        start_date: str,
        end_date: str,
        selection_criteria: Dict,
        trading_config: Dict,
        strategy_name: str = "walk_forward"
    ) -> WalkForwardResult:
        """Walk-Forward Analysis 실행

        Args:
            start_date: 전체 분석 시작일 (YYYY-MM-DD)
            end_date: 전체 분석 종료일 (YYYY-MM-DD)
            selection_criteria: 종목 선정 기준
            trading_config: 매매 설정
            strategy_name: 전략명

        Returns:
            WalkForwardResult: 종합 결과
        """
        logger.info(
            f"Walk-Forward Analysis 시작: {start_date} ~ {end_date}, "
            f"전략={strategy_name}"
        )

        # 1. Rolling 윈도우 생성
        windows_dates = self._generate_windows(start_date, end_date)
        logger.info(f"총 {len(windows_dates)}개 윈도우 생성")

        # 2. 각 윈도우별 백테스트 실행
        window_results = []
        for i, (train_start, train_end, test_start, test_end) in enumerate(windows_dates, start=1):
            logger.info(
                f"[{i}/{len(windows_dates)}] 윈도우 실행: "
                f"Train {train_start}~{train_end}, "
                f"Test {test_start}~{test_end}"
            )

            result = self._backtest_window(
                window_index=i,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                selection_criteria=selection_criteria,
                trading_config=trading_config
            )

            if result:
                window_results.append(result)
                logger.info(
                    f"  Train Sharpe: {result.train_result.sharpe_ratio:.3f}, "
                    f"Test Sharpe: {result.test_result.sharpe_ratio:.3f}, "
                    f"OF Ratio: {result.overfitting_ratio:.3f}"
                )
            else:
                logger.warning(f"  윈도우 {i} 스킵 (거래 데이터 부족)")

        # 3. 결과 종합
        total_attempted = len(windows_dates)
        if not window_results:
            logger.error(f"유효한 윈도우가 하나도 없습니다 (시도: {total_attempted}개)")
            return self._empty_result(total_attempted=total_attempted)

        final_result = self._aggregate_results(window_results, self.config, total_attempted=total_attempted)

        logger.info(
            f"Walk-Forward Analysis 완료: "
            f"유효 윈도우={final_result.valid_windows}/{final_result.total_windows}, "
            f"평균 Test Sharpe={final_result.avg_test_sharpe:.3f}, "
            f"OF Ratio={final_result.overall_overfitting_ratio:.3f}, "
            f"Consistency={final_result.consistency_score:.4f}"
        )

        return final_result

    def _generate_windows(
        self,
        start_date: str,
        end_date: str
    ) -> List[Tuple[str, str, str, str]]:
        """Rolling 윈도우 생성

        Args:
            start_date: 전체 시작일 (YYYY-MM-DD)
            end_date: 전체 종료일 (YYYY-MM-DD)

        Returns:
            List[Tuple[train_start, train_end, test_start, test_end]]
        """
        windows = []
        current_start = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        while True:
            # Train 기간
            train_start = current_start
            train_end = train_start + timedelta(days=self.config.train_window_days - 1)

            # Purge 기간 (train과 test 사이 격리)
            purge_end = train_end + timedelta(days=self.config.purge_days)

            # Test 기간
            test_start = purge_end + timedelta(days=1)
            test_end = test_start + timedelta(days=self.config.test_window_days - 1)

            # 종료일 초과 시 클리핑 후 중단
            if test_start > end_dt:
                break

            if test_end > end_dt:
                test_end = end_dt

            windows.append((
                train_start.strftime("%Y-%m-%d"),
                train_end.strftime("%Y-%m-%d"),
                test_start.strftime("%Y-%m-%d"),
                test_end.strftime("%Y-%m-%d")
            ))

            # 다음 윈도우로 이동
            current_start += timedelta(days=self.config.step_days)

            # test_end가 end_date에 도달하면 종료
            if test_end >= end_dt:
                break

        return windows

    def _backtest_window(
        self,
        window_index: int,
        train_start: str,
        train_end: str,
        test_start: str,
        test_end: str,
        selection_criteria: Dict,
        trading_config: Dict
    ) -> Optional[WindowResult]:
        """단일 윈도우 백테스트

        Args:
            window_index: 윈도우 번호
            train_start, train_end: 학습 기간
            test_start, test_end: 테스트 기간
            selection_criteria: 종목 선정 기준
            trading_config: 매매 설정

        Returns:
            WindowResult 또는 None (거래 데이터 부족 시)
        """
        try:
            # Train 백테스트
            train_result = self.backtester.backtest_selection_strategy(
                start_date=train_start,
                end_date=train_end,
                selection_criteria=selection_criteria,
                trading_config=trading_config,
                strategy_name=f"Train_W{window_index}"
            )

            # 최소 거래 수 체크
            if train_result.total_trades < self.config.min_train_trades:
                logger.warning(
                    f"윈도우 {window_index} Train 거래 부족: "
                    f"{train_result.total_trades} < {self.config.min_train_trades}"
                )
                return None

            # Test 백테스트
            test_result = self.backtester.backtest_selection_strategy(
                start_date=test_start,
                end_date=test_end,
                selection_criteria=selection_criteria,
                trading_config=trading_config,
                strategy_name=f"Test_W{window_index}"
            )

            # Overfitting Ratio 계산
            if train_result.sharpe_ratio == 0:
                overfitting_ratio = 0.0
            else:
                overfitting_ratio = test_result.sharpe_ratio / train_result.sharpe_ratio

            return WindowResult(
                window_index=window_index,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_result=train_result,
                test_result=test_result,
                overfitting_ratio=overfitting_ratio
            )

        except Exception as e:
            logger.error(
                f"윈도우 {window_index} 백테스트 실패: {e}",
                exc_info=True
            )
            return None

    def _aggregate_results(
        self,
        windows: List[WindowResult],
        config: WalkForwardConfig,
        total_attempted: int = 0
    ) -> WalkForwardResult:
        """결과 종합

        Args:
            windows: 윈도우별 결과
            config: Walk-Forward 설정
            total_attempted: 시도된 전체 윈도우 수

        Returns:
            WalkForwardResult: 종합 결과
        """
        if not windows:
            return self._empty_result()

        # 평균 Sharpe Ratio
        train_sharpes = [w.train_result.sharpe_ratio for w in windows]
        test_sharpes = [w.test_result.sharpe_ratio for w in windows]
        avg_train_sharpe = statistics.mean(train_sharpes)
        avg_test_sharpe = statistics.mean(test_sharpes)

        # 평균 수익률
        train_returns = [w.train_result.total_return for w in windows]
        test_returns = [w.test_result.total_return for w in windows]
        avg_train_return = statistics.mean(train_returns)
        avg_test_return = statistics.mean(test_returns)

        # 전체 Overfitting Ratio
        if avg_train_sharpe == 0:
            overall_of_ratio = 0.0
        else:
            overall_of_ratio = avg_test_sharpe / avg_train_sharpe

        # Consistency Score (test 수익률의 표준편차, 낮을수록 안정적)
        if len(test_returns) > 1:
            consistency_score = statistics.stdev(test_returns)
        else:
            consistency_score = 0.0

        return WalkForwardResult(
            config=config,
            windows=windows,
            avg_train_sharpe=avg_train_sharpe,
            avg_test_sharpe=avg_test_sharpe,
            avg_train_return=avg_train_return,
            avg_test_return=avg_test_return,
            overall_overfitting_ratio=overall_of_ratio,
            consistency_score=consistency_score,
            total_windows=total_attempted if total_attempted > 0 else len(windows),
            valid_windows=len(windows)
        )

    def _empty_result(self, total_attempted: int = 0) -> WalkForwardResult:
        """빈 결과"""
        return WalkForwardResult(
            config=self.config,
            windows=[],
            avg_train_sharpe=0.0,
            avg_test_sharpe=0.0,
            avg_train_return=0.0,
            avg_test_return=0.0,
            overall_overfitting_ratio=0.0,
            consistency_score=0.0,
            total_windows=total_attempted,
            valid_windows=0
        )
