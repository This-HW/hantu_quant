# 한투 퀀트 플러그인 개발 가이드

## 📋 개요

**작성일**: 2025-01-13  
**버전**: 1.0.0  
**목적**: 한투 퀀트 시스템용 플러그인 개발 가이드

## 🎯 플러그인 시스템 소개

한투 퀀트의 플러그인 시스템은 다음과 같은 특징을 제공합니다:

### 핵심 기능
- **동적 로딩**: 시스템 재시작 없이 플러그인 로딩/언로딩
- **인터페이스 기반**: 표준 인터페이스를 통한 일관된 개발
- **의존성 관리**: 플러그인 간 의존성 자동 해결
- **생명주기 관리**: 플러그인 초기화, 실행, 종료 관리

### 지원 플러그인 타입
1. **스크리닝 플러그인** (IScreeningModule): 종목 스크리닝 기능
2. **분석 플러그인** (IAnalysisModule): 종목 분석 기능
3. **학습 플러그인** (ILearningModule): AI 학습 기능
4. **트레이딩 플러그인** (ITradingModule): 트레이딩 기능

## 🏗️ 플러그인 개발 기본 구조

### 1. 기본 디렉토리 구조
```
plugins/
├── your_plugin_name/
│   ├── __init__.py
│   ├── plugin.py          # 메인 플러그인 클래스
│   ├── config.json        # 플러그인 설정
│   ├── requirements.txt   # 의존성 패키지
│   ├── README.md         # 플러그인 문서
│   └── tests/            # 테스트 코드
│       └── test_plugin.py
```

### 2. 플러그인 메타데이터
```json
{
  "name": "your_plugin_name",
  "version": "1.0.0",
  "description": "플러그인 설명",
  "author": "개발자 이름",
  "dependencies": ["pandas", "numpy"],
  "plugin_dependencies": ["api_client"],
  "supported_interfaces": ["IScreeningModule"],
  "config_schema": {
    "enabled": {"type": "boolean", "default": true},
    "threshold": {"type": "number", "default": 0.5}
  }
}
```

## 🔧 스크리닝 플러그인 개발

### 1. 기본 스크리닝 플러그인 구조

