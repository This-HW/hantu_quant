import React, { useState } from 'react';
import { Eye, TrendingUp, TrendingDown, Target, Plus } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { LoadingSpinner } from '../components/ui';
import type { WatchlistItem } from '../types';

const SimpleWatchlist: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');

  // 실제 API 데이터 사용
  const { data: watchlistData, loading, error } = useApi<WatchlistItem[]>('/api/watchlist');

  // 로딩 상태 처리
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <LoadingSpinner />
        <span className="ml-2 text-gray-600">감시 리스트를 불러오는 중...</span>
      </div>
    );
  }

  // 에러 상태 처리
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">데이터를 불러오는 중 오류가 발생했습니다.</p>
          <p className="text-gray-600">잠시 후 다시 시도해주세요.</p>
        </div>
      </div>
    );
  }

  // 데이터가 없는 경우 처리
  const watchlist = watchlistData || [];

  const filteredData = watchlist.filter(item => 
    item.stock.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.stock.code.includes(searchTerm)
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">감시 리스트</h1>
          <p className="text-gray-600">관심 종목을 모니터링하세요</p>
        </div>
        <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          <Plus className="h-4 w-4" />
          <span>종목 추가</span>
        </button>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">총 관심 종목</p>
              <p className="text-2xl font-bold text-blue-600">{watchlist.length}</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
              <Eye className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">상승 종목</p>
              <p className="text-2xl font-bold text-green-600">
                {watchlist.filter(item => item.stock.change > 0).length}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-green-50 text-green-600">
              <TrendingUp className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">하락 종목</p>
              <p className="text-2xl font-bold text-red-600">
                {watchlist.filter(item => item.stock.change < 0).length}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-red-50 text-red-600">
              <TrendingDown className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">평균 점수</p>
              <p className="text-2xl font-bold text-purple-600">
                {(watchlist.reduce((sum, item) => sum + item.score, 0) / watchlist.length).toFixed(1)}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-purple-50 text-purple-600">
              <Target className="h-6 w-6" />
            </div>
          </div>
        </div>
      </div>

      {/* 검색 */}
      <div className="card">
        <input
          type="text"
          placeholder="종목명 또는 코드로 검색..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>

      {/* 종목 리스트 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {filteredData.map((item) => (
          <div key={item.id} className="card hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{item.stock.name}</h3>
                <p className="text-sm text-gray-500">{item.stock.code} · {item.stock.sector}</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold">{item.stock.price.toLocaleString()}원</p>
                <p className={`text-sm ${item.stock.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {item.stock.change >= 0 ? '+' : ''}{item.stock.change.toLocaleString()}원
                  ({item.stock.changePercent >= 0 ? '+' : ''}{item.stock.changePercent}%)
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {item.targetPrice && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">목표가</span>
                  <span className="text-sm font-medium">{item.targetPrice.toLocaleString()}원</span>
                </div>
              )}

              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">추천 이유</span>
                <span className="text-sm font-medium">{item.reason}</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">점수</span>
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full" 
                      style={{ width: `${item.score}%` }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium">{item.score}</span>
                </div>
              </div>

              <div className="flex justify-between items-center pt-2 border-t">
                <span className="text-sm text-gray-600">추가일</span>
                <span className="text-sm text-gray-500">
                  {new Date(item.addedAt).toLocaleDateString('ko-KR')}
                </span>
              </div>
            </div>

            <div className="mt-4 flex space-x-2">
              <button className="flex-1 px-3 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 text-sm">
                차트 보기
              </button>
              <button className="flex-1 px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-sm">
                편집
              </button>
              <button className="px-3 py-2 bg-red-100 text-red-700 rounded-md hover:bg-red-200 text-sm">
                삭제
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SimpleWatchlist; 