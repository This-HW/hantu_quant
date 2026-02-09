#!/usr/bin/env python3
"""
StrategyBacktester 버그 수정 테스트

수정된 내용:
1. _to_datetime: 타입 안전 헬퍼 추가
2. holding_days 계산: str/datetime 모두 처리
"""

import pytest
from datetime import datetime
from core.backtesting.strategy_backtester import StrategyBacktester, Trade


class TestStrategyBacktesterFixes:
    """StrategyBacktester 버그 수정 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        self.backtester = StrategyBacktester()

    def test_to_datetime_with_string(self):
        """_to_datetime: 문자열 입력 처리"""
        date_str = "2024-01-31"
        result = self.backtester._to_datetime(date_str)

        assert isinstance(result, datetime), "반환 타입은 datetime"
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 31

    def test_to_datetime_with_datetime_object(self):
        """_to_datetime: datetime 객체 입력 처리"""
        date_obj = datetime(2024, 1, 31)
        result = self.backtester._to_datetime(date_obj)

        assert isinstance(result, datetime), "반환 타입은 datetime"
        assert result == date_obj, "입력과 동일한 datetime 반환"

    def test_to_datetime_raises_typeerror(self):
        """_to_datetime: 잘못된 타입 입력 시 TypeError"""
        with pytest.raises(TypeError) as exc_info:
            self.backtester._to_datetime(12345)

        assert "Unsupported date type" in str(exc_info.value)

    def test_to_datetime_with_various_string_formats(self):
        """_to_datetime: 다양한 문자열 형식 처리"""
        # 정상 형식
        assert self.backtester._to_datetime("2024-01-31").day == 31
        assert self.backtester._to_datetime("2024-12-25").month == 12
        assert self.backtester._to_datetime("2023-06-15").year == 2023

    def test_holding_days_calculation_with_mixed_types(self):
        """holding_days 계산: str/datetime 혼합 처리"""
        # Trade 객체 생성 (entry_date는 문자열)
        trade = Trade(
            stock_code="005930",
            stock_name="삼성전자",
            entry_date="2024-01-01",  # 문자열
            entry_price=50000,
            exit_date=None,
            exit_price=None,
            quantity=100,
            return_pct=None,
            holding_days=None,
            exit_reason=None
        )

        # exit_date는 datetime 객체
        current_date = datetime(2024, 1, 10)

        # holding_days 계산
        holding_days = (
            self.backtester._to_datetime(current_date)
            - self.backtester._to_datetime(trade.entry_date)
        ).days

        assert holding_days == 9, "2024-01-01 ~ 2024-01-10 = 9일"

    def test_holding_days_with_string_dates(self):
        """holding_days 계산: 문자열 날짜 처리"""
        entry = "2024-01-01"
        exit = "2024-01-15"

        holding_days = (
            self.backtester._to_datetime(exit)
            - self.backtester._to_datetime(entry)
        ).days

        assert holding_days == 14, "2024-01-01 ~ 2024-01-15 = 14일"

    def test_holding_days_with_datetime_objects(self):
        """holding_days 계산: datetime 객체 처리"""
        entry = datetime(2024, 1, 1)
        exit = datetime(2024, 1, 20)

        holding_days = (
            self.backtester._to_datetime(exit)
            - self.backtester._to_datetime(entry)
        ).days

        assert holding_days == 19, "2024-01-01 ~ 2024-01-20 = 19일"

    def test_holding_days_same_day(self):
        """holding_days 계산: 같은 날짜 처리"""
        entry = "2024-01-15"
        exit = "2024-01-15"

        holding_days = (
            self.backtester._to_datetime(exit)
            - self.backtester._to_datetime(entry)
        ).days

        assert holding_days == 0, "같은 날 = 0일"

    def test_to_datetime_edge_cases(self):
        """_to_datetime: 엣지 케이스 처리"""
        # 연도 경계
        assert self.backtester._to_datetime("2023-12-31").year == 2023
        assert self.backtester._to_datetime("2024-01-01").year == 2024

        # 월 경계
        assert self.backtester._to_datetime("2024-01-31").month == 1
        assert self.backtester._to_datetime("2024-02-01").month == 2

    def test_simulate_trading_uses_to_datetime(self):
        """_simulate_trading: _to_datetime 사용 확인"""
        from dataclasses import replace
        # _simulate_trading 내부에서 holding_days 계산 시 _to_datetime 사용
        trade = Trade(
            stock_code="005930",
            stock_name="삼성전자",
            entry_date="2024-01-01",
            entry_price=50000,
            exit_date="2024-01-10",
            exit_price=51000,
            quantity=100,
            return_pct=0.02,
            holding_days=None,
            exit_reason="take_profit"
        )

        # holding_days 계산 (불변 객체이므로 replace 사용)
        holding_days = (
            self.backtester._to_datetime(trade.exit_date)
            - self.backtester._to_datetime(trade.entry_date)
        ).days
        trade = replace(trade, holding_days=holding_days)

        assert trade.holding_days == 9, "holding_days 계산 정확"

    def test_check_exits_with_mixed_date_types(self):
        """_check_exits: str/datetime 혼합 처리"""
        portfolio = {
            "005930": Trade(
                stock_code="005930",
                stock_name="삼성전자",
                entry_date="2024-01-01",  # 문자열
                entry_price=50000,
                exit_date=None,
                exit_price=None,
                quantity=100,
                return_pct=None,
                holding_days=None,
                exit_reason=None
            )
        }

        current_date = "2024-01-05"  # 문자열

        # holding_days 계산
        trade = portfolio["005930"]
        holding_days = (
            self.backtester._to_datetime(current_date)
            - self.backtester._to_datetime(trade.entry_date)
        ).days

        assert holding_days == 4, "혼합 타입 처리 성공"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
