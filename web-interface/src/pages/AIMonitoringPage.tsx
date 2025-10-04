import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Activity,
  Filter,
  Settings,
  Bell,
  BellOff,
  Check,
  X,
  RefreshCw,
  Eye,
  BarChart3,
  Clock,
  CheckCircle
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import type { MarketAlert, Stock } from '../types';

interface AlertSettings {
  priceChangeThreshold: number;
  volumeThreshold: number;
  enableSound: boolean;
  enableNotifications: boolean;
  filterBySeverity: string[];
  filterByType: string[];
}

const AIMonitoringPage: React.FC = () => {
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [filteredAlerts, setFilteredAlerts] = useState<MarketAlert[]>([]);
  const [alertSettings, setAlertSettings] = useState<AlertSettings>({
    priceChangeThreshold: 3.0,
    volumeThreshold: 1000000,
    enableSound: true,
    enableNotifications: true,
    filterBySeverity: ['high', 'critical'],
    filterByType: ['price_spike', 'price_drop', 'ai_recommendation']
  });
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { data: alertsData, loading, error, refetch } = useApi<MarketAlert[]>('/api/alerts');

  useEffect(() => {
    if (alertsData) {
      setAlerts(alertsData);
    }
  }, [alertsData]);

  useEffect(() => {
    // 필터링 적용
    let filtered = alerts;
    
    if (selectedSeverity !== 'all') {
      filtered = filtered.filter(alert => alert.severity === selectedSeverity);
    }
    
    if (selectedType !== 'all') {
      filtered = filtered.filter(alert => alert.type === selectedType);
    }
    
    setFilteredAlerts(filtered);
  }, [alerts, selectedSeverity, selectedType]);

  useEffect(() => {
    // 자동 새로고침
    if (autoRefresh) {
      const interval = setInterval(() => {
        refetch();
      }, 5000); // 5초마다 새로고침
      
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refetch]);

  const handleAcknowledgeAlert = async (alertId: string) => {
    try {
      // API 호출로 알림 승인 처리
      setAlerts(prev => prev.map(alert => 
        alert.id === alertId ? { ...alert, acknowledged: true } : alert
      ));
    } catch (error) {
      console.error('알림 승인 실패:', error);
    }
  };

  const handleDismissAlert = async (alertId: string) => {
    try {
      // API 호출로 알림 해제 처리
      setAlerts(prev => prev.filter(alert => alert.id !== alertId));
    } catch (error) {
      console.error('알림 해제 실패:', error);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'border-red-500 bg-red-50 text-red-900';
      case 'high':
        return 'border-orange-500 bg-orange-50 text-orange-900';
      case 'medium':
        return 'border-yellow-500 bg-yellow-50 text-yellow-900';
      case 'low':
        return 'border-blue-500 bg-blue-50 text-blue-900';
      default:
        return 'border-gray-500 bg-gray-50 text-gray-900';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertTriangle className="h-5 w-5 text-red-600" />;
      case 'high':
        return <AlertTriangle className="h-5 w-5 text-orange-600" />;
      case 'medium':
        return <Clock className="h-5 w-5 text-yellow-600" />;
      case 'low':
        return <CheckCircle className="h-5 w-5 text-blue-600" />;
      default:
        return <Activity className="h-5 w-5 text-gray-600" />;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'price_spike':
        return <TrendingUp className="h-4 w-4 text-green-600" />;
      case 'price_drop':
        return <TrendingDown className="h-4 w-4 text-red-600" />;
      case 'ai_recommendation':
        return <BarChart3 className="h-4 w-4 text-purple-600" />;
      case 'volume_spike':
        return <Activity className="h-4 w-4 text-blue-600" />;
      default:
        return <Eye className="h-4 w-4 text-gray-600" />;
    }
  };

  const AlertCard: React.FC<{ alert: MarketAlert }> = ({ alert }) => (
    <div className={`p-4 rounded-lg border-l-4 ${getSeverityColor(alert.severity)} mb-4`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3">
          <div className="flex items-center space-x-2">
            {getSeverityIcon(alert.severity)}
            {getTypeIcon(alert.type)}
          </div>
          <div className="flex-1">
            <div className="flex items-center space-x-2 mb-1">
              <h3 className="font-semibold text-lg">{alert.stock.name}</h3>
              <span className="text-sm text-gray-500">({alert.stock.code})</span>
            </div>
            <p className="text-gray-700 mb-2">{alert.message}</p>
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              <span>{new Date(alert.timestamp).toLocaleString('ko-KR')}</span>
              <span>{alert.stock.sector}</span>
              <span>거래량: {alert.stock.volume.toLocaleString()}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end space-y-2">
          <div className="text-right">
            <p className="font-bold text-lg">{alert.stock.price.toLocaleString()}원</p>
            <p className={`text-sm font-medium ${
              alert.stock.change >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {alert.stock.change >= 0 ? '+' : ''}{alert.stock.change.toLocaleString()}원
              ({alert.stock.changePercent >= 0 ? '+' : ''}{alert.stock.changePercent}%)
            </p>
          </div>
          {!alert.acknowledged && (
            <div className="flex space-x-2">
              <button
                onClick={() => handleAcknowledgeAlert(alert.id)}
                className="p-1 rounded-full bg-green-100 hover:bg-green-200 text-green-600"
                title="승인"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleDismissAlert(alert.id)}
                className="p-1 rounded-full bg-red-100 hover:bg-red-200 text-red-600"
                title="해제"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const SettingsPanel: React.FC = () => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 max-h-96 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">알림 설정</h3>
          <button
            onClick={() => setIsSettingsOpen(false)}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              가격 변동 임계값 (%)
            </label>
            <input
              type="number"
              value={alertSettings.priceChangeThreshold}
              onChange={(e) => setAlertSettings(prev => ({
                ...prev,
                priceChangeThreshold: parseFloat(e.target.value)
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              step="0.1"
              min="0"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              거래량 임계값
            </label>
            <input
              type="number"
              value={alertSettings.volumeThreshold}
              onChange={(e) => setAlertSettings(prev => ({
                ...prev,
                volumeThreshold: parseInt(e.target.value)
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              step="1000"
              min="0"
            />
          </div>
          
          <div className="flex items-center space-x-3">
            <input
              type="checkbox"
              id="enableSound"
              checked={alertSettings.enableSound}
              onChange={(e) => setAlertSettings(prev => ({
                ...prev,
                enableSound: e.target.checked
              }))}
              className="rounded"
            />
            <label htmlFor="enableSound" className="text-sm text-gray-700">
              소리 알림 활성화
            </label>
          </div>
          
          <div className="flex items-center space-x-3">
            <input
              type="checkbox"
              id="enableNotifications"
              checked={alertSettings.enableNotifications}
              onChange={(e) => setAlertSettings(prev => ({
                ...prev,
                enableNotifications: e.target.checked
              }))}
              className="rounded"
            />
            <label htmlFor="enableNotifications" className="text-sm text-gray-700">
              브라우저 알림 활성화
            </label>
          </div>
        </div>
        
        <div className="mt-6 flex justify-end space-x-3">
          <button
            onClick={() => setIsSettingsOpen(false)}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            취소
          </button>
          <button
            onClick={() => setIsSettingsOpen(false)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            저장
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
          <h1 className="text-3xl font-bold text-gray-900">시장 모니터링</h1>
          <p className="text-gray-600">실시간 시장 상황과 AI 추천을 모니터링합니다</p>
        </div>
        <div className="flex items-center space-x-4">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center space-x-2 px-3 py-2 rounded-md ${
              autoRefresh 
                ? 'bg-green-100 text-green-700' 
                : 'bg-gray-100 text-gray-700'
            }`}
          >
            {autoRefresh ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
            <span>{autoRefresh ? '자동 새로고침' : '수동 모드'}</span>
          </button>
          <button
            onClick={() => refetch()}
            className="flex items-center space-x-2 px-3 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200"
          >
            <RefreshCw className="h-4 w-4" />
            <span>새로고침</span>
          </button>
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
          >
            <Settings className="h-4 w-4" />
            <span>설정</span>
          </button>
        </div>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">전체 알림</p>
              <p className="text-2xl font-bold text-gray-900">{alerts.length}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-blue-600" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">미확인 알림</p>
              <p className="text-2xl font-bold text-red-600">
                {alerts.filter(a => !a.acknowledged).length}
              </p>
            </div>
            <Bell className="h-8 w-8 text-red-600" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">AI 추천</p>
              <p className="text-2xl font-bold text-purple-600">
                {alerts.filter(a => a.type === 'ai_recommendation').length}
              </p>
            </div>
            <BarChart3 className="h-8 w-8 text-purple-600" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">가격 급등</p>
              <p className="text-2xl font-bold text-green-600">
                {alerts.filter(a => a.type === 'price_spike').length}
              </p>
            </div>
            <TrendingUp className="h-8 w-8 text-green-600" />
          </div>
        </div>
      </div>

      {/* 필터 바 */}
      <div className="card">
        <div className="flex items-center space-x-4">
          <Filter className="h-5 w-5 text-gray-600" />
          <div className="flex items-center space-x-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                심각도
              </label>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="all">전체</option>
                <option value="critical">위험</option>
                <option value="high">높음</option>
                <option value="medium">보통</option>
                <option value="low">낮음</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                유형
              </label>
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="all">전체</option>
                <option value="price_spike">가격 급등</option>
                <option value="price_drop">가격 급락</option>
                <option value="ai_recommendation">AI 추천</option>
                <option value="volume_spike">거래량 급증</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* 알림 리스트 */}
      <div className="space-y-4">
        {filteredAlerts.length === 0 ? (
          <div className="card text-center py-12">
            <AlertTriangle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">표시할 알림이 없습니다.</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))
        )}
      </div>

      {/* 설정 패널 */}
      {isSettingsOpen && <SettingsPanel />}
    </div>
  );
};

export default AIMonitoringPage; 