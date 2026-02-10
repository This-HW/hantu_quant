"""
API configuration management module.

한국투자증권 KIS API 공식 규정 준수:
- 접근 토큰: 1일 1회 발급 원칙, 1분당 1회 재발급 제한
- WebSocket: 별도 접속키(approval_key) 발급 필요
"""

import json
import os
import ssl
import time
import fcntl
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from . import settings
from core.utils.log_utils import get_logger

# 글로벌 토큰 갱신 락 파일 (멀티프로세스 대응)
_TOKEN_REFRESH_LOCK_FILE = os.path.join(tempfile.gettempdir(), "hantu_token_refresh.lock")


class TLSAdapter(HTTPAdapter):
    """TLS 1.2+ 강제 어댑터

    한국투자증권 2025년 11월 보안 강화 정책 대비:
    TLS 1.0, 1.1 지원 중단 예정
    """

    def init_poolmanager(self, *args, **kwargs):
        # TLS 1.2 이상만 허용
        ctx = create_urllib3_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

logger = get_logger(__name__)

# KIS API 에러 코드 정의
class KISErrorCode:
    """한국투자증권 API 에러 코드"""
    TOKEN_EXPIRED = "EGW00123"  # 토큰 만료
    TOKEN_INVALID = "EGW00121"  # 유효하지 않은 토큰
    TOKEN_REFRESH_RATE_LIMIT = "EGW00133"  # 토큰 재발급 제한 (1분당 1회)
    RATE_LIMIT = "EGW00201"     # 호출 제한 초과
    OPS_ROUTING_ERROR = "EGW00203"  # OPS 라우팅 오류 (서버 과부하/점검)
    SERVICE_ERROR = "EGW00500"  # 서비스 오류

    # 재시도 가능한 에러 코드 목록
    RETRYABLE_ERRORS = [RATE_LIMIT, OPS_ROUTING_ERROR, SERVICE_ERROR, TOKEN_REFRESH_RATE_LIMIT]


