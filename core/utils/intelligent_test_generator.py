"""
지능형 테스트 생성 시스템

코드 분석을 통해 자동으로 테스트 케이스를 생성하고,
edge case를 감지하며, 코드 커버리지를 최적화하는 AI 시스템
"""

import ast
import os
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from ..utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class FunctionSignature:
    """함수 시그니처 정보"""
    name: str
    args: List[str]
    defaults: Dict[str, Any]
    return_type: Optional[str]
    docstring: Optional[str]
    decorators: List[str]
    complexity: int  # 순환복잡도

@dataclass
class EdgeCase:
    """엣지 케이스 정보"""
    case_type: str  # 'null', 'empty', 'boundary', 'exception'
    description: str
    test_inputs: Dict[str, Any]
    expected_behavior: str
    confidence: float

@dataclass
class TestCase:
    """생성된 테스트 케이스"""
    name: str
    function_name: str
    test_type: str  # 'unit', 'integration', 'edge_case'
    setup_code: str
    test_code: str
    assertions: List[str]
    description: str
    edge_cases: List[EdgeCase]
    estimated_coverage: float

class CodeAnalyzer:
    """코드 분석기"""
    
    def __init__(self):
        self._logger = logger
    
    def analyze_file(self, file_path: str) -> Dict[str, FunctionSignature]:
        """파일의 모든 함수 분석"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            functions = {}
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    sig = self._analyze_function(node, source)
                    functions[sig.name] = sig
            
            self._logger.info(f"파일 분석 완료: {file_path}, 함수 {len(functions)}개 발견")
            return functions
            
        except Exception as e:
            self._logger.error(f"파일 분석 실패 {file_path}: {e}", exc_info=True)
            return {}
    
    def _analyze_function(self, node: ast.FunctionDef, source: str) -> FunctionSignature:
        """단일 함수 분석"""
        # 함수 인자 추출
        args = [arg.arg for arg in node.args.args]
        
        # 기본값 추출
        defaults = {}
        if node.args.defaults:
            default_offset = len(args) - len(node.args.defaults)
            for i, default in enumerate(node.args.defaults):
                arg_name = args[default_offset + i]
                defaults[arg_name] = ast.unparse(default)
        
        # 반환 타입 추출
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)
        
        # 독스트링 추출
        docstring = None
        if (node.body and 
            isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant)):
            docstring = node.body[0].value.value
        
        # 데코레이터 추출
        decorators = [ast.unparse(d) for d in node.decorator_list]
        
        # 순환복잡도 계산
        complexity = self._calculate_complexity(node)
        
        return FunctionSignature(
            name=node.name,
            args=args,
            defaults=defaults,
            return_type=return_type,
            docstring=docstring,
            decorators=decorators,
            complexity=complexity
        )
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """순환복잡도 계산 (McCabe complexity)"""
        complexity = 1  # 기본 경로
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.With)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and, or 연산자마다 +1
                complexity += len(child.values) - 1
        
        return complexity

class EdgeCaseDetector:
    """엣지 케이스 감지기"""
    
    def __init__(self):
        self._logger = logger
        
        # 일반적인 엣지 케이스 패턴
        self._edge_patterns = {
            'null_check': [r'if\s+.*\s+is\s+None', r'if\s+not\s+\w+'],
            'empty_check': [r'if\s+len\(.*\)', r'if\s+.*\.empty'],
            'type_check': [r'isinstance\(', r'type\(.*\)'],
            'range_check': [r'if\s+.*[<>]=?', r'range\(.*\)'],
            'exception_handling': [r'try:', r'except\s+\w+', r'raise\s+\w+']
        }
    
    def detect_edge_cases(self, function_sig: FunctionSignature, source_code: str) -> List[EdgeCase]:
        """함수의 엣지 케이스 감지"""
        edge_cases = []
        
        # 1. 파라미터 기반 엣지 케이스
        edge_cases.extend(self._detect_parameter_edges(function_sig))
        
        # 2. 코드 패턴 기반 엣지 케이스
        edge_cases.extend(self._detect_pattern_edges(function_sig, source_code))
        
        # 3. 타입 기반 엣지 케이스
        edge_cases.extend(self._detect_type_edges(function_sig))
        
        self._logger.debug(f"함수 {function_sig.name}에서 {len(edge_cases)}개 엣지 케이스 감지")
        return edge_cases
    
    def _detect_parameter_edges(self, function_sig: FunctionSignature) -> List[EdgeCase]:
        """파라미터 기반 엣지 케이스 감지"""
        edges = []
        
        for arg in function_sig.args:
            # None 값 테스트
            edges.append(EdgeCase(
                case_type="null",
                description=f"{arg} 파라미터가 None인 경우",
                test_inputs={arg: None},
                expected_behavior="None 처리 또는 예외 발생",
                confidence=0.8
            ))
            
            # 빈 값 테스트 (문자열/리스트/딕셔너리로 추정되는 경우)
            if any(keyword in arg.lower() for keyword in ['list', 'dict', 'str', 'data']):
                edges.append(EdgeCase(
                    case_type="empty",
                    description=f"{arg} 파라미터가 빈 값인 경우",
                    test_inputs={arg: []},  # 또는 {}, ""
                    expected_behavior="빈 값 처리 또는 기본값 반환",
                    confidence=0.7
                ))
        
        return edges
    
    def _detect_pattern_edges(self, function_sig: FunctionSignature, source_code: str) -> List[EdgeCase]:
        """코드 패턴 기반 엣지 케이스 감지"""
        edges = []
        
        for pattern_type, patterns in self._edge_patterns.items():
            for pattern in patterns:
                if re.search(pattern, source_code):
                    edges.append(EdgeCase(
                        case_type=pattern_type,
                        description=f"{pattern_type} 패턴 감지됨",
                        test_inputs={},
                        expected_behavior=f"{pattern_type} 상황 처리",
                        confidence=0.6
                    ))
                    break  # 같은 타입은 한 번만 추가
        
        return edges
    
    def _detect_type_edges(self, function_sig: FunctionSignature) -> List[EdgeCase]:
        """타입 기반 엣지 케이스 감지"""
        edges = []
        
        # 숫자 파라미터의 경우 경계값 테스트
        for arg in function_sig.args:
            if any(keyword in arg.lower() for keyword in ['count', 'size', 'length', 'num', 'index']):
                edges.append(EdgeCase(
                    case_type="boundary",
                    description=f"{arg} 경계값 테스트 (0, 음수, 매우 큰 수)",
                    test_inputs={arg: 0},
                    expected_behavior="경계값 적절한 처리",
                    confidence=0.9
                ))
        
        return edges

class TestCodeGenerator:
    """테스트 코드 생성기"""
    
    def __init__(self):
        self._logger = logger
    
    def generate_test_class(self, module_name: str, functions: Dict[str, FunctionSignature], 
                          edge_cases: Dict[str, List[EdgeCase]]) -> str:
        """전체 테스트 클래스 생성"""
        
        class_name = f"Test{module_name.replace('_', '').title()}"
        
        test_code = [
            '"""',
            f'{module_name} 모듈 자동 생성 테스트',
            '',
            '이 테스트는 지능형 테스트 생성 시스템에 의해 자동으로 생성되었습니다.',
            '"""',
            '',
            'import pytest',
            'import os',
            'import sys',
            'from unittest.mock import Mock, patch',
            'from datetime import datetime',
            'import pandas as pd',
            'import numpy as np',
            '',
            '# 프로젝트 경로 추가',
            "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))",
            '',
            f'from {module_name} import *',
            '',
            '',
            f'class {class_name}:',
            f'    """{{module_name}} 모듈 테스트 클래스"""',
            '',
            '    def setup_method(self):',
            '        """테스트 설정"""',
            '        pass',
            '',
            '    def teardown_method(self):',
            '        """테스트 정리"""',
            '        pass',
            ''
        ]
        
        # 각 함수별 테스트 메서드 생성
        for func_name, func_sig in functions.items():
            if not func_name.startswith('_'):  # private 함수 제외
                test_methods = self._generate_function_tests(func_name, func_sig, 
                                                           edge_cases.get(func_name, []))
                test_code.extend(test_methods)
                test_code.append('')
        
        return '\n'.join(test_code)
    
    def _generate_function_tests(self, func_name: str, func_sig: FunctionSignature, 
                               edges: List[EdgeCase]) -> List[str]:
        """단일 함수의 테스트 메서드들 생성"""
        test_methods = []
        
        # 1. 기본 기능 테스트
        basic_test = self._generate_basic_test(func_name, func_sig)
        test_methods.extend(basic_test)
        
        # 2. 엣지 케이스 테스트들
        for edge in edges:
            edge_test = self._generate_edge_case_test(func_name, func_sig, edge)
            test_methods.extend(edge_test)
        
        # 3. 복잡도가 높은 함수는 추가 테스트
        if func_sig.complexity > 5:
            complex_test = self._generate_complexity_test(func_name, func_sig)
            test_methods.extend(complex_test)
        
        return test_methods
    
    def _generate_basic_test(self, func_name: str, func_sig: FunctionSignature) -> List[str]:
        """기본 기능 테스트 생성"""
        test_name = f"test_{func_name}_basic_functionality"
        
        # 기본 테스트 인자 생성
        test_args = self._generate_test_arguments(func_sig)
        args_str = ', '.join([f"{k}={v}" for k, v in test_args.items()])
        
        test_code = [
            f'    def {test_name}(self):',
            f'        """{{func_name}} 기본 기능 테스트"""',
            f'        # 기본 호출 테스트',
            f'        result = {func_name}({args_str})',
            f'        ',
            f'        # 기본 검증',
            f'        assert result is not None',
        ]
        
        # 반환 타입이 있는 경우 타입 검증 추가
        if func_sig.return_type:
            if 'bool' in func_sig.return_type.lower():
                test_code.append('        assert isinstance(result, bool)')
            elif 'int' in func_sig.return_type.lower():
                test_code.append('        assert isinstance(result, int)')
            elif 'str' in func_sig.return_type.lower():
                test_code.append('        assert isinstance(result, str)')
            elif 'list' in func_sig.return_type.lower():
                test_code.append('        assert isinstance(result, list)')
            elif 'dict' in func_sig.return_type.lower():
                test_code.append('        assert isinstance(result, dict)')
        
        return test_code
    
    def _generate_edge_case_test(self, func_name: str, func_sig: FunctionSignature, 
                                edge: EdgeCase) -> List[str]:
        """엣지 케이스 테스트 생성"""
        test_name = f"test_{func_name}_{edge.case_type}_edge_case"
        
        test_code = [
            f'    def {test_name}(self):',
            f'        """{{func_name}} {edge.description} 테스트"""',
        ]
        
        if edge.case_type == "null":
            test_code.extend([
                f'        # None 값 테스트',
                f'        with pytest.raises(Exception):',
                f'            {func_name}(None)',
                f'        # 또는 None 처리 확인',
                f'        # result = {func_name}(None)',
                f'        # assert result is not None  # 적절한 기본값 반환',
            ])
        
        elif edge.case_type == "empty":
            test_code.extend([
                f'        # 빈 값 테스트',
                f'        result = {func_name}([])',  # 또는 적절한 빈 값
                f'        assert result is not None',
                f'        # 빈 값에 대한 적절한 처리 확인',
            ])
        
        elif edge.case_type == "boundary":
            test_code.extend([
                f'        # 경계값 테스트',
                f'        # 0 값 테스트',
                f'        result_zero = {func_name}(0)',
                f'        assert result_zero is not None',
                f'        ',
                f'        # 음수 값 테스트 (적절한 경우)',
                f'        # with pytest.raises(ValueError):',
                f'        #     {func_name}(-1)',
            ])
        
        elif edge.case_type == "exception_handling":
            test_code.extend([
                f'        # 예외 처리 테스트',
                f'        with pytest.raises(Exception):',
                f'            {func_name}("invalid_input")',
            ])
        
        else:
            test_code.extend([
                f'        # {edge.case_type} 케이스 테스트',
                f'        # TODO: 구체적인 테스트 구현 필요',
                f'        pass',
            ])
        
        return test_code
    
    def _generate_complexity_test(self, func_name: str, func_sig: FunctionSignature) -> List[str]:
        """복잡한 함수를 위한 추가 테스트 생성"""
        test_name = f"test_{func_name}_complex_scenarios"
        
        return [
            f'    def {test_name}(self):',
            f'        """{{func_name}} 복잡한 시나리오 테스트 (복잡도: {func_sig.complexity})"""',
            f'        # 복잡한 함수이므로 다양한 시나리오 테스트 필요',
            f'        # TODO: 구체적인 복잡 시나리오 구현',
            f'        ',
            f'        # 성능 테스트',
            f'        import time',
            f'        start_time = time.time()',
            f'        result = {func_name}()',  # 기본 인자로 호출
            f'        end_time = time.time()',
            f'        ',
            f'        # 성능 검증 (1초 이내 완료)',
            f'        assert end_time - start_time < 1.0',
            f'        assert result is not None',
        ]
    
    def _generate_test_arguments(self, func_sig: FunctionSignature) -> Dict[str, str]:
        """테스트용 인자 생성"""
        test_args = {}
        
        for arg in func_sig.args:
            if arg == 'self':
                continue
                
            # 기본값이 있는 경우 사용
            if arg in func_sig.defaults:
                continue
            
            # 인자 이름 기반 추측
            if 'data' in arg.lower() or 'df' in arg.lower():
                test_args[arg] = 'pd.DataFrame({"test": [1, 2, 3]})'
            elif 'list' in arg.lower() or arg.endswith('s'):
                test_args[arg] = '[1, 2, 3]'
            elif 'dict' in arg.lower():
                test_args[arg] = '{"test": "value"}'
            elif 'str' in arg.lower() or 'name' in arg.lower():
                test_args[arg] = '"test_string"'
            elif 'int' in arg.lower() or 'count' in arg.lower() or 'num' in arg.lower():
                test_args[arg] = '10'
            elif 'float' in arg.lower() or 'rate' in arg.lower():
                test_args[arg] = '0.5'
            elif 'bool' in arg.lower():
                test_args[arg] = 'True'
            else:
                # 기본값
                test_args[arg] = 'None'
        
        return test_args

