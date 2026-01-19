"""
APIConfig 클래스 테스트 모듈
"""

import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from core.config.api_config import APIConfig
from core.config import settings

class TestAPIConfig(unittest.TestCase):
    """APIConfig 클래스 테스트"""
    
    def setUp(self):
        """테스트 전 설정"""
        # 테스트용 토큰 파일 경로 생성
        test_token_dir = Path('test_tokens')
        self.test_token_file = test_token_dir / 'test_token.json'
        
        # 싱글톤 인스턴스 초기화
        APIConfig._instance = None
        
        # 설정 패치
        self.app_key = "test_app_key"
        self.app_secret = "test_app_secret"
        self.patcher_settings = patch.multiple(
            settings,
            APP_KEY=self.app_key,
            APP_SECRET=self.app_secret,
            ACCOUNT_NUMBER="1234567890",
            ACCOUNT_PROD_CODE="01",
            SERVER="virtual",
            RATE_LIMIT_PER_SEC=5
        )
        self.patcher_settings.start()
    
    def tearDown(self):
        """테스트 후 정리"""
        # 패치 종료
        self.patcher_settings.stop()
        
        # 싱글톤 인스턴스 초기화
        APIConfig._instance = None
    
    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        # 첫 번째 인스턴스 생성
        config1 = APIConfig()
        
        # 두 번째 인스턴스 생성
        config2 = APIConfig()
        
        # 동일한 인스턴스인지 확인
        self.assertIs(config1, config2)
        
    @patch('core.config.api_config.datetime')
    def test_load_token(self, mock_datetime):
        """토큰 로드 테스트"""
        # 현재 시간 설정
        now = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat.return_value = now + timedelta(hours=1)
        
        # 테스트용 토큰 데이터
        token_data = {
            'access_token': 'test_token',
            'expired_at': (now + timedelta(hours=1)).isoformat()
        }
        
        # APIConfig 인스턴스 생성
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(token_data))):
                config = APIConfig()
                
                # _token_file을 패치하여 테스트 파일로 설정
                config._token_file = self.test_token_file
                
                # 토큰 로드 메서드 직접 호출
                config._load_token()
                
                # 토큰이 올바르게 로드되었는지 확인
                self.assertEqual(config.access_token, 'test_token')
                self.assertEqual(config.token_expired_at, now + timedelta(hours=1))
    
    @patch('core.config.api_config.requests.post')
    @patch('core.config.api_config.datetime')
    def test_refresh_token(self, mock_datetime, mock_post):
        """토큰 갱신 테스트"""
        # 현재 시간 설정
        now = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now
        
        # POST 요청 응답 설정
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_test_token',
            'expires_in': 86400
        }
        mock_post.return_value = mock_response
        
        # APIConfig 인스턴스 생성
        with patch('builtins.open', mock_open()):
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.mkdir'):
                    config = APIConfig()
                    config._token_file = self.test_token_file
                    
                    # 토큰 갱신
                    with patch('json.dump') as mock_json_dump:
                        result = config.refresh_token()
                        
                        # 갱신 결과 확인
                        self.assertTrue(result)
                        self.assertEqual(config.access_token, 'new_test_token')
                        self.assertEqual(config.token_expired_at, now + timedelta(seconds=86400))
    
    def test_validate_token(self):
        """토큰 유효성 검사 테스트"""
        # APIConfig 인스턴스 생성
        config = APIConfig()
        
        # 토큰이 없는 경우
        config.access_token = None
        config.token_expired_at = None
        self.assertFalse(config.validate_token())
        
        # 토큰이 만료된 경우
        now = datetime.now()
        config.access_token = "test_token"
        config.token_expired_at = now - timedelta(minutes=5)
        self.assertFalse(config.validate_token())
        
        # 토큰이 곧 만료되는 경우
        config.token_expired_at = now + timedelta(minutes=5)
        self.assertFalse(config.validate_token())
        
        # 토큰이 유효한 경우
        config.token_expired_at = now + timedelta(minutes=30)
        self.assertTrue(config.validate_token())
    
    def test_get_headers(self):
        """헤더 생성 테스트"""
        # APIConfig 인스턴스 생성
        config = APIConfig()
        config.access_token = "test_token"
        
        # 기본 헤더 (Content-Type 포함)
        headers = config.get_headers()
        self.assertEqual(headers['authorization'], 'Bearer test_token')
        self.assertEqual(headers['appkey'], self.app_key)
        self.assertEqual(headers['appsecret'], self.app_secret)
        self.assertEqual(headers['content-type'], 'application/json; charset=utf-8')
        
        # Content-Type 제외
        headers = config.get_headers(include_content_type=False)
        self.assertNotIn('content-type', headers)
    
    @patch('core.config.api_config.time.time')
    @patch('core.config.api_config.time.sleep')
    def test_apply_rate_limit(self, mock_sleep, mock_time):
        """API 호출 제한 테스트"""
        # APIConfig 인스턴스 생성
        config = APIConfig()
        
        # 시간 패치 (1초마다 0.1초씩 증가)
        times = [1000.0 + (i * 0.1) for i in range(10)]
        mock_time.side_effect = times
        
        # 첫 번째 요청 (제한 없음)
        config.apply_rate_limit()
        mock_sleep.assert_not_called()
        self.assertEqual(len(config.request_times), 1)
        
        # 두 번째 ~ 다섯 번째 요청 (제한 없음)
        for _ in range(4):
            config.apply_rate_limit()
        mock_sleep.assert_not_called()
        self.assertEqual(len(config.request_times), 5)
        
        # 여섯 번째 요청 (제한 도달, 대기 필요)
        config.apply_rate_limit()
        mock_sleep.assert_called_once()
        
    def test_ensure_valid_token(self):
        """토큰 유효성 보장 테스트"""
        # APIConfig 인스턴스 생성
        config = APIConfig()
        
        # validate_token 패치
        with patch.object(config, 'validate_token') as mock_validate:
            # refresh_token 패치
            with patch.object(config, 'refresh_token') as mock_refresh:
                # 토큰이 유효한 경우
                mock_validate.return_value = True
                mock_refresh.return_value = True
                
                result = config.ensure_valid_token()
                self.assertTrue(result)
                mock_validate.assert_called_once()
                mock_refresh.assert_not_called()
                
                # 재설정
                mock_validate.reset_mock()
                mock_refresh.reset_mock()
                
                # 토큰이 유효하지 않은 경우
                mock_validate.return_value = False
                mock_refresh.return_value = True
                
                result = config.ensure_valid_token()
                self.assertTrue(result)
                mock_validate.assert_called_once()
                mock_refresh.assert_called_once()
    
    @patch('pathlib.Path.unlink')
    @patch('pathlib.Path.exists')
    def test_clear_token(self, mock_exists, mock_unlink):
        """토큰 초기화 테스트"""
        # 토큰 파일 존재
        mock_exists.return_value = True
        
        # APIConfig 인스턴스 생성
        config = APIConfig()
        config._token_file = self.test_token_file
        config.access_token = "test_token"
        config.token_expired_at = datetime.now() + timedelta(hours=1)
        
        # 토큰 초기화
        config.clear_token()
        
        # 토큰이 초기화되었는지 확인
        self.assertIsNone(config.access_token)
        self.assertIsNone(config.token_expired_at)
        mock_unlink.assert_called_once()

if __name__ == '__main__':
    unittest.main() 