class KISEndpoint:
    """KIS API 엔드포인트 레지스트리

    모든 API 엔드포인트의 path, tr_id, 필수 파라미터를 중앙에서 관리합니다.
    EGW00203 에러 방지를 위해 tr_id와 필수 파라미터를 명시적으로 정의합니다.

    사용법:
        endpoint = KISEndpoint.INQUIRE_PRICE
        tr_id = endpoint["tr_id"]
        path = endpoint["path"]
    """

    # ========== 시세 조회 API (모의/실전 동일 tr_id) ==========

    INQUIRE_PRICE = {
        "name": "주식현재가 시세",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-price",
        "tr_id": "FHKST01010100",
        "method": "GET",
        "required_params": ["FID_COND_MRKT_DIV_CODE", "FID_INPUT_ISCD"],
    }

    INQUIRE_DAILY_PRICE = {
        "name": "주식현재가 일자별",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-daily-price",
        "tr_id": "FHKST01010400",
        "method": "GET",
        "required_params": ["FID_COND_MRKT_DIV_CODE", "FID_INPUT_ISCD", "FID_PERIOD_DIV_CODE", "FID_ORG_ADJ_PRC"],
    }

    INQUIRE_DAILY_ITEMCHARTPRICE = {
        "name": "국내주식기간별시세(일/주/월/년)",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        "tr_id": "FHKST03010100",
        "method": "GET",
        "required_params": [
            "FID_COND_MRKT_DIV_CODE",
            "FID_INPUT_ISCD",
            "FID_INPUT_DATE_1",
            "FID_INPUT_DATE_2",
            "FID_PERIOD_DIV_CODE",
            "FID_ORG_ADJ_PRC"
        ],
    }

    INQUIRE_TIME_ITEMCHARTPRICE = {
        "name": "주식당일분봉조회",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
        "tr_id": "FHKST03010200",
        "method": "GET",
        "required_params": ["FID_COND_MRKT_DIV_CODE", "FID_INPUT_ISCD", "FID_INPUT_HOUR_1", "FID_PW_DATA_INCU_YN"],
    }

    INQUIRE_ASKING_PRICE = {
        "name": "주식현재가 호가/예상체결",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
        "tr_id": "FHKST01010200",
        "method": "GET",
        "required_params": ["FID_COND_MRKT_DIV_CODE", "FID_INPUT_ISCD"],
    }

    INQUIRE_CCNL = {
        "name": "주식현재가 체결",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-ccnl",
        "tr_id": "FHKST01010300",
        "method": "GET",
        "required_params": ["FID_COND_MRKT_DIV_CODE", "FID_INPUT_ISCD"],
    }

    INQUIRE_INVESTOR = {
        "name": "주식현재가 투자자",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-investor",
        "tr_id": "FHKST01010900",
        "method": "GET",
        "required_params": ["FID_COND_MRKT_DIV_CODE", "FID_INPUT_ISCD"],
    }

    INQUIRE_MEMBER = {
        "name": "주식현재가 회원사",
        "path": "/uapi/domestic-stock/v1/quotations/inquire-member",
        "tr_id": "FHKST01010600",
        "method": "GET",
        "required_params": ["FID_COND_MRKT_DIV_CODE", "FID_INPUT_ISCD"],
    }

    # ========== 거래 API (모의/실전 다른 tr_id) ==========

    INQUIRE_BALANCE = {
        "name": "주식잔고조회",
        "path": "/uapi/domestic-stock/v1/trading/inquire-balance",
        "tr_id": {"virtual": "VTTC8434R", "prod": "TTTC8434R"},
        "method": "GET",
        "required_params": ["CANO", "ACNT_PRDT_CD"],
    }

    ORDER_CASH = {
        "name": "주식주문(현금)",
        "path": "/uapi/domestic-stock/v1/trading/order-cash",
        "tr_id": {
            "virtual": {"buy": "VTTC0012U", "sell": "VTTC0011U"},
            "prod": {"buy": "TTTC0012U", "sell": "TTTC0011U"},
        },
        "method": "POST",
        "required_params": ["CANO", "ACNT_PRDT_CD", "PDNO", "ORD_DVSN", "ORD_QTY", "ORD_UNPR"],
    }

    @classmethod
    def get_tr_id(cls, endpoint: dict, server: str = "virtual", order_type: str = None) -> str:
        """엔드포인트에서 tr_id 추출

        Args:
            endpoint: 엔드포인트 정의 딕셔너리
            server: "virtual" 또는 "prod"
            order_type: 주문 시 "buy" 또는 "sell"

        Returns:
            str: tr_id
        """
        tr_id = endpoint.get("tr_id")

        if isinstance(tr_id, str):
            # 시세 조회 API - 모의/실전 동일
            return tr_id
        elif isinstance(tr_id, dict):
            # 거래 API - 모의/실전 다름
            server_tr_id = tr_id.get(server, tr_id.get("virtual"))
            if isinstance(server_tr_id, dict):
                # 주문 API - buy/sell 구분
                return server_tr_id.get(order_type, server_tr_id.get("buy"))
            return server_tr_id

        return ""

    @classmethod
    def validate_params(cls, endpoint: dict, params: dict) -> bool:
        """필수 파라미터 검증

        Args:
            endpoint: 엔드포인트 정의 딕셔너리
            params: 요청 파라미터

        Returns:
            bool: 모든 필수 파라미터가 있으면 True
        """
        required = endpoint.get("required_params", [])
        for param in required:
            if param not in params or params[param] is None:
                logger.warning(f"필수 파라미터 누락: {param} (endpoint: {endpoint.get('name', 'unknown')})")
                return False
        return True