class IntelligentTestGenerator:
    """지능형 테스트 생성 메인 클래스"""
    
    def __init__(self, output_dir: str = "tests/auto_generated"):
        """
        초기화
        
        Args:
            output_dir: 생성된 테스트 파일을 저장할 디렉토리
        """
        self._logger = logger
        self._output_dir = output_dir
        self._analyzer = CodeAnalyzer()
        self._edge_detector = EdgeCaseDetector()
        self._code_generator = TestCodeGenerator()
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        self._logger.info("지능형 테스트 생성기 초기화 완료")
    
    def generate_tests_for_file(self, file_path: str) -> str:
        """단일 파일에 대한 테스트 생성"""
        self._logger.info(f"테스트 생성 시작: {file_path}")
        
        # 1. 코드 분석
        functions = self._analyzer.analyze_file(file_path)
        if not functions:
            self._logger.warning(f"분석할 함수가 없습니다: {file_path}")
            return ""
        
        # 2. 엣지 케이스 감지
        edge_cases = {}
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        for func_name, func_sig in functions.items():
            edges = self._edge_detector.detect_edge_cases(func_sig, source_code)
            edge_cases[func_name] = edges
        
        # 3. 테스트 코드 생성
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        test_code = self._code_generator.generate_test_class(module_name, functions, edge_cases)
        
        # 4. 테스트 파일 저장
        test_file_path = os.path.join(self._output_dir, f"test_{module_name}_auto.py")
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        self._logger.info(f"테스트 파일 생성 완료: {test_file_path}")
        
        # 5. 요약 리포트 생성
        report = self._generate_test_report(file_path, functions, edge_cases, test_file_path)
        
        return test_file_path
    
    def generate_tests_for_directory(self, directory: str, pattern: str = "*.py") -> List[str]:
        """디렉토리의 모든 Python 파일에 대한 테스트 생성"""
        generated_files = []
        
        for root, dirs, files in os.walk(directory):
            # __pycache__, .git 등 제외
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    file_path = os.path.join(root, file)
                    try:
                        test_file = self.generate_tests_for_file(file_path)
                        if test_file:
                            generated_files.append(test_file)
                    except Exception as e:
                        self._logger.error(f"테스트 생성 실패 {file_path}: {e}", exc_info=True)
        
        self._logger.info(f"디렉토리 테스트 생성 완료: {len(generated_files)}개 파일")
        return generated_files
    
    def _generate_test_report(self, source_file: str, functions: Dict[str, FunctionSignature], 
                            edge_cases: Dict[str, List[EdgeCase]], test_file: str) -> str:
        """테스트 생성 리포트 작성"""
        report = [
            "# 자동 테스트 생성 리포트",
            "",
            f"**소스 파일**: `{source_file}`",
            f"**테스트 파일**: `{test_file}`",
            f"**생성 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📊 분석 결과",
            f"- **총 함수 수**: {len(functions)}개",
            f"- **평균 복잡도**: {sum(f.complexity for f in functions.values()) / len(functions):.1f}",
            f"- **총 엣지 케이스**: {sum(len(edges) for edges in edge_cases.values())}개",
            "",
            "## 🔍 함수별 상세",
        ]
        
        for func_name, func_sig in functions.items():
            edges = edge_cases.get(func_name, [])
            report.extend([
                f"### `{func_name}`",
                f"- **인자**: {len(func_sig.args)}개",
                f"- **복잡도**: {func_sig.complexity}",
                f"- **엣지 케이스**: {len(edges)}개",
                f"- **반환 타입**: {func_sig.return_type or '미지정'}",
                ""
            ])
        
        # 리포트 파일 저장
        report_file = test_file.replace('.py', '_report.md')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        return '\n'.join(report)
    
    def analyze_test_coverage(self, source_dir: str) -> Dict[str, float]:
        """테스트 커버리지 분석 (예상치)"""
        coverage = {}
        
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    functions = self._analyzer.analyze_file(file_path)
                    
                    if functions:
                        # 간단한 커버리지 예상 (실제로는 더 정교한 분석 필요)
                        total_complexity = sum(f.complexity for f in functions.values())
                        estimated_coverage = min(0.95, 0.6 + (len(functions) * 0.05))
                        coverage[file_path] = estimated_coverage
        
        return coverage
    
    def get_generation_summary(self) -> Dict[str, Any]:
        """테스트 생성 요약 정보"""
        summary = {
            'output_directory': self._output_dir,
            'generated_files': [],
            'total_functions_analyzed': 0,
            'total_edge_cases_detected': 0,
            'estimated_coverage': 0.0
        }
        
        # 생성된 파일들 스캔
        if os.path.exists(self._output_dir):
            for file in os.listdir(self._output_dir):
                if file.startswith('test_') and file.endswith('_auto.py'):
                    summary['generated_files'].append(file)
        
        return summary

# 전역 인스턴스
_test_generator = None

def get_test_generator() -> IntelligentTestGenerator:
    """테스트 생성기 싱글톤 인스턴스 반환"""
    global _test_generator
    if _test_generator is None:
        _test_generator = IntelligentTestGenerator()
    return _test_generator 