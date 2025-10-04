// 주식 관련 타입
export interface Stock {
  code: string;
  name: string;
  market: 'KOSPI' | 'KOSDAQ' | 'KONEX';
  sector: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap: number;
  previousClose?: number;
  dayHigh?: number;
  dayLow?: number;
}

// 감시 리스트 관련 타입
export interface WatchlistItem {
  id: string;
  stock: Stock;
  addedAt: string;
  targetPrice?: number;
  stopLoss?: number;
  reason: string;
  score: number;
  alerts?: AlertRule[];
}

export interface AlertRule {
  id: string;
  type: 'price_target' | 'price_change' | 'volume_spike' | 'technical_signal';
  condition: 'above' | 'below' | 'change_percent';
  value: number;
  enabled: boolean;
}

// 일일 선정 관련 타입
export interface DailySelection {
  id: string;
  stock: Stock;
  selectedAt: string;
  attractivenessScore: number;
  technicalScore: number;
  momentumScore: number;
  reasons: string[];
  expectedReturn: number;
  confidence: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
}

// 시장 알림 관련 타입
export interface MarketAlert {
  id: string;
  type: 'price_spike' | 'price_drop' | 'volume_spike' | 'ai_recommendation' | 'technical_signal' | 'selection_alert' | string;
  severity: 'low' | 'medium' | 'high' | 'critical' | string;
  title: string;
  stock?: Stock;
  message: string;
  timestamp: string;
  acknowledged: boolean;
  data?: Record<string, any>;
}

// 시스템 상태 관련 타입
export interface SystemStatus {
  isRunning: boolean;
  lastUpdate: string;
  activeAlerts: number;
  watchlistCount: number;
  dailySelectionsCount: number;
  performance: PerformanceMetrics;
  health: {
    api: 'healthy' | 'warning' | 'error';
    database: 'healthy' | 'warning' | 'error';
    websocket: 'healthy' | 'warning' | 'error';
  };
}

export interface PerformanceMetrics {
  accuracy: number;
  totalProcessed: number;
  avgProcessingTime: number;
  memoryUsage?: number;
  cpuUsage?: number;
  errorRate?: number;
}

// AI 모델 관련 타입
export interface ModelPerformance {
  modelName: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  lastUpdated: string;
  trainingDataSize: number;
  features: string[];
  hyperparameters?: Record<string, any>;
}

export interface PredictionResult {
  stockCode: string;
  prediction: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  expectedReturn: number;
  features: Record<string, number>;
  modelUsed: string;
  timestamp: string;
}

// 백테스트 관련 타입
export interface BacktestResult {
  id: string;
  name: string;
  strategy: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  finalCapital: number;
  totalReturn: number;
  annualizedReturn: number;
  volatility: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  profitableTrades: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  performanceData: ChartDataPoint[];
  drawdownData: ChartDataPoint[];
  monthlyReturns: ChartDataPoint[];
  tradeHistory: Trade[];
  settings: BacktestSettings;
}

export interface Trade {
  id: string;
  symbol: string;
  type: 'buy' | 'sell';
  quantity: number;
  price: number;
  date: string;
  profit: number;
  profitPercent: number;
  commission: number;
  reason?: string;
}

export interface BacktestSettings {
  strategy: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  commission: number;
  slippage: number;
  maxPositions?: number;
  riskPerTrade?: number;
}

// 차트 관련 타입
export interface ChartDataPoint {
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  value?: number;
  [key: string]: any;
}

export interface TechnicalIndicator {
  type: 'sma' | 'ema' | 'bollinger' | 'macd' | 'rsi';
  period?: number;
  color?: string;
  data?: ChartDataPoint[];
  parameters?: Record<string, any>;
}

// 설정 관련 타입
export interface SystemSettings {
  apiSettings: {
    kisApi: {
      enabled: boolean;
      rateLimit: number;
      timeout: number;
    };
    retryCount: number;
    batchSize: number;
  };
  alertSettings: {
    email: {
      enabled: boolean;
      recipients: string[];
      threshold: number;
    };
    telegram: {
      enabled: boolean;
      botToken: string;
      chatId: string;
    };
    web: {
      enabled: boolean;
      sound: boolean;
    };
  };
  backtestSettings: {
    maxHistoryDays: number;
    commission: number;
    slippage: number;
    initialCapital: number;
  };
  performanceSettings: {
    workerCount: number;
    memoryLimit: number;
    cacheSize: number;
    logLevel: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  };
  securitySettings: {
    tokenRefreshInterval: number;
    sessionTimeout: number;
    enableEncryption: boolean;
  };
}

// 실시간 데이터 관련 타입
export interface RealtimeData {
  type: 'market_update' | 'alert' | 'system_status' | 'trade_execution';
  timestamp: string;
  data: any;
}

export interface MarketIndices {
  kospi: {
    value: number;
    change: number;
    changePercent: number;
  };
  kosdaq: {
    value: number;
    change: number;
    changePercent: number;
  };
}

// API 응답 관련 타입
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
  metadata?: {
    page?: number;
    totalPages?: number;
    totalItems?: number;
  };
}

// 페이지네이션 관련 타입
export interface PaginationParams {
  page: number;
  limit: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  filters?: Record<string, any>;
}

export interface PaginatedResult<T> {
  items: T[];
  pagination: {
    currentPage: number;
    totalPages: number;
    totalItems: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
}

// 필터 관련 타입
export interface StockFilter {
  markets?: string[];
  sectors?: string[];
  priceRange?: {
    min: number;
    max: number;
  };
  volumeRange?: {
    min: number;
    max: number;
  };
  changeRange?: {
    min: number;
    max: number;
  };
}

export interface AlertFilter {
  types?: string[];
  severities?: string[];
  acknowledged?: boolean;
  dateRange?: {
    start: string;
    end: string;
  };
}

// 사용자 관련 타입
export interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'user' | 'viewer';
  preferences: UserPreferences;
  lastLogin: string;
  created: string;
}

export interface UserPreferences {
  theme: 'light' | 'dark';
  language: 'ko' | 'en';
  notifications: {
    email: boolean;
    web: boolean;
    sound: boolean;
  };
  dashboard: {
    layout: string;
    widgets: string[];
  };
}

// WebSocket 관련 타입
export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  id?: string;
}

export interface ConnectionStatus {
  connected: boolean;
  lastConnected?: string;
  reconnectAttempts: number;
  latency?: number;
}

// 통계 관련 타입
export interface Statistics {
  daily: {
    totalSelections: number;
    accuracy: number;
    averageReturn: number;
    totalVolume: number;
  };
  weekly: {
    bestPerformer: Stock;
    worstPerformer: Stock;
    totalTrades: number;
    winRate: number;
  };
  monthly: {
    totalReturn: number;
    volatility: number;
    sharpeRatio: number;
    maxDrawdown: number;
  };
}

// 에러 관련 타입
export interface AppError {
  code: string;
  message: string;
  details?: string;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

// 테마 관련 타입
export interface Theme {
  name: string;
  colors: {
    primary: string;
    secondary: string;
    success: string;
    warning: string;
    error: string;
    background: string;
    surface: string;
    text: string;
  };
  spacing: Record<string, string>;
  typography: Record<string, any>;
}

export default {}; 