#!/usr/bin/env python3
"""
PreToolUse Hook: 민감한 파일 보호

Edit 또는 Write 도구가 민감한 파일에 접근하려 할 때 차단합니다.

차단되는 파일:
- .env* (환경 변수)
- **/secrets/** (시크릿 디렉토리)
- **/*credential* (인증 정보)
- **/*secret* (시크릿)
- ~/.ssh/** (SSH 키)
- ~/.aws/** (AWS 인증)

사용법:
  settings.json에서 PreToolUse hook으로 등록

종료 코드:
  0: 허용
  2: 차단 (Claude에게 피드백)
"""

import json
import sys
import os
import re

# 공통 유틸리티 import (스크립트 위치 기반 동적 경로)
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, is_debug_mode
except ImportError:
    def debug_log(msg, error=None): pass
    def is_debug_mode(): return False


# 보호할 패턴 (정규식)
PROTECTED_PATTERNS = [
    # 환경 변수
    r'\.env($|\.)',           # .env, .env.local, .env.production 등

    # 시크릿/인증 디렉토리
    r'/secrets/',              # secrets 디렉토리
    r'credential',             # credential 포함 파일
    r'secret[^s]',            # secret 포함 (secrets 제외)

    # SSH
    r'\.ssh/',                 # SSH 키 디렉토리
    r'id_rsa',                 # SSH 개인키
    r'id_ed25519',            # SSH 개인키
    r'id_ecdsa',              # SSH 개인키
    r'known_hosts',           # SSH known hosts

    # 클라우드 설정
    r'\.aws/',                 # AWS 설정
    r'\.gcp/',                 # GCP 설정
    r'\.azure/',               # Azure 설정
    r'\.kube/config',         # Kubernetes config
    r'\.docker/config\.json', # Docker credentials

    # 패키지 관리자 토큰
    r'\.npmrc$',              # npm 토큰
    r'\.yarnrc$',             # yarn 설정
    r'\.pypirc$',             # PyPI 토큰
    r'\.netrc$',              # netrc 파일

    # 키 파일
    r'\.pem$',                 # 인증서/키 파일
    r'\.key$',                 # 키 파일
    r'\.p12$',                 # PKCS#12 파일
    r'\.pfx$',                 # PFX 파일
    r'private.*key',          # 개인 키
    r'.*_rsa$',               # RSA 키
    r'.*_ecdsa$',             # ECDSA 키

    # 기타 민감 파일
    r'token',                  # 토큰 파일
    r'password',              # 패스워드 파일
    r'\.htpasswd$',           # Apache htpasswd
]

# 차단 메시지
BLOCK_MESSAGES = {
    'env': '환경 변수 파일은 직접 수정할 수 없습니다. 수동으로 설정하세요.',
    'secrets': '시크릿 파일/디렉토리는 보호됩니다.',
    'credential': '인증 정보 파일은 보호됩니다.',
    'ssh': 'SSH 키는 보호됩니다.',
    'key': '개인 키 파일은 보호됩니다.',
    'cloud': '클라우드 설정 파일은 보호됩니다.',
    'token': '토큰/패스워드 파일은 보호됩니다.',
    'package': '패키지 관리자 인증 파일은 보호됩니다.',
}


def check_protected(file_path: str) -> tuple[bool, str]:
    """파일이 보호 대상인지 확인"""
    path_lower = file_path.lower()

    for pattern in PROTECTED_PATTERNS:
        if re.search(pattern, path_lower):
            debug_log(f"Pattern matched: {pattern} for {file_path}")

            # 어떤 유형인지 파악
            if '.env' in path_lower:
                return True, BLOCK_MESSAGES['env']
            elif 'secret' in path_lower:
                return True, BLOCK_MESSAGES['secrets']
            elif 'credential' in path_lower:
                return True, BLOCK_MESSAGES['credential']
            elif '.ssh' in path_lower or 'id_rsa' in path_lower or 'id_ed25519' in path_lower:
                return True, BLOCK_MESSAGES['ssh']
            elif any(k in path_lower for k in ['.kube', '.docker', '.aws', '.gcp', '.azure']):
                return True, BLOCK_MESSAGES['cloud']
            elif any(k in path_lower for k in ['.npmrc', '.yarnrc', '.pypirc', '.netrc']):
                return True, BLOCK_MESSAGES['package']
            elif any(k in path_lower for k in ['token', 'password']):
                return True, BLOCK_MESSAGES['token']
            elif any(k in path_lower for k in ['.pem', '.key', '.p12', '.pfx', 'private', '_rsa', '_ecdsa']):
                return True, BLOCK_MESSAGES['key']
            else:
                return True, '이 파일은 보안상 보호됩니다.'

    return False, ''


def main():
    try:
        # stdin에서 JSON 입력 읽기
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        # Edit, Write, Read 도구인 경우만 검사
        if tool_name not in ('Edit', 'Write', 'Read'):
            sys.exit(0)

        file_path = tool_input.get('file_path', '')
        if not file_path:
            sys.exit(0)

        # 보호 대상 확인
        is_protected, message = check_protected(file_path)

        if is_protected:
            # 차단 메시지 출력
            print(f"🔒 차단됨: {file_path}", file=sys.stderr)
            print(f"   {message}", file=sys.stderr)
            sys.exit(2)  # 2 = 차단

        sys.exit(0)  # 0 = 허용

    except json.JSONDecodeError:
        debug_log("JSON decode error in stdin")
        sys.exit(0)
    except Exception as e:
        debug_log(f"Hook error: {e}", e)
        sys.exit(0)


if __name__ == '__main__':
    main()
