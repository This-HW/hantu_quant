"""
Redis 캐시 클라이언트 모듈

Redis 연결 실패 시 자동으로 MemoryCache로 폴백하는 캐시 클라이언트.
데코레이터를 통한 함수 결과 캐싱 지원.

Feature: B1 - Redis 클라이언트
"""

import redis
import json
import time
import hashlib
import functools
import asyncio
from collections import OrderedDict
from typing import Any, Optional, Callable, Dict
from datetime import datetime, date
from core.config.settings import REDIS_URL
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


# ========== Redis 클라이언트 초기화 ==========

def _mask_redis_url(url: str) -> str:
    """Redis URL에서 비밀번호 마스킹

    Args:
        url: Redis 연결 URL

    Returns:
        마스킹된 URL (비밀번호는 ****)
    """
    if not url:
        return "None"
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.password:
            netloc = f"{parsed.username}:****@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            masked = parsed._replace(netloc=netloc)
            return urlunparse(masked)
    except Exception:
        pass
    return url[:20] + "..." if len(url) > 20 else url

def _create_redis_client() -> Optional[redis.Redis]:
    """Redis 클라이언트 생성 (연결 실패 시 None 반환)"""
    if not REDIS_URL:
        logger.warning("REDIS_URL이 설정되지 않았습니다. MemoryCache로 폴백합니다.")
        return None

    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=False,  # JSON bytes 사용
            socket_timeout=5,
            socket_connect_timeout=5
        )
        # 연결 테스트
        client.ping()
        logger.info(f"Redis 연결 성공: {_mask_redis_url(REDIS_URL)}")
        return client
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.warning(
            f"Redis 연결 실패, MemoryCache로 폴백: {e}\nURL: {_mask_redis_url(REDIS_URL)}",
            exc_info=True
        )
        return None
    except Exception as e:
        logger.error(f"Redis 클라이언트 생성 중 예외 발생: {e}", exc_info=True)
        return None


# Redis 클라이언트 (전역 싱글톤)
_redis_client: Optional[redis.Redis] = _create_redis_client()


# ========== 키 네이밍 규칙 ==========

CACHE_KEY_PREFIX = "hantu:cache:"

def generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """함수 이름과 인자 기반 캐시 키 생성

    Args:
        func_name: 함수 이름
        args: 위치 인자
        kwargs: 키워드 인자

    Returns:
        캐시 키 (예: "hantu:cache:get_price:abcd1234")
    """
    # 인자를 JSON으로 직렬화하여 해시 생성
    try:
        args_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    except (TypeError, ValueError) as e:
        logger.warning(f"캐시 키 생성 중 직렬화 실패: {e}. 대체 방식 사용.", exc_info=True)
        args_str = f"{args}_{kwargs}"

    args_hash = hashlib.sha256(args_str.encode()).hexdigest()[:16]
    return f"{CACHE_KEY_PREFIX}{func_name}:{args_hash}"


# ========== JSON 직렬화 헬퍼 ==========

def _json_serialize(value: Any) -> bytes:
    """Python 객체를 JSON bytes로 직렬화

    Args:
        value: 직렬화할 값 (dict, list, DataFrame 등)

    Returns:
        JSON bytes

    Raises:
        TypeError: 직렬화 불가능한 타입
    """
    def json_default(obj):
        """JSON 직렬화 기본 핸들러"""
        # datetime 처리
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # pandas Timestamp 처리 (dict 키로 사용될 수 있음)
        try:
            import pandas as pd
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
        except ImportError:
            pass

        # pandas DataFrame/Series 처리
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()

        # numpy 타입 처리
        if hasattr(obj, 'tolist'):
            return obj.tolist()

        # 기본 타입 변환
        return str(obj)

    # DataFrame의 경우 인덱스와 컬럼을 문자열로 변환 후 dict로 변환
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            value_copy = value.copy()
            # 인덱스를 항상 문자열로 변환 (Timestamp, DatetimeIndex 등 모두 처리)
            value_copy.index = value_copy.index.astype(str)
            # 컬럼도 항상 문자열로 변환
            value_copy.columns = value_copy.columns.astype(str)
            # orient='index'로 변환하여 모든 키가 문자열이 되도록 보장
            value = {
                'index': [str(idx) for idx in value_copy.index.tolist()],
                'columns': [str(col) for col in value_copy.columns.tolist()],
                'data': value_copy.values.tolist()
            }
    except Exception:
        pass  # 실패 시 원본 값 사용

    try:
        return json.dumps(value, default=json_default, ensure_ascii=False).encode('utf-8')
    except Exception as e:
        logger.error(f"JSON 직렬화 실패: {type(value).__name__} - {e}", exc_info=True)
        raise TypeError(f"직렬화 불가능한 타입: {type(value).__name__}") from e

