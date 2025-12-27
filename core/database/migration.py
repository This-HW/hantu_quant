"""
데이터베이스 마이그레이션 모듈 (P3-5)

JSON 파일에서 DB로 데이터 마이그레이션

Usage:
    from core.database.migration import DataMigrator

    migrator = DataMigrator(session)
    result = migrator.migrate_watchlist('data/watchlist.json')
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .models import (
    Base,
    Stock,
    WatchlistStock,
    DailySelection,
    TradeHistory,
)

logger = logging.getLogger(__name__)


class MigrationResult:
    """마이그레이션 결과"""

    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.errors: List[str] = []

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.success / self.total

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total': self.total,
            'success': self.success,
            'failed': self.failed,
            'success_rate': f"{self.success_rate:.1%}",
            'errors': self.errors[:10],  # 처음 10개만
        }


class DataMigrator:
    """데이터 마이그레이터

    JSON 파일에서 DB로 데이터 이관

    Usage:
        migrator = DataMigrator(session)
        result = migrator.migrate_watchlist('data/watchlist.json')
        result = migrator.migrate_daily_selections('data/selections.json')
    """

    def __init__(self, session: Session):
        """초기화

        Args:
            session: SQLAlchemy 세션
        """
        self.session = session

    def _get_or_create_stock(self, code: str, name: str = None) -> Optional[Stock]:
        """종목 조회 또는 생성"""
        try:
            stock = self.session.query(Stock).filter_by(code=code).first()
            if not stock:
                stock = Stock(
                    code=code,
                    name=name or f"종목_{code}",
                    market="KOSPI",
                )
                self.session.add(stock)
                self.session.flush()
            return stock
        except SQLAlchemyError as e:
            logger.error(f"종목 조회/생성 실패 {code}: {e}")
            return None

    def migrate_watchlist(
        self,
        json_path: str,
        clear_existing: bool = False,
    ) -> MigrationResult:
        """관심종목 마이그레이션

        Args:
            json_path: JSON 파일 경로
            clear_existing: 기존 데이터 삭제 여부

        Returns:
            MigrationResult
        """
        result = MigrationResult()

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"파일 없음: {json_path}")
            result.errors.append(f"파일 없음: {json_path}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            result.errors.append(f"JSON 파싱 실패: {str(e)}")
            return result

        # 기존 데이터 삭제
        if clear_existing:
            self.session.query(WatchlistStock).delete()
            logger.info("기존 WatchlistStock 데이터 삭제")

        # 데이터 형태 확인
        items = data if isinstance(data, list) else data.get('watchlist', data.get('items', []))

        for item in items:
            result.total += 1

            try:
                code = item.get('code') or item.get('stock_code')
                if not code:
                    result.failed += 1
                    result.errors.append(f"종목코드 없음: {item}")
                    continue

                stock = self._get_or_create_stock(
                    code=code,
                    name=item.get('name', item.get('stock_name')),
                )
                if not stock:
                    result.failed += 1
                    result.errors.append(f"종목 생성 실패: {code}")
                    continue

                # 날짜 파싱
                added_date = item.get('added_date') or item.get('date')
                if isinstance(added_date, str):
                    added_date = datetime.fromisoformat(added_date.replace('Z', '+00:00')).date()
                elif added_date is None:
                    added_date = date.today()

                watchlist = WatchlistStock(
                    stock_id=stock.id,
                    added_date=added_date,
                    total_score=item.get('total_score', item.get('score', 0)),
                    fundamental_score=item.get('fundamental_score'),
                    technical_score=item.get('technical_score'),
                    momentum_score=item.get('momentum_score'),
                    roe=item.get('roe'),
                    per=item.get('per'),
                    pbr=item.get('pbr'),
                    debt_ratio=item.get('debt_ratio'),
                    status=item.get('status', 'active'),
                )

                self.session.add(watchlist)
                result.success += 1

            except Exception as e:
                result.failed += 1
                result.errors.append(f"처리 실패 {item}: {str(e)}")
                logger.error(f"WatchlistStock 마이그레이션 실패: {e}")

        try:
            self.session.commit()
            logger.info(f"WatchlistStock 마이그레이션 완료: {result.success}/{result.total}")
        except SQLAlchemyError as e:
            self.session.rollback()
            result.errors.append(f"커밋 실패: {str(e)}")
            logger.error(f"커밋 실패: {e}")

        return result

    def migrate_daily_selections(
        self,
        json_path: str,
        clear_existing: bool = False,
    ) -> MigrationResult:
        """일일 선정종목 마이그레이션

        Args:
            json_path: JSON 파일 경로
            clear_existing: 기존 데이터 삭제 여부

        Returns:
            MigrationResult
        """
        result = MigrationResult()

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"파일 없음: {json_path}")
            result.errors.append(f"파일 없음: {json_path}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            result.errors.append(f"JSON 파싱 실패: {str(e)}")
            return result

        if clear_existing:
            self.session.query(DailySelection).delete()
            logger.info("기존 DailySelection 데이터 삭제")

        items = data if isinstance(data, list) else data.get('selections', data.get('items', []))

        for item in items:
            result.total += 1

            try:
                code = item.get('code') or item.get('stock_code')
                if not code:
                    result.failed += 1
                    result.errors.append(f"종목코드 없음: {item}")
                    continue

                stock = self._get_or_create_stock(
                    code=code,
                    name=item.get('name', item.get('stock_name')),
                )
                if not stock:
                    result.failed += 1
                    result.errors.append(f"종목 생성 실패: {code}")
                    continue

                # 날짜 파싱
                selection_date = item.get('selection_date') or item.get('date')
                if isinstance(selection_date, str):
                    selection_date = datetime.fromisoformat(selection_date.replace('Z', '+00:00')).date()
                elif selection_date is None:
                    selection_date = date.today()

                selection = DailySelection(
                    stock_id=stock.id,
                    selection_date=selection_date,
                    total_score=item.get('total_score', item.get('score', 0)),
                    technical_score=item.get('technical_score'),
                    volume_score=item.get('volume_score'),
                    momentum_score=item.get('momentum_score'),
                    risk_score=item.get('risk_score'),
                    rsi=item.get('rsi'),
                    macd=item.get('macd'),
                    bb_position=item.get('bb_position'),
                    target_price=item.get('target_price'),
                    stop_loss=item.get('stop_loss'),
                    position_size=item.get('position_size'),
                    signal=item.get('signal', 'hold'),
                    signal_strength=item.get('signal_strength'),
                    actual_return=item.get('actual_return'),
                )

                self.session.add(selection)
                result.success += 1

            except Exception as e:
                result.failed += 1
                result.errors.append(f"처리 실패 {item}: {str(e)}")
                logger.error(f"DailySelection 마이그레이션 실패: {e}")

        try:
            self.session.commit()
            logger.info(f"DailySelection 마이그레이션 완료: {result.success}/{result.total}")
        except SQLAlchemyError as e:
            self.session.rollback()
            result.errors.append(f"커밋 실패: {str(e)}")
            logger.error(f"커밋 실패: {e}")

        return result

    def migrate_trades(
        self,
        json_path: str,
        clear_existing: bool = False,
    ) -> MigrationResult:
        """거래 이력 마이그레이션

        Args:
            json_path: JSON 파일 경로
            clear_existing: 기존 데이터 삭제 여부

        Returns:
            MigrationResult
        """
        result = MigrationResult()

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"파일 없음: {json_path}")
            result.errors.append(f"파일 없음: {json_path}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            result.errors.append(f"JSON 파싱 실패: {str(e)}")
            return result

        if clear_existing:
            self.session.query(TradeHistory).delete()
            logger.info("기존 TradeHistory 데이터 삭제")

        items = data if isinstance(data, list) else data.get('trades', data.get('items', []))

        for item in items:
            result.total += 1

            try:
                code = item.get('code') or item.get('stock_code')
                if not code:
                    result.failed += 1
                    result.errors.append(f"종목코드 없음: {item}")
                    continue

                stock = self._get_or_create_stock(
                    code=code,
                    name=item.get('name', item.get('stock_name')),
                )
                if not stock:
                    result.failed += 1
                    result.errors.append(f"종목 생성 실패: {code}")
                    continue

                # 날짜 파싱
                order_datetime = item.get('order_datetime') or item.get('datetime')
                if isinstance(order_datetime, str):
                    order_datetime = datetime.fromisoformat(order_datetime.replace('Z', '+00:00'))
                elif order_datetime is None:
                    order_datetime = datetime.now()

                trade = TradeHistory(
                    stock_id=stock.id,
                    order_id=item.get('order_id'),
                    order_datetime=order_datetime,
                    order_type=item.get('order_type', 'market'),
                    side=item.get('side', item.get('type', 'buy')),
                    quantity=item.get('quantity', 0),
                    filled_quantity=item.get('filled_quantity', item.get('quantity', 0)),
                    price=item.get('price'),
                    filled_price=item.get('filled_price', item.get('price')),
                    amount=item.get('amount'),
                    commission=item.get('commission', 0),
                    tax=item.get('tax', 0),
                    strategy=item.get('strategy'),
                    status=item.get('status', 'filled'),
                )

                self.session.add(trade)
                result.success += 1

            except Exception as e:
                result.failed += 1
                result.errors.append(f"처리 실패 {item}: {str(e)}")
                logger.error(f"TradeHistory 마이그레이션 실패: {e}")

        try:
            self.session.commit()
            logger.info(f"TradeHistory 마이그레이션 완료: {result.success}/{result.total}")
        except SQLAlchemyError as e:
            self.session.rollback()
            result.errors.append(f"커밋 실패: {str(e)}")
            logger.error(f"커밋 실패: {e}")

        return result

    def create_tables(self):
        """테이블 생성"""
        from .session import engine
        Base.metadata.create_all(engine)
        logger.info("데이터베이스 테이블 생성 완료")

    def migrate_all(
        self,
        data_dir: str = "data",
        clear_existing: bool = False,
    ) -> Dict[str, MigrationResult]:
        """전체 마이그레이션

        Args:
            data_dir: 데이터 디렉토리
            clear_existing: 기존 데이터 삭제 여부

        Returns:
            마이그레이션 결과 딕셔너리
        """
        results = {}
        data_path = Path(data_dir)

        # 관심종목
        watchlist_files = list(data_path.glob("*watchlist*.json"))
        if watchlist_files:
            results['watchlist'] = self.migrate_watchlist(
                str(watchlist_files[0]),
                clear_existing=clear_existing,
            )

        # 일일 선정
        selection_files = list(data_path.glob("*selection*.json"))
        if selection_files:
            results['selections'] = self.migrate_daily_selections(
                str(selection_files[0]),
                clear_existing=clear_existing,
            )

        # 거래 이력
        trade_files = list(data_path.glob("*trade*.json"))
        if trade_files:
            results['trades'] = self.migrate_trades(
                str(trade_files[0]),
                clear_existing=clear_existing,
            )

        return results
