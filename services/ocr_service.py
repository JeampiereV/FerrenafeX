import logging
import os
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)
OCR_URL = 'https://www.ocrwebservice.com/restservices/processDocument'
SUPPORTED_LANGUAGES = {'english': 'Inglés', 'afrikaans': 'Afrikáans', 'albanian': 'Albanés', 'basque': 'Vasco', 'bulgarian': 'Búlgaro', 'byelorussian': 'Bielorruso', 'catalan': 'Catalán', 'chinesesimplified': 'Chino simplificado', 'chinesetraditional': 'Chino tradicional', 'croatian': 'Croata', 'czech': 'Checo', 'danish': 'Danés', 'dutch': 'Neerlandés', 'esperanto': 'Esperanto', 'estonian': 'Estonio', 'finnish': 'Finés', 'french': 'Francés', 'galician': 'Gallego', 'german': 'Alemán', 'greek': 'Griego', 'hungarian': 'Húngaro', 'icelandic': 'Islandés', 'indonesian': 'Indonesio', 'italian': 'Italiano', 'japanese': 'Japonés', 'korean': 'Coreano', 'latin': 'Latín', 'latvian': 'Letón', 'lithuanian': 'Lituano', 'macedonian': 'Macedonio', 'malay': 'Malayo', 'moldavian': 'Moldavo', 'norwegian': 'Noruego', 'polish': 'Polaco', 'portuguese': 'Portugués', 'romanian': 'Rumano', 'russian': 'Ruso', 'serbian': 'Serbio', 'slovak': 'Eslovaco', 'slovenian': 'Esloveno', 'spanish': 'Español', 'swedish': 'Sueco', 'tagalog': 'Tagalo', 'turkish': 'Turco', 'ukrainian': 'Ucraniano'}

# The official service documents 100 MB as the maximum input size.
MAX_FILE_BYTES = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp', 'gif'}


def api_credentials():
    username = os.getenv('ONLINEOCR_USERNAME') or os.getenv('ONLINEOCR_USER')
    license_code = os.getenv('ONLINEOCR_LICENSE_CODE') or os.getenv('ONLINEOCR_API_KEY')
    return username, license_code


def _flatten_ocr_text(ocr_text) -> str:
    lines: List[str] = []
    for zone in ocr_text or []:
        if isinstance(zone, list):
            lines.extend(str(page or '') for page in zone)
        elif zone:
            lines.append(str(zone))
    return '\n\n'.join(x.strip() for x in lines if x and x.strip()).strip()


def process_document(file_storage, language: str) -> Dict:
    username, license_code = api_credentials()
    if not username or not license_code:
        raise RuntimeError('OCR no está configurado en el servidor.')
    language = language if language in SUPPORTED_LANGUAGES else 'spanish'

    file_storage.stream.seek(0)
    response = requests.post(
        OCR_URL,
        params={
            'language': language,
            'pagerange': 'allpages',
            'gettext': 'true',
            'newline': '1',
        },
        headers={
            'UserName': username,
            'LicenseCode': license_code,
            'Accept': 'application/json',
        },
        files={'file': (file_storage.filename, file_storage.stream, file_storage.mimetype or 'application/octet-stream')},
        timeout=(20, 180),
    )
    if response.status_code in (401, 402):
        logger.warning('OCR authentication/account error: status=%s', response.status_code)
        raise PermissionError('La cuenta OCR no pudo autorizar el procesamiento.')
    if response.status_code == 400:
        logger.warning('OCR rejected document: %s', response.text[:500])
        raise ValueError('El servicio OCR rechazó el documento.')
    if response.status_code >= 500:
        logger.error('OCR upstream server error: status=%s', response.status_code)
        raise ConnectionError('El servicio OCR no está disponible temporalmente.')
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as exc:
        logger.error('OCR returned invalid JSON')
        raise ValueError('La respuesta del servicio OCR no es válida.') from exc

    error_message = data.get('ErrorMessage') or data.get('OCRErrorMessage')
    if error_message:
        logger.warning('OCR service error: %s', error_message[:500])
        raise ValueError('El servicio OCR no pudo reconocer el documento.')

    text = _flatten_ocr_text(data.get('OCRText'))
    return {
        'text': text,
        'processed_pages': data.get('ProcessedPages', 0),
        'available_pages': data.get('AvailablePages'),
        'output_file_url': data.get('OutputFileUrl') or '',
    }
