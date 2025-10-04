import { useState, useMemo } from 'react';

export interface PaginationConfig {
  current: number;
  pageSize: number;
  total: number;
  onChange: (page: number, pageSize: number) => void;
}

export interface UsePaginationOptions {
  defaultPageSize?: number;
  pageSizeOptions?: number[];
  showSizeChanger?: boolean;
}

export function usePagination<T>(
  data: T[],
  options: UsePaginationOptions = {}
) {
  const {
    defaultPageSize = 10,
    pageSizeOptions = [10, 20, 50, 100],
    showSizeChanger = true,
  } = options;

  const [current, setCurrent] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);

  const total = data.length;
  const totalPages = Math.ceil(total / pageSize);

  // 현재 페이지의 데이터 계산
  const paginatedData = useMemo(() => {
    const startIndex = (current - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    return data.slice(startIndex, endIndex);
  }, [data, current, pageSize]);

  // 페이지 변경 핸들러
  const onChange = (page: number, newPageSize?: number) => {
    if (newPageSize && newPageSize !== pageSize) {
      // 페이지 크기가 변경된 경우, 현재 항목의 위치를 유지하려고 시도
      const currentItemIndex = (current - 1) * pageSize;
      const newPage = Math.floor(currentItemIndex / newPageSize) + 1;
      setCurrent(newPage);
      setPageSize(newPageSize);
    } else {
      setCurrent(page);
    }
  };

  // 페이지 이동 함수들
  const goToFirst = () => onChange(1);
  const goToLast = () => onChange(totalPages);
  const goToPrevious = () => onChange(Math.max(1, current - 1));
  const goToNext = () => onChange(Math.min(totalPages, current + 1));

  // 페이지네이션 설정 객체
  const pagination: PaginationConfig = {
    current,
    pageSize,
    total,
    onChange,
  };

  return {
    // 페이지네이션된 데이터
    data: paginatedData,
    
    // 페이지네이션 설정
    pagination,
    
    // 페이지 정보
    current,
    pageSize,
    total,
    totalPages,
    
    // 페이지 이동 함수들
    goToFirst,
    goToLast,
    goToPrevious,
    goToNext,
    
    // 상태 확인
    isFirstPage: current === 1,
    isLastPage: current === totalPages,
    hasData: data.length > 0,
    
    // 설정
    pageSizeOptions,
    showSizeChanger,
  };
}

// 서버 사이드 페이지네이션을 위한 훅
export function useServerPagination(options: UsePaginationOptions = {}) {
  const {
    defaultPageSize = 10,
    pageSizeOptions = [10, 20, 50, 100],
    showSizeChanger = true,
  } = options;

  const [current, setCurrent] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);
  const [total, setTotal] = useState(0);

  const onChange = (page: number, newPageSize?: number) => {
    if (newPageSize && newPageSize !== pageSize) {
      setCurrent(1); // 페이지 크기 변경 시 첫 페이지로
      setPageSize(newPageSize);
    } else {
      setCurrent(page);
    }
  };

  const pagination: PaginationConfig = {
    current,
    pageSize,
    total,
    onChange,
  };

  return {
    pagination,
    current,
    pageSize,
    total,
    setTotal,
    pageSizeOptions,
    showSizeChanger,
  };
} 