import axios from 'axios';
import type { AxiosInstance, AxiosResponse } from 'axios';
import type {
  ApiResponse,
  Stock,
  WatchlistItem,
  DailySelection,
  ModelPerformance,
  BacktestResult,
  MarketAlert,
  SystemStatus,
  PerformanceMetrics,
  SystemSettings,
} from '../types';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 요청 인터셉터
    this.api.interceptors.request.use(
      (config) => {
        // 인증 토큰이 있다면 헤더에 추가
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // 응답 인터셉터
    this.api.interceptors.response.use(
      (response: AxiosResponse<ApiResponse<any>>) => response,
      (error) => {
        console.error('API Error:', error);
        return Promise.reject(error);
      }
    );
  }

  // 시스템 상태 관련
  async getSystemStatus(): Promise<SystemStatus> {
    const response = await this.api.get<SystemStatus>('/api/system/status');
    return response.data;
  }

  // 감시 리스트 관련
  async getWatchlist(): Promise<WatchlistItem[]> {
    const response = await this.api.get<WatchlistItem[]>('/api/watchlist');
    return response.data || [];
  }

  async addToWatchlist(stockCode: string, reason: string, targetPrice?: number): Promise<WatchlistItem> {
    const response = await this.api.post<WatchlistItem>('/api/watchlist', {
      stockCode,
      reason,
      targetPrice,
    });
    return response.data;
  }

  async removeFromWatchlist(id: string): Promise<void> {
    await this.api.delete(`/api/watchlist/${id}`);
  }

  async updateWatchlistItem(id: string, updates: Partial<WatchlistItem>): Promise<WatchlistItem> {
    const response = await this.api.patch<WatchlistItem>(`/api/watchlist/${id}`, updates);
    return response.data;
  }

  // 일일 선정 종목 관련
  async getDailySelections(date?: string): Promise<DailySelection[]> {
    const params = date ? { date } : {};
    const response = await this.api.get<DailySelection[]>('/api/daily-selections', { params });
    return response.data || [];
  }

  async runDailySelection(): Promise<DailySelection[]> {
    const response = await this.api.post<DailySelection[]>('/api/daily-selections/run');
    return response.data || [];
  }

  // 주식 정보 관련
  async searchStocks(query: string): Promise<Stock[]> {
    const response = await this.api.get<ApiResponse<Stock[]>>('/stocks/search', {
      params: { q: query },
    });
    return response.data.data || [];
  }

  async getStockDetail(code: string): Promise<Stock> {
    const response = await this.api.get<ApiResponse<Stock>>(`/stocks/${code}`);
    return response.data.data!;
  }

  // AI 모델 성능 관련
  async getModelPerformance(): Promise<ModelPerformance[]> {
    const response = await this.api.get<ApiResponse<ModelPerformance[]>>('/ai/models/performance');
    return response.data.data || [];
  }

  async retrainModel(modelName: string): Promise<void> {
    await this.api.post(`/ai/models/${modelName}/retrain`);
  }

  // 백테스트 관련
  async getBacktestResults(): Promise<BacktestResult[]> {
    const response = await this.api.get<ApiResponse<BacktestResult[]>>('/backtest/results');
    return response.data.data || [];
  }

  async runBacktest(strategyName: string, startDate: string, endDate: string): Promise<BacktestResult> {
    const response = await this.api.post<ApiResponse<BacktestResult>>('/backtest/run', {
      strategyName,
      startDate,
      endDate,
    });
    return response.data.data!;
  }

  // 시장 모니터링 알림 관련
  async getMarketAlerts(): Promise<MarketAlert[]> {
    const response = await this.api.get<ApiResponse<MarketAlert[]>>('/market/alerts');
    return response.data.data || [];
  }

  async acknowledgeAlert(alertId: string): Promise<void> {
    await this.api.patch(`/market/alerts/${alertId}/acknowledge`);
  }

  async clearAllAlerts(): Promise<void> {
    await this.api.delete('/market/alerts');
  }

  // 성과 지표 관련
  async getPerformanceMetrics(period: 'daily' | 'weekly' | 'monthly' | 'yearly'): Promise<PerformanceMetrics> {
    const response = await this.api.get<ApiResponse<PerformanceMetrics>>('/performance/metrics', {
      params: { period },
    });
    return response.data.data!;
  }

  // 설정 관련
  async getSettings(): Promise<SystemSettings> {
    const response = await this.api.get<SystemSettings>('/api/settings');
    return response.data;
  }

  async updateSettings(settings: Partial<SystemSettings>): Promise<SystemSettings> {
    const response = await this.api.patch<SystemSettings>('/api/settings', settings);
    return response.data;
  }

  // 실시간 데이터 스트림
  async getRealtimeData(stockCodes: string[]): Promise<Stock[]> {
    const response = await this.api.post<ApiResponse<Stock[]>>('/realtime/stocks', {
      stockCodes,
    });
    return response.data.data || [];
  }
}

// 싱글톤 인스턴스 생성
export const apiService = new ApiService();
export default apiService; 