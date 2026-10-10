"""Canonical website verification and stable document download URLs."""
import base64
import json

API = 'https://v2.abissol.org/abissol/api/v1/medical/validate/'


def verification_url(row):
    value = base64.urlsafe_b64encode(json.dumps({'code': row.token}, separators=(',', ':')).encode()).decode().rstrip('=')
    return 'https://abissol.org/?consulta=' + value


def document_url(row, kind):
    return API + row.token + '/' + kind
