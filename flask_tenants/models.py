

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BaseTenant(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)  # Ensure unique constraint
    name = Column(String(128), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.current_timestamp(),
                           onupdate=func.current_timestamp())


class BaseDomain(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_name = Column(String(128), ForeignKey('tenants.name'), nullable=False)
    domain_name = Column(String(255), unique=True, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)


class BaseTenantModel(Base):
    __abstract__ = True
    __table_args__ = ({'schema': 'tenant'})
