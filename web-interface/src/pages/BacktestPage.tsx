import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Calendar,
  Download,
  RefreshCw,
  Settings,
  PieChart,
  Target,
  AlertTriangle,
  CheckCircle,
  DollarSign
} from 'lucide-react';
import { Chart, type ChartDataPoint } from '../components/ui/Chart';
import { useApi } from '../hooks/useApi';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

interface BacktestResult {
  id: string;
  name: string;
  strategy: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  finalCapital: number;
  totalReturn: number;
  annualizedReturn: number;
  volatility: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  profitableTrades: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  performanceData: ChartDataPoint[];
  drawdownData: ChartDataPoint[];
  monthlyReturns: ChartDataPoint[];
  tradeHistory: Trade[];
}

interface Trade {
  id: string;
  symbol: string;
  type: 'buy' | 'sell';
  quantity: number;
  price: number;
  date: string;
  profit: number;
  profitPercent: number;
}

interface BacktestSettings {
  strategy: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  commission: number;
  slippage: number;
}

const BacktestPage: React.FC = () => {
  const [selectedResult, setSelectedResult] = useState<string>('');
  const [isRunning, setIsRunning] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<BacktestSettings>({
    strategy: 'momentum',
    startDate: '2024-01-01',
    endDate: '2024-12-31',
    initialCapital: 10000000,
    commission: 0.0015,
    slippage: 0.001
  });

  const { data: results, loading, error, refetch } = useApi<BacktestResult[]>('/api/backtest/results');
  const { data: currentResult } = useApi<BacktestResult>(
    selectedResult ? `/api/backtest/results/${selectedResult}` : null
  );

  useEffect(() => {
    if (results && results.length > 0 && !selectedResult) {
      setSelectedResult(results[0].id);
    }
  }, [results, selectedResult]);

  const runBacktest = async () => {
    setIsRunning(true);
    try {
      // API 호출로 백테스트 실행
      await new Promise(resolve => setTimeout(resolve, 3000)); // 시뮬레이션
      refetch();
    } catch (error) {
      console.error('백테스트 실행 실패:', error);
    } finally {
      setIsRunning(false);
    }
  };

  const downloadReport = () => {
    if (!currentResult) return;
    
    // CSV 형태로 리포트 다운로드
    const csvContent = generateCSVReport(currentResult);
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_report_${currentResult.name}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const generateCSVReport = (result: BacktestResult): string => {
    const headers = ['Metric', 'Value'];
    const metrics = [
      ['전략명', result.strategy],
      ['기간', `${result.startDate} ~ ${result.endDate}`],
      ['초기 자본', result.initialCapital.toLocaleString()],
      ['최종 자본', result.finalCapital.toLocaleString()],
      ['총 수익률', `${result.totalReturn}%`],
      ['연간 수익률', `${result.annualizedReturn}%`],
      ['변동성', `${result.volatility}%`],
      ['샤프 비율', result.sharpeRatio.toString()],
      ['최대 낙폭', `${result.maxDrawdown}%`],
      ['승률', `${result.winRate}%`],
      ['총 거래', result.totalTrades.toString()],
      ['수익 거래', result.profitableTrades.toString()],
      ['평균 승', result.avgWin.toString()],
      ['평균 패', result.avgLoss.toString()],
      ['수익 팩터', result.profitFactor.toString()]
    ];
    
    return [headers, ...metrics].map(row => row.join(',')).join('\n');
  };

  const getReturnColor = (value: number) => {
    if (value > 0) return 'text-green-600';
    if (value < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  const MetricCard: React.FC<{
    title: string;
    value: string | number;
    change?: number;
    icon: React.ReactNode;
    format?: 'number' | 'percent' | 'currency';
  }> = ({ title, value, change, icon, format = 'number' }) => {
    const formatValue = (val: string | number) => {
      if (format === 'percent') {
        return `${val}%`;
      } else if (format === 'currency') {
        return `${Number(val).toLocaleString()}원`;
      }
      return val.toString();
    };

    return (
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600 mb-1">{title}</p>
            <p className={`text-2xl font-bold ${getReturnColor(Number(value))}`}>
              {formatValue(value)}
            </p>
            {change !== undefined && (
              <div className="flex items-center mt-2">
                {change >= 0 ? (
                  <TrendingUp className="h-4 w-4 text-green-500 mr-1" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-red-500 mr-1" />
                )}
                <span className={`text-sm ${getReturnColor(change)}`}>
                  {change >= 0 ? '+' : ''}{change}%
                </span>
              </div>
            )}
          </div>
          <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
            {icon}
          </div>
        </div>
      </div>
    );
  };

  const TradeHistoryTable: React.FC<{ trades: Trade[] }> = ({ trades }) => (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              종목
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              유형
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              수량
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              가격
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              일시
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              손익
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {trades.slice(0, 10).map((trade) => (
            <tr key={trade.id}>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                {trade.symbol}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span
                  className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                    trade.type === 'buy'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {trade.type === 'buy' ? '매수' : '매도'}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {trade.quantity.toLocaleString()}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {trade.price.toLocaleString()}원
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {new Date(trade.date).toLocaleDateString('ko-KR')}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm">
                <div className={getReturnColor(trade.profit)}>
                  {trade.profit >= 0 ? '+' : ''}{trade.profit.toLocaleString()}원
                  <br />
                  <span className="text-xs">
                    ({trade.profitPercent >= 0 ? '+' : ''}{trade.profitPercent}%)
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const SettingsModal: React.FC = () => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 max-h-96 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">백테스트 설정</h3>
          <button
            onClick={() => setShowSettings(false)}
            className="text-gray-500 hover:text-gray-700"
          >
            ×
          </button>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              전략
            </label>
            <select
              value={settings.strategy}
              onChange={(e) => setSettings(prev => ({...prev, strategy: e.target.value}))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="momentum">모멘텀 전략</option>
              <option value="mean_reversion">평균회귀 전략</option>
              <option value="trend_following">추세추종 전략</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              시작일
            </label>
            <input
              type="date"
              value={settings.startDate}
              onChange={(e) => setSettings(prev => ({...prev, startDate: e.target.value}))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              종료일
            </label>
            <input
              type="date"
              value={settings.endDate}
              onChange={(e) => setSettings(prev => ({...prev, endDate: e.target.value}))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              초기 자본 (원)
            </label>
            <input
              type="number"
              value={settings.initialCapital}
              onChange={(e) => setSettings(prev => ({...prev, initialCapital: parseInt(e.target.value)}))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              step="1000000"
            />
          </div>
        </div>
        
        <div className="mt-6 flex justify-end space-x-3">
          <button
            onClick={() => setShowSettings(false)}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            취소
          </button>
          <button
            onClick={() => {
              setShowSettings(false);
              runBacktest();
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            실행
          </button>
        </div>
      </div>
    </div>
  );

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">오류: {error}</div>;

  return (
    <div className="space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">백테스트 결과</h1>
          <p className="text-gray-600">전략의 성과를 분석하고 최적화하세요</p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={selectedResult}
            onChange={(e) => setSelectedResult(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md"
          >
            {results?.map((result) => (
              <option key={result.id} value={result.id}>
                {result.name} ({result.strategy})
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowSettings(true)}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
          >
            <Settings className="h-4 w-4" />
            <span>새 백테스트</span>
          </button>
          {currentResult && (
            <button
              onClick={downloadReport}
              className="flex items-center space-x-2 px-3 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200"
            >
              <Download className="h-4 w-4" />
              <span>리포트</span>
            </button>
          )}
        </div>
      </div>

      {currentResult && (
        <>
          {/* 주요 성과 지표 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title="총 수익률"
              value={currentResult.totalReturn}
              icon={<TrendingUp className="h-6 w-6" />}
              format="percent"
            />
            <MetricCard
              title="샤프 비율"
              value={currentResult.sharpeRatio.toFixed(2)}
              icon={<BarChart3 className="h-6 w-6" />}
            />
            <MetricCard
              title="승률"
              value={currentResult.winRate}
              icon={<Target className="h-6 w-6" />}
              format="percent"
            />
            <MetricCard
              title="최대 낙폭"
              value={currentResult.maxDrawdown}
              icon={<TrendingDown className="h-6 w-6" />}
              format="percent"
            />
          </div>

          {/* 차트 섹션 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 수익률 차트 */}
            <div className="card">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                누적 수익률
              </h2>
              <Chart
                data={currentResult.performanceData}
                type="line"
                height={300}
                strokeColor="#10b981"
                showBrush={true}
              />
            </div>

            {/* 낙폭 차트 */}
            <div className="card">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                최대 낙폭
              </h2>
              <Chart
                data={currentResult.drawdownData}
                type="area"
                height={300}
                strokeColor="#ef4444"
                fillColor="#fecaca"
                showBrush={true}
              />
            </div>
          </div>

          {/* 월별 수익률 */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              월별 수익률
            </h2>
            <Chart
              data={currentResult.monthlyReturns}
              type="bar"
              height={300}
              fillColor="#3b82f6"
            />
          </div>

          {/* 상세 통계 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 수익성 지표 */}
            <div className="card">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                수익성 지표
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-600">연간 수익률</span>
                  <span className={`font-medium ${getReturnColor(currentResult.annualizedReturn)}`}>
                    {currentResult.annualizedReturn}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">변동성</span>
                  <span className="font-medium">{currentResult.volatility}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">수익 팩터</span>
                  <span className={`font-medium ${getReturnColor(currentResult.profitFactor - 1)}`}>
                    {currentResult.profitFactor.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">평균 승</span>
                  <span className="font-medium text-green-600">
                    +{currentResult.avgWin.toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">평균 패</span>
                  <span className="font-medium text-red-600">
                    {currentResult.avgLoss.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>

            {/* 거래 통계 */}
            <div className="card">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                거래 통계
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-600">총 거래</span>
                  <span className="font-medium">{currentResult.totalTrades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">수익 거래</span>
                  <span className="font-medium text-green-600">
                    {currentResult.profitableTrades}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">손실 거래</span>
                  <span className="font-medium text-red-600">
                    {currentResult.totalTrades - currentResult.profitableTrades}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">초기 자본</span>
                  <span className="font-medium">
                    {currentResult.initialCapital.toLocaleString()}원
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">최종 자본</span>
                  <span className={`font-medium ${getReturnColor(currentResult.finalCapital - currentResult.initialCapital)}`}>
                    {currentResult.finalCapital.toLocaleString()}원
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 거래 내역 */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              최근 거래 내역 (상위 10개)
            </h2>
            <TradeHistoryTable trades={currentResult.tradeHistory} />
          </div>
        </>
      )}

      {/* 설정 모달 */}
      {showSettings && <SettingsModal />}

      {/* 로딩 오버레이 */}
      {isRunning && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 text-center">
            <LoadingSpinner />
            <p className="mt-4 text-gray-600">백테스트를 실행하고 있습니다...</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default BacktestPage; 