def _json_deserialize(data: bytes) -> Any:
    """JSON bytes를 Python 객체로 역직렬화

    Args:
        data: JSON bytes

    Returns:
        역직렬화된 객체

    Raises:
        ValueError: 잘못된 JSON 형식
    """
    try:
        return json.loads(data.decode('utf-8'))
    except Exception as e:
        logger.error(f"JSON 역직렬화 실패: {e}", exc_info=True)
        raise ValueError("잘못된 JSON 데이터") from e


# ========== MemoryCache (폴백용) ==========

class MemoryCache:
    """메모리 기반 캐시 (Redis 폴백용)

    LRU 방식으로 최대 1000개 항목 유지.
    TTL 지원 (타임스탬프 체크).
    """

    def __init__(self, max_size: int = 1000):
        """초기화

        Args:
            max_size: 최대 캐시 항목 수 (LRU)
        """
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        """캐시 조회

        Args:
            key: 캐시 키

        Returns:
            캐시 값 (없거나 만료 시 None)
        """
        if key not in self._cache:
            return None

        value, expire_at = self._cache[key]

        # TTL 체크
        if expire_at and time.time() > expire_at:
            del self._cache[key]
            return None

        # LRU: 최근 사용 항목으로 이동
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시 저장

        Args:
            key: 캐시 키
            value: 캐시 값
            ttl: 만료 시간 (초, None이면 무제한)

        Returns:
            성공 여부
        """
        expire_at = (time.time() + ttl) if ttl else None

        # 기존 키 제거 (순서 갱신)
        if key in self._cache:
            del self._cache[key]

        self._cache[key] = (value, expire_at)

        # LRU: 최대 크기 초과 시 가장 오래된 항목 제거
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

        return True

    def delete(self, key: str) -> bool:
        """캐시 삭제

        Args:
            key: 캐시 키

        Returns:
            삭제 성공 여부
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def delete_by_pattern(self, pattern: str) -> int:
        """패턴 매칭 삭제

        Args:
            pattern: 삭제할 키 패턴 (예: "hantu:cache:get_price:*")

        Returns:
            삭제된 키 개수
        """
        # 단순 prefix 매칭 (Redis SCAN 패턴과 동일)
        prefix = pattern.rstrip('*')
        keys_to_delete = [key for key in self._cache if key.startswith(prefix)]

        for key in keys_to_delete:
            del self._cache[key]

        return len(keys_to_delete)

    def clear(self) -> bool:
        """전체 캐시 삭제

        Returns:
            성공 여부
        """
        self._cache.clear()
        return True

    def size(self) -> int:
        """현재 캐시 항목 수"""
        return len(self._cache)


# 폴백 캐시 인스턴스 (전역 싱글톤)
_memory_cache = MemoryCache()


# ========== RedisCache 클래스 ==========

