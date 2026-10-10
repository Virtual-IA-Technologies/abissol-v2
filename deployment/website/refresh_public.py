"""Apply the document-display and status UX update to the V2-connected website."""
import argparse
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();s=a.source.read_text(encoding='utf-8-sig')
def replace(old,new):
    global s
    if s.count(old)!=1:raise SystemExit('Website changed; inspect anchor: '+old[:65])
    s=s.replace(old,new,1)

replace('    .message.success {', '''    .message.info {
      color: #0c4a6e;
      background: #f0f9ff;
      border: 1px solid #bae6fd;
    }
    .message.info .assistance-result,
    .message.info .assistance-field { border-color: #cce7f5; }
    .message.success {''')
replace('        isTest: Boolean(item.is_test),', "        isTest: Boolean(item.is_test),\n        publicStatus: item.status_public || '',\n        displayDocument: item.document_display || '',")
replace('escapeHtml(maskDocument(item.documentNumber))','escapeHtml(item.displayDocument || maskDocument(item.documentNumber))')
replace('const validityMessage = item.message || (item.isValid', "const validityMessage = item.publicStatus === 'future' ? 'Tu programa está registrado. La cobertura comienza en la fecha de inicio indicada.' : item.message || (item.isValid")
replace("    form.addEventListener('submit', async function (event) {", "    let qrQuery = '';\n    form.addEventListener('submit', async function (event) {")
replace('      const documentNumber = input.value.trim();', "      if (button.disabled) return;\n      const documentNumber = qrQuery || input.value.trim();\n      qrQuery = '';")
replace("          setMessage('error', escapeHtml(data.message || 'No se pudo validar la asistencia.'));", "          setMessage(response.status === 404 ? 'neutral' : 'error', escapeHtml(data.message || 'No se pudo validar la asistencia.'));")
replace("          setMessage(result.hasValid ? 'success' : 'error', buildAssistanceListHtml(result));", """          const document = result.items[0].displayDocument;
          if (/^[0-9]{6,20}$/.test(document)) input.value = document;
          else if (!/^[0-9]{6,20}$/.test(input.value)) input.value = '';
          const tone = result.hasValid ? 'success' : result.items.some(item => item.isTest || item.publicStatus === 'future') ? 'info' : result.items.every(item => item.isCancelled) ? 'error' : 'neutral';
          setMessage(tone, buildAssistanceListHtml(result));""")
replace('        input.value = autoQuery;', "        qrQuery = autoQuery;\n        input.value = /^[0-9]{6,20}$/.test(autoQuery) ? autoQuery : '';")
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('x',encoding='utf-8',newline='') as f:f.write(s)
print('Prepared document display, informative status colors and duplicate-submit guard.')
