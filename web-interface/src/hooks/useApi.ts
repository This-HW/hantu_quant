import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  execute: () => Promise<T>;
  reset: () => void;
}

const API_BASE_URL = 'http://localhost:8000';

export function useApi<T>(url: string | null): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async (): Promise<T> => {
    if (!url) {
      throw new Error('URL이 제공되지 않았습니다');
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE_URL}${url}`);
      
      // API 응답이 직접 데이터를 반환하는 경우와 wrapped 형태 모두 처리
      let result;
      if (response.data.success !== undefined) {
        // wrapped 형태: { success: true, data: [...] }
        if (response.data.success) {
          result = response.data.data;
        } else {
          throw new Error(response.data.error || '알 수 없는 오류가 발생했습니다');
        }
      } else {
        // 직접 데이터 반환: [...]
        result = response.data;
      }
      
      setData(result);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '네트워크 오류가 발생했습니다';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [url]);

  const refetch = useCallback(async (): Promise<void> => {
    if (url) {
      await execute();
    }
  }, [execute, url]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (url) {
      execute().catch(() => {
        // Error는 이미 상태에 저장되었으므로 여기서는 무시
      });
    }
  }, [url, execute]);

  return {
    data,
    loading,
    error,
    refetch,
    execute,
    reset,
  };
}

export default useApi;

// 특정 API 엔드포인트를 위한 훅들
export function useSystemStatus() {
  return useApi('/api/system-status');
}

export function useWatchlist() {
  return useApi('/api/watchlist');
}

export function useDailySelections(date?: string) {
  return useApi(`/api/daily-selections?date=${date}`);
}

export function useModelPerformance() {
  return useApi('/api/model-performance');
}

export function useMarketAlerts() {
  return useApi('/api/market-alerts');
}

export function usePerformanceMetrics(period: 'daily' | 'weekly' | 'monthly' | 'yearly' = 'daily') {
  return useApi(`/api/performance-metrics?period=${period}`);
} 