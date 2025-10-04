# 트레이딩 전략 개발 워크플로우

## 작업 전 준비
1. 환경 설정 확인
   ```
   python scripts/manage.py setup
   ```

2. 필요한 데이터 준비
   ```
   python scripts/collect_data.py --stock-codes 005930,000660 --period 1y
   ```

## 참조할 파일
- hantu_backtest/strategies/base.py
- hantu_backtest/strategies/momentum.py (참고용)
- hantu_common/indicators/base.py
- hantu_common/indicators/볼린저.py (신규 지표 개발 시)

## 작업 단계
1. 전략 설계
   - 트레이딩 로직 정의
   - 진입/퇴출 조건 설정
   - 필요한 기술 지표 선정

2. 필요한 기술 지표 구현
   - hantu_common/indicators/ 디렉토리에 신규 지표 추가
   - 기존 지표 활용 또는 확장

3. 전략 클래스 구현
   - BacktestStrategy 상속
   - find_candidates 메서드 구현
   - generate_signals 메서드 구현
   - 파라미터 최적화 고려

4. 백테스트 실행
   ```
   python -m hantu_backtest.main --strategy 전략명 --period 1y
   ```

5. 성능 분석
   - 샤프 비율, MDD 등 지표 확인
   - 매매 패턴 분석
   - 파라미터 조정

## 주의사항
- 과적합 방지를 위한 적절한 테스트 기간 설정
- 거래 비용 및 슬리피지 고려
- 실제 환경과 백테스트 환경의 차이 인식 