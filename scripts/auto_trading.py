#!/usr/bin/env python3
"""
자동 매매 실행 스크립트
가상계좌를 사용한 실시간 자동매매
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.trading.trading_engine import get_trading_engine, TradingConfig
from core.utils.log_utils import get_logger, setup_logging

# 로깅 설정
log_filename = f"logs/auto_trading_{datetime.now().strftime('%Y%m%d')}.log"
setup_logging(log_filename, add_sensitive_filter=True)
logger = get_logger(__name__)

class AutoTradingCLI:
    """자동 매매 CLI"""
    
    def __init__(self):
        self.engine = None
        self.is_running = False
        
    async def start(self, config: TradingConfig):
        """자동 매매 시작"""
        try:
            print("="*60)
            print("🚀 한투 퀀트 자동 매매 시스템")
            print("="*60)
            
            # 매매 엔진 초기화
            self.engine = get_trading_engine()
            self.engine.config = config
            
            # 설정 정보 표시
            print("\n📊 매매 설정:")
            print(f"  • 최대 보유 종목: {config.max_positions}개")
            print(f"  • 포지션 방식: {config.position_size_method}")
            if config.position_size_method == "account_pct":
                print(f"  • 계좌 대비 비율: {config.position_size_value:.1%}")
            elif config.position_size_method == "fixed":
                print(f"  • 고정 투자금: {config.fixed_position_size:,.0f}원")
            elif config.position_size_method == "kelly":
                print(f"  • Kelly Criterion (보수계수: {config.kelly_multiplier})")
            print(f"  • 손절매 비율: {config.stop_loss_pct:.1%}")
            print(f"  • 익절매 비율: {config.take_profit_pct:.1%}")
            print(f"  • 일일 최대 거래: {config.max_trades_per_day}건")
            print(f"  • 매매 시간: {config.market_start} ~ {config.market_end}")
            
            # 최종 확인
            print("\n⚠️  주의사항:")
            print("  • 가상계좌를 사용하여 실제 매매가 실행됩니다")
            print("  • 손실 위험이 있으니 주의하시기 바랍니다")
            print("  • Ctrl+C로 언제든지 중지할 수 있습니다")
            
            response = input("\n자동 매매를 시작하시겠습니까? (yes/no): ").strip().lower()
            
            if response not in ['yes', 'y']:
                print("자동 매매가 취소되었습니다.")
                return False
                
            print("\n🚀 자동 매매를 시작합니다...")
            print(f"📝 로그 파일: {log_filename}")
            
            # 시그널 핸들러 등록
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            self.is_running = True
            
            # 자동 매매 실행
            success = await self.engine.start_trading()
            
            if success:
                print("✅ 자동 매매가 정상적으로 완료되었습니다.")
                return True
            else:
                print("❌ 자동 매매 실행 중 오류가 발생했습니다.")
                return False
                
        except KeyboardInterrupt:
            print("\n\n⚠️ 사용자가 중지를 요청했습니다...")
            await self._stop_trading("사용자 중지 요청")
            return False
        except Exception as e:
            logger.error(f"자동 매매 실행 실패: {e}")
            print(f"❌ 오류가 발생했습니다: {e}")
            return False
            
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        print(f"\n\n📡 종료 신호 받음 (Signal: {signum})")
        if self.is_running:
            self.is_running = False
            asyncio.create_task(self._stop_trading("시스템 종료 신호"))
            
    async def _stop_trading(self, reason: str):
        """매매 중지"""
        if self.engine and self.is_running:
            print(f"⏹️ 자동 매매를 중지합니다... ({reason})")
            await self.engine.stop_trading(reason)
            self.is_running = False
            
    async def status(self):
        """매매 상태 조회"""
        try:
            engine = get_trading_engine()
            status = engine.get_status()
            
            print("="*60)
            print("📊 자동 매매 상태")
            print("="*60)
            
            print(f"실행 상태: {'🟢 실행 중' if status['is_running'] else '🔴 중지됨'}")
            
            if status['start_time']:
                start_time = datetime.fromisoformat(status['start_time'])
                print(f"시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                if status['is_running']:
                    runtime = datetime.now() - start_time
                    print(f"실행 시간: {str(runtime).split('.')[0]}")
                    
            print(f"보유 포지션: {status['positions_count']}개")
            print(f"오늘 거래 횟수: {status['daily_trades']}건")
            
            # 포지션 상세
            if status['positions']:
                print("\n📋 보유 포지션:")
                print(f"{'종목명':<15} {'수량':<8} {'평가손익':<12} {'수익률':<10}")
                print("-" * 50)
                
                for code, pos in status['positions'].items():
                    pnl = pos['unrealized_pnl']
                    ret = pos['unrealized_return'] * 100
                    
                    print(f"{pos['stock_name']:<15} {pos['quantity']:<8,} "
                          f"{pnl:>+10,.0f}원 {ret:>+6.1f}%")
                          
            # 설정 정보
            config = status['config']
            print("\n⚙️ 매매 설정:")
            print(f"  최대 포지션: {config['max_positions']}개")
            print(f"  포지션 크기: {config['position_size']:,.0f}원")
            print(f"  손절매: {config['stop_loss_pct']:.1%}")
            print(f"  익절매: {config['take_profit_pct']:.1%}")
            
        except Exception as e:
            print(f"❌ 상태 조회 실패: {e}")
            
    async def stop(self):
        """매매 강제 중지"""
        try:
            engine = get_trading_engine()
            
            if not engine.is_running:
                print("매매가 실행 중이 아닙니다.")
                return
                
            print("자동 매매를 중지합니다...")
            success = await engine.stop_trading("수동 중지")
            
            if success:
                print("✅ 자동 매매가 중지되었습니다.")
            else:
                print("❌ 매매 중지 중 오류가 발생했습니다.")
                
        except Exception as e:
            print(f"❌ 매매 중지 실패: {e}")

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="한투 퀀트 자동 매매 시스템")
    parser.add_argument("command", choices=["start", "stop", "status"], 
                       help="실행할 명령")
    parser.add_argument("--max-positions", type=int, default=10,
                       help="최대 보유 종목수 (기본값: 10)")
    parser.add_argument("--position-method", choices=["fixed", "account_pct", "risk_based", "kelly"], 
                       default="account_pct", help="포지션 크기 결정 방법 (기본값: account_pct)")
    parser.add_argument("--position-pct", type=float, default=0.10,
                       help="계좌 대비 투자 비율 (기본값: 0.10 = 10%%)")
    parser.add_argument("--position-size", type=float, default=1000000,
                       help="고정 투자금액 (fixed 모드용, 기본값: 1,000,000원)")
    parser.add_argument("--stop-loss", type=float, default=0.05,
                       help="손절매 비율 (기본값: 0.05 = 5%%)")
    parser.add_argument("--take-profit", type=float, default=0.10,
                       help="익절매 비율 (기본값: 0.10 = 10%%)")
    parser.add_argument("--max-trades", type=int, default=20,
                       help="일일 최대 거래횟수 (기본값: 20)")
    parser.add_argument("--use-kelly", action="store_true", default=True,
                       help="Kelly Criterion 사용 (기본값: True)")
    parser.add_argument("--kelly-multiplier", type=float, default=0.25,
                       help="Kelly Criterion 보수 계수 (기본값: 0.25)")
    
    args = parser.parse_args()
    
    # 매매 설정
    config = TradingConfig(
        max_positions=args.max_positions,
        position_size_method=args.position_method,
        position_size_value=args.position_pct,
        fixed_position_size=args.position_size,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        max_trades_per_day=args.max_trades,
        use_kelly_criterion=args.use_kelly,
        kelly_multiplier=args.kelly_multiplier
    )
    
    cli = AutoTradingCLI()
    
    try:
        if args.command == "start":
            await cli.start(config)
        elif args.command == "stop":
            await cli.stop()
        elif args.command == "status":
            await cli.status()
    except KeyboardInterrupt:
        print("\n프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Windows에서 asyncio 이벤트 루프 정책 설정
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())