```python
# plugins/fundamental_screener/plugin.py
from typing import Dict, List, Any
import json
import os
from core.interfaces.i_module import IModule
from core.interfaces.i_screening import IScreeningModule
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class FundamentalScreener(IScreeningModule):
    """재무 기반 종목 스크리닝 플러그인"""
    
    def __init__(self):
        """플러그인 초기화"""
        self.config = {}
        self.initialized = False
        
    def get_module_info(self) -> Dict[str, Any]:
        """모듈 정보 반환"""
        return {
            'name': 'fundamental_screener',
            'version': '1.0.0',
            'description': '재무 지표 기반 종목 스크리닝',
            'author': 'Hantu Quant Team',
            'type': 'screening'
        }
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """플러그인 초기화"""
        try:
            self.config = config
            
            # 설정 검증
            required_keys = ['roe_min', 'per_max', 'pbr_max']
            for key in required_keys:
                if key not in config:
                    logger.error(f"필수 설정 키가 없습니다: {key}")
                    return False
            
            # 리소스 초기화
            self._initialize_resources()
            
            self.initialized = True
            logger.info("FundamentalScreener 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"플러그인 초기화 실패: {e}")
            return False
    
    def shutdown(self) -> bool:
        """플러그인 종료"""
        try:
            # 리소스 정리
            self._cleanup_resources()
            
            self.initialized = False
            logger.info("FundamentalScreener 종료 완료")
            return True
            
        except Exception as e:
            logger.error(f"플러그인 종료 실패: {e}")
            return False
    
    def get_dependencies(self) -> List[str]:
        """의존성 모듈 목록 반환"""
        return ['api_client', 'data_processor']
    
    def get_api_endpoints(self) -> Dict[str, callable]:
        """API 엔드포인트 반환"""
        return {
            'screen_stocks': self.screen_stocks,
            'get_screening_criteria': self.get_screening_criteria,
            'update_screening_criteria': self.update_screening_criteria
        }
    
    def screen_stocks(self, stock_list: List[str]) -> List[Dict]:
        """종목 스크리닝 실행"""
        if not self.initialized:
            raise RuntimeError("플러그인이 초기화되지 않았습니다")
        
        results = []
        for stock_code in stock_list:
            try:
                # 종목 데이터 가져오기
                stock_data = self._get_stock_data(stock_code)
                
                # 스크리닝 로직 실행
                screening_result = self._evaluate_fundamental(stock_data)
                
                results.append({
                    'stock_code': stock_code,
                    'passed': screening_result['passed'],
                    'score': screening_result['score'],
                    'details': screening_result['details']
                })
                
            except Exception as e:
                logger.error(f"종목 {stock_code} 스크리닝 실패: {e}")
                results.append({
                    'stock_code': stock_code,
                    'passed': False,
                    'score': 0,
                    'error': str(e)
                })
        
        return results
    
    def get_screening_criteria(self) -> Dict:
        """스크리닝 기준 반환"""
        return {
            'roe_min': self.config.get('roe_min', 15.0),
            'per_max': self.config.get('per_max', 20.0),
            'pbr_max': self.config.get('pbr_max', 1.5),
            'debt_ratio_max': self.config.get('debt_ratio_max', 200.0)
        }
    
    def update_screening_criteria(self, criteria: Dict) -> bool:
        """스크리닝 기준 업데이트"""
        try:
            # 기준 검증
            if not self._validate_criteria(criteria):
                return False
            
            # 설정 업데이트
            self.config.update(criteria)
            
            logger.info(f"스크리닝 기준 업데이트 완료: {criteria}")
            return True
            
        except Exception as e:
            logger.error(f"스크리닝 기준 업데이트 실패: {e}")
            return False
    
    def _initialize_resources(self):
        """리소스 초기화"""
        # 필요한 리소스 초기화 (DB 연결, 캐시 등)
        pass
    
    def _cleanup_resources(self):
        """리소스 정리"""
        # 리소스 정리 (연결 해제, 캐시 정리 등)
        pass
    
    def _get_stock_data(self, stock_code: str) -> Dict:
        """종목 데이터 가져오기"""
        # 실제 구현에서는 API 호출
        return {
            'code': stock_code,
            'roe': 18.5,
            'per': 12.3,
            'pbr': 1.2,
            'debt_ratio': 150.0
        }
    
    def _evaluate_fundamental(self, stock_data: Dict) -> Dict:
        """재무 지표 평가"""
        criteria = self.get_screening_criteria()
        
        # 각 지표별 점수 계산
        roe_score = self._calculate_roe_score(stock_data['roe'], criteria['roe_min'])
        per_score = self._calculate_per_score(stock_data['per'], criteria['per_max'])
        pbr_score = self._calculate_pbr_score(stock_data['pbr'], criteria['pbr_max'])
        debt_score = self._calculate_debt_score(stock_data['debt_ratio'], criteria['debt_ratio_max'])
        
        # 종합 점수 계산
        total_score = (roe_score * 0.3 + per_score * 0.25 + 
                      pbr_score * 0.25 + debt_score * 0.2)
        
        # 통과 여부 판단
        passed = total_score >= 70.0
        
        return {
            'passed': passed,
            'score': total_score,
            'details': {
                'roe_score': roe_score,
                'per_score': per_score,
                'pbr_score': pbr_score,
                'debt_score': debt_score
            }
        }
    
    def _calculate_roe_score(self, roe: float, min_roe: float) -> float:
        """ROE 점수 계산"""
        if roe >= min_roe:
            return min(100, (roe / min_roe) * 80)
        else:
            return (roe / min_roe) * 50
    
    def _calculate_per_score(self, per: float, max_per: float) -> float:
        """PER 점수 계산"""
        if per <= max_per:
            return 100 - (per / max_per) * 20
        else:
            return max(0, 50 - (per - max_per) * 5)
    
    def _calculate_pbr_score(self, pbr: float, max_pbr: float) -> float:
        """PBR 점수 계산"""
        if pbr <= max_pbr:
            return 100 - (pbr / max_pbr) * 20
        else:
            return max(0, 50 - (pbr - max_pbr) * 10)
    
    def _calculate_debt_score(self, debt_ratio: float, max_debt: float) -> float:
        """부채비율 점수 계산"""
        if debt_ratio <= max_debt:
            return 100 - (debt_ratio / max_debt) * 30
        else:
            return max(0, 30 - (debt_ratio - max_debt) * 0.1)
    
    def _validate_criteria(self, criteria: Dict) -> bool:
        """기준 검증"""
        required_keys = ['roe_min', 'per_max', 'pbr_max', 'debt_ratio_max']
        
        for key in required_keys:
            if key not in criteria:
                logger.error(f"필수 기준이 없습니다: {key}")
                return False
            
            if not isinstance(criteria[key], (int, float)):
                logger.error(f"기준값은 숫자여야 합니다: {key}")
                return False
        
        return True

# 플러그인 클래스 반환 함수
def get_plugin_class():
    """플러그인 클래스 반환"""
    return FundamentalScreener
```

