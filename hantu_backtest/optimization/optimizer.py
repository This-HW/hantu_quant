"""
Strategy optimization module.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Callable
from itertools import product
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import json
from datetime import datetime

from ..core.backtest import Backtest
from ..strategies.base import BacktestStrategy
from ..visualization.base import BaseVisualizer

logger = logging.getLogger(__name__)

class StrategyOptimizer:
    """전략 최적화"""
    
    def __init__(self,
                 strategy_class: type,
                 param_grid: Dict[str, List[Any]],
                 start_date: str,
                 end_date: str,
                 initial_capital: float = 100_000_000,
                 commission: float = 0.00015,
                 slippage: float = 0.0001,
                 metric: str = 'sharpe_ratio',
                 n_jobs: int = -1):
        """
        Args:
            strategy_class: 전략 클래스
            param_grid: 파라미터 그리드
                예: {
                    'rsi_period': [10, 14, 20],
                    'ma_short': [5, 10, 15]
                }
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            initial_capital: 초기 자본금
            commission: 수수료율
            slippage: 슬리피지
            metric: 최적화 기준 지표
            n_jobs: 병렬 처리 수 (-1: 모든 CPU 사용)
        """
        self.strategy_class = strategy_class
        self.param_grid = param_grid
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.metric = metric
        self.n_jobs = n_jobs if n_jobs > 0 else None  # None: 모든 CPU 사용
        
        # 결과 저장 경로
        self.results_dir = Path(__file__).parent.parent / 'data' / 'results' / 'optimization'
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # 시각화 도구
        self.visualizer = BaseVisualizer()
        
    def optimize(self) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """전략 최적화 실행
        
        Returns:
            Tuple[Dict, DataFrame]: (최적 파라미터, 전체 결과)
        """
        try:
            logger.info("[optimize] 전략 최적화 시작")
            logger.info(f"[optimize] 파라미터 그리드: {self.param_grid}")
            
            # 파라미터 조합 생성
            param_combinations = [
                dict(zip(self.param_grid.keys(), values))
                for values in product(*self.param_grid.values())
            ]
            
            logger.info(f"[optimize] 총 {len(param_combinations)}개 파라미터 조합 테스트")
            
            # 병렬 처리로 백테스트 실행
            results = []
            with ProcessPoolExecutor(max_workers=self.n_jobs) as executor:
                futures = [
                    executor.submit(self._run_backtest, params)
                    for params in param_combinations
                ]
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        logger.debug(f"[optimize] 백테스트 완료: {result}")
                    except Exception as e:
                        logger.error(f"[optimize] 백테스트 실행 중 오류 발생: {str(e)}")
                        
            # 결과 분석
            results_df = pd.DataFrame(results)
            
            # 최적 파라미터 선택
            best_result = results_df.loc[results_df[self.metric].idxmax()]
            best_params = {
                col: best_result[col]
                for col in self.param_grid.keys()
            }
            
            logger.info(f"[optimize] 최적 파라미터: {best_params}")
            logger.info(f"[optimize] 최적 성과: {self.metric}={best_result[self.metric]:.4f}")
            
            # 결과 저장
            self._save_results(results_df, best_params)
            
            # 결과 시각화
            self._visualize_results(results_df)
            
            return best_params, results_df
            
        except Exception as e:
            logger.error(f"[optimize] 최적화 중 오류 발생: {str(e)}")
            raise
            
    def _run_backtest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """개별 백테스트 실행"""
        try:
            # 전략 인스턴스 생성
            strategy = self.strategy_class(**params)
            
            # 백테스터 생성
            backtest = Backtest(
                strategy=strategy,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.initial_capital,
                commission=self.commission,
                slippage=self.slippage
            )
            
            # 백테스트 실행
            results = backtest.run()
            
            # 결과 추출
            metrics = results['metrics']
            metrics.update(params)  # 파라미터 추가
            
            return metrics
            
        except Exception as e:
            logger.error(f"[_run_backtest] 백테스트 실행 중 오류 발생: {str(e)}")
            raise
            
    def _save_results(self, results_df: pd.DataFrame, best_params: Dict[str, Any]):
        """최적화 결과 저장"""
        try:
            # 타임스탬프
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # CSV 파일로 저장
            csv_path = self.results_dir / f"optimization_results_{timestamp}.csv"
            results_df.to_csv(csv_path, index=False)
            
            # JSON 파일로 저장
            json_path = self.results_dir / f"best_params_{timestamp}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'best_params': best_params,
                    'metric': self.metric,
                    'period': {
                        'start': self.start_date,
                        'end': self.end_date
                    }
                }, f, indent=2, ensure_ascii=False)
                
            logger.info(f"[_save_results] 최적화 결과 저장 완료")
            logger.info(f"[_save_results] 결과 파일: {csv_path}")
            logger.info(f"[_save_results] 최적 파라미터 파일: {json_path}")
            
        except Exception as e:
            logger.error(f"[_save_results] 결과 저장 중 오류 발생: {str(e)}")
            
    def _visualize_results(self, results_df: pd.DataFrame):
        """최적화 결과 시각화"""
        try:
            # 1. 파라미터별 성과 분포
            self._plot_parameter_distributions(results_df)
            
            # 2. 파라미터 간 상관관계
            self._plot_parameter_correlations(results_df)
            
            # 3. 성과 지표 간 산점도
            self._plot_metric_relationships(results_df)
            
        except Exception as e:
            logger.error(f"[_visualize_results] 결과 시각화 중 오류 발생: {str(e)}")
            
    def _plot_parameter_distributions(self, results_df: pd.DataFrame):
        """파라미터별 성과 분포 플롯"""
        try:
            param_names = list(self.param_grid.keys())
            fig, axes = plt.subplots(len(param_names), 1, figsize=(10, 5*len(param_names)))
            
            if len(param_names) == 1:
                axes = [axes]
                
            for ax, param in zip(axes, param_names):
                sns.boxplot(data=results_df, x=param, y=self.metric, ax=ax)
                ax.set_title(f'{param} vs {self.metric}')
                
            plt.tight_layout()
            self.visualizer.save_figure(fig, 'parameter_distributions')
            
        except Exception as e:
            logger.error(f"[_plot_parameter_distributions] 차트 생성 중 오류 발생: {str(e)}")
            
    def _plot_parameter_correlations(self, results_df: pd.DataFrame):
        """파라미터 간 상관관계 플롯"""
        try:
            # 상관계수 계산
            param_names = list(self.param_grid.keys())
            corr = results_df[param_names + [self.metric]].corr()
            
            # 히트맵 생성
            fig, ax = plt.subplots(figsize=(10, 8))
            sns.heatmap(corr, annot=True, cmap='RdYlBu', center=0, ax=ax)
            ax.set_title('Parameter Correlations')
            
            self.visualizer.save_figure(fig, 'parameter_correlations')
            
        except Exception as e:
            logger.error(f"[_plot_parameter_correlations] 차트 생성 중 오류 발생: {str(e)}")
            
    def _plot_metric_relationships(self, results_df: pd.DataFrame):
        """성과 지표 간 산점도 플롯"""
        try:
            metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate']
            metrics = [m for m in metrics if m in results_df.columns]
            
            if len(metrics) < 2:
                return
                
            fig = sns.pairplot(results_df[metrics])
            fig.fig.suptitle('Metric Relationships', y=1.02)
            
            self.visualizer.save_figure(fig.fig, 'metric_relationships')
            
        except Exception as e:
            logger.error(f"[_plot_metric_relationships] 차트 생성 중 오류 발생: {str(e)}") 