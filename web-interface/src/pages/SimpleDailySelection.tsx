import React, { useState } from 'react';
import { Target, TrendingUp, BarChart3, Filter } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { LoadingSpinner } from '../components/ui';
import type { DailySelection } from '../types';

const SimpleDailySelection: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSector, setSelectedSector] = useState('');

  // 실제 API 데이터 사용
  const { data: dailySelectionsData, loading, error } = useApi<DailySelection[]>('/api/daily-selections');

  // 로딩 상태 처리
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <LoadingSpinner />
        <span className="ml-2 text-gray-600">일일 선정 종목을 불러오는 중...</span>
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
  const dailySelections = dailySelectionsData || [];

  const filteredData = dailySelections.filter(item => {
    const matchesSearch = item.stock.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         item.stock.code.includes(searchTerm);
    const matchesSector = !selectedSector || item.stock.sector === selectedSector;
    return matchesSearch && matchesSector;
  });

  const avgAttractiveness = dailySelections.reduce((sum, item) => sum + item.attractivenessScore, 0) / dailySelections.length;
  const avgTechnical = dailySelections.reduce((sum, item) => sum + item.technicalScore, 0) / dailySelections.length;
  const avgMomentum = dailySelections.reduce((sum, item) => sum + item.momentumScore, 0) / dailySelections.length;
  const avgExpectedReturn = dailySelections.reduce((sum, item) => sum + item.expectedReturn, 0) / dailySelections.length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">일일 선정 종목</h1>
        <p className="text-gray-600">AI가 분석한 오늘의 추천 종목을 확인하세요</p>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">평균 매력도</p>
              <p className="text-2xl font-bold text-blue-600">{avgAttractiveness.toFixed(1)}</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
              <Target className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">평균 기술점수</p>
              <p className="text-2xl font-bold text-green-600">{avgTechnical.toFixed(1)}</p>
            </div>
            <div className="p-3 rounded-lg bg-green-50 text-green-600">
              <TrendingUp className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">평균 모멘텀</p>
              <p className="text-2xl font-bold text-purple-600">{avgMomentum.toFixed(1)}</p>
            </div>
            <div className="p-3 rounded-lg bg-purple-50 text-purple-600">
              <BarChart3 className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">평균 기대수익</p>
              <p className="text-2xl font-bold text-orange-600">{avgExpectedReturn.toFixed(1)}%</p>
            </div>
            <div className="p-3 rounded-lg bg-orange-50 text-orange-600">
              <Target className="h-6 w-6" />
            </div>
          </div>
        </div>
      </div>

      {/* 필터 */}
      <div className="card">
        <div className="flex items-center space-x-4">
          <Filter className="h-5 w-5 text-gray-600" />
          <div className="flex-1">
            <input
              type="text"
              placeholder="종목명 또는 코드로 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <select
              value={selectedSector}
              onChange={(e) => setSelectedSector(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">전체 섹터</option>
              <option value="전자">전자</option>
              <option value="반도체">반도체</option>
              <option value="바이오">바이오</option>
            </select>
          </div>
        </div>
      </div>

      {/* 종목 리스트 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {filteredData.map((selection) => (
          <div key={selection.id} className="card hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{selection.stock.name}</h3>
                <p className="text-sm text-gray-500">{selection.stock.code} · {selection.stock.sector}</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold">{selection.stock.price.toLocaleString()}원</p>
                <p className={`text-sm ${selection.stock.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {selection.stock.change >= 0 ? '+' : ''}{selection.stock.change.toLocaleString()}원
                  ({selection.stock.changePercent >= 0 ? '+' : ''}{selection.stock.changePercent}%)
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">매력도</span>
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full" 
                      style={{ width: `${selection.attractivenessScore}%` }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium">{selection.attractivenessScore}</span>
                </div>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">기술점수</span>
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-green-600 h-2 rounded-full" 
                      style={{ width: `${selection.technicalScore}%` }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium">{selection.technicalScore}</span>
                </div>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">모멘텀</span>
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-purple-600 h-2 rounded-full" 
                      style={{ width: `${selection.momentumScore}%` }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium">{selection.momentumScore}</span>
                </div>
              </div>

              <div className="flex justify-between items-center pt-2 border-t">
                <span className="text-sm text-gray-600">기대수익률</span>
                <span className="text-sm font-bold text-orange-600">{selection.expectedReturn}%</span>
              </div>

              <div className="flex flex-wrap gap-1 pt-2">
                {selection.reasons.map((reason, index) => (
                  <span 
                    key={index}
                    className="inline-flex px-2 py-1 text-xs font-medium bg-gray-100 text-gray-800 rounded-full"
                  >
                    {reason}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SimpleDailySelection; 