class RedisCache:
    """Redis 캐시 클라이언트

    Redis 연결 실패 시 MemoryCache로 자동 폴백.
    직렬화는 JSON 사용 (보안 강화).
    """

    def __init__(self):
        """초기화"""
        self._redis = _redis_client
        self._fallback = _memory_cache
        self._is_fallback = self._redis is None

        if self._is_fallback:
            logger.info("Redis를 사용할 수 없습니다. MemoryCache로 동작합니다.")

    def is_available(self) -> bool:
        """Redis 사용 가능 여부

        Returns:
            Redis 사용 가능하면 True, 폴백이면 False
        """
        return not self._is_fallback

    def get(self, key: str) -> Optional[Any]:
        """캐시 조회

        Args:
            key: 캐시 키

        Returns:
            캐시 값 (없으면 None)
        """
        try:
            if self._redis:
                data = self._redis.get(key)
                if data is None:
                    logger.debug(f"캐시 미스: {key}")
                    return None

                logger.debug(f"캐시 히트: {key}")
                return _json_deserialize(data)
            else:
                # 폴백
                value = self._fallback.get(key)
                if value is None:
                    logger.debug(f"캐시 미스 (폴백): {key}")
                else:
                    logger.debug(f"캐시 히트 (폴백): {key}")
                return value

        except redis.ConnectionError as e:
            logger.warning(f"Redis 연결 에러 (get): {e}. 폴백으로 전환합니다.", exc_info=True)
            self._switch_to_fallback()
            return self._fallback.get(key)

        except (ValueError, TypeError) as e:
            logger.error(f"역직렬화 실패 (key={key}): {e}", exc_info=True)
            return None

        except Exception as e:
            logger.error(f"캐시 조회 중 에러 (key={key}): {e}", exc_info=True)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시 저장

        Args:
            key: 캐시 키
            value: 캐시 값
            ttl: 만료 시간 (초, None이면 무제한)

        Returns:
            성공 여부
        """
        try:
            if self._redis:
                data = _json_serialize(value)
                if ttl:
                    self._redis.setex(key, ttl, data)
                else:
                    self._redis.set(key, data)
                logger.debug(f"캐시 저장: {key} (TTL={ttl})")
                return True
            else:
                # 폴백
                self._fallback.set(key, value, ttl)
                logger.debug(f"캐시 저장 (폴백): {key} (TTL={ttl})")
                return True

        except redis.ConnectionError as e:
            logger.warning(f"Redis 연결 에러 (set): {e}. 폴백으로 전환합니다.", exc_info=True)
            self._switch_to_fallback()
            return self._fallback.set(key, value, ttl)

        except TypeError as e:
            logger.error(f"직렬화 실패 (key={key}): {e}", exc_info=True)
            return False

        except Exception as e:
            logger.error(f"캐시 저장 중 에러 (key={key}): {e}", exc_info=True)
            return False

    def delete(self, key: str) -> bool:
        """캐시 삭제

        Args:
            key: 캐시 키

        Returns:
            삭제 성공 여부
        """
        try:
            if self._redis:
                deleted = self._redis.delete(key)
                logger.debug(f"캐시 삭제: {key} (deleted={deleted})")
                return deleted > 0
            else:
                # 폴백
                return self._fallback.delete(key)

        except redis.ConnectionError as e:
            logger.warning(f"Redis 연결 에러 (delete): {e}. 폴백으로 전환합니다.", exc_info=True)
            self._switch_to_fallback()
            return self._fallback.delete(key)

        except Exception as e:
            logger.error(f"캐시 삭제 중 에러 (key={key}): {e}", exc_info=True)
            return False

    def delete_by_pattern(self, pattern: str) -> int:
        """패턴 매칭 삭제

        Args:
            pattern: 삭제할 키 패턴 (예: "hantu:cache:get_price:*")

        Returns:
            삭제된 키 개수
        """
        try:
            if self._redis:
                # Redis SCAN으로 패턴 매칭 키 조회
                cursor = 0
                deleted_count = 0

                while True:
                    cursor, keys = self._redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        deleted = self._redis.delete(*keys)
                        deleted_count += deleted

                    if cursor == 0:
                        break

                logger.info(f"패턴 매칭 캐시 삭제: {pattern} (deleted={deleted_count})")
                return deleted_count
            else:
                # 폴백
                return self._fallback.delete_by_pattern(pattern)

        except redis.ConnectionError as e:
            logger.warning(f"Redis 연결 에러 (delete_by_pattern): {e}. 폴백으로 전환합니다.", exc_info=True)
            self._switch_to_fallback()
            return self._fallback.delete_by_pattern(pattern)

        except Exception as e:
            logger.error(f"패턴 매칭 삭제 중 에러 (pattern={pattern}): {e}", exc_info=True)
            return 0

    def clear(self) -> bool:
        """전체 캐시 삭제 (FLUSHDB)

        주의: 현재 DB의 모든 키를 삭제합니다.

        Returns:
            성공 여부
        """
        try:
            if self._redis:
                self._redis.flushdb()
                logger.warning("Redis FLUSHDB 실행: 모든 캐시 삭제됨")
                return True
            else:
                # 폴백
                self._fallback.clear()
                logger.info("MemoryCache 전체 삭제")
                return True

        except redis.ConnectionError as e:
            logger.warning(f"Redis 연결 에러 (clear): {e}. 폴백으로 전환합니다.", exc_info=True)
            self._switch_to_fallback()
            return self._fallback.clear()

        except Exception as e:
            logger.error(f"캐시 전체 삭제 중 에러: {e}", exc_info=True)
            return False

    def _switch_to_fallback(self):
        """Redis → MemoryCache 폴백 전환"""
        if not self._is_fallback:
            logger.warning("Redis 폴백 전환: MemoryCache로 동작합니다.")
            self._redis = None
            self._is_fallback = True


# 캐시 인스턴스 (전역 싱글톤)
cache = RedisCache()


# ========== CacheDecorator ==========

def cache_with_ttl(ttl: int = 600, key_prefix: Optional[str] = None):
    """함수 결과를 캐싱하는 데코레이터

    동기/비동기 함수 모두 지원.

    Args:
        ttl: 캐시 만료 시간 (초)
        key_prefix: 캐시 키 prefix (기본값: 함수명)

    Example:
        @cache_with_ttl(ttl=600)
        def get_stock_price(stock_code: str) -> float:
            ...

        @cache_with_ttl(ttl=300, key_prefix="api")
        async def fetch_data(url: str) -> dict:
            ...
    """
    def decorator(func: Callable):
        func_name = key_prefix or func.__name__

        # 동기 함수 래퍼
        if not asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # 캐시 키 생성
                cache_key = generate_cache_key(func_name, args, kwargs)

                # 캐시 조회
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"캐시 히트: {func_name}")
                    return cached_value

                # 함수 실행
                logger.debug(f"캐시 미스: {func_name}, 함수 실행")
                result = func(*args, **kwargs)

                # 캐시 저장
                cache.set(cache_key, result, ttl)
                return result

            return sync_wrapper

        # 비동기 함수 래퍼
        else:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # 캐시 키 생성
                cache_key = generate_cache_key(func_name, args, kwargs)

                # 캐시 조회
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"캐시 히트 (async): {func_name}")
                    return cached_value

                # 함수 실행
                logger.debug(f"캐시 미스 (async): {func_name}, 함수 실행")
                result = await func(*args, **kwargs)

                # 캐시 저장
                cache.set(cache_key, result, ttl)
                return result

            return async_wrapper

    return decorator


# ========== 유틸리티 함수 ==========

def invalidate_cache(func: Callable, *args, **kwargs):
    """특정 함수 호출에 대한 캐시 무효화

    Args:
        func: 함수
        *args: 함수 위치 인자
        **kwargs: 함수 키워드 인자

    Example:
        invalidate_cache(get_stock_price, "005930")
    """
    cache_key = generate_cache_key(func.__name__, args, kwargs)
    cache.delete(cache_key)
    logger.info(f"캐시 무효화: {func.__name__}")


def invalidate_function_cache(func: Callable):
    """특정 함수의 모든 캐시 무효화

    Args:
        func: 함수

    Example:
        invalidate_function_cache(get_stock_price)
    """
    pattern = f"{CACHE_KEY_PREFIX}{func.__name__}:*"
    deleted = cache.delete_by_pattern(pattern)
    logger.info(f"함수 캐시 무효화: {func.__name__} (deleted={deleted})")


def get_cache_stats() -> Dict[str, Any]:
    """캐시 통계 조회

    Returns:
        캐시 통계 (available, type, size 등)
    """
    stats = {
        "available": cache.is_available(),
        "type": "redis" if cache.is_available() else "memory",
    }

    if not cache.is_available():
        stats["size"] = _memory_cache.size()
        stats["max_size"] = _memory_cache._max_size

    return stats
