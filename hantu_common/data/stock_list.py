"""
Stock list management module.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class StockListManager:
    """종목 목록 관리"""
    
    def __init__(self):
        """초기화"""
        self.stock_dir = Path(__file__).parent.parent.parent / 'data' / 'stock'
        self.stock_dir.mkdir(parents=True, exist_ok=True)
        
    def load_latest_stock_list(self) -> List[Dict]:
        """가장 최근의 KRX 종목 목록 파일 로드
        
        Returns:
            List[Dict]: 종목 목록
            [
                {
                    'ticker': 종목코드,
                    'name': 종목명,
                    'market': 시장구분
                },
                ...
            ]
        """
        try:
            # 가장 최근 파일 찾기
            stock_files = list(self.stock_dir.glob('krx_stock_list_*.json'))
            if not stock_files:
                raise FileNotFoundError("KRX 종목 목록 파일이 없습니다. 'python main.py list-stocks' 명령을 실행하세요.")
            
            latest_file = max(stock_files, key=lambda x: x.name)
            logger.info(f"[load_latest_stock_list] 최신 종목 목록 파일: {latest_file}")
            
            # JSON 파일 로드
            with open(latest_file, 'r', encoding='utf-8') as f:
                stock_list = json.load(f)
            
            return stock_list
            
        except Exception as e:
            logger.error(f"[load_latest_stock_list] 종목 목록 로드 중 오류 발생: {str(e)}")
            raise
            
    def save_stock_list(self, stock_list: List[Dict]):
        """종목 목록 저장
        
        Args:
            stock_list: 종목 목록
        """
        try:
            # 현재 날짜로 파일명 생성
            today = datetime.now().strftime('%Y%m%d')
            filename = f'krx_stock_list_{today}.json'
            filepath = self.stock_dir / filename
            
            # JSON 파일로 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(stock_list, f, ensure_ascii=False, indent=2)
                
            logger.info(f"[save_stock_list] 종목 목록 저장 완료: {filepath}")
            
        except Exception as e:
            logger.error(f"[save_stock_list] 종목 목록 저장 중 오류 발생: {str(e)}")
            raise 