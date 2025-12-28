"""
실시간 모듈 테스트 설정

외부 의존성을 모킹하여 테스트 환경 구성
"""

import sys
from unittest.mock import Mock, MagicMock

# 외부 의존성 모킹 (임포트 전에 실행)
mock_modules = {
    'sqlalchemy': MagicMock(),
    'sqlalchemy.orm': MagicMock(),
    'sqlalchemy.ext.declarative': MagicMock(),
}

# 데이터베이스 모듈 모킹
mock_db = MagicMock()
mock_db.DatabaseSession = MagicMock()
mock_db.StockRepository = MagicMock()

mock_modules['core.database'] = mock_db
mock_modules['core.database.session'] = MagicMock()
mock_modules['core.database.models'] = MagicMock()

# 인디케이터 모듈 모킹
mock_indicators = MagicMock()
mock_indicators.RSI = MagicMock()
mock_indicators.MovingAverage = MagicMock()
mock_indicators.BollingerBands = MagicMock()

mock_modules['hantu_common'] = MagicMock()
mock_modules['hantu_common.indicators'] = mock_indicators

# 모듈 패치
for mod_name, mock_obj in mock_modules.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj
