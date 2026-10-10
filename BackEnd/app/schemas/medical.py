from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator, field_validator

Money = Annotated[Decimal, Field(ge=0, le=99999999, max_digits=12, decimal_places=2)]
Name = Annotated[str, Field(min_length=2, max_length=180)]

class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class PlanInput(Payload):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    prefix: str = Field(min_length=1, max_length=15, pattern=r"^[A-Z0-9-]+$")
    price: Money
    provider_cost: Money
    seller_commission: Money
    platform_fee: Money = Decimal(0)
    meta_percent: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)] = Decimal(10)
    validity_days: int = Field(default=365, ge=1, le=3660)
    conditions_url: str = Field(default="", max_length=500, pattern=r"^(https://[^\s]+)?$")
    active: bool = True
    @model_validator(mode="after")
    def costs(self):
        if self.provider_cost + self.seller_commission + self.platform_fee > self.price:
            raise ValueError("Los costos y comisiones no pueden superar el precio")
        return self

class SourceInput(Payload):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    kind: Literal["internal", "afocat", "partner"] = "internal"
    external_key: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9_-]+$")
    active: bool = True

class ProfileInput(Payload):
    user_id: int | None = Field(default=None, gt=0)
    display_name: str = Field(default="", max_length=180)
    external_user_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    source_id: int = Field(gt=0)
    manager_id: int | None = None
    kind: Literal["source_admin", "responsible", "emitter"]
    active: bool = True
    apply_role: bool = False

class BillingPreference(Payload):
    invoice_type_code: Literal["01","03"] = "03"
    customer_document_type: Literal["RUC","DNI","CE","PASSPORT"] | None = None
    customer_document_number: str = Field(default="",max_length=20,pattern=r"^[A-Za-z0-9]*$")
    customer_name: str = Field(default="",max_length=180)
    customer_address: str = Field(default="",max_length=250)
    customer_ubigeo: str = Field(default="",pattern=r"^(\d{6})?$")
    due_date: date | None = None

    @field_validator('customer_name', 'customer_address', mode='before')
    @classmethod
    def uppercase(cls, value):
        return value.upper() if isinstance(value,str) else value

    @model_validator(mode="after")
    def receiver(self):
        if self.invoice_type_code=="01" and (self.customer_document_type!='RUC' or len(self.customer_document_number)!=11 or not self.customer_document_number.isdigit() or len(self.customer_name)<2 or not self.customer_address):
            raise ValueError("La factura requiere RUC, razón social y dirección del adquirente")
        if self.invoice_type_code=='03' and (self.customer_document_number or self.customer_name or self.customer_document_type):
            if not self.customer_document_type or not self.customer_name or not self.customer_document_number:
                raise ValueError("Completa los datos del adquirente de la boleta")
            expected={'DNI':8,'RUC':11}.get(self.customer_document_type)
            if expected and (len(self.customer_document_number)!=expected or not self.customer_document_number.isdigit()):
                raise ValueError("Documento del adquirente inválido")
        return self


class IssuanceInput(Payload):
    plan_id: int = Field(gt=0)
    emitter_id: int = Field(gt=0)
    document_type: Literal["DNI", "CE", "PASSPORT"] = "DNI"
    document_number: str = Field(min_length=6, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    customer: Name
    first_names: str = Field(default="", max_length=100)
    paternal_surname: str = Field(default="", max_length=80)
    maternal_surname: str = Field(default="", max_length=80)
    email: EmailStr | Literal[""] = ""
    phone: str = Field(default="", max_length=25, pattern=r"^[+0-9 ()-]*$")
    starts_on: date
    payment_method: Literal["cash", "transfer", "card", "online"] = "cash"
    payment_status: Literal["pending", "collected_by_seller", "paid_to_abissol"] = "pending"
    external_source: str | None = Field(default=None, min_length=1, max_length=80)
    external_reference: str | None = Field(default=None, min_length=1, max_length=100)
    billing: BillingPreference | None = None

    @field_validator('customer', 'first_names', 'paternal_surname', 'maternal_surname', mode='before')
    @classmethod
    def uppercase(cls, value):
        return value.upper() if isinstance(value,str) else value

    @model_validator(mode="after")
    def valid_document(self):
        parts = [self.first_names, self.paternal_surname, self.maternal_surname]
        if any(parts) and " ".join(p for p in parts if p).casefold() != self.customer.casefold():
            raise ValueError("Los nombres y apellidos no coinciden con el titular")
        if self.document_type == "DNI" and (len(self.document_number) != 8 or not self.document_number.isdigit()):
            raise ValueError("El DNI debe tener ocho dígitos")
        if bool(self.external_source) != bool(self.external_reference):
            raise ValueError("El origen externo y la referencia se requieren juntos")
        if self.payment_method == "online" and self.payment_status == "collected_by_seller":
            raise ValueError("Un pago en línea no puede quedar en caja del vendedor")
        return self

class PaymentInput(Payload):
    payment_status: Literal["collected_by_seller", "paid_to_abissol"]
    reference: str = Field(min_length=3, max_length=100)

class ReasonInput(Payload):
    reason: str = Field(min_length=5, max_length=1000)

class LiquidationInput(Payload):
    kind: Literal["seller", "meta", "platform"]
    responsible_id: int | None = Field(default=None, gt=0)
    issuance_ids: list[Annotated[int, Field(gt=0)]] | None = Field(default=None, min_length=1, max_length=1000)
    starts_on: date
    ends_on: date
    @model_validator(mode="after")
    def period(self):
        if self.kind == "seller" and self.responsible_id is None:
            raise ValueError("Selecciona al vendedor responsable")
        if self.kind != "seller" and self.responsible_id is not None:
            raise ValueError("META y plataforma son consolidados de todos los vendedores")
        if self.ends_on < self.starts_on or (not self.issuance_ids and (self.ends_on - self.starts_on).days > 366):
            raise ValueError("El período debe estar ordenado y no superar un año")
        return self

class InvoiceInput(Payload):
    issuance_id: int = Field(gt=0)
    document_type: Literal["boleta", "factura"] = "boleta"
    customer: Name
    document_number: str = Field(min_length=8, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    @model_validator(mode="after")
    def ruc(self):
        if self.document_type == "factura" and (len(self.document_number) != 11 or not self.document_number.isdigit()):
            raise ValueError("La factura requiere RUC de once dígitos")
        return self

class DispatchInput(Payload):
    issuance_id: int = Field(gt=0)
    channel: Literal["email", "whatsapp"]
