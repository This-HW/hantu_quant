---
name: add-project
description: 새 프로젝트를 동기화 대상에 추가합니다.
domain: claude_setting
model: sonnet
allowed-tools: Write, Bash, Read, AskUserQuestion
---

# 새 프로젝트 추가

새 프로젝트를 Claude Code 설정 동기화 대상에 추가합니다.

## 입력 정보

사용자에게 다음 정보를 확인하세요:

1. **프로젝트 이름** (예: my_project)
2. **프로젝트 경로** (예: /Users/grimm/Documents/Dev/my_project)
3. **프로젝트 타입** (예: web, api, optimization, algorithmic-trading)
4. **프로젝트 설명** (한 줄)

## 실행 단계

### 1. 프로젝트 디렉토리 확인

```bash
ls -la <프로젝트_경로>
```

프로젝트 디렉토리가 존재하는지 확인합니다.

### 2. YAML 설정 파일 생성

`projects/<프로젝트_이름>.yaml` 파일을 생성합니다:

```yaml
# <프로젝트_이름> 프로젝트 설정
# 에이전트 동기화 및 배포 설정

# 프로젝트 정보
project:
  name: <프로젝트_이름>
  path: <프로젝트_경로>
  type: <프로젝트_타입>
  description: "<프로젝트_설명>"

# Tier 1: 공통 에이전트
common:
  enabled: true
  # 자동으로 모든 공통 에이전트 포함

# Tier 2: 도메인 에이전트
domains: []
  # 향후 필요시 추가:
  # - name: <도메인명>
  #   version: "1.0.0"
  #   agents: all

# Tier 3: 커스텀 에이전트
custom:
  enabled: false
  # 향후 필요시 project-agents/<프로젝트_이름>/ 생성

# 동기화 옵션
sync:
  auto_update: true
  backup_before_sync: true
  auto_commit: true
  auto_push: false

# 배포 대상
deployment:
  target_dirs:
    - .claude/agents/
  exclude_patterns:
    - "*.pyc"
    - "__pycache__"
    - ".DS_Store"

# 메타데이터
metadata:
  created_at: "<오늘_날짜>"
  last_updated: "<오늘_날짜>"
  version: "1.0.0"
  maintainer: "Claude Opus 4.5"
  notes: |
    - 공통 에이전트만 사용
    - 도메인/커스텀 에이전트 미사용
```

### 3. 초기 동기화 실행

```bash
./scripts/sync-domain.sh <프로젝트_이름>
```

### 4. 결과 확인

```bash
ls -la <프로젝트_경로>/.claude/
```

## 체크리스트

- [ ] 프로젝트 디렉토리 존재 확인
- [ ] `projects/<프로젝트_이름>.yaml` 생성
- [ ] `sync-domain.sh` 실행
- [ ] `.claude/` 디렉토리 생성 확인

## 도메인/커스텀 에이전트 추가 시

### 도메인 에이전트 추가

1. `domain-agents/<도메인명>/` 디렉토리에 에이전트가 있는지 확인
2. yaml 파일의 `domains` 섹션 수정:

```yaml
domains:
  - name: <도메인명>
    version: "1.0.0"
    agents: all # 또는 개별 에이전트 리스트
```

### 커스텀 에이전트 추가

1. `project-agents/<프로젝트_이름>/` 디렉토리 생성
2. 에이전트 파일 추가 (`.md`)
3. yaml 파일의 `custom` 섹션 수정:

```yaml
custom:
  enabled: true
  agents: all # 또는 개별 에이전트 리스트
```

## 현재 등록된 프로젝트

```bash
ls -1 projects/*.yaml | xargs -n 1 basename | sed 's/.yaml$//'
```

## 주의사항

- 프로젝트 경로는 절대 경로로 지정
- 프로젝트 이름은 디렉토리명과 일치 권장
- 동기화 전 프로젝트 디렉토리가 존재해야 함