class APIConfig:
    """API 설정 관리 클래스 (싱글톤)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """초기화"""
        if self._initialized:
            return
            
        # API 설정 로드
        self.app_key = settings.APP_KEY
        self.app_secret = settings.APP_SECRET
        self.account_number = settings.ACCOUNT_NUMBER
        self.account_prod_code = settings.ACCOUNT_PROD_CODE
        self.server = settings.SERVER
        
        # 서버 설정 (virtual: 모의투자, prod: 실제투자)
        if self.server == 'virtual':
            self.base_url = settings.VIRTUAL_URL
            self.ws_url = settings.SOCKET_VIRTUAL_URL
            self._token_file = settings.TOKEN_DIR / 'token_info_virtual.json'
            logger.info("[APIConfig] 모의투자 환경으로 설정되었습니다.")
        else:
            self.base_url = settings.PROD_URL
            self.ws_url = settings.SOCKET_PROD_URL
            self._token_file = settings.TOKEN_DIR / 'token_info_real.json'
            logger.info("[APIConfig] 실제투자 환경으로 설정되었습니다.")
        
        # 토큰 관련 변수
        self.access_token = None
        self.token_expired_at = None
        self._last_token_issued_at: Optional[datetime] = None  # 마지막 토큰 발급 시간

        # WebSocket 접속키 (REST 토큰과 별도)
        self.ws_approval_key: Optional[str] = None
        self._ws_approval_key_file = settings.TOKEN_DIR / f'ws_approval_key_{self.server}.json'

        # 토큰 디렉토리 생성
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        
        # API 호출 제한 설정
        self.rate_limit = settings.RATE_LIMIT_PER_SEC
        self.last_request_time = 0
        self.request_times = []

        # TLS 1.2+ 세션 생성 (2025년 보안 정책 대비)
        self._session = requests.Session()
        self._session.mount('https://', TLSAdapter())

        # 초기화 완료
        self._initialized = True

        # 저장된 토큰 로드
        self._load_token()
        
    def _save_token(self) -> None:
        """토큰 정보 저장"""
        try:
            token_data = {
                'access_token': self.access_token,
                'expired_at': self.token_expired_at.isoformat() if self.token_expired_at else None,
                'issued_at': self._last_token_issued_at.isoformat() if self._last_token_issued_at else None
            }

            with open(self._token_file, 'w') as f:
                json.dump(token_data, f)

            # 파일 권한 제한 (소유자만 읽기/쓰기)
            os.chmod(self._token_file, 0o600)

            logger.debug(f"[_save_token] 토큰 정보 저장 완료: {self._token_file} (권한: 600)")

        except Exception as e:
            logger.error(f"[_save_token] 토큰 정보 저장 중 오류 발생: {str(e)}", exc_info=True)

    def _load_token(self) -> None:
        """저장된 토큰 정보 로드"""
        try:
            if not self._token_file.exists():
                return

            with open(self._token_file, 'r') as f:
                token_data = json.load(f)

            self.access_token = token_data.get('access_token')
            expired_at = token_data.get('expired_at')
            issued_at = token_data.get('issued_at')

            if expired_at:
                self.token_expired_at = datetime.fromisoformat(expired_at)
            if issued_at:
                self._last_token_issued_at = datetime.fromisoformat(issued_at)

            logger.debug("[_load_token] 토큰 정보 로드 완료")

        except Exception as e:
            logger.error(f"[_load_token] 토큰 정보 로드 중 오류 발생: {str(e)}", exc_info=True)

    def _can_refresh_token(self) -> bool:
        """토큰 재발급 가능 여부 확인 (1분당 1회 제한)

        한국투자증권 공식 규정: 토큰 재발급은 1분당 1회 제한

        Returns:
            bool: 재발급 가능 여부
        """
        if self._last_token_issued_at is None:
            return True

        elapsed = datetime.now() - self._last_token_issued_at
        if elapsed < timedelta(minutes=1):
            remaining = 60 - elapsed.total_seconds()
            logger.warning(f"[_can_refresh_token] 토큰 재발급 제한 중 (남은 시간: {remaining:.0f}초)")
            return False

        return True
            
    def get_headers(self, include_content_type: bool = True) -> Dict:
        """API 요청 헤더 생성
        
        Args:
            include_content_type: Content-Type 헤더 포함 여부
            
        Returns:
            Dict: 요청 헤더
        """
        headers = {
            'authorization': f'Bearer {self.access_token}' if self.access_token else '',
            'appkey': self.app_key,
            'appsecret': self.app_secret,
        }
        
        if include_content_type:
            headers['content-type'] = 'application/json; charset=utf-8'
            
        # 로깅 시 민감 정보 마스킹
        safe_headers = headers.copy()
        if self.access_token:
            safe_headers['authorization'] = 'Bearer ***MASKED***'
        safe_headers['appkey'] = '***MASKED***'
        safe_headers['appsecret'] = '***MASKED***'
        
        logger.debug(f"[get_headers] 헤더 생성: {safe_headers}")
        
        return headers
    
    def apply_rate_limit(self) -> None:
        """API 호출 제한 적용 (Rate Limiting)
        
        한국투자증권 API 호출 제한을 준수하기 위한 처리
        설정된 초당 최대 요청 수(RATE_LIMIT_PER_SEC)를 초과하지 않도록 함
        """
        current_time = time.time()
        
        # 1초 이내의 요청 시간만 유지
        self.request_times = [t for t in self.request_times if current_time - t < 1.0]
        
        # 요청 횟수가 제한에 도달한 경우 대기
        if len(self.request_times) >= self.rate_limit:
            # 가장 오래된 요청으로부터 1초가 지날 때까지 대기
            wait_time = 1.0 - (current_time - self.request_times[0])
            if wait_time > 0:
                logger.debug(f"[apply_rate_limit] Rate limit 도달, {wait_time:.4f}초 대기")
                time.sleep(wait_time)
                current_time = time.time()  # 대기 후 현재 시간 갱신
        
        # 현재 요청 시간 기록
        self.request_times.append(current_time)
        self.last_request_time = current_time
        
    def refresh_token(self, force: bool = False) -> bool:
        """토큰 갱신 (전역 락으로 동시 갱신 방지)

        한국투자증권 공식 규정:
        - 접근 토큰은 1일 1회 발급이 원칙
        - 토큰 재발급은 1분당 1회 제한

        Args:
            force: 강제 갱신 여부

        Returns:
            bool: 갱신 성공 여부
        """
        # 전역 락을 사용하여 멀티프로세스/스레드에서 동시 갱신 방지
        try:
            with open(_TOKEN_REFRESH_LOCK_FILE, 'w') as lock_file:
                # 배타적 락 획득 (다른 프로세스가 갱신 중이면 대기)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

                try:
                    # 락 획득 후 토큰 파일 재로드 (다른 프로세스가 이미 갱신했을 수 있음)
                    self._load_token()

                    # 토큰이 유효하고 강제 갱신이 아닌 경우
                    if not force and self.validate_token():
                        logger.debug("[refresh_token] 토큰이 이미 유효함 (다른 프로세스가 갱신했을 수 있음)")
                        return True

                    # 1분당 1회 재발급 제한 확인
                    if not self._can_refresh_token():
                        logger.warning("[refresh_token] 토큰 재발급 제한으로 기존 토큰 유지 시도")
                        # 기존 토큰이 있으면 그대로 사용
                        if self.access_token:
                            return True
                        # 토큰이 없으면 대기 후 재시도
                        elapsed = datetime.now() - self._last_token_issued_at
                        wait_time = 60 - elapsed.total_seconds()
                        if wait_time > 0:
                            logger.info(f"[refresh_token] {wait_time:.0f}초 대기 후 재발급 시도")
                            time.sleep(wait_time + 1)

                    # API 호출 제한 적용
                    self.apply_rate_limit()

                    url = f"{self.base_url}/oauth2/tokenP"

                    data = {
                        "grant_type": "client_credentials",
                        "appkey": self.app_key,
                        "appsecret": self.app_secret
                    }

                    # 로깅 시 민감 정보 마스킹
                    safe_data = data.copy()
                    safe_data["appkey"] = "***MASKED***"
                    safe_data["appsecret"] = "***MASKED***"
                    logger.debug(f"[refresh_token] 토큰 갱신 요청: {safe_data}")

                    headers = {
                        "content-type": "application/json; charset=utf-8",
                        "Accept": "text/plain"
                    }
                    # TLS 1.2+ 세션 사용
                    response = self._session.post(url, json=data, headers=headers, timeout=settings.REQUEST_TIMEOUT)

                    if response.status_code == 200:
                        token_data = response.json()
                        self.access_token = token_data.get('access_token')
                        expires_in = int(token_data.get('expires_in', 86400))  # 기본값 24시간
                        self.token_expired_at = datetime.now() + timedelta(seconds=expires_in)
                        self._last_token_issued_at = datetime.now()  # 발급 시간 기록

                        # 로그에 토큰 데이터 마스킹
                        safe_token_data = {k: "***MASKED***" if k == "access_token" else v for k, v in token_data.items()}
                        logger.debug(f"[refresh_token] 토큰 응답: {safe_token_data}")

                        # 토큰 정보 저장
                        self._save_token()

                        logger.info("[refresh_token] 토큰 갱신 성공")
                        return True
                    else:
                        logger.error(f"[refresh_token] 토큰 갱신 실패 - 상태 코드: {response.status_code}", exc_info=True)
                        # 응답 본문에 민감 정보가 포함될 수 있으므로 마스킹
                        try:
                            error_data = response.json()
                            # access_token, appkey, appsecret 등 민감 필드 마스킹
                            safe_error_data = {
                                k: "***MASKED***" if k in ("access_token", "appkey", "appsecret", "approval_key") else v
                                for k, v in error_data.items()
                            }
                            logger.error(f"[refresh_token] 응답 데이터: {safe_error_data}")
                        except Exception:
                            # JSON 파싱 실패 시 응답 본문 길이만 로깅
                            logger.error(f"[refresh_token] 응답 본문 길이: {len(response.text)} bytes")
                        return False

                finally:
                    # 락 해제
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        except Exception as e:
            logger.error(f"[refresh_token] 토큰 갱신 중 오류 발생: {str(e)}", exc_info=True)
            return False
            
    def validate_token(self) -> bool:
        """토큰 유효성 검사
        
        Returns:
            bool: 토큰 유효 여부
        """
        if not self.access_token or not self.token_expired_at:
            return False
            
        # 만료 10분 전부터는 갱신 필요
        if datetime.now() + timedelta(minutes=10) >= self.token_expired_at:
            return False
            
        return True
        
    def ensure_valid_token(self) -> bool:
        """토큰 유효성 보장
        
        Returns:
            bool: 토큰 유효 여부
        """
        if not self.validate_token():
            return self.refresh_token()
        return True

    # 간단한 접근자 제공 (호환성용)
    def get_access_token(self) -> Optional[str]:
        """액세스 토큰 반환 (호환성용)
        실제 유효성 보장은 ensure_valid_token()에서 수행합니다.
        """
        return self.access_token
        
    def clear_token(self) -> None:
        """토큰 정보 초기화"""
        self.access_token = None
        self.token_expired_at = None
        self._last_token_issued_at = None

        if self._token_file.exists():
            self._token_file.unlink()

        logger.info("[clear_token] 토큰 정보 초기화 완료")

    # ========== WebSocket 접속키 관리 ==========

    def get_ws_approval_key(self, force: bool = False) -> Optional[str]:
        """WebSocket 접속키 발급

        한국투자증권 보안 강화 정책에 따라 WebSocket 연결 시
        REST API 토큰 대신 별도의 접속키(approval_key)를 사용해야 함

        Args:
            force: 강제 재발급 여부

        Returns:
            str: WebSocket 접속키 (실패 시 None)
        """
        try:
            # 캐시된 접속키 확인
            if not force and self.ws_approval_key:
                return self.ws_approval_key

            # 저장된 접속키 로드 시도
            if not force:
                self._load_ws_approval_key()
                if self.ws_approval_key:
                    return self.ws_approval_key

            # 새 접속키 발급
            url = f"{self.base_url}/oauth2/Approval"

            data = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.app_secret
            }

            # 로깅 시 민감 정보 마스킹
            safe_data = data.copy()
            safe_data["appkey"] = "***MASKED***"
            safe_data["secretkey"] = "***MASKED***"
            logger.debug(f"[get_ws_approval_key] 접속키 요청: {safe_data}")

            headers = {"content-type": "application/json; charset=utf-8"}
            # TLS 1.2+ 세션 사용
            response = self._session.post(url, json=data, headers=headers, timeout=settings.REQUEST_TIMEOUT)

            if response.status_code == 200:
                result = response.json()
                self.ws_approval_key = result.get('approval_key')
                self._save_ws_approval_key()
                logger.info("[get_ws_approval_key] WebSocket 접속키 발급 성공")
                return self.ws_approval_key
            else:
                logger.error(f"[get_ws_approval_key] 접속키 발급 실패: {response.status_code}", exc_info=True)
                # 응답 본문에 민감 정보가 포함될 수 있으므로 마스킹
                try:
                    error_data = response.json()
                    safe_error_data = {
                        k: "***MASKED***" if k in ("approval_key", "appkey", "secretkey") else v
                        for k, v in error_data.items()
                    }
                    logger.error(f"[get_ws_approval_key] 응답 데이터: {safe_error_data}")
                except Exception:
                    logger.error(f"[get_ws_approval_key] 응답 본문 길이: {len(response.text)} bytes")
                return None

        except Exception as e:
            logger.error(f"[get_ws_approval_key] 오류: {e}", exc_info=True)
            return None

    def _save_ws_approval_key(self) -> None:
        """WebSocket 접속키 저장"""
        try:
            data = {
                'approval_key': self.ws_approval_key,
                'issued_at': datetime.now().isoformat()
            }
            with open(self._ws_approval_key_file, 'w') as f:
                json.dump(data, f)

            # 파일 권한 제한 (소유자만 읽기/쓰기)
            os.chmod(self._ws_approval_key_file, 0o600)

            logger.debug(f"[_save_ws_approval_key] WebSocket 접속키 저장 완료 (권한: 600)")
        except Exception as e:
            logger.error(f"[_save_ws_approval_key] 저장 실패: {e}", exc_info=True)

    def _load_ws_approval_key(self) -> None:
        """WebSocket 접속키 로드"""
        try:
            if not self._ws_approval_key_file.exists():
                return
            with open(self._ws_approval_key_file, 'r') as f:
                data = json.load(f)
            self.ws_approval_key = data.get('approval_key')
        except Exception as e:
            logger.error(f"[_load_ws_approval_key] 로드 실패: {e}", exc_info=True)

    # ========== 에러 처리 유틸리티 ==========

    @staticmethod
    def is_token_error(response: Dict) -> bool:
        """토큰 관련 에러인지 확인

        Args:
            response: API 응답 딕셔너리

        Returns:
            bool: 토큰 에러 여부
        """
        if not isinstance(response, dict):
            return False

        error_code = response.get('msg_cd', '') or response.get('rt_cd', '')
        return error_code in [KISErrorCode.TOKEN_EXPIRED, KISErrorCode.TOKEN_INVALID]

    @staticmethod
    def is_rate_limit_error(response: Dict) -> bool:
        """Rate Limit 에러인지 확인

        Args:
            response: API 응답 딕셔너리

        Returns:
            bool: Rate Limit 에러 여부
        """
        if not isinstance(response, dict):
            return False

        error_code = response.get('msg_cd', '') or response.get('rt_cd', '')
        return error_code == KISErrorCode.RATE_LIMIT

    @staticmethod
    def is_ops_routing_error(response: Dict) -> bool:
        """OPS 라우팅 에러인지 확인 (서버 과부하/점검)

        Args:
            response: API 응답 딕셔너리

        Returns:
            bool: OPS 라우팅 에러 여부
        """
        if not isinstance(response, dict):
            return False

        error_code = response.get('msg_cd', '') or response.get('rt_cd', '')
        return error_code == KISErrorCode.OPS_ROUTING_ERROR

    @staticmethod
    def is_retryable_kis_error(response: Dict) -> bool:
        """재시도 가능한 KIS 에러인지 확인

        Args:
            response: API 응답 딕셔너리

        Returns:
            bool: 재시도 가능 여부
        """
        if not isinstance(response, dict):
            return False

        error_code = response.get('msg_cd', '') or response.get('rt_cd', '')
        return error_code in KISErrorCode.RETRYABLE_ERRORS

    def handle_api_error(self, response: Dict) -> bool:
        """API 에러 처리 및 복구 시도

        Args:
            response: API 응답 딕셔너리

        Returns:
            bool: 재시도 가능 여부
        """
        if self.is_token_error(response):
            logger.warning("[handle_api_error] 토큰 에러 감지, 토큰 갱신 시도")
            return self.refresh_token(force=True)

        if self.is_rate_limit_error(response):
            logger.warning("[handle_api_error] Rate Limit 에러 (EGW00201), 2초 대기")
            time.sleep(2)
            return True

        if self.is_ops_routing_error(response):
            logger.warning("[handle_api_error] OPS 라우팅 에러 (EGW00203), 서버 과부하/점검 - 10초 대기")
            time.sleep(10)
            return True

        return False