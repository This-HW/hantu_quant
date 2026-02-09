"""
감시 리스트 관리 시스템
- 기본 CRUD 기능
- 데이터 저장/로드
- 중복 체크 및 검증
- 통계 정보 제공
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import threading

from core.database.unified_db import get_session
from core.database.models import Stock as DBStock, WatchlistStock as DBWatchlistStock

from core.utils.log_utils import get_logger
from core.interfaces.trading import IWatchlistManager, WatchlistEntry

# 새로운 아키텍처 imports - 사용 가능할 때만 import
try:
    from core.plugins.decorators import plugin  # noqa: F401
    from core.di.injector import inject  # noqa: F401
    from core.interfaces.base import ILogger, IConfiguration  # noqa: F401

    ARCHITECTURE_AVAILABLE = True
except ImportError:
    # 새 아키텍처가 아직 완전히 구축되지 않은 경우 임시 대안
    ARCHITECTURE_AVAILABLE = False

    def plugin(**kwargs):
        """임시 플러그인 데코레이터"""

        def decorator(cls):
            cls._plugin_metadata = kwargs
            return cls

        return decorator

    def inject(cls):
        """임시 DI 데코레이터"""
        return cls


logger = get_logger(__name__)


@dataclass
class WatchlistStock:
    """감시 리스트 종목 데이터 클래스 (기존 호환성용)"""

    stock_code: str
    stock_name: str
    added_date: str
    added_reason: str
    target_price: float
    stop_loss: float
    sector: str
    screening_score: float
    last_updated: str
    notes: str = ""
    status: str = "active"  # active, paused, removed

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, p_data: Dict) -> "WatchlistStock":
        """딕셔너리에서 생성"""
        return cls(**p_data)

    def to_watchlist_entry(self) -> WatchlistEntry:
        """새로운 WatchlistEntry로 변환"""
        return WatchlistEntry(
            stock_code=self.stock_code,
            stock_name=self.stock_name,
            added_date=(
                datetime.fromisoformat(self.added_date)
                if isinstance(self.added_date, str)
                else self.added_date
            ),
            added_reason=self.added_reason,
            target_price=self.target_price,
            stop_loss=self.stop_loss,
            sector=self.sector,
            screening_score=self.screening_score,
            status=self.status,
            notes=self.notes,
        )


@plugin(
    name="watchlist_manager",
    version="1.0.0",
    description="감시 리스트 관리 플러그인",
    author="HantuQuant",
    dependencies=["logger"],
    category="watchlist",
)
class WatchlistManager(IWatchlistManager):
    """감시 리스트 관리 클래스 - 새로운 아키텍처 적용"""

    @inject
    def __init__(self, p_data_file: str = "data/watchlist/watchlist.json", logger=None):
        """초기화 메서드

        Args:
            p_data_file: 데이터 파일 경로
            logger: 로거 인스턴스
        """
        self._data_file = p_data_file
        self._logger = logger or get_logger(__name__)
        self._stocks = {}  # Dict[str, WatchlistStock]
        self._lock = threading.RLock()  # 스레드 안전성을 위한 락

        # 데이터 디렉토리 생성
        os.makedirs(os.path.dirname(self._data_file), exist_ok=True)


        # DB 연결 초기화
        self._use_db = True  # DB 우선 사용
        try:
            # DB 연결 테스트
            with get_session() as session:
                session.query(DBWatchlistStock).limit(1).first()
            self._logger.info("WatchlistManager DB 연결 성공")
        except Exception as e:
            self._logger.warning(f"DB 연결 실패, JSON 폴백 사용: {e}")
            self._use_db = False

        # 기존 데이터 로드
        self._load_data()

        self._logger.info(
            f"WatchlistManager 초기화 완료 (새 아키텍처) - 종목 수: {len(self._stocks)}"
        )

    def initialize(self):
        """플러그인 초기화 메서드 (플러그인 데코레이터 요구사항)"""
        self._logger.info("WatchlistManager 플러그인 초기화 완료")
        return True

    def add_stock(self, entry: WatchlistEntry) -> bool:
        """종목 추가 (새 인터페이스 구현)

        Args:
            entry: 감시 리스트 항목

        Returns:
            bool: 성공 여부
        """
        try:
            with self._lock:
                if entry.stock_code in self._stocks:
                    self._logger.warning(f"이미 존재하는 종목: {entry.stock_code}")
                    return False

                # WatchlistEntry를 WatchlistStock으로 변환 (기존 호환성)
                _v_stock = WatchlistStock(
                    stock_code=entry.stock_code,
                    stock_name=entry.stock_name,
                    added_date=(
                        entry.added_date.isoformat()
                        if isinstance(entry.added_date, datetime)
                        else str(entry.added_date)
                    ),
                    added_reason=entry.added_reason,
                    target_price=entry.target_price,
                    stop_loss=entry.stop_loss,
                    sector=entry.sector,
                    screening_score=entry.screening_score,
                    last_updated=datetime.now().isoformat(),
                    notes=entry.notes,
                    status=entry.status,
                )

                self._stocks[entry.stock_code] = _v_stock
                self._save_data()

                self._logger.info(
                    f"종목 추가 완료: {entry.stock_code} ({entry.stock_name})"
                )
                return True

        except Exception as e:
            self._logger.error(f"종목 추가 오류: {e}", exc_info=True)
            return False

    def add_stock_legacy(
        self,
        p_stock_code: str,
        p_stock_name: str,
        p_added_reason: str,
        p_target_price: float,
        p_stop_loss: float,
        p_sector: str,
        p_screening_score: float,
        p_notes: str = "",
    ) -> bool:
        """종목 추가 (기존 호환성용)

        Args:
            p_stock_code: 종목 코드
            p_stock_name: 종목명
            p_added_reason: 추가 사유
            p_target_price: 목표가
            p_stop_loss: 손절가
            p_sector: 섹터
            p_screening_score: 스크리닝 점수
            p_notes: 메모

        Returns:
            bool: 성공 여부
        """
        _v_entry = WatchlistEntry(
            stock_code=p_stock_code,
            stock_name=p_stock_name,
            added_date=datetime.now(),
            added_reason=p_added_reason,
            target_price=p_target_price,
            stop_loss=p_stop_loss,
            sector=p_sector,
            screening_score=p_screening_score,
            status="active",
            notes=p_notes,
        )

        return self.add_stock(_v_entry)

    def get_stock(self, p_stock_code: str) -> Optional[WatchlistEntry]:
        """종목 조회 (새 인터페이스 구현)

        Args:
            p_stock_code: 종목 코드

        Returns:
            Optional[WatchlistEntry]: 종목 정보 (없으면 None)
        """
        try:
            with self._lock:
                _v_stock = self._stocks.get(p_stock_code)
                if _v_stock:
                    return _v_stock.to_watchlist_entry()
                return None

        except Exception as e:
            self._logger.error(f"종목 조회 오류: {e}", exc_info=True)
            return None

    def update_stock(self, p_stock_code: str, p_updates: Dict) -> bool:
        """종목 정보 업데이트 (새 인터페이스 구현)

        Args:
            p_stock_code: 종목 코드
            p_updates: 업데이트할 필드들

        Returns:
            bool: 성공 여부
        """
        try:
            with self._lock:
                if p_stock_code not in self._stocks:
                    self._logger.warning(f"존재하지 않는 종목: {p_stock_code}")
                    return False

                _v_stock = self._stocks[p_stock_code]
                _v_updated = False

                # 업데이트 가능한 필드들
                _v_updatable_fields = [
                    "stock_name",
                    "target_price",
                    "stop_loss",
                    "sector",
                    "screening_score",
                    "notes",
                    "status",
                    "added_reason",
                ]

                for _v_field, _v_value in p_updates.items():
                    if _v_field in _v_updatable_fields:
                        if hasattr(_v_stock, _v_field):
                            setattr(_v_stock, _v_field, _v_value)
                            _v_updated = True

                if _v_updated:
                    _v_stock.last_updated = datetime.now().isoformat()
                    self._save_data()
                    self._logger.info(f"종목 업데이트 완료: {p_stock_code}")
                    return True
                else:
                    self._logger.warning(f"업데이트할 필드가 없음: {p_stock_code}")
                    return False

        except Exception as e:
            self._logger.error(f"종목 업데이트 오류: {e}", exc_info=True)
            return False

    def remove_stock(self, p_stock_code: str, p_permanent: bool = False) -> bool:
        """종목 제거 (새 인터페이스 구현)

        Args:
            p_stock_code: 종목 코드
            p_permanent: 영구 삭제 여부 (False면 상태만 변경)

        Returns:
            bool: 성공 여부
        """
        try:
            with self._lock:
                if p_stock_code not in self._stocks:
                    self._logger.warning(f"존재하지 않는 종목: {p_stock_code}")
                    return False

                if p_permanent:
                    # 영구 삭제
                    _v_removed_stock = self._stocks.pop(p_stock_code)
                    self._logger.info(
                        f"종목 영구 삭제: {p_stock_code} ({_v_removed_stock.stock_name})"
                    )
                else:
                    # 상태만 변경
                    self._stocks[p_stock_code].status = "removed"
                    self._stocks[p_stock_code].last_updated = datetime.now().isoformat()
                    self._logger.info(f"종목 상태 변경 (제거): {p_stock_code}")

                self._save_data()
                return True

        except Exception as e:
            self._logger.error(f"종목 제거 오류: {e}", exc_info=True)
            return False

    def list_stocks(
        self,
        p_status: Optional[str] = None,
        p_sector: Optional[str] = None,
        p_sort_by: str = "screening_score",
        p_ascending: bool = False,
    ) -> List[WatchlistEntry]:
        """종목 목록 조회 (새 인터페이스 구현)

        Args:
            p_status: 상태 필터 (None이면 모든 상태)
            p_sector: 섹터 필터 (None이면 모든 섹터)
            p_sort_by: 정렬 기준 (screening_score, stock_code, stock_name, added_date)
            p_ascending: 오름차순 정렬 여부 (False이면 내림차순)

        Returns:
            List[WatchlistEntry]: 필터링된 종목 목록
        """
        try:
            with self._lock:
                _v_filtered_stocks = []

                for _v_stock in self._stocks.values():
                    # 상태 필터링
                    if p_status and _v_stock.status != p_status:
                        continue

                    # 섹터 필터링
                    if p_sector and _v_stock.sector != p_sector:
                        continue

                    _v_filtered_stocks.append(_v_stock.to_watchlist_entry())

                # 정렬 기준에 따른 정렬
                if p_sort_by == "screening_score":
                    _v_filtered_stocks.sort(
                        key=lambda x: x.screening_score, reverse=not p_ascending
                    )
                elif p_sort_by == "stock_code":
                    _v_filtered_stocks.sort(
                        key=lambda x: x.stock_code, reverse=not p_ascending
                    )
                elif p_sort_by == "stock_name":
                    _v_filtered_stocks.sort(
                        key=lambda x: x.stock_name, reverse=not p_ascending
                    )
                elif p_sort_by == "added_date":
                    _v_filtered_stocks.sort(
                        key=lambda x: x.added_date, reverse=not p_ascending
                    )
                else:
                    # 기본값: 스크리닝 점수 내림차순
                    _v_filtered_stocks.sort(
                        key=lambda x: x.screening_score, reverse=True
                    )

                return _v_filtered_stocks

        except Exception as e:
            self._logger.error(f"종목 목록 조회 오류: {e}", exc_info=True)
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 조회 (새 인터페이스 구현)

        Returns:
            Dict[str, Any]: 통계 정보
        """
        try:
            with self._lock:
                if not self._stocks:
                    return {
                        "total_count": 0,
                        "active_count": 0,
                        "paused_count": 0,
                        "removed_count": 0,
                        "sectors": {},
                        "score_distribution": {},
                        "avg_score": 0.0,
                        "max_score": 0.0,
                        "min_score": 0.0,
                    }

                # 기본 통계
                _v_total_count = len(self._stocks)
                _v_active_count = sum(
                    1 for s in self._stocks.values() if s.status == "active"
                )
                _v_paused_count = sum(
                    1 for s in self._stocks.values() if s.status == "paused"
                )
                _v_removed_count = sum(
                    1 for s in self._stocks.values() if s.status == "removed"
                )

                # 섹터별 분포
                _v_sector_count = {}
                for _v_stock in self._stocks.values():
                    _v_sector = _v_stock.sector
                    _v_sector_count[_v_sector] = _v_sector_count.get(_v_sector, 0) + 1

                # 점수 분포 및 통계
                _v_scores = [s.screening_score for s in self._stocks.values()]
                _v_avg_score = sum(_v_scores) / len(_v_scores) if _v_scores else 0.0
                _v_max_score = max(_v_scores) if _v_scores else 0.0
                _v_min_score = min(_v_scores) if _v_scores else 0.0

                # 점수 구간별 분포
                _v_score_ranges = {
                    "90-100": sum(1 for s in _v_scores if 90 <= s <= 100),
                    "80-89": sum(1 for s in _v_scores if 80 <= s < 90),
                    "70-79": sum(1 for s in _v_scores if 70 <= s < 80),
                    "60-69": sum(1 for s in _v_scores if 60 <= s < 70),
                    "50-59": sum(1 for s in _v_scores if 50 <= s < 60),
                    "0-49": sum(1 for s in _v_scores if 0 <= s < 50),
                }

                return {
                    "total_count": _v_total_count,
                    "active_count": _v_active_count,
                    "paused_count": _v_paused_count,
                    "removed_count": _v_removed_count,
                    "sectors": _v_sector_count,
                    "score_distribution": _v_score_ranges,
                    "avg_score": round(_v_avg_score, 2),
                    "max_score": _v_max_score,
                    "min_score": _v_min_score,
                    "last_updated": datetime.now().isoformat(),
                }

        except Exception as e:
            self._logger.error(f"통계 정보 조회 오류: {e}", exc_info=True)
            return {}

    def backup_data(self, p_backup_file: Optional[str] = None) -> bool:
        """데이터 백업

        Args:
            p_backup_file: 백업 파일 경로 (None이면 자동 생성)

        Returns:
            백업 성공 여부
        """
        try:
            if not p_backup_file:
                _v_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                p_backup_file = (
                    f"data/watchlist/backup/watchlist_backup_{_v_timestamp}.json"
                )

            # 백업 디렉토리 생성
            os.makedirs(os.path.dirname(p_backup_file), exist_ok=True)

            with self._lock:
                _v_backup_data = {
                    "timestamp": datetime.now().isoformat(),
                    "metadata": self._stocks,  # 메타데이터는 현재 데이터를 사용
                    "watchlist": {
                        code: stock.to_dict() for code, stock in self._stocks.items()
                    },
                }

                with open(p_backup_file, "w", encoding="utf-8") as f:
                    json.dump(_v_backup_data, f, ensure_ascii=False, indent=2)

                self._logger.info(f"감시 리스트 백업 완료: {p_backup_file}")
                return True

        except Exception as e:
            self._logger.error(f"백업 오류: {e}", exc_info=True)
            return False

    def restore_data(self, p_backup_file: str) -> bool:
        """데이터 복원

        Args:
            p_backup_file: 백업 파일 경로

        Returns:
            복원 성공 여부
        """
        try:
            if not os.path.exists(p_backup_file):
                self._logger.error(
                    f"백업 파일이 존재하지 않습니다: {p_backup_file}", exc_info=True
                )
                return False

            with open(p_backup_file, "r", encoding="utf-8") as f:
                _v_backup_data = json.load(f)

            with self._lock:
                # 현재 데이터 백업
                self.backup_data()

                # 데이터 복원
                _v_watchlist_data = _v_backup_data.get("watchlist", {})

                self._stocks = {}
                for code, stock_data in _v_watchlist_data.items():
                    self._stocks[code] = WatchlistStock.from_dict(stock_data)

                # 데이터 저장
                self._save_data()

                self._logger.info(f"감시 리스트 복원 완료: {p_backup_file}")
                return True

        except Exception as e:
            self._logger.error(f"복원 오류: {e}", exc_info=True)
            return False

    def _load_data(self) -> None:
        """데이터 로드 (DB 우선, JSON 폴백)"""
        try:
            if self._use_db:
                # DB에서 로드
                self._load_from_db()
            else:
                # JSON에서 로드 (폴백)
                self._load_from_json()
        except Exception as e:
            self._logger.error(f"데이터 로드 오류: {e}", exc_info=True)
            # JSON 폴백 시도
            if self._use_db:
                self._logger.warning("DB 로드 실패, JSON 폴백 시도")
                try:
                    self._load_from_json()
                except Exception as json_error:
                    self._logger.error(
                        f"JSON 폴백 로드 실패: {json_error}",
                        exc_info=True,
                        extra={'fallback_path': self._data_file}
                    )
                    self._stocks = {}
            else:
                self._stocks = {}

    def _load_from_db(self) -> None:
        """DB에서 감시 리스트 로드"""
        with get_session() as session:
            # JOIN하여 종목 정보와 함께 조회
            watchlist_items = session.query(DBWatchlistStock, DBStock)\
                .join(DBStock, DBWatchlistStock.stock_id == DBStock.id)\
                .filter(DBWatchlistStock.status == 'active')\
                .all()
            
            self._stocks = {}
            for ws, stock in watchlist_items:
                # DB 모델 → WatchlistStock 변환
                _v_stock = WatchlistStock(
                    stock_code=stock.code,
                    stock_name=stock.name,
                    added_date=ws.added_date.isoformat(),
                    added_reason="DB 마이그레이션",
                    target_price=0.0,  # 추후 계산
                    stop_loss=0.0,
                    sector=stock.sector or "기타",
                    screening_score=ws.total_score,
                    last_updated=datetime.now().isoformat(),
                    notes=f"점수: {ws.total_score:.2f}",
                    status=ws.status
                )
                self._stocks[stock.code] = _v_stock
            
            self._logger.info(f"감시 리스트 데이터 로드 완료: {len(self._stocks)}개 종목 (DB)")

    def _load_from_json(self) -> None:
        """JSON 파일에서 감시 리스트 로드 (폴백)"""
        if os.path.exists(self._data_file):
            with open(self._data_file, "r", encoding="utf-8") as f:
                _v_data = json.load(f)

            # 감시 리스트 로드
            if "data" in _v_data and "stocks" in _v_data["data"]:
                _v_watchlist_data = _v_data["data"]["stocks"]
            else:
                _v_watchlist_data = _v_data.get("stocks", [])

            self._stocks = {}
            for stock_data in _v_watchlist_data:
                _v_stock = WatchlistStock.from_dict(stock_data)
                self._stocks[_v_stock.stock_code] = _v_stock

            self._logger.info(f"감시 리스트 데이터 로드 완료: {len(self._stocks)}개 종목 (JSON)")
        else:
            self._logger.info("감시 리스트 데이터 파일이 없습니다.")
            self._stocks = {}

    def _save_data(self) -> None:
        """데이터 저장 (DB 우선, JSON 백업)"""
        try:
            if self._use_db:
                self._save_to_db()
            
            # JSON 백업은 항상 유지
            self._save_to_json()
            
        except Exception as e:
            self._logger.error(f"데이터 저장 오류: {e}", exc_info=True)

    def _save_to_db(self) -> None:
        """DB에 감시 리스트 저장"""
        with get_session() as session:
            # 기존 active 상태를 모두 제거
            session.query(DBWatchlistStock)\
                .filter(DBWatchlistStock.status == 'active')\
                .delete()
            
            # 새 데이터 저장
            for stock_code, stock in self._stocks.items():
                # stock_code → stock_id 조회
                db_stock = session.query(DBStock).filter_by(code=stock_code).first()
                if not db_stock:
                    self._logger.warning(f"종목 없음: {stock_code}")
                    continue
                
                # DB 저장
                db_watchlist = DBWatchlistStock(
                    stock_id=db_stock.id,
                    added_date=datetime.fromisoformat(stock.added_date.replace('Z', '+00:00')).date()
                        if isinstance(stock.added_date, str)
                        else stock.added_date,
                    total_score=stock.screening_score,
                    status=stock.status
                )
                session.add(db_watchlist)
            
            session.commit()
            self._logger.debug("감시 리스트 데이터 저장 완료 (DB)")

    def _save_to_json(self) -> None:
        """JSON 파일에 백업 저장"""
        os.makedirs(os.path.dirname(self._data_file), exist_ok=True)
        
        _v_save_data = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "data": {
                "stocks": [stock.to_dict() for stock in self._stocks.values()]
            },
        }

        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump(_v_save_data, f, ensure_ascii=False, indent=2)

        self._logger.debug("감시 리스트 데이터 저장 완료 (JSON 백업)")

    def update_sectors(self) -> Dict[str, int]:
        """감시 리스트 종목들의 섹터 정보 갱신

        Returns:
            {'success': 성공 건수, 'failed': 실패 건수}
        """
        try:
            from core.api.krx_client import KRXClient

            krx = KRXClient()
            success = 0
            failed = 0

            with self._lock:
                for stock_code, stock in self._stocks.items():
                    try:
                        sector = krx.get_sector_by_code(stock_code)
                        if sector:
                            stock.sector = sector
                            success += 1
                            self._logger.debug(f"섹터 갱신 성공: {stock_code} → {sector}")
                        else:
                            self._logger.warning(f"섹터 조회 실패: {stock_code}")
                            failed += 1
                    except Exception as e:
                        self._logger.error(
                            f"섹터 갱신 에러: {stock_code}, {e}", exc_info=True
                        )
                        failed += 1

                # DB 저장
                if success > 0:
                    self._save_data()

            self._logger.info(f"섹터 갱신 완료 - 성공: {success}건, 실패: {failed}건")
            return {'success': success, 'failed': failed}

        except Exception as e:
            self._logger.error(f"섹터 갱신 오류: {e}", exc_info=True)
            return {'success': 0, 'failed': len(self._stocks)}

    def validate_data(self) -> Tuple[bool, List[str]]:
        """데이터 무결성 검증

        Returns:
            (검증 성공 여부, 오류 메시지 리스트)
        """
        _v_errors = []

        try:
            with self._lock:
                for code, stock in self._stocks.items():
                    # 필수 필드 검증
                    if not stock.stock_code:
                        _v_errors.append(f"종목 코드가 비어있습니다: {code}")

                    if not stock.stock_name:
                        _v_errors.append(f"종목명이 비어있습니다: {code}")

                    if stock.target_price <= 0:
                        _v_errors.append(f"목표가가 유효하지 않습니다: {code}")

                    if stock.stop_loss <= 0:
                        _v_errors.append(f"손절가가 유효하지 않습니다: {code}")

                    if stock.screening_score < 0 or stock.screening_score > 100:
                        _v_errors.append(f"스크리닝 점수가 유효하지 않습니다: {code}")

                    if stock.status not in ["active", "paused", "removed"]:
                        _v_errors.append(f"상태가 유효하지 않습니다: {code}")

            _v_is_valid = len(_v_errors) == 0

            if _v_is_valid:
                self._logger.info("데이터 무결성 검증 통과")
            else:
                self._logger.warning(
                    f"데이터 무결성 검증 실패: {len(_v_errors)}개 오류"
                )

            return _v_is_valid, _v_errors

        except Exception as e:
            self._logger.error(f"데이터 검증 오류: {e}", exc_info=True)
            return False, [str(e)]
