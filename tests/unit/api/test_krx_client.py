"""
KRXClient 단위 테스트
"""

import pytest
from core.api.krx_client import KRXClient


class TestKRXClientSector:
    """KRXClient 섹터 조회 기능 테스트"""

    def test_get_sector_by_code_success(self):
        """섹터 조회 성공 케이스"""
        krx = KRXClient()

        # 대표 종목 테스트 (DB 또는 하드코딩 매핑에 있음)
        sector = krx.get_sector_by_code("005930")  # 삼성전자
        assert sector is not None, "삼성전자 섹터가 None이면 안됨"
        assert sector in ["반도체", "전자/전기"], f"Expected semiconductor sector, got {sector}"

    def test_get_sector_by_code_hynix(self):
        """SK하이닉스 섹터 조회"""
        krx = KRXClient()

        # sector_map에 있는 종목
        sector = krx.get_sector_by_code("000660")  # SK하이닉스
        assert sector is not None, "SK하이닉스 섹터가 None이면 안됨"
        assert sector == "반도체", f"Expected 반도체, got {sector}"

    def test_get_sector_by_code_fallback(self):
        """하드코딩 매핑에 없는 종목 (폴백)"""
        krx = KRXClient()

        # 하드코딩에 없는 종목은 DB에서 조회 시도 후 "기타" 폴백
        sector = krx.get_sector_by_code("999999")  # 존재하지 않는 종목
        assert sector in [None, "기타"], f"Expected None or 기타, got {sector}"

    def test_get_sector_by_code_bank(self):
        """금융(은행) 섹터 조회"""
        krx = KRXClient()

        sector = krx.get_sector_by_code("105560")  # KB금융
        assert sector is not None
        assert sector == "은행", f"Expected 은행, got {sector}"

    def test_get_sector_by_code_internet(self):
        """인터넷/플랫폼 섹터 조회"""
        krx = KRXClient()

        sector = krx.get_sector_by_code("035720")  # 카카오
        assert sector is not None
        assert sector == "인터넷/플랫폼", f"Expected 인터넷/플랫폼, got {sector}"

    def test_get_sector_by_code_invalid(self):
        """잘못된 종목 코드 입력"""
        krx = KRXClient()

        # 빈 문자열
        sector = krx.get_sector_by_code("")
        assert sector in [None, "기타"]

        # 잘못된 형식
        sector = krx.get_sector_by_code("INVALID")
        assert sector in [None, "기타"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