### 2. 플러그인 설정 파일

```json
{
  "name": "fundamental_screener",
  "version": "1.0.0",
  "description": "재무 지표 기반 종목 스크리닝 플러그인",
  "author": "Hantu Quant Team",
  "dependencies": ["pandas>=1.3.0", "numpy>=1.21.0"],
  "plugin_dependencies": ["api_client"],
  "supported_interfaces": ["IScreeningModule"],
  "config_schema": {
    "roe_min": {"type": "number", "default": 15.0, "description": "최소 ROE (%)"},
    "per_max": {"type": "number", "default": 20.0, "description": "최대 PER"},
    "pbr_max": {"type": "number", "default": 1.5, "description": "최대 PBR"},
    "debt_ratio_max": {"type": "number", "default": 200.0, "description": "최대 부채비율 (%)"}
  }
}
```

## 🧪 분석 플러그인 개발

### 1. 기본 분석 플러그인 구조

```python
# plugins/technical_analyzer/plugin.py
from typing import Dict, List, Any
import pandas as pd
import numpy as np
from core.interfaces.i_module import IModule
from core.interfaces.i_analysis import IAnalysisModule
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class TechnicalAnalyzer(IAnalysisModule):
    """기술적 분석 플러그인"""
    
    def __init__(self):
        self.config = {}
        self.initialized = False
        
    def get_module_info(self) -> Dict[str, Any]:
        return {
            'name': 'technical_analyzer',
            'version': '1.0.0',
            'description': '기술적 지표 기반 종목 분석',
            'author': 'Hantu Quant Team',
            'type': 'analysis'
        }
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        try:
            self.config = config
            self.initialized = True
            logger.info("TechnicalAnalyzer 초기화 완료")
            return True
        except Exception as e:
            logger.error(f"초기화 실패: {e}")
            return False
    
    def shutdown(self) -> bool:
        try:
            self.initialized = False
            logger.info("TechnicalAnalyzer 종료 완료")
            return True
        except Exception as e:
            logger.error(f"종료 실패: {e}")
            return False
    
    def get_dependencies(self) -> List[str]:
        return ['api_client']
    
    def get_api_endpoints(self) -> Dict[str, callable]:
        return {
            'analyze_stock': self.analyze_stock,
            'analyze_multiple_stocks': self.analyze_multiple_stocks,
            'get_analysis_indicators': self.get_analysis_indicators
        }
    
    def analyze_stock(self, stock_data: Dict) -> Dict:
        """단일 종목 분석"""
        if not self.initialized:
            raise RuntimeError("플러그인이 초기화되지 않았습니다")
        
        try:
            # 기술적 지표 계산
            indicators = self._calculate_technical_indicators(stock_data)
            
            # 분석 결과 생성
            analysis_result = self._generate_analysis_result(indicators)
            
            return {
                'stock_code': stock_data['code'],
                'analysis_date': stock_data.get('date', ''),
                'indicators': indicators,
                'signals': analysis_result['signals'],
                'recommendation': analysis_result['recommendation'],
                'confidence': analysis_result['confidence']
            }
            
        except Exception as e:
            logger.error(f"종목 분석 실패: {e}")
            return {
                'stock_code': stock_data['code'],
                'error': str(e)
            }
    
    def analyze_multiple_stocks(self, stock_list: List[Dict]) -> List[Dict]:
        """복수 종목 분석"""
        results = []
        for stock_data in stock_list:
            result = self.analyze_stock(stock_data)
            results.append(result)
        return results
    
    def get_analysis_indicators(self) -> List[str]:
        """분석 지표 목록 반환"""
        return [
            'RSI', 'MACD', 'Bollinger Bands', 'Moving Averages',
            'Stochastic', 'CCI', 'Volume Analysis'
        ]
    
    def _calculate_technical_indicators(self, stock_data: Dict) -> Dict:
        """기술적 지표 계산"""
        prices = stock_data.get('prices', [])
        volumes = stock_data.get('volumes', [])
        
        if not prices:
            return {}
        
        # 가격 데이터를 Series로 변환
        price_series = pd.Series(prices)
        volume_series = pd.Series(volumes) if volumes else None
        
        indicators = {}
        
        # RSI 계산
        indicators['rsi'] = self._calculate_rsi(price_series)
        
        # MACD 계산
        indicators['macd'] = self._calculate_macd(price_series)
        
        # 볼린저 밴드 계산
        indicators['bollinger'] = self._calculate_bollinger_bands(price_series)
        
        # 이동평균 계산
        indicators['moving_averages'] = self._calculate_moving_averages(price_series)
        
        # 스토캐스틱 계산
        if len(prices) > 14:
            indicators['stochastic'] = self._calculate_stochastic(stock_data)
        
        # 거래량 분석
        if volume_series is not None:
            indicators['volume_analysis'] = self._analyze_volume(price_series, volume_series)
        
        return indicators
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """MACD 계산"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal).mean()
        histogram = macd - signal_line
        
        return {
            'macd': macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0.0,
            'signal': signal_line.iloc[-1] if not pd.isna(signal_line.iloc[-1]) else 0.0,
            'histogram': histogram.iloc[-1] if not pd.isna(histogram.iloc[-1]) else 0.0
        }
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict:
        """볼린저 밴드 계산"""
        rolling_mean = prices.rolling(window=period).mean()
        rolling_std = prices.rolling(window=period).std()
        upper_band = rolling_mean + (rolling_std * std_dev)
        lower_band = rolling_mean - (rolling_std * std_dev)
        
        current_price = prices.iloc[-1]
        return {
            'upper_band': upper_band.iloc[-1] if not pd.isna(upper_band.iloc[-1]) else current_price * 1.1,
            'middle_band': rolling_mean.iloc[-1] if not pd.isna(rolling_mean.iloc[-1]) else current_price,
            'lower_band': lower_band.iloc[-1] if not pd.isna(lower_band.iloc[-1]) else current_price * 0.9,
            'position': self._get_bollinger_position(current_price, upper_band.iloc[-1], lower_band.iloc[-1])
        }
    
    def _calculate_moving_averages(self, prices: pd.Series) -> Dict:
        """이동평균 계산"""
        return {
            'ma5': prices.rolling(window=5).mean().iloc[-1] if len(prices) >= 5 else prices.iloc[-1],
            'ma20': prices.rolling(window=20).mean().iloc[-1] if len(prices) >= 20 else prices.iloc[-1],
            'ma60': prices.rolling(window=60).mean().iloc[-1] if len(prices) >= 60 else prices.iloc[-1]
        }
    
    def _calculate_stochastic(self, stock_data: Dict, k_period: int = 14, d_period: int = 3) -> Dict:
        """스토캐스틱 계산"""
        highs = pd.Series(stock_data.get('highs', []))
        lows = pd.Series(stock_data.get('lows', []))
        closes = pd.Series(stock_data.get('prices', []))
        
        lowest_low = lows.rolling(window=k_period).min()
        highest_high = highs.rolling(window=k_period).max()
        
        k_percent = 100 * ((closes - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'k_percent': k_percent.iloc[-1] if not pd.isna(k_percent.iloc[-1]) else 50.0,
            'd_percent': d_percent.iloc[-1] if not pd.isna(d_percent.iloc[-1]) else 50.0
        }
    
    def _analyze_volume(self, prices: pd.Series, volumes: pd.Series) -> Dict:
        """거래량 분석"""
        volume_ma = volumes.rolling(window=20).mean()
        volume_ratio = volumes.iloc[-1] / volume_ma.iloc[-1] if not pd.isna(volume_ma.iloc[-1]) else 1.0
        
        # 가격-거래량 상관관계
        price_change = prices.pct_change()
        volume_change = volumes.pct_change()
        correlation = price_change.corr(volume_change)
        
        return {
            'volume_ratio': volume_ratio,
            'volume_trend': 'increasing' if volume_ratio > 1.5 else 'normal',
            'price_volume_correlation': correlation if not pd.isna(correlation) else 0.0
        }
    
    def _get_bollinger_position(self, price: float, upper: float, lower: float) -> str:
        """볼린저 밴드 내 위치 계산"""
        if price > upper:
            return 'above_upper'
        elif price < lower:
            return 'below_lower'
        else:
            return 'within_bands'
    
    def _generate_analysis_result(self, indicators: Dict) -> Dict:
        """분석 결과 생성"""
        signals = []
        confidence = 0.0
        
        # RSI 신호
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 30:
                signals.append({'type': 'buy', 'indicator': 'RSI', 'strength': 'strong'})
                confidence += 0.2
            elif rsi > 70:
                signals.append({'type': 'sell', 'indicator': 'RSI', 'strength': 'strong'})
                confidence += 0.2
        
        # MACD 신호
        if 'macd' in indicators:
            macd_data = indicators['macd']
            if macd_data['macd'] > macd_data['signal']:
                signals.append({'type': 'buy', 'indicator': 'MACD', 'strength': 'medium'})
                confidence += 0.15
            else:
                signals.append({'type': 'sell', 'indicator': 'MACD', 'strength': 'medium'})
                confidence += 0.15
        
        # 볼린저 밴드 신호
        if 'bollinger' in indicators:
            position = indicators['bollinger']['position']
            if position == 'below_lower':
                signals.append({'type': 'buy', 'indicator': 'Bollinger', 'strength': 'medium'})
                confidence += 0.15
            elif position == 'above_upper':
                signals.append({'type': 'sell', 'indicator': 'Bollinger', 'strength': 'medium'})
                confidence += 0.15
        
        # 추천 결정
        buy_signals = len([s for s in signals if s['type'] == 'buy'])
        sell_signals = len([s for s in signals if s['type'] == 'sell'])
        
        if buy_signals > sell_signals:
            recommendation = 'BUY'
        elif sell_signals > buy_signals:
            recommendation = 'SELL'
        else:
            recommendation = 'HOLD'
        
        return {
            'signals': signals,
            'recommendation': recommendation,
            'confidence': min(confidence, 1.0)
        }

# 플러그인 클래스 반환 함수
def get_plugin_class():
    return TechnicalAnalyzer
```

