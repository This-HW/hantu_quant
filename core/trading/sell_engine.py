"""
Phase 6: 매도 로직 엔진 - 완전한 매매 시스템 구축

다양한 매도 전략을 통합한 지능형 매도 엔진
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json

from core.utils.log_utils import get_logger
from core.interfaces.trading import ISellEngine, ISellStrategy

logger = get_logger(__name__)

class SellSignalType(Enum):
    """매도 신호 유형"""
    STOP_LOSS = "stop_loss"                    # 스톱로스
    TRAILING_STOP = "trailing_stop"            # 트레일링 스톱
    TAKE_PROFIT = "take_profit"                # 목표 수익률
    RSI_OVERBOUGHT = "rsi_overbought"          # RSI 과매수
    BOLLINGER_REVERSAL = "bollinger_reversal"  # 볼린저 밴드 반전
    TIME_BASED = "time_based"                  # 시간 기반
    MACD_BEARISH = "macd_bearish"             # MACD 약세 전환
    VOLUME_DECLINE = "volume_decline"          # 거래량 감소
    MARKET_CONDITION = "market_condition"      # 시장 상황 변화
    # ORDERBOOK_IMBALANCE = "orderbook_imbalance"  # 호가 불균형 (기존 MARKET_CONDITION으로 처리)

@dataclass
class SellSignal:
    """매도 신호 클래스"""
    stock_code: str
    stock_name: str
    signal_type: SellSignalType
    signal_strength: float      # 신호 강도 (0-1)
    current_price: float
    entry_price: float
    current_return: float       # 현재 수익률
    target_price: Optional[float] = None
    reason: str = ""
    timestamp: str = ""
    confidence: float = 0.0     # 신뢰도
    suggested_ratio: Optional[float] = None  # 부분청산 권고 비율
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

@dataclass
class PositionInfo:
    """보유 포지션 정보"""
    stock_code: str
    stock_name: str
    entry_price: float
    current_price: float
    quantity: int
    entry_date: str
    hold_days: int
    current_return: float
    stop_loss_price: float
    trailing_stop_price: float
    take_profit_price: float

class SellEngine(ISellEngine):
    """통합 매도 엔진"""
    
    def __init__(self, config: Optional[Dict] = None):
        """초기화
        
        Args:
            config: 매도 엔진 설정
        """
        self._logger = logger
        self._config = config or self._get_default_config()
        
        # 매도 전략 설정
        self._sell_strategies = {
            SellSignalType.STOP_LOSS: self._check_stop_loss,
            SellSignalType.TRAILING_STOP: self._check_trailing_stop,
            SellSignalType.TAKE_PROFIT: self._check_take_profit,
            SellSignalType.RSI_OVERBOUGHT: self._check_rsi_overbought,
            SellSignalType.BOLLINGER_REVERSAL: self._check_bollinger_reversal,
            SellSignalType.TIME_BASED: self._check_time_based,
            SellSignalType.MACD_BEARISH: self._check_macd_bearish,
        }
        
        # 활성 포지션 추적
        self._positions: Dict[str, PositionInfo] = {}
        
        self._logger.info("SellEngine 초기화 완료")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            # 스톱로스 설정
            "stop_loss_percent": 0.05,          # 5% 손실 시 매도
            "trailing_stop_percent": 0.03,      # 3% 트레일링 스톱
            
            # 목표 수익률 설정
            "take_profit_levels": [0.10, 0.15, 0.20],  # 10%, 15%, 20%
            "partial_sell_ratios": [0.3, 0.3, 0.4],   # 부분 매도 비율
            
            # 기술적 지표 설정
            "rsi_overbought_threshold": 70,     # RSI 과매수 기준
            "rsi_period": 14,                   # RSI 계산 기간
            "bollinger_period": 20,             # 볼린저 밴드 기간
            "bollinger_std": 2,                 # 볼린저 밴드 표준편차
            
            # 시간 기반 설정
            "max_hold_days": 10,                # 최대 보유 일수
            "intraday_exit_time": "15:00",      # 장중 매도 시간
            
            # 시장 상황 설정
            "market_decline_threshold": 0.02,   # 시장 2% 하락 시 매도
            "volume_decline_threshold": 0.5,    # 거래량 50% 감소
            
            # 신호 가중치
            "signal_weights": {
                SellSignalType.STOP_LOSS: 1.0,
                SellSignalType.TRAILING_STOP: 0.8,
                SellSignalType.TAKE_PROFIT: 0.9,
                SellSignalType.RSI_OVERBOUGHT: 0.6,
                SellSignalType.BOLLINGER_REVERSAL: 0.7,
                SellSignalType.TIME_BASED: 0.5,
                SellSignalType.MACD_BEARISH: 0.6,
            }
            ,
            # ATR 기반 트레일링 스톱 보강
            "atr_trailing_multiplier": 2.0,
        }
    
    def add_position(self, stock_code: str, stock_name: str, entry_price: float, 
                    quantity: int, entry_date: str) -> bool:
        """포지션 추가
        
        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            entry_price: 진입 가격
            quantity: 수량
            entry_date: 진입 날짜
            
        Returns:
            bool: 추가 성공 여부
        """
        try:
            # 스톱로스, 트레일링 스톱, 목표가 계산
            stop_loss_price = entry_price * (1 - self._config["stop_loss_percent"])
            trailing_stop_price = stop_loss_price
            take_profit_price = entry_price * (1 + self._config["take_profit_levels"][0])
            
            position = PositionInfo(
                stock_code=stock_code,
                stock_name=stock_name,
                entry_price=entry_price,
                current_price=entry_price,
                quantity=quantity,
                entry_date=entry_date,
                hold_days=0,
                current_return=0.0,
                stop_loss_price=stop_loss_price,
                trailing_stop_price=trailing_stop_price,
                take_profit_price=take_profit_price
            )
            
            self._positions[stock_code] = position
            self._logger.info(f"포지션 추가: {stock_code} ({stock_name}) - {quantity}주 @ {entry_price:,.0f}원")
            
            return True
            
        except Exception as e:
            self._logger.error(f"포지션 추가 오류: {e}", exc_info=True)
            return False
    
    def update_position_price(self, stock_code: str, current_price: float) -> bool:
        """포지션 현재가 업데이트
        
        Args:
            stock_code: 종목 코드
            current_price: 현재가
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            if stock_code not in self._positions:
                return False
            
            position = self._positions[stock_code]
            position.current_price = current_price
            position.current_return = (current_price - position.entry_price) / position.entry_price
            
            # 트레일링 스톱 업데이트 (수익 시에만)
            if position.current_return > 0:
                new_trailing_stop = current_price * (1 - self._config["trailing_stop_percent"])
                if new_trailing_stop > position.trailing_stop_price:
                    position.trailing_stop_price = new_trailing_stop
                    self._logger.debug(f"트레일링 스톱 업데이트: {stock_code} -> {new_trailing_stop:,.0f}원")
            
            return True
            
        except Exception as e:
            self._logger.error(f"포지션 가격 업데이트 오류: {e}", exc_info=True)
            return False
    
    def check_sell_signals(self, stock_data: Dict[str, Any]) -> List[SellSignal]:
        """매도 신호 검사
        
        Args:
            stock_data: 종목 데이터 (price, volume, indicators 포함)
            
        Returns:
            List[SellSignal]: 매도 신호 리스트
        """
        try:
            stock_code = stock_data.get("stock_code", "")
            if stock_code not in self._positions:
                return []
            
            position = self._positions[stock_code]
            current_price = stock_data.get("current_price", position.current_price)
            
            # 현재가 업데이트
            self.update_position_price(stock_code, current_price)
            
            sell_signals = []
            
            # 각 매도 전략 검사
            for signal_type, strategy_func in self._sell_strategies.items():
                try:
                    signal = strategy_func(position, stock_data)
                    if signal and signal.signal_strength > 0:
                        sell_signals.append(signal)
                except Exception as e:
                    self._logger.error(f"매도 전략 {signal_type} 검사 오류: {e}", exc_info=True)
            
            # 신호 강도 순으로 정렬
            sell_signals.sort(key=lambda x: x.signal_strength, reverse=True)
            
            if sell_signals:
                self._logger.info(f"매도 신호 발견: {stock_code} - {len(sell_signals)}개 신호")
                for signal in sell_signals:
                    self._logger.info(f"  - {signal.signal_type.value}: 강도 {signal.signal_strength:.2f}")
            
            return sell_signals
            
        except Exception as e:
            self._logger.error(f"매도 신호 검사 오류: {e}", exc_info=True)
            return []
    
    def _check_stop_loss(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        """스톱로스 검사"""
        current_price = stock_data.get("current_price", position.current_price)
        
        if current_price <= position.stop_loss_price:
            return SellSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SellSignalType.STOP_LOSS,
                signal_strength=1.0,  # 최고 우선순위
                current_price=current_price,
                entry_price=position.entry_price,
                current_return=position.current_return,
                target_price=position.stop_loss_price,
                reason=f"손실 제한: {position.current_return*100:.1f}% 손실",
                timestamp=datetime.now().isoformat(),
                confidence=0.95
            )
        return None
    
    def _check_trailing_stop(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        """트레일링 스톱 검사"""
        current_price = stock_data.get("current_price", position.current_price)
        # ATR 기반 보강: 분봉 데이터가 있는 경우 트레일링을 동적으로 조정
        try:
            df = stock_data.get("minute_bars")
            if df is not None:
                import pandas as _pd
                if isinstance(df, dict):
                    df = _pd.DataFrame(df)
                highs = _pd.to_numeric(df.get('high', df.get('stck_hgpr', [])), errors='coerce')
                lows = _pd.to_numeric(df.get('low', df.get('stck_lwpr', [])), errors='coerce')
                closes = _pd.to_numeric(df.get('close', df.get('stck_prpr', [])), errors='coerce')
                if len(highs) > 1 and len(lows) > 1 and len(closes) > 1:
                    prev_close = closes.shift(1)
                    tr = _pd.concat([(highs - lows).abs(), (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
                    atr = tr.rolling(window=14, min_periods=5).mean().iloc[-1]
                    if _np_is_finite := (atr is not None):
                        new_trailing = max(position.trailing_stop_price, current_price - self._config.get("atr_trailing_multiplier", 2.0) * float(atr))
                        if new_trailing > position.trailing_stop_price:
                            position.trailing_stop_price = new_trailing
        except Exception:
            pass

        if current_price <= position.trailing_stop_price and position.current_return > 0:
            return SellSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SellSignalType.TRAILING_STOP,
                signal_strength=0.9,
                current_price=current_price,
                entry_price=position.entry_price,
                current_return=position.current_return,
                target_price=position.trailing_stop_price,
                reason=f"트레일링 스톱: {position.current_return*100:.1f}% 수익 보호",
                timestamp=datetime.now().isoformat(),
                confidence=0.9
            )
        return None
    
    def _check_take_profit(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        """목표 수익률 검사"""
        current_price = stock_data.get("current_price", position.current_price)
        
        # 목표 수익률 달성 여부 확인
        for i, target_return in enumerate(self._config["take_profit_levels"]):
            if position.current_return >= target_return:
                partial_ratio = self._config["partial_sell_ratios"][i]
                
                return SellSignal(
                    stock_code=position.stock_code,
                    stock_name=position.stock_name,
                    signal_type=SellSignalType.TAKE_PROFIT,
                    signal_strength=0.8,
                    current_price=current_price,
                    entry_price=position.entry_price,
                    current_return=position.current_return,
                    target_price=position.entry_price * (1 + target_return),
                    reason=f"목표 수익률 달성: {position.current_return*100:.1f}% (부분매도 {partial_ratio*100:.0f}%)",
                    timestamp=datetime.now().isoformat(),
                    confidence=0.85,
                    suggested_ratio=partial_ratio
                )
        return None
    
    def _check_rsi_overbought(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        """RSI 과매수 검사"""
        indicators = stock_data.get("indicators", {})
        rsi = indicators.get("rsi", 50)
        
        if rsi >= self._config["rsi_overbought_threshold"]:
            signal_strength = min(1.0, (rsi - 70) / 30)  # 70-100 구간에서 강도 계산
            
            return SellSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SellSignalType.RSI_OVERBOUGHT,
                signal_strength=signal_strength * 0.6,  # 기본 가중치 적용
                current_price=stock_data.get("current_price", position.current_price),
                entry_price=position.entry_price,
                current_return=position.current_return,
                reason=f"RSI 과매수: {rsi:.1f}",
                timestamp=datetime.now().isoformat(),
                confidence=0.7
            )
        return None
    
    def _check_bollinger_reversal(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        """볼린저 밴드 반전 검사"""
        indicators = stock_data.get("indicators", {})
        bb_upper = indicators.get("bollinger_upper", 0)
        bb_position = indicators.get("bollinger_position", 0.5)  # 0-1 사이 값
        current_price = stock_data.get("current_price", position.current_price)
        
        # 볼린저 밴드 상단(0.8 이상) 접촉 후 반전 신호
        if bb_position >= 0.8 and current_price < bb_upper:
            signal_strength = bb_position * 0.7  # 위치에 따른 강도 조절
            
            return SellSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SellSignalType.BOLLINGER_REVERSAL,
                signal_strength=signal_strength,
                current_price=current_price,
                entry_price=position.entry_price,
                current_return=position.current_return,
                reason=f"볼린저 밴드 반전: 상단 접촉 후 하락",
                timestamp=datetime.now().isoformat(),
                confidence=0.6
            )
        return None
    
    def _check_time_based(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        """시간 기반 매도 검사"""
        # 보유 일수 계산
        entry_date = datetime.strptime(position.entry_date, "%Y-%m-%d")
        current_date = datetime.now()
        hold_days = (current_date - entry_date).days
        
        max_hold_days = self._config["max_hold_days"]
        
        if hold_days >= max_hold_days:
            signal_strength = min(1.0, hold_days / max_hold_days) * 0.5
            
            return SellSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SellSignalType.TIME_BASED,
                signal_strength=signal_strength,
                current_price=stock_data.get("current_price", position.current_price),
                entry_price=position.entry_price,
                current_return=position.current_return,
                reason=f"보유 기간 초과: {hold_days}일 (최대 {max_hold_days}일)",
                timestamp=datetime.now().isoformat(),
                confidence=0.5
            )
        return None
    
    def _check_macd_bearish(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        """MACD 약세 전환 검사"""
        indicators = stock_data.get("indicators", {})
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)
        macd_histogram = indicators.get("macd_histogram", 0)
        
        # MACD 약세 전환 (MACD < Signal && Histogram < 0)
        if macd < macd_signal and macd_histogram < 0:
            signal_strength = abs(macd_histogram) * 0.6  # 히스토그램 크기에 비례
            
            return SellSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SellSignalType.MACD_BEARISH,
                signal_strength=min(signal_strength, 0.8),
                current_price=stock_data.get("current_price", position.current_price),
                entry_price=position.entry_price,
                current_return=position.current_return,
                reason=f"MACD 약세 전환: 히스토그램 {macd_histogram:.3f}",
                timestamp=datetime.now().isoformat(),
                confidence=0.65
            )
        return None

    # 추가: 호가 불균형/수급 악화 시 시장상황 신호
    def _check_market_condition_ex(self, position: PositionInfo, stock_data: Dict) -> Optional[SellSignal]:
        try:
            imb = stock_data.get("orderbook_imbalance")  # (Σask-Σbid)/(Σask+Σbid)
            foreign_net = None
            inv = stock_data.get("investor_flow")
            if isinstance(inv, dict):
                # 가능한 키에서 외국인 순매수 추정 (문서에 따라 키명 상이 가능)
                for k in inv.keys():
                    if str(k).lower().startswith("frgn") and "net" in str(k).lower():
                        try:
                            foreign_net = float(inv[k])
                            break
                        except Exception:
                            pass
            trigger = False
            reason = []
            if imb is not None and imb > 0.2:
                trigger = True
                reason.append(f"호가 불균형 {imb:.2f}")
            if foreign_net is not None and foreign_net < 0:
                trigger = True
                reason.append("외국인 순매도")
            if trigger:
                return SellSignal(
                    stock_code=position.stock_code,
                    stock_name=position.stock_name,
                    signal_type=SellSignalType.MARKET_CONDITION,
                    signal_strength=0.6,
                    current_price=stock_data.get("current_price", position.current_price),
                    entry_price=position.entry_price,
                    current_return=position.current_return,
                    reason=", ".join(reason),
                    timestamp=datetime.now().isoformat(),
                    confidence=0.6
                )
        except Exception:
            return None
        return None
    
    def execute_sell_order(self, sell_signal: SellSignal, quantity_ratio: float = 1.0) -> bool:
        """매도 주문 실행
        
        Args:
            sell_signal: 매도 신호
            quantity_ratio: 매도 비율 (0.0 - 1.0)
            
        Returns:
            bool: 매도 성공 여부
        """
        try:
            stock_code = sell_signal.stock_code
            if stock_code not in self._positions:
                self._logger.error(f"매도 실행 실패: 포지션 없음 - {stock_code}", exc_info=True)
                return False
            
            position = self._positions[stock_code]
            sell_quantity = int(position.quantity * quantity_ratio)
            
            if sell_quantity <= 0:
                self._logger.warning(f"매도 수량 없음: {stock_code}")
                return False
            
            # 실제 매도 주문 로직 (여기서는 로그만 출력)
            self._logger.info(f"💰 매도 주문 실행: {stock_code}")
            self._logger.info(f"   종목명: {sell_signal.stock_name}")
            self._logger.info(f"   매도사유: {sell_signal.reason}")
            self._logger.info(f"   수량: {sell_quantity:,}주 ({quantity_ratio*100:.0f}%)")
            self._logger.info(f"   가격: {sell_signal.current_price:,.0f}원")
            self._logger.info(f"   수익률: {sell_signal.current_return*100:.1f}%")
            self._logger.info(f"   신호강도: {sell_signal.signal_strength:.2f}")
            
            # 포지션 업데이트
            if quantity_ratio >= 1.0:
                # 전량 매도
                del self._positions[stock_code]
                self._logger.info(f"포지션 완전 정리: {stock_code}")
            else:
                # 부분 매도
                position.quantity -= sell_quantity
                self._logger.info(f"부분 매도 완료: {stock_code} - 잔여 {position.quantity:,}주")
            
            return True
            
        except Exception as e:
            self._logger.error(f"매도 주문 실행 오류: {e}", exc_info=True)
            return False
    
    def get_positions_summary(self) -> Dict[str, Any]:
        """포지션 요약 정보 반환"""
        try:
            if not self._positions:
                return {"total_positions": 0, "positions": []}
            
            positions_data = []
            total_investment = 0
            total_current_value = 0
            
            for position in self._positions.values():
                investment = position.entry_price * position.quantity
                current_value = position.current_price * position.quantity
                
                total_investment += investment
                total_current_value += current_value
                
                positions_data.append({
                    "stock_code": position.stock_code,
                    "stock_name": position.stock_name,
                    "quantity": position.quantity,
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "return_rate": position.current_return * 100,
                    "investment": investment,
                    "current_value": current_value,
                    "profit_loss": current_value - investment,
                    "hold_days": position.hold_days,
                    "stop_loss_price": position.stop_loss_price,
                    "trailing_stop_price": position.trailing_stop_price,
                    "take_profit_price": position.take_profit_price
                })
            
            total_return = (total_current_value - total_investment) / total_investment if total_investment > 0 else 0
            
            return {
                "total_positions": len(self._positions),
                "total_investment": total_investment,
                "total_current_value": total_current_value,
                "total_profit_loss": total_current_value - total_investment,
                "total_return_rate": total_return * 100,
                "positions": positions_data
            }
            
        except Exception as e:
            self._logger.error(f"포지션 요약 생성 오류: {e}", exc_info=True)
            return {"error": str(e)}