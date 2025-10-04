import React, { useState, useMemo } from 'react';
import {
  Play,
  Search,
  Calendar,
  TrendingUp,
  TrendingDown,
  Target,
  Activity,
  Zap,
  RefreshCw,
} from 'lucide-react';
import { Table, Button, Input, LoadingSpinner } from '../components/ui';
import type { Column } from '../components/ui';
import type { DailySelection } from '../types';
import { useDailySelections } from '../hooks/useApi';
import { usePagination } from '../hooks/usePagination';
import apiService from '../services/api';

const DailySelectionPage: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const { data: selectionsData, loading, error, execute: refetchSelections } = useDailySelections(selectedDate);
  const [searchTerm, setSearchTerm] = useState('');
  const [isRunning, setIsRunning] = useState(false);

  // 필터링된 데이터
  const filteredData = useMemo(() => {
    if (!selectionsData) return [];
    
    return selectionsData.filter((item) => {
      const matchesSearch = 
        item.stock.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.stock.code.includes(searchTerm);
      
      return matchesSearch;
    });
  }, [selectionsData, searchTerm]);

  // 페이지네이션
  const {
    data: paginatedData,
    pagination,
  } = usePagination(filteredData, { defaultPageSize: 20 });

  // 일일 선정 실행
  const handleRunDailySelection = async () => {
    setIsRunning(true);
    try {
      await apiService.runDailySelection();
      refetchSelections();
    } catch (error) {
      console.error('일일 선정 실행 실패:', error);
    } finally {
      setIsRunning(false);
    }
  };

  // 테이블 컬럼 정의
  const columns: Column<DailySelection>[] = [
    {
      key: 'stock',
      title: '종목명',
      render: (_, record) => (
        <div>
          <div className="font-medium text-gray-900">{record.stock.name}</div>
          <div className="text-sm text-gray-500">{record.stock.code}</div>
        </div>
      ),
      sortable: true,
    },
    {
      key: 'stock',
      title: '섹터',
      render: (_, record) => (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
          {record.stock.sector}
        </span>
      ),
    },
    {
      key: 'stock',
      title: '현재가',
      render: (_, record) => (
        <div className="text-right">
          <div className="font-medium">{record.stock.price.toLocaleString()}원</div>
          <div className={`text-sm flex items-center justify-end ${
            record.stock.change >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {record.stock.change >= 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
            {record.stock.change >= 0 ? '+' : ''}{record.stock.changePercent}%
          </div>
        </div>
      ),
      align: 'right',
    },
    {
      key: 'attractivenessScore',
      title: '매력도',
      render: (value) => (
        <div className="text-center">
          <div className={`inline-flex items-center px-2 py-1 rounded-md text-sm font-medium ${
            value >= 80 ? 'bg-green-100 text-green-800' :
            value >= 60 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
          }`}>
            <Target className="h-3 w-3 mr-1" />
            {value.toFixed(1)}
          </div>
        </div>
      ),
      sortable: true,
      align: 'center',
    },
    {
      key: 'technicalScore',
      title: '기술적',
      render: (value) => (
        <div className="text-center">
          <div className={`inline-flex items-center px-2 py-1 rounded-md text-sm font-medium ${
            value >= 80 ? 'bg-green-100 text-green-800' :
            value >= 60 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
          }`}>
            <Activity className="h-3 w-3 mr-1" />
            {value.toFixed(1)}
          </div>
        </div>
      ),
      sortable: true,
      align: 'center',
    },
    {
      key: 'momentumScore',
      title: '모멘텀',
      render: (value) => (
        <div className="text-center">
          <div className={`inline-flex items-center px-2 py-1 rounded-md text-sm font-medium ${
            value >= 80 ? 'bg-green-100 text-green-800' :
            value >= 60 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
          }`}>
            <Zap className="h-3 w-3 mr-1" />
            {value.toFixed(1)}
          </div>
        </div>
      ),
      sortable: true,
      align: 'center',
    },
    {
      key: 'expectedReturn',
      title: '기대 수익률',
      render: (value) => (
        <div className="text-right">
          <span className={`font-medium ${
            value >= 15 ? 'text-green-600' : 
            value >= 10 ? 'text-yellow-600' : 'text-gray-600'
          }`}>
            +{value.toFixed(1)}%
          </span>
        </div>
      ),
      sortable: true,
      align: 'right',
    },
    {
      key: 'reasons',
      title: '선정 이유',
      render: (value) => (
        <div className="max-w-xs">
          {value.map((reason: string, index: number) => (
            <span
              key={index}
              className="inline-block bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded mr-1 mb-1"
            >
              {reason}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: 'selectedAt',
      title: '선정 시간',
      render: (value) => {
        const date = new Date(value);
        return (
          <div className="text-sm text-gray-600">
            <div>{date.toLocaleDateString('ko-KR')}</div>
            <div>{date.toLocaleTimeString('ko-KR')}</div>
          </div>
        );
      },
      sortable: true,
    },
  ];

  // 통계 계산
  const stats = useMemo(() => {
    if (!selectionsData) return null;
    
    const avgAttractiveness = selectionsData.reduce((sum, item) => sum + item.attractivenessScore, 0) / selectionsData.length;
    const avgTechnical = selectionsData.reduce((sum, item) => sum + item.technicalScore, 0) / selectionsData.length;
    const avgMomentum = selectionsData.reduce((sum, item) => sum + item.momentumScore, 0) / selectionsData.length;
    const avgExpectedReturn = selectionsData.reduce((sum, item) => sum + item.expectedReturn, 0) / selectionsData.length;
    
    return {
      avgAttractiveness: avgAttractiveness.toFixed(1),
      avgTechnical: avgTechnical.toFixed(1),
      avgMomentum: avgMomentum.toFixed(1),
      avgExpectedReturn: avgExpectedReturn.toFixed(1),
    };
  }, [selectionsData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" text="일일 선정 종목 로딩 중..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-red-500 text-lg mb-2">오류가 발생했습니다</div>
        <div className="text-gray-600 mb-4">{error}</div>
        <Button onClick={refetchSelections}>다시 시도</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">일일 선정 종목</h1>
          <p className="text-gray-600">
            매일 선정된 매매 대상 종목을 확인하세요 ({filteredData.length}개 종목)
          </p>
        </div>
        <div className="flex space-x-3">
          <Button
            variant="secondary"
            icon={<RefreshCw className="h-5 w-5" />}
            onClick={refetchSelections}
          >
            새로고침
          </Button>
          <Button
            icon={<Play className="h-5 w-5" />}
            loading={isRunning}
            onClick={handleRunDailySelection}
          >
            일일 선정 실행
          </Button>
        </div>
      </div>

      {/* 날짜 선택 및 검색 */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="sm:w-48">
            <Input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              prefix={<Calendar className="h-4 w-4" />}
              fullWidth
            />
          </div>
          <div className="flex-1">
            <Input
              placeholder="종목명 또는 코드로 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              prefix={<Search className="h-4 w-4" />}
              fullWidth
            />
          </div>
        </div>
      </div>

      {/* 통계 카드 */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card text-center">
            <div className="text-2xl font-bold text-primary-600">{stats.avgAttractiveness}</div>
            <div className="text-sm text-gray-600">평균 매력도</div>
          </div>
          <div className="card text-center">
            <div className="text-2xl font-bold text-green-600">{stats.avgTechnical}</div>
            <div className="text-sm text-gray-600">평균 기술적 점수</div>
          </div>
          <div className="card text-center">
            <div className="text-2xl font-bold text-yellow-600">{stats.avgMomentum}</div>
            <div className="text-sm text-gray-600">평균 모멘텀</div>
          </div>
          <div className="card text-center">
            <div className="text-2xl font-bold text-success-600">+{stats.avgExpectedReturn}%</div>
            <div className="text-sm text-gray-600">평균 기대 수익률</div>
          </div>
        </div>
      )}

      {/* 일일 선정 테이블 */}
      <Table
        columns={columns}
        data={paginatedData}
        rowKey="id"
        pagination={pagination}
        onRowClick={(record) => console.log('Row clicked:', record)}
      />
    </div>
  );
};

export default DailySelectionPage; 