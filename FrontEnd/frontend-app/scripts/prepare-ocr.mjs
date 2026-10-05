import { mkdir, copyFile, readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const destination = path.join(root, 'public', 'ocr');
await mkdir(destination, { recursive: true });
let copied = 0;
let unchanged = 0;
const copy = async (source, target) => {
  const sourcePath = path.join(root, 'node_modules', source);
  const targetPath = path.join(destination, target);
  try {
    const [sourceBytes, targetBytes] = await Promise.all([readFile(sourcePath), readFile(targetPath)]);
    if (sourceBytes.equals(targetBytes)) {
      unchanged += 1;
      return;
    }
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  await copyFile(sourcePath, targetPath);
  copied += 1;
};
await copy('tesseract.js/dist/worker.min.js', 'worker.min.js');
await copy('tesseract.js/dist/worker.min.js.LICENSE.txt', 'worker.LICENSE.txt');
for (const name of await readdir(path.join(root, 'node_modules', 'tesseract.js-core'))) {
  if (name.endsWith('-lstm.wasm.js') || name === 'LICENSE') await copy(`tesseract.js-core/${name}`, name);
}
for (const language of ['spa', 'eng']) await copy(`@tesseract.js-data/${language}/4.0.0_best_int/${language}.traineddata.gz`, `${language}.traineddata.gz`);
console.log(`OCR local preparado: ${copied} archivo(s) actualizado(s), ${unchanged} sin cambios.`);
