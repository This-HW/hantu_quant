"""
일일 선정 정확도 자동 측정 시스템

AI 시스템의 종목 선정 정확도를 매일 자동으로 측정하고 추적
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import json
import threading
import time
import schedule

from core.utils.log_utils import get_logger
from core.api.kis_api import KISAPI
from core.database.models import Base
from core.database.session import SessionLocal

logger = get_logger(__name__)

@dataclass
class DailyAccuracyResult:
    """일일 정확도 결과"""
    date: str
    total_predictions: int
    
    # 1일 후 성과
    positive_1d: int
    positive_rate_1d: float
    avg_return_1d: float
    
    # 7일 후 성과  
    positive_7d: int
    positive_rate_7d: float
    avg_return_7d: float
    
    # 30일 후 성과
    positive_30d: int
    positive_rate_30d: float
    avg_return_30d: float
    
    # 강한 수익 기준 (5% 이상)
    strong_positive_1d: int
    strong_positive_rate_1d: float
    strong_positive_7d: int
    strong_positive_rate_7d: float
    
    # 섹터별 정확도
    sector_accuracy: Dict[str, float]
    
    # 상위 성과 종목
    top_performers: List[Dict[str, Any]]
    
    # 하위 성과 종목
    worst_performers: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

@dataclass
class AccuracyTrend:
    """정확도 트렌드 분석"""
    period_days: int
    
    # 트렌드 지표
    avg_accuracy_1d: float
    avg_accuracy_7d: float
    trend_direction: str  # 'improving', 'declining', 'stable'
    
    # 변동성
    accuracy_volatility: float
    consistency_score: float  # 0-1 점수
    
    # 최고/최저
    best_day: str
    best_accuracy: float
    worst_day: str
    worst_accuracy: float
    
    # 예측
    predicted_next_accuracy: Optional[float] = None

class AccuracyTracker:
    """일일 선정 정확도 자동 추적 시스템"""
    
    def __init__(self, db_path: str = "data/accuracy_tracking.db"):
        """초기화
        
        Args:
            db_path: 추적 데이터베이스 경로
        """
        self._logger = logger
        self._db_path = db_path
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        
        # API 클라이언트 (주가 데이터 조회용)
        self._api_client: Optional[KISApiClient] = None
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 스케줄러 설정
        self._setup_scheduler()
        
        self._logger.info("AccuracyTracker 초기화 완료")
    
    def set_api_client(self, api_client: KISApiClient):
        """API 클라이언트 설정"""
        self._api_client = api_client
    
    def _init_database(self):
        """데이터베이스 테이블 초기화"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                # 일일 선정 기록 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS daily_selections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        selection_date TEXT NOT NULL,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT,
                        sector TEXT,
                        selection_price REAL,
                        selection_reason TEXT,
                        confidence_score REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(selection_date, stock_code)
                    )
                ''')
                
                # 성과 추적 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS performance_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        selection_date TEXT NOT NULL,
                        stock_code TEXT NOT NULL,
                        
                        -- 1일 후 성과
                        price_1d REAL,
                        return_1d REAL,
                        
                        -- 7일 후 성과
                        price_7d REAL,
                        return_7d REAL,
                        
                        -- 30일 후 성과
                        price_30d REAL,
                        return_30d REAL,
                        
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(selection_date, stock_code)
                    )
                ''')
                
                # 일일 정확도 결과 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS daily_accuracy (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        analysis_date TEXT NOT NULL UNIQUE,
                        target_date TEXT NOT NULL,
                        total_predictions INTEGER,
                        
                        -- 1일 성과
                        positive_1d INTEGER,
                        positive_rate_1d REAL,
                        avg_return_1d REAL,
                        
                        -- 7일 성과
                        positive_7d INTEGER,
                        positive_rate_7d REAL,
                        avg_return_7d REAL,
                        
                        -- 30일 성과
                        positive_30d INTEGER,
                        positive_rate_30d REAL,
                        avg_return_30d REAL,
                        
                        -- 강한 수익 기준
                        strong_positive_1d INTEGER,
                        strong_positive_rate_1d REAL,
                        strong_positive_7d INTEGER,
                        strong_positive_rate_7d REAL,
                        
                        -- JSON 데이터
                        sector_accuracy TEXT,
                        top_performers TEXT,
                        worst_performers TEXT,
                        
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                self._logger.info("데이터베이스 테이블 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}", exc_info=True)
    
    def _setup_scheduler(self):
        """스케줄러 설정"""
        # 매일 오후 6시에 정확도 분석 실행
        schedule.every().day.at("18:00").do(self._run_daily_accuracy_analysis)
        
        # 매일 오전 9시에 성과 업데이트 (1일, 7일, 30일 후 데이터)
        schedule.every().day.at("09:00").do(self._update_performance_data)
    
    def record_daily_selection(self, date: str, stock_code: str, stock_name: str,
                             sector: str, selection_price: float,
                             selection_reason: str = "", confidence_score: float = 0.0):
        """일일 선정 종목 기록
        
        Args:
            date: 선정 날짜 (YYYY-MM-DD)
            stock_code: 종목 코드
            stock_name: 종목명
            sector: 섹터
            selection_price: 선정 시점 주가
            selection_reason: 선정 이유
            confidence_score: 신뢰도 점수 (0-1)
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO daily_selections 
                    (selection_date, stock_code, stock_name, sector, selection_price,
                     selection_reason, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (date, stock_code, stock_name, sector, selection_price,
                      selection_reason, confidence_score))
                
                conn.commit()
                self._logger.debug(f"일일 선정 기록: {date} - {stock_code} ({stock_name})")
                
        except Exception as e:
            self._logger.error(f"일일 선정 기록 중 오류: {e}", exc_info=True)
    
    def _get_stock_price(self, stock_code: str, date: str) -> Optional[float]:
        """특정 날짜의 주가 조회
        
        Args:
            stock_code: 종목 코드
            date: 날짜 (YYYY-MM-DD)
            
        Returns:
            해당 날짜의 종가, 조회 실패 시 None
        """
        if not self._api_client:
            self._logger.warning("API 클라이언트가 설정되지 않았습니다.")
            return None
        
        try:
            # API를 통해 주가 데이터 조회
            # 실제 구현에서는 캐시된 데이터를 우선 확인
            price_data = self._api_client.get_daily_price(stock_code, date, date)
            
            if price_data and len(price_data) > 0:
                return float(price_data[0].get('stck_clpr', 0))  # 종가
            
            return None
            
        except Exception as e:
            self._logger.error(f"주가 조회 중 오류 - {stock_code} ({date}): {e}", exc_info=True)
            return None
    
    def _update_performance_data(self):
        """성과 데이터 업데이트 (1일, 7일, 30일 후)"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                # 업데이트가 필요한 선정 기록 조회
                cursor = conn.execute('''
                    SELECT ds.selection_date, ds.stock_code, ds.selection_price
                    FROM daily_selections ds
                    LEFT JOIN performance_tracking pt 
                        ON ds.selection_date = pt.selection_date 
                        AND ds.stock_code = pt.stock_code
                    WHERE ds.selection_date >= date('now', '-35 days')
                      AND (pt.id IS NULL OR pt.last_updated < date('now', '-1 day'))
                ''')
                
                selections = cursor.fetchall()
                
                for selection_date, stock_code, selection_price in selections:
                    # 각 기간별 성과 계산
                    price_1d = self._get_price_after_days(stock_code, selection_date, 1)
                    price_7d = self._get_price_after_days(stock_code, selection_date, 7)
                    price_30d = self._get_price_after_days(stock_code, selection_date, 30)
                    
                    # 수익률 계산
                    return_1d = ((price_1d / selection_price) - 1) * 100 if price_1d else None
                    return_7d = ((price_7d / selection_price) - 1) * 100 if price_7d else None
                    return_30d = ((price_30d / selection_price) - 1) * 100 if price_30d else None
                    
                    # 데이터베이스 업데이트
                    conn.execute('''
                        INSERT OR REPLACE INTO performance_tracking
                        (selection_date, stock_code, price_1d, return_1d,
                         price_7d, return_7d, price_30d, return_30d, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ''', (selection_date, stock_code, price_1d, return_1d,
                          price_7d, return_7d, price_30d, return_30d))
                
                conn.commit()
                self._logger.info(f"성과 데이터 업데이트 완료: {len(selections)}개 종목")
                
        except Exception as e:
            self._logger.error(f"성과 데이터 업데이트 중 오류: {e}", exc_info=True)
    
    def _get_price_after_days(self, stock_code: str, base_date: str, days: int) -> Optional[float]:
        """기준 날짜로부터 N일 후 주가 조회"""
        try:
            target_date = datetime.strptime(base_date, '%Y-%m-%d') + timedelta(days=days)
            
            # 주말/공휴일 고려하여 최대 7일까지 앞으로 이동
            for i in range(7):
                check_date = (target_date + timedelta(days=i)).strftime('%Y-%m-%d')
                price = self._get_stock_price(stock_code, check_date)
                if price:
                    return price
            
            return None
            
        except Exception as e:
            self._logger.error(f"N일 후 주가 조회 중 오류: {e}", exc_info=True)
            return None
    
    def _run_daily_accuracy_analysis(self):
        """일일 정확도 분석 실행"""
        try:
            # 분석 대상 날짜들 결정
            today = datetime.now().strftime('%Y-%m-%d')
            
            # 1일, 7일, 30일 전 선정에 대한 분석
            dates_to_analyze = [
                (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),   # 1일 전
                (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),   # 7일 전  
                (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),  # 30일 전
            ]
            
            for target_date in dates_to_analyze:
                accuracy_result = self._analyze_accuracy_for_date(target_date)
                if accuracy_result:
                    self._save_accuracy_result(today, accuracy_result)
            
            self._logger.info("일일 정확도 분석 완료")
            
        except Exception as e:
            self._logger.error(f"일일 정확도 분석 중 오류: {e}", exc_info=True)
    
    def _analyze_accuracy_for_date(self, target_date: str) -> Optional[DailyAccuracyResult]:
        """특정 날짜의 선정에 대한 정확도 분석"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                # 해당 날짜의 선정 및 성과 데이터 조회
                query = '''
                    SELECT ds.stock_code, ds.stock_name, ds.sector,
                           ds.selection_price, ds.confidence_score,
                           pt.return_1d, pt.return_7d, pt.return_30d
                    FROM daily_selections ds
                    LEFT JOIN performance_tracking pt 
                        ON ds.selection_date = pt.selection_date 
                        AND ds.stock_code = pt.stock_code
                    WHERE ds.selection_date = ?
                '''
                
                df = pd.read_sql_query(query, conn, params=[target_date])
                
                if df.empty:
                    return None
                
                # 유효한 데이터만 필터링 (None 값 제외)
                df_1d = df[df['return_1d'].notna()]
                df_7d = df[df['return_7d'].notna()]
                df_30d = df[df['return_30d'].notna()]
                
                # 기본 지표 계산
                total_predictions = len(df)
                
                # 1일 성과
                positive_1d = len(df_1d[df_1d['return_1d'] > 0]) if not df_1d.empty else 0
                positive_rate_1d = (positive_1d / len(df_1d) * 100) if not df_1d.empty else 0.0
                avg_return_1d = df_1d['return_1d'].mean() if not df_1d.empty else 0.0
                
                # 7일 성과
                positive_7d = len(df_7d[df_7d['return_7d'] > 0]) if not df_7d.empty else 0
                positive_rate_7d = (positive_7d / len(df_7d) * 100) if not df_7d.empty else 0.0
                avg_return_7d = df_7d['return_7d'].mean() if not df_7d.empty else 0.0
                
                # 30일 성과
                positive_30d = len(df_30d[df_30d['return_30d'] > 0]) if not df_30d.empty else 0
                positive_rate_30d = (positive_30d / len(df_30d) * 100) if not df_30d.empty else 0.0
                avg_return_30d = df_30d['return_30d'].mean() if not df_30d.empty else 0.0
                
                # 강한 수익 기준 (5% 이상)
                strong_positive_1d = len(df_1d[df_1d['return_1d'] >= 5.0]) if not df_1d.empty else 0
                strong_positive_rate_1d = (strong_positive_1d / len(df_1d) * 100) if not df_1d.empty else 0.0
                strong_positive_7d = len(df_7d[df_7d['return_7d'] >= 5.0]) if not df_7d.empty else 0
                strong_positive_rate_7d = (strong_positive_7d / len(df_7d) * 100) if not df_7d.empty else 0.0
                
                # 섹터별 정확도
                sector_accuracy = {}
                if not df_7d.empty:
                    for sector in df_7d['sector'].unique():
                        sector_df = df_7d[df_7d['sector'] == sector]
                        if not sector_df.empty:
                            sector_positive = len(sector_df[sector_df['return_7d'] > 0])
                            sector_accuracy[sector] = (sector_positive / len(sector_df) * 100)
                
                # 상위/하위 성과 종목
                top_performers = []
                worst_performers = []
                
                if not df_7d.empty:
                    # 상위 5개
                    top_5 = df_7d.nlargest(5, 'return_7d')
                    top_performers = [
                        {
                            'stock_code': row['stock_code'],
                            'stock_name': row['stock_name'],
                            'sector': row['sector'],
                            'return_7d': row['return_7d']
                        }
                        for _, row in top_5.iterrows()
                    ]
                    
                    # 하위 5개
                    worst_5 = df_7d.nsmallest(5, 'return_7d')
                    worst_performers = [
                        {
                            'stock_code': row['stock_code'],
                            'stock_name': row['stock_name'],
                            'sector': row['sector'],
                            'return_7d': row['return_7d']
                        }
                        for _, row in worst_5.iterrows()
                    ]
                
                return DailyAccuracyResult(
                    date=target_date,
                    total_predictions=total_predictions,
                    positive_1d=positive_1d,
                    positive_rate_1d=positive_rate_1d,
                    avg_return_1d=avg_return_1d,
                    positive_7d=positive_7d,
                    positive_rate_7d=positive_rate_7d,
                    avg_return_7d=avg_return_7d,
                    positive_30d=positive_30d,
                    positive_rate_30d=positive_rate_30d,
                    avg_return_30d=avg_return_30d,
                    strong_positive_1d=strong_positive_1d,
                    strong_positive_rate_1d=strong_positive_rate_1d,
                    strong_positive_7d=strong_positive_7d,
                    strong_positive_rate_7d=strong_positive_rate_7d,
                    sector_accuracy=sector_accuracy,
                    top_performers=top_performers,
                    worst_performers=worst_performers
                )
                
        except Exception as e:
            self._logger.error(f"날짜별 정확도 분석 중 오류: {e}", exc_info=True)
            return None
    
    def _save_accuracy_result(self, analysis_date: str, result: DailyAccuracyResult):
        """정확도 분석 결과 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO daily_accuracy
                    (analysis_date, target_date, total_predictions,
                     positive_1d, positive_rate_1d, avg_return_1d,
                     positive_7d, positive_rate_7d, avg_return_7d,
                     positive_30d, positive_rate_30d, avg_return_30d,
                     strong_positive_1d, strong_positive_rate_1d,
                     strong_positive_7d, strong_positive_rate_7d,
                     sector_accuracy, top_performers, worst_performers)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis_date, result.date, result.total_predictions,
                    result.positive_1d, result.positive_rate_1d, result.avg_return_1d,
                    result.positive_7d, result.positive_rate_7d, result.avg_return_7d,
                    result.positive_30d, result.positive_rate_30d, result.avg_return_30d,
                    result.strong_positive_1d, result.strong_positive_rate_1d,
                    result.strong_positive_7d, result.strong_positive_rate_7d,
                    json.dumps(result.sector_accuracy, ensure_ascii=False),
                    json.dumps(result.top_performers, ensure_ascii=False),
                    json.dumps(result.worst_performers, ensure_ascii=False)
                ))
                
                conn.commit()
                self._logger.info(f"정확도 분석 결과 저장: {result.date}")
                
        except Exception as e:
            self._logger.error(f"정확도 결과 저장 중 오류: {e}", exc_info=True)
    
    def get_recent_accuracy(self, days: int = 30) -> List[DailyAccuracyResult]:
        """최근 정확도 결과 조회
        
        Args:
            days: 조회할 일수
            
        Returns:
            최근 정확도 결과 리스트
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                query = '''
                    SELECT * FROM daily_accuracy
                    WHERE analysis_date >= date('now', '-{} days')
                    ORDER BY analysis_date DESC
                '''.format(days)
                
                cursor = conn.execute(query)
                results = []
                
                for row in cursor.fetchall():
                    result = DailyAccuracyResult(
                        date=row[2],  # target_date
                        total_predictions=row[3],
                        positive_1d=row[4],
                        positive_rate_1d=row[5],
                        avg_return_1d=row[6],
                        positive_7d=row[7],
                        positive_rate_7d=row[8],
                        avg_return_7d=row[9],
                        positive_30d=row[10],
                        positive_rate_30d=row[11],
                        avg_return_30d=row[12],
                        strong_positive_1d=row[13],
                        strong_positive_rate_1d=row[14],
                        strong_positive_7d=row[15],
                        strong_positive_rate_7d=row[16],
                        sector_accuracy=json.loads(row[17]) if row[17] else {},
                        top_performers=json.loads(row[18]) if row[18] else [],
                        worst_performers=json.loads(row[19]) if row[19] else []
                    )
                    results.append(result)
                
                return results
                
        except Exception as e:
            self._logger.error(f"최근 정확도 조회 중 오류: {e}", exc_info=True)
            return []
    
    def analyze_accuracy_trend(self, days: int = 30) -> Optional[AccuracyTrend]:
        """정확도 트렌드 분석"""
        try:
            recent_results = self.get_recent_accuracy(days)
            
            if len(recent_results) < 7:  # 최소 7일 데이터 필요
                return None
            
            # 7일 정확도 시계열 추출
            accuracy_7d_series = [r.positive_rate_7d for r in recent_results]
            accuracy_1d_series = [r.positive_rate_1d for r in recent_results]
            
            # 평균 정확도
            avg_accuracy_7d = np.mean(accuracy_7d_series)
            avg_accuracy_1d = np.mean(accuracy_1d_series)
            
            # 트렌드 방향 분석 (선형 회귀)
            x = np.arange(len(accuracy_7d_series))
            trend_slope = np.polyfit(x, accuracy_7d_series, 1)[0]
            
            if trend_slope > 0.5:
                trend_direction = 'improving'
            elif trend_slope < -0.5:
                trend_direction = 'declining'
            else:
                trend_direction = 'stable'
            
            # 변동성 계산
            accuracy_volatility = np.std(accuracy_7d_series)
            
            # 일관성 점수 (변동성이 낮을수록 높은 점수)
            consistency_score = max(0, 1 - (accuracy_volatility / 50))  # 0-1 범위
            
            # 최고/최저 날짜
            best_idx = np.argmax(accuracy_7d_series)
            worst_idx = np.argmin(accuracy_7d_series)
            
            return AccuracyTrend(
                period_days=len(recent_results),
                avg_accuracy_1d=avg_accuracy_1d,
                avg_accuracy_7d=avg_accuracy_7d,
                trend_direction=trend_direction,
                accuracy_volatility=accuracy_volatility,
                consistency_score=consistency_score,
                best_day=recent_results[best_idx].date,
                best_accuracy=accuracy_7d_series[best_idx],
                worst_day=recent_results[worst_idx].date,
                worst_accuracy=accuracy_7d_series[worst_idx]
            )
            
        except Exception as e:
            self._logger.error(f"정확도 트렌드 분석 중 오류: {e}", exc_info=True)
            return None
    
    def start_auto_tracking(self):
        """자동 추적 시작"""
        if self._running:
            self._logger.warning("자동 추적이 이미 실행 중입니다.")
            return
        
        self._running = True
        
        def scheduler_loop():
            while self._running:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 스케줄 확인
        
        self._scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        self._logger.info("정확도 자동 추적 시작")
    
    def stop_auto_tracking(self):
        """자동 추적 중지"""
        if not self._running:
            return
        
        self._running = False
        schedule.clear()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        self._logger.info("정확도 자동 추적 중지")
    
    def export_accuracy_report(self, days: int = 30, file_path: str = "accuracy_report.json"):
        """정확도 리포트 내보내기"""
        try:
            recent_results = self.get_recent_accuracy(days)
            trend_analysis = self.analyze_accuracy_trend(days)
            
            report = {
                'generated_at': datetime.now().isoformat(),
                'period_days': days,
                'total_analysis_days': len(recent_results),
                'daily_results': [result.to_dict() for result in recent_results],
                'trend_analysis': asdict(trend_analysis) if trend_analysis else None
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"정확도 리포트를 {file_path}에 저장했습니다.")
            
        except Exception as e:
            self._logger.error(f"정확도 리포트 내보내기 중 오류: {e}", exc_info=True)

# 글로벌 인스턴스
_accuracy_tracker_instance: Optional[AccuracyTracker] = None

def get_accuracy_tracker() -> AccuracyTracker:
    """정확도 추적기 인스턴스 반환 (싱글톤)"""
    global _accuracy_tracker_instance
    if _accuracy_tracker_instance is None:
        _accuracy_tracker_instance = AccuracyTracker()
    return _accuracy_tracker_instance 