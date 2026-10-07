from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class BillingConfigurationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    enabled: bool
    environment: Literal['beta','production']
    v2_series: str = Field(pattern=r'^B[A-Z0-9]{3}$')
    v2_invoice_series: str = Field(default='',pattern=r'^(F[A-Z0-9]{3})?$')
    company_name: str = Field(min_length=3,max_length=180)
    trade_name: str = Field(max_length=180)
    ruc: str = Field(pattern=r'^\d{11}$')
    address: str = Field(min_length=3,max_length=250)
    ubigeo: str = Field(pattern=r'^\d{6}$')
    department: str = Field(min_length=2,max_length=100)
    province: str = Field(min_length=2,max_length=100)
    district: str = Field(min_length=2,max_length=100)
    sol_user: str = Field(default='',max_length=100)
    sol_password: str = Field(default='',max_length=200)
    certificate_password: str = Field(default='',max_length=200)
