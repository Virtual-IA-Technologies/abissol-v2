from sqlalchemy import Boolean, Column, Index, String

from ..database import Base


class Ubigeo(Base):
    __tablename__ = "ubigeos"
    __table_args__ = (
        Index("ix_ubigeos_department", "department_code", "department"),
        Index("ix_ubigeos_province", "province_code", "province"),
    )

    code = Column(String(6), primary_key=True)
    department_code = Column(String(2), nullable=False)
    department = Column(String(80), nullable=False)
    province_code = Column(String(4), nullable=False)
    province = Column(String(80), nullable=False)
    district = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