## 🧪 플러그인 테스트

### 1. 기본 테스트 구조

```python
# plugins/fundamental_screener/tests/test_plugin.py
import unittest
import sys
import os

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from plugins.fundamental_screener.plugin import FundamentalScreener

class TestFundamentalScreener(unittest.TestCase):
    """FundamentalScreener 플러그인 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.plugin = FundamentalScreener()
        self.config = {
            'roe_min': 15.0,
            'per_max': 20.0,
            'pbr_max': 1.5,
            'debt_ratio_max': 200.0
        }
    
    def test_plugin_initialization(self):
        """플러그인 초기화 테스트"""
        result = self.plugin.initialize(self.config)
        self.assertTrue(result)
        self.assertTrue(self.plugin.initialized)
    
    def test_plugin_info(self):
        """플러그인 정보 테스트"""
        info = self.plugin.get_module_info()
        self.assertEqual(info['name'], 'fundamental_screener')
        self.assertEqual(info['type'], 'screening')
    
    def test_dependencies(self):
        """의존성 테스트"""
        dependencies = self.plugin.get_dependencies()
        self.assertIn('api_client', dependencies)
    
    def test_stock_screening(self):
        """종목 스크리닝 테스트"""
        # 플러그인 초기화
        self.plugin.initialize(self.config)
        
        # 테스트 데이터
        stock_list = ['005930', '000660']
        
        # 스크리닝 실행
        results = self.plugin.screen_stocks(stock_list)
        
        # 결과 검증
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertIn('stock_code', result)
            self.assertIn('passed', result)
            self.assertIn('score', result)
    
    def test_criteria_update(self):
        """기준 업데이트 테스트"""
        self.plugin.initialize(self.config)
        
        new_criteria = {'roe_min': 20.0}
        result = self.plugin.update_screening_criteria(new_criteria)
        
        self.assertTrue(result)
        self.assertEqual(self.plugin.config['roe_min'], 20.0)
    
    def test_plugin_shutdown(self):
        """플러그인 종료 테스트"""
        self.plugin.initialize(self.config)
        result = self.plugin.shutdown()
        
        self.assertTrue(result)
        self.assertFalse(self.plugin.initialized)

if __name__ == '__main__':
    unittest.main()
```

