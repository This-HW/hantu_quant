"""
WebSocket Mock 사용 예시 테스트

E2E 테스트 인프라 검증
"""

import pytest
import asyncio
from typing import List, Dict


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_websocket_server_basic(mock_websocket_server):
    """WebSocket 서버 기본 동작 테스트"""
    # Given: 서버가 실행 중
    assert mock_websocket_server.is_running

    # When: 가격 업데이트 전송
    received_data = []

    async def callback(data: Dict):
        received_data.append(data)

    mock_websocket_server.add_subscriber("005930", callback)
    await mock_websocket_server.send_price_update(
        stock_code="005930", price=70500, volume=1000
    )

    # Then: 콜백이 호출됨
    await asyncio.sleep(0.1)  # 비동기 처리 대기
    assert len(received_data) == 1
    assert received_data[0]["stock_code"] == "005930"
    assert received_data[0]["current_price"] == 70500


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_websocket_client_subscribe(mock_kis_websocket_client):
    """WebSocket 클라이언트 구독 테스트"""
    # Given: 클라이언트가 연결됨
    assert mock_kis_websocket_client.websocket is not None

    # When: 종목 구독
    received_data = []

    async def price_callback(data: Dict):
        received_data.append(data)

    mock_kis_websocket_client.add_callback("H0STCNT0", price_callback)
    success = await mock_kis_websocket_client.subscribe("005930", ["H0STCNT0"])

    # Then: 구독 성공
    assert success
    assert "005930" in mock_kis_websocket_client.subscribed_codes


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_websocket_delay_simulation(mock_websocket_server):
    """WebSocket 지연 시뮬레이션 테스트"""
    # Given: 100ms 지연 설정
    mock_websocket_server.set_response_delay(100)

    # When: 메시지 전송
    import time

    received_data = []

    async def callback(data: Dict):
        received_data.append(data)

    mock_websocket_server.add_subscriber("005930", callback)

    start_time = time.time()
    await mock_websocket_server.send_price_update(
        stock_code="005930", price=70000, volume=1000
    )
    elapsed = (time.time() - start_time) * 1000  # 밀리초 변환

    # Then: 100ms 이상 지연됨
    await asyncio.sleep(0.2)
    assert elapsed >= 100
    assert len(received_data) == 1


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_websocket_disconnect_simulation(mock_kis_websocket_client):
    """WebSocket 연결 끊김 시뮬레이션 테스트"""
    # Given: 정상 연결 상태
    assert await mock_kis_websocket_client.heartbeat()

    # When: 연결 끊김 시뮬레이션
    await mock_kis_websocket_client.mock_server.simulate_disconnect()

    # Then: Heartbeat 실패
    assert not await mock_kis_websocket_client.heartbeat()

    # When: 재연결 시뮬레이션
    await mock_kis_websocket_client.mock_server.simulate_reconnect()

    # Then: Heartbeat 성공
    assert await mock_kis_websocket_client.heartbeat()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_price_stream_generation(sample_price_stream):
    """가격 스트림 생성 테스트"""
    # Given: 가격 스트림 생성기
    stream = sample_price_stream

    # When: 10개 데이터 생성
    prices = [next(stream) for _ in range(10)]

    # Then: 데이터 형식 검증
    assert len(prices) == 10
    for price_data in prices:
        assert "stock_code" in price_data
        assert "current_price" in price_data
        assert "timestamp" in price_data
        assert price_data["current_price"] > 0


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.slow
async def test_websocket_concurrent_subscribers(mock_websocket_server):
    """WebSocket 다중 구독자 테스트"""
    # Given: 3개 구독자 등록
    received_data_1 = []
    received_data_2 = []
    received_data_3 = []

    async def callback_1(data: Dict):
        received_data_1.append(data)

    async def callback_2(data: Dict):
        received_data_2.append(data)

    async def callback_3(data: Dict):
        received_data_3.append(data)

    mock_websocket_server.add_subscriber("005930", callback_1)
    mock_websocket_server.add_subscriber("005930", callback_2)
    mock_websocket_server.add_subscriber("005930", callback_3)

    # When: 메시지 전송
    await mock_websocket_server.send_price_update(
        stock_code="005930", price=71000, volume=2000
    )

    # Then: 모든 구독자가 메시지 수신
    await asyncio.sleep(0.2)
    assert len(received_data_1) == 1
    assert len(received_data_2) == 1
    assert len(received_data_3) == 1

    # 모두 동일한 데이터
    assert received_data_1[0]["current_price"] == 71000
    assert received_data_2[0]["current_price"] == 71000
    assert received_data_3[0]["current_price"] == 71000
