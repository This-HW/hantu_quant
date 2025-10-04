import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Eye,
  Target,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { SystemStatus, MarketAlert, DailySelection, WatchlistItem } from '../types';
import { useApi } from '../hooks/useApi';

// 더미 성과 데이터 (실제로는 백테스트 결과에서 가져와야 함)
const mockPerformanceData = [
  { date: '01/20', value: 15.2 },
  { date: '01/21', value: 18.5 },
  { date: '01/22', value: 12.8 },
  { date: '01/23', value: 22.1 },
  { date: '01/24', value: 19.7 },
  { date: '01/25', value: 25.3 },
  { date: '01/26', value: 28.9 },
];

export default function Dashboard() {
  // 실제 API 데이터 사용
  const { data: systemStatus, loading: statusLoading } = useApi<SystemStatus>('/api/system/status');
  const { data: alerts, loading: alertsLoading } = useApi<MarketAlert[]>('/api/alerts');
  const { data: dailySelections, loading: selectionsLoading } = useApi<DailySelection[]>('/api/daily-selections');
  const { data: watchlist, loading: watchlistLoading } = useApi<WatchlistItem[]>('/api/watchlist');

  // 로딩 상태
  if (statusLoading || alertsLoading || selectionsLoading || watchlistLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // 기본값 설정
  const currentStatus = systemStatus || {
    isRunning: false,
    lastUpdate: new Date().toISOString(),
    activeAlerts: 0,
    watchlistCount: 0,
    dailySelectionsCount: 0,
    performance: { accuracy: 0, totalProcessed: 0, avgProcessingTime: 0 },
    health: { api: 'unknown', database: 'unknown', websocket: 'unknown' }
  };

  const currentAlerts = alerts || [];
  const currentSelections = dailySelections || [];
  const currentWatchlist = watchlist || [];

  const getHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      default:
        return <AlertTriangle className="w-4 h-4 text-red-500" />;
    }
  };

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'warning':
        return 'text-yellow-700 bg-yellow-50 border-yellow-200';
      default:
        return 'text-red-700 bg-red-50 border-red-200';
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">대시보드</h1>
        <p className="text-gray-600">한투 퀀트 시스템 현황을 한눈에 확인하세요</p>
      </div>

      {/* 시스템 상태 카드들 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* 시스템 실행 상태 */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">시스템 상태</p>
              <p className={`text-2xl font-bold ${currentStatus.isRunning ? 'text-green-600' : 'text-red-600'}`}>
                {currentStatus.isRunning ? '실행 중' : '정지'}
              </p>
            </div>
            <Activity className={`w-8 h-8 ${currentStatus.isRunning ? 'text-green-600' : 'text-red-600'}`} />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            마지막 업데이트: {new Date(currentStatus.lastUpdate).toLocaleString()}
          </p>
        </div>

        {/* 활성 알림 */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">활성 알림</p>
              <p className="text-2xl font-bold text-orange-600">{currentStatus.activeAlerts}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-orange-600" />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            미확인 알림 {currentAlerts.filter(alert => !alert.acknowledged).length}개
          </p>
        </div>

        {/* 감시 리스트 */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">감시 리스트</p>
              <p className="text-2xl font-bold text-blue-600">{currentStatus.watchlistCount}</p>
            </div>
            <Eye className="w-8 h-8 text-blue-600" />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            실제 종목 {currentWatchlist.length}개
          </p>
        </div>

        {/* 일일 선정 */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">일일 선정</p>
              <p className="text-2xl font-bold text-purple-600">{currentStatus.dailySelectionsCount}</p>
            </div>
            <Target className="w-8 h-8 text-purple-600" />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            선정 종목 {currentSelections.length}개
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 시스템 건강도 */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">시스템 건강도</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">API 서버</span>
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full border text-xs font-medium ${getHealthColor(currentStatus.health.api)}`}>
                {getHealthIcon(currentStatus.health.api)}
                <span className="capitalize">{currentStatus.health.api}</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">데이터베이스</span>
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full border text-xs font-medium ${getHealthColor(currentStatus.health.database)}`}>
                {getHealthIcon(currentStatus.health.database)}
                <span className="capitalize">{currentStatus.health.database}</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">WebSocket</span>
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full border text-xs font-medium ${getHealthColor(currentStatus.health.websocket)}`}>
                {getHealthIcon(currentStatus.health.websocket)}
                <span className="capitalize">{currentStatus.health.websocket}</span>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-medium text-gray-900 mb-2">성능 지표</h4>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-blue-600">{currentStatus.performance.accuracy}%</p>
                <p className="text-xs text-gray-600">정확도</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{currentStatus.performance.totalProcessed.toLocaleString()}</p>
                <p className="text-xs text-gray-600">처리 종목</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-purple-600">{currentStatus.performance.avgProcessingTime}분</p>
                <p className="text-xs text-gray-600">평균 시간</p>
              </div>
            </div>
          </div>
        </div>

        {/* 성과 차트 */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">일주일 성과</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={mockPerformanceData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip formatter={(value) => [`${value}%`, '수익률']} />
              <Line 
                type="monotone" 
                dataKey="value" 
                stroke="#3B82F6" 
                strokeWidth={2}
                dot={{ fill: '#3B82F6', strokeWidth: 2, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 최근 선정 종목 */}
      {currentSelections.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">최근 선정 종목</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {currentSelections.slice(0, 6).map((selection) => (
              <div key={selection.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-gray-900">{selection.stock.name}</h4>
                  <span className="text-sm text-gray-500">{selection.stock.code}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">기대수익률:</span>
                  <span className="font-medium text-green-600">+{selection.expectedReturn}%</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">신뢰도:</span>
                  <span className="font-medium">{(selection.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="mt-2">
                  <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                    selection.riskLevel === 'LOW' ? 'bg-green-100 text-green-800' :
                    selection.riskLevel === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {selection.riskLevel} 리스크
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 최근 알림 */}
      {currentAlerts.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">최근 알림</h3>
          <div className="space-y-3">
            {currentAlerts.slice(0, 5).map((alert) => (
              <div key={alert.id} className={`p-3 rounded-lg border-l-4 ${
                alert.severity === 'high' ? 'border-red-400 bg-red-50' :
                alert.severity === 'medium' ? 'border-yellow-400 bg-yellow-50' :
                'border-blue-400 bg-blue-50'
              }`}>
                <div className="flex items-center justify-between">
                  <h4 className="font-medium text-gray-900">{alert.title}</h4>
                  <span className="text-sm text-gray-500">
                    {new Date(alert.timestamp).toLocaleString()}
                  </span>
                </div>
                <p className="text-sm text-gray-700 mt-1">{alert.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
} 