### 2. 테스트 실행 방법

```bash
# 단일 플러그인 테스트
python -m pytest plugins/fundamental_screener/tests/test_plugin.py -v

# 모든 플러그인 테스트
python -m pytest plugins/*/tests/ -v

# 커버리지 테스트
python -m pytest plugins/*/tests/ --cov=plugins --cov-report=html
```

## 📦 플러그인 패키징 및 배포

### 1. 패키지 생성

```python
# 패키지 생성 스크립트
from core.framework.package_manager import PackageManager

package_manager = PackageManager()

# 플러그인 패키지 생성
package_key = package_manager.create_package(
    module_name="fundamental_screener",
    version="1.0.0",
    dependencies=["pandas>=1.3.0", "numpy>=1.21.0"]
)

print(f"패키지 생성 완료: {package_key}")
```

### 2. 플러그인 설치

```python
# 플러그인 설치 스크립트
from core.framework.plugin_loader import PluginLoader

loader = PluginLoader()

# 플러그인 설치
loader.install_plugin("fundamental_screener", "1.0.0")

# 플러그인 로드
plugin = loader.load_plugin("fundamental_screener", config={
    'roe_min': 15.0,
    'per_max': 20.0,
    'pbr_max': 1.5,
    'debt_ratio_max': 200.0
})
```

