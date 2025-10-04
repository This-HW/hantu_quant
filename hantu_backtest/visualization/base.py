"""
Base visualization module.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class BaseVisualizer:
    """시각화 기본 클래스"""
    
    def __init__(self):
        """초기화"""
        # 결과 저장 경로
        self.output_dir = Path(__file__).parent.parent / 'data' / 'results' / 'charts'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 스타일 설정
        plt.style.use('default')  # 기본 스타일 사용
        sns.set_theme(style='whitegrid')  # seaborn 테마 설정
        
    def save_figure(self, fig: plt.Figure, filename: str):
        """차트 저장
        
        Args:
            fig: matplotlib Figure 객체
            filename: 파일명
        """
        try:
            # 파일명에 타임스탬프 추가
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = self.output_dir / f"{filename}_{timestamp}.png"
            
            # 차트 저장
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            logger.info(f"[save_figure] 차트 저장 완료: {filepath}")
            
        except Exception as e:
            logger.error(f"[save_figure] 차트 저장 중 오류 발생: {str(e)}")
            raise
            
    def create_subplot_grid(self, num_plots: int) -> Tuple[plt.Figure, List[plt.Axes]]:
        """서브플롯 그리드 생성
        
        Args:
            num_plots: 플롯 개수
            
        Returns:
            Tuple[plt.Figure, List[plt.Axes]]: (Figure 객체, Axes 리스트)
        """
        # 행과 열 개수 계산
        num_cols = min(3, num_plots)
        num_rows = (num_plots - 1) // num_cols + 1
        
        # 서브플롯 생성
        fig, axes = plt.subplots(num_rows, num_cols, figsize=(6*num_cols, 4*num_rows))
        
        # axes를 1차원 리스트로 변환
        if num_plots == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
        
        # 사용하지 않는 서브플롯 제거
        for idx in range(num_plots, len(axes)):
            fig.delaxes(axes[idx])
            
        return fig, axes[:num_plots] 