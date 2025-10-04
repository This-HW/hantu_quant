import React from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Brush,
} from 'recharts';

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

export interface ChartProps {
  data: ChartDataPoint[];
  type: 'line' | 'area' | 'bar' | 'candlestick' | 'volume';
  height?: number;
  showGrid?: boolean;
  showTooltip?: boolean;
  showBrush?: boolean;
  strokeColor?: string;
  fillColor?: string;
  indicators?: TechnicalIndicator[];
  onDataPointClick?: (data: any) => void;
}

export interface TechnicalIndicator {
  type: 'sma' | 'ema' | 'bollinger' | 'macd' | 'rsi';
  period?: number;
  color?: string;
  data?: ChartDataPoint[];
}

const CustomTooltip: React.FC<{
  active?: boolean;
  payload?: any[];
  label?: string;
  type: string;
}> = ({ active, payload, label, type }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    
    return (
      <div className="bg-white p-3 border border-gray-300 rounded-lg shadow-lg">
        <p className="font-medium text-gray-900">{label}</p>
        {type === 'candlestick' && (
          <div className="space-y-1 text-sm">
            <p>시가: <span className="font-medium">{data.open?.toLocaleString()}원</span></p>
            <p>고가: <span className="font-medium text-red-600">{data.high?.toLocaleString()}원</span></p>
            <p>저가: <span className="font-medium text-blue-600">{data.low?.toLocaleString()}원</span></p>
            <p>종가: <span className="font-medium">{data.close?.toLocaleString()}원</span></p>
            {data.volume && (
              <p>거래량: <span className="font-medium">{data.volume?.toLocaleString()}</span></p>
            )}
          </div>
        )}
        {type === 'volume' && (
          <p className="text-sm">거래량: <span className="font-medium">{data.volume?.toLocaleString()}</span></p>
        )}
        {type === 'line' && (
          <p className="text-sm">값: <span className="font-medium">{data.value?.toLocaleString()}</span></p>
        )}
      </div>
    );
  }
  return null;
};

const CandlestickBar: React.FC<{
  payload: ChartDataPoint;
  x: number;
  y: number;
  width: number;
  height: number;
}> = ({ payload, x, y, width, height }) => {
  const { open, high, low, close } = payload;
  
  if (!open || !high || !low || !close) return null;
  
  const isUp = close > open;
  const color = isUp ? '#10b981' : '#ef4444';
  const bodyHeight = Math.abs(close - open);
  const bodyY = isUp ? y + height - (close - Math.min(high, low)) * height / (high - low) : y + height - (open - Math.min(high, low)) * height / (high - low);
  
  return (
    <g>
      {/* 고저 라인 */}
      <line
        x1={x + width / 2}
        y1={y + height - (high - Math.min(high, low)) * height / (high - low)}
        x2={x + width / 2}
        y2={y + height - (low - Math.min(high, low)) * height / (high - low)}
        stroke={color}
        strokeWidth={1}
      />
      {/* 몸통 */}
      <rect
        x={x + width * 0.2}
        y={bodyY}
        width={width * 0.6}
        height={bodyHeight * height / (high - low)}
        fill={isUp ? color : color}
        stroke={color}
        strokeWidth={1}
      />
    </g>
  );
};

