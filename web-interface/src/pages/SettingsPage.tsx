import React, { useState, useEffect } from 'react';
import {
  Settings,
  Database,
  Bell,
  Shield,
  Cpu,
  HardDrive,
  Wifi,
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Server,
  Mail,
  Smartphone
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

interface SystemSettings {
  // API 설정
  apiSettings: {
    kisApi: {
      enabled: boolean;
      rateLimit: number;
      timeout: number;
    };
    retryCount: number;
    batchSize: number;
  };
  
  // 알림 설정
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
  
  // 백테스트 설정
  backtestSettings: {
    maxHistoryDays: number;
    commission: number;
    slippage: number;
    initialCapital: number;
  };
  
  // 성능 설정
  performanceSettings: {
    workerCount: number;
    memoryLimit: number;
    cacheSize: number;
    logLevel: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  };
  
  // 보안 설정
  securitySettings: {
    tokenRefreshInterval: number;
    sessionTimeout: number;
    enableEncryption: boolean;
  };
}

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('api');
  const [settings, setSettings] = useState<SystemSettings>({
    apiSettings: {
      kisApi: {
        enabled: true,
        rateLimit: 15,
        timeout: 30000,
      },
      retryCount: 3,
      batchSize: 500,
    },
    alertSettings: {
      email: {
        enabled: false,
        recipients: [],
        threshold: 3.0,
      },
      telegram: {
        enabled: false,
        botToken: '',
        chatId: '',
      },
      web: {
        enabled: true,
        sound: true,
      },
    },
    backtestSettings: {
      maxHistoryDays: 365,
      commission: 0.0015,
      slippage: 0.001,
      initialCapital: 10000000,
    },
    performanceSettings: {
      workerCount: 4,
      memoryLimit: 2048,
      cacheSize: 1000,
      logLevel: 'INFO',
    },
    securitySettings: {
      tokenRefreshInterval: 3600,
      sessionTimeout: 7200,
      enableEncryption: true,
    },
  });
  
  const [isModified, setIsModified] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'success' | 'error' | null>(null);

  const { data: currentSettings, loading, error, refetch } = useApi<SystemSettings>('/api/settings');

  useEffect(() => {
    if (currentSettings) {
      setSettings(currentSettings);
    }
  }, [currentSettings]);

  const handleSettingChange = (category: string, field: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [category]: {
        ...prev[category as keyof SystemSettings],
        [field]: value,
      },
    }));
    setIsModified(true);
    setSaveStatus(null);
  };

  const handleNestedSettingChange = (category: string, subCategory: string, field: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [category]: {
        ...prev[category as keyof SystemSettings],
        [subCategory]: {
          ...((prev[category as keyof SystemSettings] as any)[subCategory]),
          [field]: value,
        },
      },
    }));
    setIsModified(true);
    setSaveStatus(null);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // API 호출로 설정 저장
      await new Promise(resolve => setTimeout(resolve, 1000)); // 시뮬레이션
      setSaveStatus('success');
      setIsModified(false);
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (error) {
      setSaveStatus('error');
      console.error('설정 저장 실패:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    if (currentSettings) {
      setSettings(currentSettings);
      setIsModified(false);
      setSaveStatus(null);
    }
  };

  const tabs = [
    { id: 'api', label: 'API 설정', icon: <Server className="h-4 w-4" /> },
    { id: 'alerts', label: '알림 설정', icon: <Bell className="h-4 w-4" /> },
    { id: 'backtest', label: '백테스트', icon: <Database className="h-4 w-4" /> },
    { id: 'performance', label: '성능', icon: <Cpu className="h-4 w-4" /> },
    { id: 'security', label: '보안', icon: <Shield className="h-4 w-4" /> },
  ];

  const SettingCard: React.FC<{
    title: string;
    description: string;
    children: React.ReactNode;
  }> = ({ title, description, children }) => (
    <div className="card">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <p className="text-sm text-gray-600">{description}</p>
      </div>
      {children}
    </div>
  );

  const ApiSettings: React.FC = () => (
    <div className="space-y-6">
      <SettingCard
        title="한국투자증권 API"
        description="한국투자증권 API 연동 설정을 관리합니다"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.apiSettings.kisApi.enabled}
                onChange={(e) => handleNestedSettingChange('apiSettings', 'kisApi', 'enabled', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm font-medium">API 사용 활성화</span>
            </label>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              초당 호출 제한 (건)
            </label>
            <input
              type="number"
              value={settings.apiSettings.kisApi.rateLimit}
              onChange={(e) => handleNestedSettingChange('apiSettings', 'kisApi', 'rateLimit', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="1"
              max="20"
            />
            <p className="text-xs text-gray-500 mt-1">권장: 15건 (실제 제한: 20건)</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              타임아웃 (ms)
            </label>
            <input
              type="number"
              value={settings.apiSettings.kisApi.timeout}
              onChange={(e) => handleNestedSettingChange('apiSettings', 'kisApi', 'timeout', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="5000"
              max="60000"
              step="1000"
            />
          </div>
        </div>
      </SettingCard>

      <SettingCard
        title="일반 API 설정"
        description="API 호출 및 재시도 정책을 설정합니다"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              재시도 횟수
            </label>
            <input
              type="number"
              value={settings.apiSettings.retryCount}
              onChange={(e) => handleSettingChange('apiSettings', 'retryCount', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="1"
              max="5"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              배치 크기 (종목 수)
            </label>
            <input
              type="number"
              value={settings.apiSettings.batchSize}
              onChange={(e) => handleSettingChange('apiSettings', 'batchSize', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="100"
              max="1000"
              step="100"
            />
          </div>
        </div>
      </SettingCard>
    </div>
  );

  const AlertSettings: React.FC = () => (
    <div className="space-y-6">
      <SettingCard
        title="이메일 알림"
        description="이메일을 통한 알림 설정을 관리합니다"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.alertSettings.email.enabled}
                onChange={(e) => handleNestedSettingChange('alertSettings', 'email', 'enabled', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm font-medium">이메일 알림 활성화</span>
            </label>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              알림 임계값 (%)
            </label>
            <input
              type="number"
              value={settings.alertSettings.email.threshold}
              onChange={(e) => handleNestedSettingChange('alertSettings', 'email', 'threshold', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="0.1"
              max="10"
              step="0.1"
            />
          </div>
        </div>
      </SettingCard>

      <SettingCard
        title="텔레그램 알림"
        description="텔레그램 봇을 통한 실시간 알림을 설정합니다"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.alertSettings.telegram.enabled}
                onChange={(e) => handleNestedSettingChange('alertSettings', 'telegram', 'enabled', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm font-medium">텔레그램 알림 활성화</span>
            </label>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              봇 토큰
            </label>
            <input
              type="password"
              value={settings.alertSettings.telegram.botToken}
              onChange={(e) => handleNestedSettingChange('alertSettings', 'telegram', 'botToken', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              채팅 ID
            </label>
            <input
              type="text"
              value={settings.alertSettings.telegram.chatId}
              onChange={(e) => handleNestedSettingChange('alertSettings', 'telegram', 'chatId', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="-1001234567890"
            />
          </div>
        </div>
      </SettingCard>

      <SettingCard
        title="웹 알림"
        description="브라우저 알림 설정을 관리합니다"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.alertSettings.web.enabled}
                onChange={(e) => handleNestedSettingChange('alertSettings', 'web', 'enabled', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm font-medium">웹 알림 활성화</span>
            </label>
          </div>
          
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.alertSettings.web.sound}
                onChange={(e) => handleNestedSettingChange('alertSettings', 'web', 'sound', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm font-medium">소리 알림</span>
            </label>
          </div>
        </div>
      </SettingCard>
    </div>
  );

  const BacktestSettings: React.FC = () => (
    <div className="space-y-6">
      <SettingCard
        title="백테스트 기본 설정"
        description="백테스트 실행 시 사용할 기본 매개변수를 설정합니다"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              최대 히스토리 기간 (일)
            </label>
            <input
              type="number"
              value={settings.backtestSettings.maxHistoryDays}
              onChange={(e) => handleSettingChange('backtestSettings', 'maxHistoryDays', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="30"
              max="1095"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              수수료율 (%)
            </label>
            <input
              type="number"
              value={settings.backtestSettings.commission}
              onChange={(e) => handleSettingChange('backtestSettings', 'commission', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="0"
              max="1"
              step="0.0001"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              슬리피지 (%)
            </label>
            <input
              type="number"
              value={settings.backtestSettings.slippage}
              onChange={(e) => handleSettingChange('backtestSettings', 'slippage', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="0"
              max="0.1"
              step="0.001"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              초기 자본 (원)
            </label>
            <input
              type="number"
              value={settings.backtestSettings.initialCapital}
              onChange={(e) => handleSettingChange('backtestSettings', 'initialCapital', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="1000000"
              max="1000000000"
              step="1000000"
            />
          </div>
        </div>
      </SettingCard>
    </div>
  );

  const PerformanceSettings: React.FC = () => (
    <div className="space-y-6">
      <SettingCard
        title="시스템 성능"
        description="시스템 리소스 사용량을 조정합니다"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              워커 프로세스 수
            </label>
            <input
              type="number"
              value={settings.performanceSettings.workerCount}
              onChange={(e) => handleSettingChange('performanceSettings', 'workerCount', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="1"
              max="8"
            />
            <p className="text-xs text-gray-500 mt-1">권장: CPU 코어 수와 동일</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              메모리 제한 (MB)
            </label>
            <input
              type="number"
              value={settings.performanceSettings.memoryLimit}
              onChange={(e) => handleSettingChange('performanceSettings', 'memoryLimit', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="512"
              max="8192"
              step="256"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              캐시 크기 (항목 수)
            </label>
            <input
              type="number"
              value={settings.performanceSettings.cacheSize}
              onChange={(e) => handleSettingChange('performanceSettings', 'cacheSize', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="100"
              max="10000"
              step="100"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              로그 레벨
            </label>
            <select
              value={settings.performanceSettings.logLevel}
              onChange={(e) => handleSettingChange('performanceSettings', 'logLevel', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>
        </div>
      </SettingCard>
    </div>
  );

  const SecuritySettings: React.FC = () => (
    <div className="space-y-6">
      <SettingCard
        title="보안 설정"
        description="시스템 보안과 인증 관련 설정을 관리합니다"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              토큰 갱신 주기 (초)
            </label>
            <input
              type="number"
              value={settings.securitySettings.tokenRefreshInterval}
              onChange={(e) => handleSettingChange('securitySettings', 'tokenRefreshInterval', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="300"
              max="7200"
              step="300"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              세션 만료 시간 (초)
            </label>
            <input
              type="number"
              value={settings.securitySettings.sessionTimeout}
              onChange={(e) => handleSettingChange('securitySettings', 'sessionTimeout', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              min="1800"
              max="28800"
              step="300"
            />
          </div>
          
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.securitySettings.enableEncryption}
                onChange={(e) => handleSettingChange('securitySettings', 'enableEncryption', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm font-medium">데이터 암호화 활성화</span>
            </label>
          </div>
        </div>
      </SettingCard>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'api':
        return <ApiSettings />;
      case 'alerts':
        return <AlertSettings />;
      case 'backtest':
        return <BacktestSettings />;
      case 'performance':
        return <PerformanceSettings />;
      case 'security':
        return <SecuritySettings />;
      default:
        return <ApiSettings />;
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">오류: {error}</div>;

  return (
    <div className="space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">시스템 설정</h1>
          <p className="text-gray-600">한투 퀀트 시스템의 설정을 관리합니다</p>
        </div>
        <div className="flex items-center space-x-4">
          {saveStatus === 'success' && (
            <div className="flex items-center space-x-2 text-green-600">
              <CheckCircle className="h-4 w-4" />
              <span className="text-sm">저장 완료</span>
            </div>
          )}
          {saveStatus === 'error' && (
            <div className="flex items-center space-x-2 text-red-600">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm">저장 실패</span>
            </div>
          )}
          <button
            onClick={handleReset}
            disabled={!isModified}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50"
          >
            <RefreshCw className="h-4 w-4" />
            <span>초기화</span>
          </button>
          <button
            onClick={handleSave}
            disabled={!isModified || isSaving}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? (
              <LoadingSpinner size="sm" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            <span>{isSaving ? '저장 중...' : '저장'}</span>
          </button>
        </div>
      </div>

      {/* 탭 네비게이션 */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* 탭 컨텐츠 */}
      {renderTabContent()}
    </div>
  );
};

export default SettingsPage; 