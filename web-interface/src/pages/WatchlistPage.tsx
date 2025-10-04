import React, { useState, useMemo } from 'react';
import {
  Plus,
  Search,
  Filter,
  TrendingUp,
  TrendingDown,
  Edit,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import { Table, Modal, Button, Input, LoadingSpinner } from '../components/ui';
import type { Column } from '../components/ui';
import type { WatchlistItem, Stock } from '../types';
import { useWatchlist } from '../hooks/useApi';
import { usePagination } from '../hooks/usePagination';
import apiService from '../services/api';

const WatchlistPage: React.FC = () => {
  const { data: watchlistData, loading, error, execute: refetchWatchlist } = useWatchlist();
  const [searchTerm, setSearchTerm] = useState('');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<WatchlistItem | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // 필터링된 데이터
  const filteredData = useMemo(() => {
    if (!watchlistData) return [];
    
    return watchlistData.filter((item) => {
      const matchesSearch = 
        item.stock.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.stock.code.includes(searchTerm);
      
      const matchesSector = 
        sectorFilter === 'all' || item.stock.sector === sectorFilter;
      
      return matchesSearch && matchesSector;
    });
  }, [watchlistData, searchTerm, sectorFilter]);

  // 페이지네이션
  const {
    data: paginatedData,
    pagination,
  } = usePagination(filteredData, { defaultPageSize: 20 });

  // 섹터 목록 (필터링용)
  const sectors = useMemo(() => {
    if (!watchlistData) return [];
    const uniqueSectors = [...new Set(watchlistData.map(item => item.stock.sector))];
    return uniqueSectors.sort();
  }, [watchlistData]);

  // 테이블 컬럼 정의
  const columns: Column<WatchlistItem>[] = [
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
      key: 'targetPrice',
      title: '목표가',
      render: (value) => value ? `${value.toLocaleString()}원` : '-',
      align: 'right',
    },
    {
      key: 'score',
      title: '점수',
      render: (value) => (
        <div className="text-right">
          <span className={`font-medium ${
            value >= 80 ? 'text-green-600' : 
            value >= 60 ? 'text-yellow-600' : 'text-red-600'
          }`}>
            {value.toFixed(1)}
          </span>
        </div>
      ),
      sortable: true,
      align: 'right',
    },
    {
      key: 'reason',
      title: '선정 이유',
      render: (value) => (
        <span className="text-sm text-gray-600 max-w-xs truncate block">
          {value}
        </span>
      ),
    },
    {
      key: 'addedAt',
      title: '추가일',
      render: (value) => new Date(value).toLocaleDateString('ko-KR'),
      sortable: true,
    },
    {
      key: 'id',
      title: '액션',
      render: (_, record) => (
        <div className="flex space-x-2">
          <Button
            size="sm"
            variant="ghost"
            icon={<Edit className="h-4 w-4" />}
            onClick={() => handleEdit(record)}
          />
          <Button
            size="sm"
            variant="ghost"
            icon={<Trash2 className="h-4 w-4" />}
            onClick={() => handleDelete(record.id)}
          />
          <Button
            size="sm"
            variant="ghost"
            icon={<ExternalLink className="h-4 w-4" />}
            onClick={() => window.open(`https://finance.naver.com/item/main.naver?code=${record.stock.code}`, '_blank')}
          />
        </div>
      ),
    },
  ];

  const handleEdit = (item: WatchlistItem) => {
    setSelectedItem(item);
    setIsEditModalOpen(true);
  };

  const handleDelete = async (itemId: string) => {
    if (window.confirm('정말로 삭제하시겠습니까?')) {
      try {
        await apiService.removeFromWatchlist(itemId);
        refetchWatchlist();
      } catch (error) {
        console.error('삭제 실패:', error);
      }
    }
  };

  const AddStockModal: React.FC = () => {
    const [stockCode, setStockCode] = useState('');
    const [reason, setReason] = useState('');
    const [targetPrice, setTargetPrice] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      setSubmitting(true);

      try {
        await apiService.addToWatchlist(
          stockCode,
          reason,
          targetPrice ? parseFloat(targetPrice) : undefined
        );
        setIsAddModalOpen(false);
        refetchWatchlist();
        // Reset form
        setStockCode('');
        setReason('');
        setTargetPrice('');
      } catch (error) {
        console.error('추가 실패:', error);
      } finally {
        setSubmitting(false);
      }
    };

    return (
      <Modal
        open={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="감시 리스트에 종목 추가"
        footer={
          <div className="flex space-x-3">
            <Button
              variant="secondary"
              onClick={() => setIsAddModalOpen(false)}
            >
              취소
            </Button>
            <Button
              type="submit"
              loading={submitting}
              onClick={handleSubmit}
            >
              추가
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="종목 코드"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            placeholder="예: 005930"
            required
            fullWidth
          />
          <Input
            label="선정 이유"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="예: AI 추천, 기술적 분석"
            required
            fullWidth
          />
          <Input
            label="목표가 (선택사항)"
            type="number"
            value={targetPrice}
            onChange={(e) => setTargetPrice(e.target.value)}
            placeholder="예: 80000"
            suffix="원"
            fullWidth
          />
        </form>
      </Modal>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" text="감시 리스트 로딩 중..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-red-500 text-lg mb-2">오류가 발생했습니다</div>
        <div className="text-gray-600 mb-4">{error}</div>
        <Button onClick={refetchWatchlist}>다시 시도</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">감시 리스트</h1>
          <p className="text-gray-600">
            관심 종목을 관리하고 추적하세요 ({filteredData.length}개 종목)
          </p>
        </div>
        <Button
          icon={<Plus className="h-5 w-5" />}
          onClick={() => setIsAddModalOpen(true)}
        >
          종목 추가
        </Button>
      </div>

      {/* 필터 및 검색 */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <Input
              placeholder="종목명 또는 코드로 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              prefix={<Search className="h-4 w-4" />}
              fullWidth
            />
          </div>
          <div className="sm:w-48">
            <select
              value={sectorFilter}
              onChange={(e) => setSectorFilter(e.target.value)}
              className="input w-full"
            >
              <option value="all">모든 섹터</option>
              {sectors.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 감시 리스트 테이블 */}
      <Table
        columns={columns}
        data={paginatedData}
        rowKey="id"
        pagination={pagination}
        onRowClick={(record) => console.log('Row clicked:', record)}
      />

      {/* 모달들 */}
      <AddStockModal />
    </div>
  );
};

export default WatchlistPage; 