export const Chart: React.FC<ChartProps> = ({
  data,
  type,
  height = 300,
  showGrid = true,
  showTooltip = true,
  showBrush = false,
  strokeColor = '#3b82f6',
  fillColor = '#93c5fd',
  indicators = [],
  onDataPointClick,
}) => {
  const formatXAxisLabel = (value: string) => {
    const date = new Date(value);
    return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
  };

  const formatYAxisLabel = (value: number) => {
    if (type === 'volume') {
      if (value >= 1000000) {
        return `${(value / 1000000).toFixed(1)}M`;
      } else if (value >= 1000) {
        return `${(value / 1000).toFixed(1)}K`;
      }
      return value.toString();
    }
    return value.toLocaleString();
  };

  const renderChart = () => {
    const commonProps = {
      data,
      margin: { top: 5, right: 30, left: 20, bottom: 5 },
    };

    switch (type) {
      case 'line':
        return (
          <LineChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis 
              dataKey="date" 
              tickFormatter={formatXAxisLabel}
              tick={{ fontSize: 12 }}
            />
            <YAxis 
              tickFormatter={formatYAxisLabel}
              tick={{ fontSize: 12 }}
            />
            {showTooltip && (
              <Tooltip content={<CustomTooltip type={type} />} />
            )}
            <Line
              type="monotone"
              dataKey="value"
              stroke={strokeColor}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            {indicators.map((indicator, index) => (
              <Line
                key={index}
                type="monotone"
                dataKey={`${indicator.type}_${indicator.period}`}
                stroke={indicator.color || '#6b7280'}
                strokeWidth={1}
                strokeDasharray="5 5"
                dot={false}
              />
            ))}
            {showBrush && <Brush />}
          </LineChart>
        );

      case 'area':
        return (
          <AreaChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis 
              dataKey="date" 
              tickFormatter={formatXAxisLabel}
              tick={{ fontSize: 12 }}
            />
            <YAxis 
              tickFormatter={formatYAxisLabel}
              tick={{ fontSize: 12 }}
            />
            {showTooltip && (
              <Tooltip content={<CustomTooltip type={type} />} />
            )}
            <Area
              type="monotone"
              dataKey="value"
              stroke={strokeColor}
              fill={fillColor}
              fillOpacity={0.6}
            />
            {showBrush && <Brush />}
          </AreaChart>
        );

      case 'bar':
      case 'volume':
        return (
          <BarChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis 
              dataKey="date" 
              tickFormatter={formatXAxisLabel}
              tick={{ fontSize: 12 }}
            />
            <YAxis 
              tickFormatter={formatYAxisLabel}
              tick={{ fontSize: 12 }}
            />
            {showTooltip && (
              <Tooltip content={<CustomTooltip type={type} />} />
            )}
            <Bar
              dataKey={type === 'volume' ? 'volume' : 'value'}
              fill={fillColor}
              opacity={0.8}
            />
            {showBrush && <Brush />}
          </BarChart>
        );

      case 'candlestick':
        return (
          <LineChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis 
              dataKey="date" 
              tickFormatter={formatXAxisLabel}
              tick={{ fontSize: 12 }}
            />
            <YAxis 
              tickFormatter={formatYAxisLabel}
              tick={{ fontSize: 12 }}
            />
            {showTooltip && (
              <Tooltip content={<CustomTooltip type={type} />} />
            )}
            <Line
              type="monotone"
              dataKey="close"
              stroke={strokeColor}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="open"
              stroke="#6b7280"
              strokeWidth={1}
              strokeDasharray="3 3"
              dot={false}
            />
            {showBrush && <Brush />}
          </LineChart>
        );

      default:
        return null;
    }
  };

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        {renderChart() || <div>차트를 불러올 수 없습니다</div>}
      </ResponsiveContainer>
    </div>
  );
};

// 기술지표 계산 유틸리티
export const calculateSMA = (data: ChartDataPoint[], period: number = 20): ChartDataPoint[] => {
  return data.map((item, index) => {
    if (index < period - 1) {
      return { ...item, [`sma_${period}`]: null };
    }
    
    const sum = data
      .slice(index - period + 1, index + 1)
      .reduce((acc, curr) => acc + (curr.close || curr.value || 0), 0);
    
    return { ...item, [`sma_${period}`]: sum / period };
  });
};

export const calculateEMA = (data: ChartDataPoint[], period: number = 12): ChartDataPoint[] => {
  const multiplier = 2 / (period + 1);
  let ema = 0;
  
  return data.map((item, index) => {
    const price = item.close || item.value || 0;
    
    if (index === 0) {
      ema = price;
    } else {
      ema = (price * multiplier) + (ema * (1 - multiplier));
    }
    
    return { ...item, [`ema_${period}`]: ema };
  });
};

export const calculateRSI = (data: ChartDataPoint[], period: number = 14): ChartDataPoint[] => {
  const changes = data.map((item, index) => {
    if (index === 0) return { gain: 0, loss: 0 };
    const change = (item.close || item.value || 0) - (data[index - 1].close || data[index - 1].value || 0);
    return {
      gain: change > 0 ? change : 0,
      loss: change < 0 ? Math.abs(change) : 0
    };
  });
  
  return data.map((item, index) => {
    if (index < period) {
      return { ...item, rsi: null };
    }
    
    const periodChanges = changes.slice(index - period + 1, index + 1);
    const avgGain = periodChanges.reduce((sum, change) => sum + change.gain, 0) / period;
    const avgLoss = periodChanges.reduce((sum, change) => sum + change.loss, 0) / period;
    
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = 100 - (100 / (1 + rs));
    
    return { ...item, rsi };
  });
};

export default Chart; 