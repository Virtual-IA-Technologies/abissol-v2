from pydantic import BaseModel, Field, model_validator
from typing import Literal


class NotificationPreferencesWrite(BaseModel):
    enabled_types: list[str] = Field(default_factory=list, max_length=100)


class RecipientRule(BaseModel):
    kind: Literal['eligible','participants','administrators','roles','users'] = 'eligible'
    ids: list[int] = Field(default_factory=list, max_length=500)


class NotificationRuleWrite(BaseModel):
    recipients: RecipientRule
    channels: list[Literal['platform','email','whatsapp']] = Field(default_factory=lambda:['platform'], min_length=1, max_length=3)

    @model_validator(mode='after')
    def validate_rule(self):
        if len(self.channels)!=len(set(self.channels)) or 'platform' not in self.channels:
            raise ValueError('Plataforma permanece como registro base; canales sin duplicados')
        if self.recipients.kind in ('roles','users') and not self.recipients.ids:
            raise ValueError('Selecciona destinatarios')
        if self.recipients.kind not in ('roles','users') and self.recipients.ids:
            raise ValueError('Este grupo no requiere IDs')
        return self


class NotificationRulesWrite(BaseModel):
    rules: dict[str,NotificationRuleWrite] = Field(max_length=100)
