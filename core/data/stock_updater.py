"""
종목 정보 업데이트 자동화 시스템

종목의 기본 정보, 재무 정보, 섹터 분류 등을 자동으로 업데이트
"""

import sqlite3
import pandas as pd
import json
import threading
import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from pathlib import Path

from ..utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class StockInfo:
    """종목 정보"""
    stock_code: str
    stock_name: str
    market_type: str  # 'KOSPI', 'KOSDAQ', 'KONEX'
    
    # 기본 정보
    sector: str
    industry: str
    listing_date: Optional[str] = None
    
    # 재무 정보
    market_cap: Optional[int] = None  # 시가총액
    shares_outstanding: Optional[int] = None  # 발행주식수
    par_value: Optional[int] = None   # 액면가
    
    # 상태 정보
    is_active: bool = True
    is_suspended: bool = False  # 거래정지
    delisting_date: Optional[str] = None
    
    # 메타데이터
    last_updated: str = ""
    data_source: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

@dataclass
class UpdateResult:
    """업데이트 결과"""
    update_date: str
    total_stocks: int
    updated_stocks: int
    new_stocks: int
    delisted_stocks: int
    errors: List[str]
    elapsed_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

class StockUpdater:
    """종목 정보 업데이트 자동화 시스템"""
    
    def __init__(self, db_path: str = "data/stock_info.db"):
        """초기화
        
        Args:
            db_path: 종목 정보 데이터베이스 경로
        """
        self._logger = logger
        self._db_path = db_path
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        
        # 업데이트 설정
        self._update_settings = {
            'daily_update_time': "06:00",     # 매일 오전 6시
            'weekly_full_update': "sunday",   # 매주 일요일 전체 업데이트
            'monthly_cleanup': 1,             # 매월 1일 정리 작업
            'api_delay': 0.1,                 # API 호출 간격 (초)
            'batch_size': 100,                # 배치 크기
        }
        
        # 외부 API 클라이언트 (실제 구현에서 설정)
        self._api_client = None
        
        # 캐시된 데이터
        self._cached_stocks: Dict[str, StockInfo] = {}
        self._cache_expiry: Optional[datetime] = None
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 스케줄러 설정
        self._setup_scheduler()
        
        self._logger.info("StockUpdater 초기화 완료")
    
    def set_api_client(self, api_client):
        """API 클라이언트 설정"""
        self._api_client = api_client
        self._logger.info("API 클라이언트 설정 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                # 종목 정보 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS stock_info (
                        stock_code TEXT PRIMARY KEY,
                        stock_name TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        sector TEXT,
                        industry TEXT,
                        listing_date TEXT,
                        market_cap INTEGER,
                        shares_outstanding INTEGER,
                        par_value INTEGER,
                        is_active INTEGER DEFAULT 1,
                        is_suspended INTEGER DEFAULT 0,
                        delisting_date TEXT,
                        last_updated TEXT,
                        data_source TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 업데이트 이력 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS update_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        update_date TEXT NOT NULL,
                        update_type TEXT NOT NULL,  -- 'daily', 'weekly', 'manual'
                        total_stocks INTEGER,
                        updated_stocks INTEGER,
                        new_stocks INTEGER,
                        delisted_stocks INTEGER,
                        errors TEXT,  -- JSON
                        elapsed_time REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 섹터 매핑 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sector_mapping (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT,
                        old_sector TEXT,
                        new_sector TEXT,
                        change_date TEXT,
                        reason TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 인덱스 생성
                conn.execute('CREATE INDEX IF NOT EXISTS idx_market_type ON stock_info(market_type)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_sector ON stock_info(sector)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_is_active ON stock_info(is_active)')
                
                conn.commit()
                self._logger.info("종목 정보 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}")
    
    def _setup_scheduler(self):
        """스케줄러 설정"""
        # 매일 오전 6시에 일일 업데이트
        schedule.every().day.at(self._update_settings['daily_update_time']).do(self._run_daily_update)
        
        # 매주 일요일 오전 7시에 전체 업데이트
        schedule.every().sunday.at("07:00").do(self._run_weekly_update)
        
        # 매월 1일 오전 8시에 정리 작업
        schedule.every().month.do(self._run_monthly_cleanup)
    
    def _fetch_stock_list_from_api(self) -> List[Dict[str, Any]]:
        """API에서 종목 리스트 조회"""
        if not self._api_client:
            self._logger.warning("API 클라이언트가 설정되지 않았습니다.")
            return []
        
        try:
            # 실제 구현에서는 KIS API를 사용
            # 여기서는 임시 데이터 반환
            mock_data = []
            for i in range(100):  # 임시로 100개 종목
                stock_code = f"00{i:04d}"
                mock_data.append({
                    'stock_code': stock_code,
                    'stock_name': f"테스트종목{i}",
                    'market_type': 'KOSPI' if i < 50 else 'KOSDAQ',
                    'sector': f"섹터{i % 10}",
                    'industry': f"업종{i % 20}",
                    'market_cap': (i + 1) * 1000000000,
                    'shares_outstanding': (i + 1) * 1000000,
                    'par_value': 500
                })
            
            self._logger.info(f"API에서 {len(mock_data)}개 종목 정보 조회")
            return mock_data
            
        except Exception as e:
            self._logger.error(f"API 종목 리스트 조회 중 오류: {e}")
            return []
    
    def _fetch_detailed_stock_info(self, stock_code: str) -> Optional[StockInfo]:
        """특정 종목의 상세 정보 조회"""
        if not self._api_client:
            return None
        
        try:
            # 실제 구현에서는 KIS API 호출
            # 여기서는 임시 데이터 반환
            import random
            
            stock_info = StockInfo(
                stock_code=stock_code,
                stock_name=f"종목{stock_code}",
                market_type=random.choice(['KOSPI', 'KOSDAQ']),
                sector=random.choice(['IT', '바이오', '금융', '제조', '유통']),
                industry=random.choice(['소프트웨어', '제약', '은행', '자동차', '의류']),
                listing_date="2020-01-01",
                market_cap=random.randint(100000000, 10000000000),
                shares_outstanding=random.randint(1000000, 100000000),
                par_value=500,
                is_active=True,
                is_suspended=False,
                last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                data_source="KIS_API"
            )
            
            # API 호출 제한 대응
            time.sleep(self._update_settings['api_delay'])
            
            return stock_info
            
        except Exception as e:
            self._logger.error(f"종목 {stock_code} 상세 정보 조회 중 오류: {e}")
            return None
    
    def _update_stock_info(self, stock_info: StockInfo) -> bool:
        """종목 정보 업데이트
        
        Args:
            stock_info: 업데이트할 종목 정보
            
        Returns:
            성공 여부
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                # 기존 정보 확인
                cursor = conn.execute(
                    'SELECT sector FROM stock_info WHERE stock_code = ?',
                    (stock_info.stock_code,)
                )
                existing = cursor.fetchone()
                
                # 섹터 변경 기록
                if existing and existing[0] != stock_info.sector:
                    conn.execute('''
                        INSERT INTO sector_mapping
                        (stock_code, old_sector, new_sector, change_date, reason)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        stock_info.stock_code, existing[0], stock_info.sector,
                        datetime.now().strftime('%Y-%m-%d'), 'automatic_update'
                    ))
                
                # 종목 정보 업데이트/삽입
                conn.execute('''
                    INSERT OR REPLACE INTO stock_info
                    (stock_code, stock_name, market_type, sector, industry,
                     listing_date, market_cap, shares_outstanding, par_value,
                     is_active, is_suspended, delisting_date, last_updated,
                     data_source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    stock_info.stock_code, stock_info.stock_name, stock_info.market_type,
                    stock_info.sector, stock_info.industry, stock_info.listing_date,
                    stock_info.market_cap, stock_info.shares_outstanding, stock_info.par_value,
                    1 if stock_info.is_active else 0, 1 if stock_info.is_suspended else 0,
                    stock_info.delisting_date, stock_info.last_updated, stock_info.data_source
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self._logger.error(f"종목 정보 업데이트 중 오류 - {stock_info.stock_code}: {e}")
            return False
    
    def _run_daily_update(self):
        """일일 업데이트 실행"""
        try:
            start_time = time.time()
            update_date = datetime.now().strftime('%Y-%m-%d')
            errors = []
            
            self._logger.info("일일 종목 정보 업데이트 시작")
            
            # 활성 종목 목록 조회
            stock_list = self._fetch_stock_list_from_api()
            
            if not stock_list:
                errors.append("API에서 종목 목록을 가져올 수 없습니다.")
                return
            
            total_stocks = len(stock_list)
            updated_stocks = 0
            new_stocks = 0
            
            # 배치 단위로 처리
            batch_size = self._update_settings['batch_size']
            
            for i in range(0, len(stock_list), batch_size):
                batch = stock_list[i:i + batch_size]
                
                for stock_data in batch:
                    try:
                        # 기존 종목인지 확인
                        is_new = not self._stock_exists(stock_data['stock_code'])
                        
                        # StockInfo 객체 생성
                        stock_info = StockInfo(
                            stock_code=stock_data['stock_code'],
                            stock_name=stock_data['stock_name'],
                            market_type=stock_data['market_type'],
                            sector=stock_data.get('sector', '기타'),
                            industry=stock_data.get('industry', '기타'),
                            market_cap=stock_data.get('market_cap'),
                            shares_outstanding=stock_data.get('shares_outstanding'),
                            par_value=stock_data.get('par_value'),
                            last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            data_source="daily_update"
                        )
                        
                        # 업데이트 실행
                        if self._update_stock_info(stock_info):
                            updated_stocks += 1
                            if is_new:
                                new_stocks += 1
                        
                    except Exception as e:
                        error_msg = f"종목 {stock_data.get('stock_code', 'Unknown')} 처리 중 오류: {e}"
                        errors.append(error_msg)
                        self._logger.error(error_msg)
                
                # 배치 간 대기
                time.sleep(1)
            
            # 상장폐지 종목 확인
            delisted_stocks = self._check_delisted_stocks()
            
            elapsed_time = time.time() - start_time
            
            # 결과 저장
            result = UpdateResult(
                update_date=update_date,
                total_stocks=total_stocks,
                updated_stocks=updated_stocks,
                new_stocks=new_stocks,
                delisted_stocks=delisted_stocks,
                errors=errors,
                elapsed_time=elapsed_time
            )
            
            self._save_update_result(result, 'daily')
            
            self._logger.info(
                f"일일 업데이트 완료: {updated_stocks}/{total_stocks} 종목 "
                f"(신규 {new_stocks}, 상장폐지 {delisted_stocks}, "
                f"소요시간 {elapsed_time:.1f}초)"
            )
            
        except Exception as e:
            self._logger.error(f"일일 업데이트 중 오류: {e}")
    
    def _run_weekly_update(self):
        """주간 전체 업데이트 실행"""
        try:
            self._logger.info("주간 전체 업데이트 시작")
            
            # 모든 종목의 상세 정보 업데이트
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute('SELECT stock_code FROM stock_info WHERE is_active = 1')
                active_stocks = [row[0] for row in cursor.fetchall()]
            
            updated_count = 0
            errors = []
            
            for stock_code in active_stocks:
                try:
                    detailed_info = self._fetch_detailed_stock_info(stock_code)
                    if detailed_info and self._update_stock_info(detailed_info):
                        updated_count += 1
                except Exception as e:
                    errors.append(f"종목 {stock_code}: {e}")
            
            self._logger.info(f"주간 업데이트 완료: {updated_count}/{len(active_stocks)} 종목")
            
        except Exception as e:
            self._logger.error(f"주간 업데이트 중 오류: {e}")
    
    def _run_monthly_cleanup(self):
        """월간 정리 작업 실행"""
        try:
            self._logger.info("월간 정리 작업 시작")
            
            with sqlite3.connect(self._db_path) as conn:
                # 90일 이상 된 업데이트 이력 삭제
                conn.execute('''
                    DELETE FROM update_history 
                    WHERE created_at < date('now', '-90 days')
                ''')
                
                # 30일 이상 된 섹터 변경 이력 정리
                conn.execute('''
                    DELETE FROM sector_mapping 
                    WHERE created_at < date('now', '-30 days')
                ''')
                
                conn.commit()
            
            self._logger.info("월간 정리 작업 완료")
            
        except Exception as e:
            self._logger.error(f"월간 정리 작업 중 오류: {e}")
    
    def _stock_exists(self, stock_code: str) -> bool:
        """종목 존재 여부 확인"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM stock_info WHERE stock_code = ?',
                    (stock_code,)
                )
                return cursor.fetchone()[0] > 0
        except:
            return False
    
    def _check_delisted_stocks(self) -> int:
        """상장폐지 종목 확인 및 업데이트"""
        # 실제 구현에서는 API를 통해 상장폐지 종목 확인
        # 여기서는 임시로 0 반환
        return 0
    
    def _save_update_result(self, result: UpdateResult, update_type: str):
        """업데이트 결과 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT INTO update_history
                    (update_date, update_type, total_stocks, updated_stocks,
                     new_stocks, delisted_stocks, errors, elapsed_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result.update_date, update_type, result.total_stocks,
                    result.updated_stocks, result.new_stocks, result.delisted_stocks,
                    json.dumps(result.errors, ensure_ascii=False), result.elapsed_time
                ))
                conn.commit()
        except Exception as e:
            self._logger.error(f"업데이트 결과 저장 중 오류: {e}")
    
    def get_stock_info(self, stock_code: str) -> Optional[StockInfo]:
        """종목 정보 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM stock_info WHERE stock_code = ?',
                    (stock_code,)
                )
                row = cursor.fetchone()
                
                if row:
                    return StockInfo(
                        stock_code=row[0],
                        stock_name=row[1],
                        market_type=row[2],
                        sector=row[3],
                        industry=row[4],
                        listing_date=row[5],
                        market_cap=row[6],
                        shares_outstanding=row[7],
                        par_value=row[8],
                        is_active=bool(row[9]),
                        is_suspended=bool(row[10]),
                        delisting_date=row[11],
                        last_updated=row[12],
                        data_source=row[13]
                    )
                return None
                
        except Exception as e:
            self._logger.error(f"종목 정보 조회 중 오류: {e}")
            return None
    
    def get_stocks_by_sector(self, sector: str) -> List[StockInfo]:
        """섹터별 종목 목록 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM stock_info WHERE sector = ? AND is_active = 1',
                    (sector,)
                )
                
                stocks = []
                for row in cursor.fetchall():
                    stock_info = StockInfo(
                        stock_code=row[0],
                        stock_name=row[1],
                        market_type=row[2],
                        sector=row[3],
                        industry=row[4],
                        listing_date=row[5],
                        market_cap=row[6],
                        shares_outstanding=row[7],
                        par_value=row[8],
                        is_active=bool(row[9]),
                        is_suspended=bool(row[10]),
                        delisting_date=row[11],
                        last_updated=row[12],
                        data_source=row[13]
                    )
                    stocks.append(stock_info)
                
                return stocks
                
        except Exception as e:
            self._logger.error(f"섹터별 종목 조회 중 오류: {e}")
            return []
    
    def get_update_history(self, days: int = 30) -> List[UpdateResult]:
        """업데이트 이력 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM update_history
                    WHERE created_at >= date('now', '-{} days')
                    ORDER BY created_at DESC
                '''.format(days))
                
                results = []
                for row in cursor.fetchall():
                    result = UpdateResult(
                        update_date=row[1],
                        total_stocks=row[3],
                        updated_stocks=row[4],
                        new_stocks=row[5],
                        delisted_stocks=row[6],
                        errors=json.loads(row[7]) if row[7] else [],
                        elapsed_time=row[8]
                    )
                    results.append(result)
                
                return results
                
        except Exception as e:
            self._logger.error(f"업데이트 이력 조회 중 오류: {e}")
            return []
    
    def manual_update_stock(self, stock_code: str) -> bool:
        """수동 종목 정보 업데이트"""
        try:
            detailed_info = self._fetch_detailed_stock_info(stock_code)
            if detailed_info:
                return self._update_stock_info(detailed_info)
            return False
        except Exception as e:
            self._logger.error(f"수동 업데이트 중 오류: {e}")
            return False
    
    def start_auto_update(self):
        """자동 업데이트 시작"""
        if self._running:
            self._logger.warning("자동 업데이트가 이미 실행 중입니다.")
            return
        
        self._running = True
        
        def scheduler_loop():
            while self._running:
                schedule.run_pending()
                time.sleep(60)
        
        self._scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        self._logger.info("종목 정보 자동 업데이트 시작")
    
    def stop_auto_update(self):
        """자동 업데이트 중지"""
        if not self._running:
            return
        
        self._running = False
        schedule.clear()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        self._logger.info("종목 정보 자동 업데이트 중지")

# 글로벌 인스턴스
_stock_updater_instance: Optional[StockUpdater] = None

def get_stock_updater() -> StockUpdater:
    """종목 업데이터 인스턴스 반환 (싱글톤)"""
    global _stock_updater_instance
    if _stock_updater_instance is None:
        _stock_updater_instance = StockUpdater()
    return _stock_updater_instance 