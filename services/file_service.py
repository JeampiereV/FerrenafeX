from pathlib import Path
from uuid import uuid4

ALLOWED = {
    'image/jpeg': {'.jpg', '.jpeg'},
    'image/png': {'.png'},
    'image/webp': {'.webp'},
    'application/pdf': {'.pdf'},
}

def save_upload(file_obj, folder: Path, max_bytes: int = 5 * 1024 * 1024):
    if not file_obj or not file_obj.filename:
        return None, 'No se seleccionó archivo.'
    filename = file_obj.filename.strip()
    ext = Path(filename).suffix.lower()
    mime = (file_obj.mimetype or '').lower()
    if mime not in ALLOWED or ext not in ALLOWED[mime]:
        return None, 'Tipo de archivo no permitido. Usa JPG, PNG o WEBP.'
    file_obj.stream.seek(0, 2)
    size = file_obj.stream.tell()
    file_obj.stream.seek(0)
    if size > max_bytes:
        return None, 'El archivo supera el límite permitido de 5 MB.'
    folder.mkdir(parents=True, exist_ok=True)
    stored = f'{uuid4().hex}{ext}'
    path = folder / stored
    file_obj.save(path)
    return {'path': str(path), 'name': filename, 'mime': mime, 'size': size}, None
