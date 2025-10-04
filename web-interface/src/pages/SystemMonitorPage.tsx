import React, { useState, useEffect } from 'react';
import { 
  Server, 
  Globe, 
  Calendar, 
  Eye, 
  BarChart3,
  Activity,
  Play,
  Square,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Monitor
} from 'lucide-react';
import { Button, LoadingSpinner } from '../components/ui';

interface ServiceStatus {
  name: string;
  description: string;
  running: boolean;
  port?: number;
  pid?: number;
  uptime: string;
  auto_start: boolean;
}

interface SystemOverview {
  total_services: number;
  running_services: number;
  stopped_services: number;
  system_health: string;
  uptime: string;
  last_update: string;
  services: Record<string, { name: string; running: boolean }>;
}

const ServiceCard: React.FC<{
  id: string;
  service: ServiceStatus;
  onStart: (id: string) => void;
  onStop: (id: string) => void;
  loading: boolean;
}> = ({ id, service, onStart, onStop, loading }) => {
  const getIcon = (id: string) => {
    switch (id) {
      case 'api_server': return <Server className="w-6 h-6" />;
      case 'web_interface': return <Globe className="w-6 h-6" />;
      case 'scheduler': return <Calendar className="w-6 h-6" />;
      case 'phase1_watchlist': return <Eye className="w-6 h-6" />;
      case 'phase2_daily': return <BarChart3 className="w-6 h-6" />;
      case 'realtime_monitor': return <Activity className="w-6 h-6" />;
      default: return <Monitor className="w-6 h-6" />;
    }
  };

  const getStatusColor = (running: boolean) => {
    return running 
      ? 'text-green-600 bg-green-50 border-green-200' 
      : 'text-red-600 bg-red-50 border-red-200';
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${service.running ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'}`}>
            {getIcon(id)}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{service.name}</h3>
            <p className="text-sm text-gray-600">{service.description}</p>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full border text-xs font-medium ${getStatusColor(service.running)}`}>
          {service.running ? (
            <div className="flex items-center space-x-1">
              <CheckCircle className="w-3 h-3" />
              <span>실행 중</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1">
              <XCircle className="w-3 h-3" />
              <span>정지</span>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2 mb-4">
        {service.port && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">포트:</span>
            <span className="font-mono">{service.port}</span>
          </div>
        )}
        {service.pid && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">PID:</span>
            <span className="font-mono">{service.pid}</span>
          </div>
        )}
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">상태:</span>
          <span>{service.uptime}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">자동 시작:</span>
          <span>{service.auto_start ? '활성화' : '비활성화'}</span>
        </div>
      </div>

      <div className="flex space-x-2">
        {!service.running ? (
          <Button
            onClick={() => onStart(id)}
            disabled={loading}
            className="flex-1 bg-green-600 hover:bg-green-700 text-white"
          >
            {loading ? <LoadingSpinner /> : (
              <>
                <Play className="w-4 h-4 mr-2" />
                시작
              </>
            )}
          </Button>
        ) : (
          <Button
            onClick={() => onStop(id)}
            disabled={loading || id === 'api_server'}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white disabled:bg-gray-400"
            title={id === 'api_server' ? 'API 서버는 직접 정지할 수 없습니다' : ''}
          >
            {loading ? <LoadingSpinner /> : (
              <>
                <Square className="w-4 h-4 mr-2" />
                정지
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
};

export default function SystemMonitorPage() {
  const [services, setServices] = useState<Record<string, ServiceStatus>>({});
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchSystemData = async () => {
    console.log('🔍 시스템 데이터 조회 시작...');
    try {
      const [servicesRes, overviewRes] = await Promise.all([
        fetch('http://localhost:8000/api/system/services'),
        fetch('http://localhost:8000/api/system/overview')
      ]);

      console.log('📡 API 응답:', { 
        services: servicesRes.status, 
        overview: overviewRes.status 
      });

      if (servicesRes.ok && overviewRes.ok) {
        const servicesData = await servicesRes.json();
        const overviewData = await overviewRes.json();
        
        console.log('✅ 서비스 데이터:', servicesData);
        console.log('✅ 개요 데이터:', overviewData);
        
        setServices(servicesData);
        setOverview(overviewData);
        setError(null);
      } else {
        throw new Error(`API 응답 오류: services(${servicesRes.status}), overview(${overviewRes.status})`);
      }
    } catch (error) {
      console.error('❌ 시스템 데이터 조회 실패:', error);
      setError(error instanceof Error ? error.message : '알 수 없는 오류');
    } finally {
      setLoading(false);
    }
  };

  const handleServiceAction = async (action: 'start' | 'stop', serviceId: string) => {
    console.log(`🎯 서비스 ${action}: ${serviceId}`);
    setActionLoading(serviceId);
    try {
      const response = await fetch(
        `http://localhost:8000/api/system/services/${serviceId}/${action}`,
        { method: 'POST' }
      );
      
      if (response.ok) {
        const result = await response.json();
        console.log('✅ 서비스 제어 성공:', result);
        // 1초 후 데이터 새로고침
        setTimeout(fetchSystemData, 1000);
      } else {
        throw new Error(`서비스 ${action} 실패: ${response.status}`);
      }
    } catch (error) {
      console.error(`❌ 서비스 ${action} 실패:`, error);
      setError(error instanceof Error ? error.message : '서비스 제어 실패');
    } finally {
      setActionLoading(null);
    }
  };

  useEffect(() => {
    console.log('🚀 SystemMonitorPage 마운트됨');
    fetchSystemData();
    // 10초마다 자동 새로고침
    const interval = setInterval(fetchSystemData, 10000);
    return () => {
      console.log('🔄 SystemMonitorPage 언마운트됨');
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <LoadingSpinner />
        <p className="mt-4 text-gray-600">시스템 데이터를 로딩 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <XCircle className="w-12 h-12 text-red-500 mb-4" />
        <p className="text-red-600 font-medium">시스템 데이터 로딩 실패</p>
        <p className="text-gray-600 text-sm mt-2">{error}</p>
        <Button
          onClick={fetchSystemData}
          className="mt-4"
        >
          다시 시도
        </Button>
      </div>
    );
  }

  const getHealthIcon = (health: string) => {
    switch (health) {
      case 'healthy': return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'warning': return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
      default: return <XCircle className="w-5 h-5 text-red-600" />;
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">시스템 모니터링</h1>
          <p className="text-gray-600">한투 퀀트 시스템의 모든 서비스 상태를 관리합니다</p>
        </div>
        <Button
          onClick={fetchSystemData}
          className="flex items-center space-x-2"
        >
          <RefreshCw className="w-4 h-4" />
          <span>새로고침</span>
        </Button>
      </div>

      {/* 디버깅 정보 */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <h3 className="font-medium text-gray-900 mb-2">🔍 디버깅 정보</h3>
        <div className="text-sm text-gray-600 space-y-1">
          <p>서비스 개수: {Object.keys(services).length}</p>
          <p>개요 데이터: {overview ? '로딩됨' : '없음'}</p>
          <p>오류: {error || '없음'}</p>
        </div>
      </div>

      {/* 시스템 개요 */}
      {overview && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">시스템 개요</h2>
            <div className="flex items-center space-x-2">
              {getHealthIcon(overview.system_health)}
              <span className="text-sm font-medium">
                {overview.system_health === 'healthy' ? '정상' : '주의'}
              </span>
            </div>
          </div>
          
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">{overview.total_services}</div>
              <div className="text-sm text-blue-600">전체 서비스</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-green-600">{overview.running_services}</div>
              <div className="text-sm text-green-600">실행 중</div>
            </div>
            <div className="bg-red-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-red-600">{overview.stopped_services}</div>
              <div className="text-sm text-red-600">정지됨</div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-gray-600">{overview.uptime}</div>
              <div className="text-sm text-gray-600">시스템 상태</div>
            </div>
          </div>
        </div>
      )}

      {/* 서비스 목록 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {Object.entries(services).map(([id, service]) => (
          <ServiceCard
            key={id}
            id={id}
            service={service}
            onStart={(serviceId) => handleServiceAction('start', serviceId)}
            onStop={(serviceId) => handleServiceAction('stop', serviceId)}
            loading={actionLoading === id}
          />
        ))}
      </div>

      {/* 서비스가 없는 경우 */}
      {Object.keys(services).length === 0 && (
        <div className="text-center py-12">
          <Monitor className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">서비스 정보를 찾을 수 없습니다.</p>
          <Button
            onClick={fetchSystemData}
            className="mt-4"
          >
            다시 시도
          </Button>
        </div>
      )}

      {/* 실행 가이드 */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-4">🚀 실행 가이드</h3>
        <div className="space-y-3 text-sm text-blue-800">
          <div><strong>기본 실행:</strong> API 서버와 웹 인터페이스만 실행하면 모든 기본 기능 사용 가능</div>
          <div><strong>자동화 실행:</strong> 통합 스케줄러를 실행하면 매일 자동으로 종목 분석</div>
          <div><strong>수동 분석:</strong> Phase1/Phase2를 개별 실행하여 즉시 분석 가능</div>
          <div><strong>실시간 모니터링:</strong> 실시간 모니터를 실행하면 시장 데이터 추적</div>
        </div>
      </div>
    </div>
  );
} 