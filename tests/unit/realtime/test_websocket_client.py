"""WebSocket 클라이언트 단위 테스트

Tests:
    - KIS WebSocket 메시지 파싱 (체결가, 호가)
    - 메시지 정규화
    - 필드 매핑
"""

import pytest
from core.api.websocket_client import KISWebSocketClient


class TestKISWebSocketMessageParsing:
    """KIS WebSocket 메시지 파싱 테스트"""

    def test_normalize_체결가_메시지_성공(self):
        """체결가 메시지 정규화 성공 케이스"""
        client = KISWebSocketClient(approval_key="test_key")

        # KIS 실시간 체결가 메시지 (파이프 구분)
        # 필드: 종목코드|체결시간|현재가|전일대비부호|전일대비|등락율|...|체결량|...|누적거래량|...|시가|고가|저가|...
        body = "005930|153000|71000|2|500|0.71|0|0|0|1000|0|0|50000000|0|0|0|70500|71500|70000|0|0"

        result = client._normalize_kis_message("H0STCNT0", body)

        assert result is not None
        assert result["stock_code"] == "005930"
        assert result["timestamp"] == "153000"
        assert result["current_price"] == 71000
        assert result["change"] == "2"  # 상승
        assert result["change_price"] == 500
        assert result["change_rate"] == 0.71
        assert result["volume"] == 1000
        assert result["accumulated_volume"] == 50000000
        assert result["open_price"] == 70500
        assert result["high_price"] == 71500
        assert result["low_price"] == 70000

    def test_normalize_호가_메시지_성공(self):
        """호가 메시지 정규화 성공 케이스"""
        client = KISWebSocketClient(approval_key="test_key")

        # KIS 실시간 호가 메시지
        # 필드: 종목코드|시간|기타|매도호가10개|매수호가10개|매도잔량10개|매수잔량10개|총매도잔량|총매수잔량|...
        ask_prices = "|".join([str(71000 + i*100) for i in range(10)])
        bid_prices = "|".join([str(70900 - i*100) for i in range(10)])
        ask_volumes = "|".join([str(100 * (i+1)) for i in range(10)])
        bid_volumes = "|".join([str(200 * (i+1)) for i in range(10)])

        # 필드 60개 맞추기: stock_code|timestamp|X + ask_prices(10) + bid_prices(10) + ask_volumes(10) + bid_volumes(10) + total_ask|total_bid + padding(15개)
        padding = "|".join(["0"] * 15)
        body = f"005930|153000|X|{ask_prices}|{bid_prices}|{ask_volumes}|{bid_volumes}|5500|11000|{padding}"

        result = client._normalize_kis_message("H0STASP0", body)

        assert result is not None
        assert result["stock_code"] == "005930"
        assert result["timestamp"] == "153000"
        assert len(result["ask_prices"]) == 10
        assert len(result["bid_prices"]) == 10
        assert len(result["ask_volumes"]) == 10
        assert len(result["bid_volumes"]) == 10
        assert result["total_ask_volume"] == 5500
        assert result["total_bid_volume"] == 11000

    def test_normalize_체결가_필드부족_실패(self):
        """체결가 메시지 필드 부족 시 None 반환"""
        client = KISWebSocketClient(approval_key="test_key")

        # 필드가 부족한 메시지 (20개 미만)
        body = "005930|153000|71000|2|500"

        result = client._normalize_kis_message("H0STCNT0", body)

        assert result is None

    def test_normalize_호가_필드부족_실패(self):
        """호가 메시지 필드 부족 시 None 반환"""
        client = KISWebSocketClient(approval_key="test_key")

        # 필드가 부족한 메시지 (60개 미만)
        body = "005930|153000|X|71000|70900"

        result = client._normalize_kis_message("H0STASP0", body)

        assert result is None

    def test_normalize_알수없는_tr_id(self):
        """알 수 없는 TR_ID의 경우 raw 데이터 반환"""
        client = KISWebSocketClient(approval_key="test_key")

        body = "test|data|123"
        result = client._normalize_kis_message("UNKNOWN_TR", body)

        assert result is not None
        assert "raw" in result
        assert result["raw"] == body

    def test_normalize_빈_필드_처리(self):
        """빈 필드가 있는 경우 기본값(0) 처리"""
        client = KISWebSocketClient(approval_key="test_key")

        # 일부 필드가 빈 문자열
        body = "005930|153000||2|||0|0|0||0|0||0|0|0|70500|71500|70000|0|0"

        result = client._normalize_kis_message("H0STCNT0", body)

        assert result is not None
        assert result["current_price"] == 0  # 빈 필드 → 0
        assert result["change_price"] == 0
        assert result["change_rate"] == 0.0
        assert result["volume"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
