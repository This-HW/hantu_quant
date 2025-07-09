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
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import threading
from copy import deepcopy

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

@dataclass
class WatchlistStock:
    """감시 리스트 종목 데이터 클래스"""
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
    def from_dict(cls, p_data: Dict) -> 'WatchlistStock':
        """딕셔너리에서 생성"""
        return cls(**p_data)

class WatchlistManager:
    """감시 리스트 관리 클래스"""
    
    def __init__(self, p_data_file: str = "data/watchlist/watchlist.json"):
        """초기화 메서드
        
        Args:
            p_data_file: 데이터 파일 경로
        """
        self._v_data_file = p_data_file
        self._v_watchlist = {}  # stock_code -> WatchlistStock
        self._v_lock = threading.Lock()
        self._v_metadata = {
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        # 데이터 로드
        self._load_data()
        logger.info(f"WatchlistManager 초기화 완료 - 종목 수: {len(self._v_watchlist)}")
    
    def add_stock(self, p_stock_code: str, p_stock_name: str, p_added_reason: str,
                  p_target_price: float, p_stop_loss: float, p_sector: str,
                  p_screening_score: float, p_notes: str = "") -> bool:
        """감시 리스트에 종목 추가
        
        Args:
            p_stock_code: 종목 코드
            p_stock_name: 종목명
            p_added_reason: 추가 이유
            p_target_price: 목표가
            p_stop_loss: 손절가
            p_sector: 섹터
            p_screening_score: 스크리닝 점수
            p_notes: 메모
            
        Returns:
            추가 성공 여부
        """
        try:
            with self._v_lock:
                # 중복 체크
                if p_stock_code in self._v_watchlist:
                    _v_existing_stock = self._v_watchlist[p_stock_code]
                    if _v_existing_stock.status == "active":
                        logger.warning(f"종목 {p_stock_code}은 이미 감시 리스트에 존재합니다.")
                        return False
                    else:
                        # 제거된 종목을 다시 활성화
                        _v_existing_stock.status = "active"
                        _v_existing_stock.added_reason = p_added_reason
                        _v_existing_stock.target_price = p_target_price
                        _v_existing_stock.stop_loss = p_stop_loss
                        _v_existing_stock.screening_score = p_screening_score
                        _v_existing_stock.notes = p_notes
                        _v_existing_stock.last_updated = datetime.now().isoformat()
                        logger.info(f"종목 {p_stock_code} 재활성화 완료")
                else:
                    # 새 종목 추가
                    _v_new_stock = WatchlistStock(
                        stock_code=p_stock_code,
                        stock_name=p_stock_name,
                        added_date=datetime.now().strftime("%Y-%m-%d"),
                        added_reason=p_added_reason,
                        target_price=p_target_price,
                        stop_loss=p_stop_loss,
                        sector=p_sector,
                        screening_score=p_screening_score,
                        last_updated=datetime.now().isoformat(),
                        notes=p_notes,
                        status="active"
                    )
                    
                    self._v_watchlist[p_stock_code] = _v_new_stock
                    logger.info(f"종목 {p_stock_code} 감시 리스트 추가 완료")
                
                # 메타데이터 업데이트
                self._v_metadata["last_updated"] = datetime.now().isoformat()
                
                # 데이터 저장
                self._save_data()
                
                return True
                
        except Exception as e:
            logger.error(f"종목 추가 오류: {e}")
            return False
    
    def get_stock(self, p_stock_code: str) -> Optional[WatchlistStock]:
        """특정 종목 조회
        
        Args:
            p_stock_code: 종목 코드
            
        Returns:
            종목 정보 또는 None
        """
        try:
            with self._v_lock:
                return self._v_watchlist.get(p_stock_code)
                
        except Exception as e:
            logger.error(f"종목 조회 오류: {e}")
            return None
    
    def update_stock(self, p_stock_code: str, p_updates: Dict) -> bool:
        """종목 정보 수정
        
        Args:
            p_stock_code: 종목 코드
            p_updates: 수정할 정보 딕셔너리
            
        Returns:
            수정 성공 여부
        """
        try:
            with self._v_lock:
                if p_stock_code not in self._v_watchlist:
                    logger.warning(f"종목 {p_stock_code}이 감시 리스트에 없습니다.")
                    return False
                
                _v_stock = self._v_watchlist[p_stock_code]
                
                # 수정 가능한 필드만 업데이트
                _v_updatable_fields = {
                    "added_reason", "target_price", "stop_loss", "notes", "status"
                }
                
                _v_updated = False
                for field, value in p_updates.items():
                    if field in _v_updatable_fields and hasattr(_v_stock, field):
                        setattr(_v_stock, field, value)
                        _v_updated = True
                
                if _v_updated:
                    _v_stock.last_updated = datetime.now().isoformat()
                    self._v_metadata["last_updated"] = datetime.now().isoformat()
                    self._save_data()
                    logger.info(f"종목 {p_stock_code} 정보 수정 완료")
                    return True
                else:
                    logger.warning(f"종목 {p_stock_code} 수정할 내용이 없습니다.")
                    return False
                
        except Exception as e:
            logger.error(f"종목 수정 오류: {e}")
            return False
    
    def remove_stock(self, p_stock_code: str, p_permanent: bool = False) -> bool:
        """종목 제거
        
        Args:
            p_stock_code: 종목 코드
            p_permanent: 영구 삭제 여부 (False면 상태만 변경)
            
        Returns:
            제거 성공 여부
        """
        try:
            with self._v_lock:
                if p_stock_code not in self._v_watchlist:
                    logger.warning(f"종목 {p_stock_code}이 감시 리스트에 없습니다.")
                    return False
                
                if p_permanent:
                    # 영구 삭제
                    del self._v_watchlist[p_stock_code]
                    logger.info(f"종목 {p_stock_code} 영구 삭제 완료")
                else:
                    # 상태만 변경
                    self._v_watchlist[p_stock_code].status = "removed"
                    self._v_watchlist[p_stock_code].last_updated = datetime.now().isoformat()
                    logger.info(f"종목 {p_stock_code} 제거 상태로 변경 완료")
                
                # 메타데이터 업데이트
                self._v_metadata["last_updated"] = datetime.now().isoformat()
                
                # 데이터 저장
                self._save_data()
                
                return True
                
        except Exception as e:
            logger.error(f"종목 제거 오류: {e}")
            return False
    
    def list_stocks(self, p_status: Optional[str] = "active", p_sector: Optional[str] = None,
                   p_sort_by: str = "screening_score", p_ascending: bool = False) -> List[WatchlistStock]:
        """감시 리스트 조회
        
        Args:
            p_status: 상태 필터 (None이면 모든 상태)
            p_sector: 섹터 필터 (None이면 모든 섹터)
            p_sort_by: 정렬 기준
            p_ascending: 오름차순 여부
            
        Returns:
            종목 리스트
        """
        try:
            with self._v_lock:
                _v_stocks = list(self._v_watchlist.values())
                
                # 상태 필터링
                if p_status:
                    _v_stocks = [stock for stock in _v_stocks if stock.status == p_status]
                
                # 섹터 필터링
                if p_sector:
                    _v_stocks = [stock for stock in _v_stocks if stock.sector == p_sector]
                
                # 정렬
                if p_sort_by and _v_stocks and hasattr(_v_stocks[0], p_sort_by):
                    _v_stocks.sort(key=lambda x: getattr(x, p_sort_by), reverse=not p_ascending)
                
                return _v_stocks
                
        except Exception as e:
            logger.error(f"감시 리스트 조회 오류: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """통계 정보 조회
        
        Returns:
            통계 정보 딕셔너리
        """
        try:
            with self._v_lock:
                _v_all_stocks = list(self._v_watchlist.values())
                _v_active_stocks = [s for s in _v_all_stocks if s.status == "active"]
                
                # 기본 통계
                _v_stats = {
                    "total_count": len(_v_all_stocks),
                    "active_count": len(_v_active_stocks),
                    "paused_count": len([s for s in _v_all_stocks if s.status == "paused"]),
                    "removed_count": len([s for s in _v_all_stocks if s.status == "removed"]),
                    "sector_distribution": {},
                    "score_distribution": {
                        "high": 0,      # 80점 이상
                        "medium": 0,    # 60-80점
                        "low": 0        # 60점 미만
                    },
                    "average_score": 0.0,
                    "top_stocks": []
                }
                
                if _v_active_stocks:
                    # 섹터별 분포
                    for stock in _v_active_stocks:
                        _v_stats["sector_distribution"][stock.sector] = _v_stats["sector_distribution"].get(stock.sector, 0) + 1
                    
                    # 점수 분포
                    _v_scores = [stock.screening_score for stock in _v_active_stocks]
                    _v_stats["average_score"] = sum(_v_scores) / len(_v_scores)
                    
                    for score in _v_scores:
                        if score >= 80:
                            _v_stats["score_distribution"]["high"] += 1
                        elif score >= 60:
                            _v_stats["score_distribution"]["medium"] += 1
                        else:
                            _v_stats["score_distribution"]["low"] += 1
                    
                    # 상위 종목 (점수 기준)
                    _v_sorted_stocks = sorted(_v_active_stocks, key=lambda x: x.screening_score, reverse=True)
                    _v_stats["top_stocks"] = [
                        {
                            "stock_code": stock.stock_code,
                            "stock_name": stock.stock_name,
                            "score": stock.screening_score,
                            "sector": stock.sector
                        }
                        for stock in _v_sorted_stocks[:10]
                    ]
                
                return _v_stats
                
        except Exception as e:
            logger.error(f"통계 정보 조회 오류: {e}")
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
                p_backup_file = f"data/watchlist/backup/watchlist_backup_{_v_timestamp}.json"
            
            # 백업 디렉토리 생성
            os.makedirs(os.path.dirname(p_backup_file), exist_ok=True)
            
            with self._v_lock:
                _v_backup_data = {
                    "timestamp": datetime.now().isoformat(),
                    "metadata": self._v_metadata,
                    "watchlist": {code: stock.to_dict() for code, stock in self._v_watchlist.items()}
                }
                
                with open(p_backup_file, 'w', encoding='utf-8') as f:
                    json.dump(_v_backup_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"감시 리스트 백업 완료: {p_backup_file}")
                return True
                
        except Exception as e:
            logger.error(f"백업 오류: {e}")
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
                logger.error(f"백업 파일이 존재하지 않습니다: {p_backup_file}")
                return False
            
            with open(p_backup_file, 'r', encoding='utf-8') as f:
                _v_backup_data = json.load(f)
            
            with self._v_lock:
                # 현재 데이터 백업
                self.backup_data()
                
                # 데이터 복원
                self._v_metadata = _v_backup_data.get("metadata", self._v_metadata)
                _v_watchlist_data = _v_backup_data.get("watchlist", {})
                
                self._v_watchlist = {}
                for code, stock_data in _v_watchlist_data.items():
                    self._v_watchlist[code] = WatchlistStock.from_dict(stock_data)
                
                # 데이터 저장
                self._save_data()
                
                logger.info(f"감시 리스트 복원 완료: {p_backup_file}")
                return True
                
        except Exception as e:
            logger.error(f"복원 오류: {e}")
            return False
    
    def _load_data(self) -> None:
        """데이터 로드"""
        try:
            if os.path.exists(self._v_data_file):
                with open(self._v_data_file, 'r', encoding='utf-8') as f:
                    _v_data = json.load(f)
                
                # 메타데이터 로드
                self._v_metadata = _v_data.get("metadata", self._v_metadata)
                
                # 감시 리스트 로드
                _v_watchlist_data = _v_data.get("data", {}).get("stocks", [])
                
                self._v_watchlist = {}
                for stock_data in _v_watchlist_data:
                    _v_stock = WatchlistStock.from_dict(stock_data)
                    self._v_watchlist[_v_stock.stock_code] = _v_stock
                
                logger.info(f"감시 리스트 데이터 로드 완료: {len(self._v_watchlist)}개 종목")
            else:
                logger.info("감시 리스트 데이터 파일이 없습니다. 새로 생성합니다.")
                self._save_data()
                
        except Exception as e:
            logger.error(f"데이터 로드 오류: {e}")
            self._v_watchlist = {}
    
    def _save_data(self) -> None:
        """데이터 저장"""
        try:
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self._v_data_file), exist_ok=True)
            
            _v_save_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "metadata": self._v_metadata,
                "data": {
                    "stocks": [stock.to_dict() for stock in self._v_watchlist.values()]
                }
            }
            
            with open(self._v_data_file, 'w', encoding='utf-8') as f:
                json.dump(_v_save_data, f, ensure_ascii=False, indent=2)
            
            logger.debug("감시 리스트 데이터 저장 완료")
            
        except Exception as e:
            logger.error(f"데이터 저장 오류: {e}")
    
    def validate_data(self) -> Tuple[bool, List[str]]:
        """데이터 무결성 검증
        
        Returns:
            (검증 성공 여부, 오류 메시지 리스트)
        """
        _v_errors = []
        
        try:
            with self._v_lock:
                for code, stock in self._v_watchlist.items():
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
                logger.info("데이터 무결성 검증 통과")
            else:
                logger.warning(f"데이터 무결성 검증 실패: {len(_v_errors)}개 오류")
            
            return _v_is_valid, _v_errors
            
        except Exception as e:
            logger.error(f"데이터 검증 오류: {e}")
            return False, [str(e)] 