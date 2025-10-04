import React from 'react';
import { TrendingUp, BarChart3, Target } from 'lucide-react';

const SimpleBacktest: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">백테스트 결과</h1>
        <p className="text-gray-600">전략의 성과를 분석하고 최적화하세요</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">총 수익률</p>
              <p className="text-2xl font-bold text-green-600">18.5%</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
              <TrendingUp className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">샤프 비율</p>
              <p className="text-2xl font-bold text-gray-900">1.45</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
              <BarChart3 className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">승률</p>
              <p className="text-2xl font-bold text-gray-900">68.4%</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
              <Target className="h-6 w-6" />
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">최대 낙폭</p>
              <p className="text-2xl font-bold text-red-600">-8.2%</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
              <TrendingUp className="h-6 w-6" />
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">상세 통계</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">수익성 지표</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">연간 수익률</span>
                <span className="font-medium text-green-600">18.5%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">변동성</span>
                <span className="font-medium">12.7%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">수익 팩터</span>
                <span className="font-medium text-green-600">1.89</span>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">거래 통계</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">총 거래</span>
                <span className="font-medium">125</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">수익 거래</span>
                <span className="font-medium text-green-600">85</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">손실 거래</span>
                <span className="font-medium text-red-600">40</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SimpleBacktest; 