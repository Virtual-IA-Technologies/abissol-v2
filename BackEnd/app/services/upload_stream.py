"""Cargas documentales ABISSOL sobre el spool multipart, sin copiar 500 MB a RAM."""
import hashlib
import io
import shutil
import warnings
import zipfile
import codecs
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, ImageFilter, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

MAX_DOCUMENT_BYTES = 500 * 1024 * 1024


def optimized_raster(stream, size, *, avatar=False):
    """Optimiza fotos; documentos conservan formato y nunca crecen de tamaño."""
    stream.seek(0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(stream) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'} or source.width * source.height > 40_000_000 or getattr(source, 'n_frames', 1) > 1:
                    if avatar:
                        raise ValueError('Avatar no compatible o demasiado grande en dimensiones')
                    return None
                image = ImageOps.exif_transpose(source)
                image.thumbnail((512, 512) if avatar else (4000, 4000), Image.Resampling.LANCZOS)
                image = image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
                image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=65, threshold=3))
                image.info.clear()
                output = io.BytesIO()
                fmt = 'WEBP' if avatar else source.format
                options = {'quality': 85} if fmt != 'PNG' else {'optimize': True}
                image.save(output, fmt, **options)
                if avatar or output.tell() < size:
                    output.seek(0)
                    return output
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        if avatar:
            raise ValueError('El avatar debe ser una imagen PNG, JPG o WebP válida') from error
    finally:
        stream.seek(0)
    return None


class UploadData:
    def __init__(self, stream, size):
        self.stream, self.size = stream, size

    def __len__(self):
        return self.size

    def startswith(self, prefix):
        self.stream.seek(0)
        return self.stream.read(len(prefix)).startswith(prefix)

    def __getitem__(self, key):
        self.stream.seek(key.start or 0)
        return self.stream.read(key.stop - (key.start or 0))

    def decode(self, encoding):
        if self.size > 60_000:
            raise ValueError('La vista textual requiere lectura acotada')
        self.stream.seek(0)
        return self.stream.read().decode(encoding)

    def digest(self):
        digest = hashlib.sha256()
        self.stream.seek(0)
        while chunk := self.stream.read(1024 * 1024):
            digest.update(chunk)
        self.stream.seek(0)
        return digest.hexdigest()

    def write(self, path):
        self.stream.seek(0)
        created = False
        try:
            with path.open('xb') as target:
                created = True
                shutil.copyfileobj(self.stream, target, 1024 * 1024)
        except OSError as error:
            if created:
                path.unlink(missing_ok=True)
            raise HTTPException(507, 'No se pudo guardar el documento') from error
        finally:
            self.stream.seek(0)


async def prepare_upload(file):
    def prepare():
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        if not 0 < size <= MAX_DOCUMENT_BYTES:
            raise HTTPException(413, 'El archivo debe tener entre 1 byte y 500 MB')
        stream = optimized_raster(file.file, size) or file.file
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)
        return UploadData(stream, size)
    return await run_in_threadpool(prepare)


def document_mime(data, filename):
    """Valida firmas/Office/texto por bloques; no afecta adjuntos de Documentación."""
    suffix = Path(filename).suffix.lower()
    signatures = {'.png': (b'\x89PNG\r\n\x1a\n', 'image/png'), '.jpg': (b'\xff\xd8\xff', 'image/jpeg'),
                  '.jpeg': (b'\xff\xd8\xff', 'image/jpeg'), '.pdf': (b'%PDF-', 'application/pdf')}
    if suffix in signatures and data.startswith(signatures[suffix][0]):
        return signatures[suffix][1]
    if suffix == '.webp' and data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'image/webp'
    office = {'.docx': ('word/document.xml', 'wordprocessingml.document'),
              '.xlsx': ('xl/workbook.xml', 'spreadsheetml.sheet'), '.pptx': ('ppt/presentation.xml', 'presentationml.presentation')}
    if suffix in office:
        try:
            data.stream.seek(0)
            with zipfile.ZipFile(data.stream) as archive:
                if office[suffix][0] in archive.namelist() and '[Content_Types].xml' in archive.namelist():
                    return 'application/vnd.openxmlformats-officedocument.' + office[suffix][1]
        except zipfile.BadZipFile:
            pass
        finally:
            data.stream.seek(0)
    if suffix in {'.md', '.txt'}:
        decoder = codecs.getincrementaldecoder('utf-8-sig')()
        try:
            data.stream.seek(0)
            while chunk := data.stream.read(1024 * 1024):
                if b'\0' in chunk:
                    raise ValueError('Texto binario')
                decoder.decode(chunk)
            decoder.decode(b'', final=True)
            return 'text/plain'
        except (ValueError, UnicodeDecodeError):
            pass
        finally:
            data.stream.seek(0)
    raise HTTPException(422, 'Formato documental o contenido no válido')


async def save_document_upload(db, user, file, document, reason):
    """Adaptador probado con las rutas ABISSOL antes de sustituir el cargador."""
    import re
    from uuid import uuid4
    from ..models.documents import DocumentVersion
    from . import documents as service
    name = re.sub(r'[\x00-\x1f\x7f]', '', (file.filename or 'archivo').replace('\\', '/').split('/')[-1])[:180]
    data = await prepare_upload(file)
    mime = document_mime(data, name)
    key = uuid4().hex + Path(name).suffix.lower()
    service.STORAGE.mkdir(parents=True, exist_ok=True)
    path = service.STORAGE / key
    try:
        data.write(path)
        version = DocumentVersion(document_id=document.id, number=document.current_version, author_id=user.id,
            filename=name, storage_key=key, mime=mime, size=len(data), sha256=data.digest(), reason=reason.strip() or 'Carga de archivo',
            processing='text_ready' if mime == 'text/plain' and len(data) <= 60000 else 'pending',
            text=data.decode('utf-8-sig') if mime == 'text/plain' and len(data) <= 60000 else None)
        db.add(version)
        return version, path
    except Exception:
        path.unlink(missing_ok=True)
        raise