## 🛠️ 고급 기능

### 1. 플러그인 간 통신

```python
# 이벤트 기반 통신
from core.framework.event_bus import EventBus

class AdvancedPlugin(IScreeningModule):
    def __init__(self):
        super().__init__()
        self.event_bus = EventBus()
        
    def initialize(self, config):
        # 이벤트 구독
        self.event_bus.subscribe('market_data_updated', self.on_market_data_updated)
        return super().initialize(config)
    
    def on_market_data_updated(self, data):
        """시장 데이터 업데이트 이벤트 처리"""
        # 업데이트된 데이터로 재분석
        self.refresh_analysis(data)
    
    def screen_stocks(self, stock_list):
        results = super().screen_stocks(stock_list)
        
        # 결과 이벤트 발행
        self.event_bus.publish('screening_completed', {
            'plugin': self.get_module_info()['name'],
            'results': results
        })
        
        return results
```

### 2. 플러그인 설정 UI

```python
# 동적 설정 인터페이스
class ConfigurablePlugin(IScreeningModule):
    def get_config_ui(self):
        """설정 UI 정의 반환"""
        return {
            'title': '재무 스크리닝 설정',
            'fields': [
                {
                    'name': 'roe_min',
                    'label': '최소 ROE (%)',
                    'type': 'number',
                    'min': 0,
                    'max': 100,
                    'default': 15.0
                },
                {
                    'name': 'per_max',
                    'label': '최대 PER',
                    'type': 'number',
                    'min': 1,
                    'max': 100,
                    'default': 20.0
                }
            ]
        }
```

## 📝 베스트 프랙티스

### 1. 코딩 가이드라인
- **에러 처리**: 모든 외부 호출에 try-catch 구문 사용
- **로깅**: 중요한 작업에 대한 로그 기록
- **설정 검증**: 초기화 시 설정값 검증
- **리소스 관리**: 초기화/종료 시 리소스 적절히 관리

### 2. 성능 최적화
- **지연 로딩**: 필요할 때만 리소스 로드
- **캐싱**: 반복적인 계산 결과 캐시
- **병렬 처리**: CPU 집약적 작업 병렬화
- **메모리 관리**: 대용량 데이터 처리 시 메모리 관리

### 3. 보안 고려사항
- **입력 검증**: 모든 외부 입력 검증
- **권한 관리**: 필요한 권한만 요청
- **민감 정보**: 설정 파일에 민감 정보 하드코딩 금지
- **API 키**: 환경 변수 또는 설정 파일 사용

## 🔍 디버깅 및 문제 해결

### 1. 로그 활용
```python
# 로그 레벨 설정
import logging
logging.basicConfig(level=logging.DEBUG)

# 플러그인 로그
logger = get_logger(__name__)
logger.debug("디버그 메시지")
logger.info("정보 메시지")
logger.warning("경고 메시지")
logger.error("오류 메시지")
```

### 2. 일반적인 문제 해결
- **초기화 실패**: 설정값 및 의존성 확인
- **성능 문제**: 프로파일링 도구 사용
- **메모리 누수**: 리소스 정리 코드 확인
- **호환성 문제**: 인터페이스 구현 확인

---

이 가이드를 참고하여 한투 퀀트 시스템에 최적화된 플러그인을 개발하세요! 