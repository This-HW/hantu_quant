"""섹터 모멘텀 계산기

섹터 ETF 수익률 기반으로 모멘텀을 계산합니다.

Feature: B3 - 시장 분석 강화
"""

from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from scipy.stats import linregress

from core.utils.log_utils import get_logger
from core.api.market_data_client import PyKRXClient
from core.api.redis_client import cache_with_ttl


class SectorMomentumCalculator:
    """섹터 모멘텀 계산기"""

    def __init__(self):
        self._logger = get_logger(__name__)
        self._client = PyKRXClient()
        self._config = self._load_config()

        # Config에서 섹터 ETF 매핑 로드
        self.sector_etf_map = self._config.get("sector_etf_map", self._get_default_sector_etf_map())
        self._logger.info(f"섹터 ETF 매핑 로드 완료: {len(self.sector_etf_map)}개 섹터")

    def _load_config(self) -> dict:
        """Phase2 Config 로드"""
        try:
            import yaml
            from pathlib import Path

            config_path = Path(__file__).parent.parent.parent / "config" / "phase2.yaml"
            if not config_path.exists():
                self._logger.warning(f"Config 파일 없음: {config_path}. 하드코딩 기본값 사용")
                return self._get_default_config()

            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            self._logger.debug("Phase2 config 로드 완료")
            return config

        except Exception as e:
            self._logger.error(f"Config 로드 실패: {e}. 하드코딩 기본값 사용", exc_info=True)
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """하드코딩 기본 Config (파일 로드 실패 시)"""
        return {
            "sector_etf_map": self._get_default_sector_etf_map(),
            "api_fallback": {
                "sector_momentum_neutral": 50.0,
            }
        }

    def _get_default_sector_etf_map(self) -> dict:
        """하드코딩 기본 섹터 ETF 매핑 (Config 로드 실패 시)"""
        return {
            "IT": "139270",          # TIGER 200IT
            "금융": "139260",        # TIGER 200금융
            "건설": "102780",        # KODEX 건설
            "에너지화학": "117680",  # TIGER 에너지화학
            "철강소재": "117700",    # TIGER 철강소재
            "자동차": "091180",      # KODEX 자동차
            "반도체": "091160",      # KODEX 반도체
            "바이오": "091230",      # TIGER 헬스케어
            "운송": "140700",        # KODEX 운송
            "유통": "117460",        # TIGER 유통
            "미디어통신": "091220",  # KODEX 미디어통신
        }

    @cache_with_ttl(ttl=600, key_prefix="sector_momentum")
    def calculate_momentum(self, sector: str) -> float:
        """섹터 모멘텀 계산 (0~100 점수)

        Args:
            sector: 섹터명 (예: "IT", "금융")

        Returns:
            모멘텀 점수 (0~100)
        """
        etf_ticker = self.sector_etf_map.get(sector)

        if not etf_ticker:
            neutral_value = self._config.get("api_fallback", {}).get("sector_momentum_neutral", 50.0)
            self._logger.warning(f"섹터 ETF 매핑 없음: {sector}. 중립값({neutral_value}) 반환")
            return neutral_value

        # PyKRX로 ETF 가격 조회
        df = self._client.get_sector_etf_prices(etf_ticker, period_days=60)

        if df is None or len(df) < 10:
            self._logger.warning(f"섹터 ETF 데이터 부족: {sector} ({etf_ticker}). 감시 리스트 기반 폴백")
            # 폴백: 감시 리스트 기반 계산
            return self._calculate_from_watchlist(sector)

        # 선형 회귀로 추세 계산
        try:
            closes = df['종가'].values
            x = np.arange(len(closes))
            slope, _, r_value, _, _ = linregress(x, closes)

            # 모멘텀 점수 계산 (slope를 0~100으로 정규화)
            # slope > 0: 상승 추세, slope < 0: 하락 추세
            momentum_raw = slope * 100 / np.mean(closes)  # 일간 변화율 기준

            # 0~100 범위로 스케일링
            momentum_score = 50.0 + (momentum_raw * 10)  # -5% ~ +5% → 0 ~ 100
            momentum_score = np.clip(momentum_score, 0.0, 100.0)

            self._logger.info(f"섹터 모멘텀 계산 완료: {sector}={momentum_score:.2f} (slope={slope:.4f}, r²={r_value**2:.3f})")
            return float(momentum_score)

        except Exception as e:
            self._logger.error(f"섹터 모멘텀 계산 실패: {sector}: {e}", exc_info=True)
            neutral_value = self._config.get("api_fallback", {}).get("sector_momentum_neutral", 50.0)
            return neutral_value

    def _calculate_from_watchlist(self, sector: str) -> float:
        """감시 리스트 기반 섹터 모멘텀 계산 (폴백)

        Args:
            sector: 섹터명

        Returns:
            모멘텀 점수 (0~100)
        """
        try:
            from core.watchlist.watchlist_manager import WatchlistManager

            wl_manager = WatchlistManager()
            stocks = wl_manager.list_stocks(p_sector=sector)

            if len(stocks) < 3:
                neutral_value = self._config.get("api_fallback", {}).get("sector_momentum_neutral", 50.0)
                self._logger.warning(f"감시 리스트 섹터 종목 부족: {sector} ({len(stocks)}개). 중립값({neutral_value}) 반환")
                return neutral_value

            # 각 종목의 최근 수익률 평균 계산
            # TODO(P2): 실제 수익률 계산 구현 필요 (현재는 중립값)
            neutral_value = self._config.get("api_fallback", {}).get("sector_momentum_neutral", 50.0)
            self._logger.warning(f"감시 리스트 기반 모멘텀 계산 미구현: {sector}. 중립값({neutral_value}) 반환")
            return neutral_value

        except Exception as e:
            self._logger.error(f"감시 리스트 기반 계산 실패: {sector}: {e}", exc_info=True)
            neutral_value = self._config.get("api_fallback", {}).get("sector_momentum_neutral", 50.0)
            return neutral_value
