"""Fail deployment before switching if the isolated print engine is unavailable."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.medical_rendering import render
html='<html><style>body{font-family:DejaVu Sans}</style><body><p>Validación de impresión ABISSOL</p><img width="80" src="qr.png"></body></html>'
assert render(html,'https://v2.abissol.org','welcome').startswith(b'%PDF-')
print('Motor de impresión original verificado; sin documentos de negocio.')
