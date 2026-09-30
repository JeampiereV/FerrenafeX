# FerreñafeX
Funcionando en https://ferrenafex.onrender.com 
BETA
Plataforma web comunitaria para Ferreñafe orientada a reportes, ayuda voluntaria, comunicación local, prevención y participación responsable.

## Tecnologías

- Python 3.11+
- Flask 3.1+
- SQLite
- HTML5
- CSS3
- JavaScript Vanilla
- Leaflet para el mapa y OpenStreetMap como proveedor cartográfico

No se utiliza React, Vue, Angular, Node.js, PHP, Django, Bootstrap, Tailwind, Firebase, MongoDB, Supabase ni jQuery.

## Requisitos

Se recomienda Python 3.11, 3.12 o 3.13 para desarrollo y despliegue. Python 3.14 puede presentar incompatibilidades con paquetes de terceros que no sean necesarios para este proyecto.

## Instalación local

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install flask
pip install -r requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copia `.env.example` como `.env` y define una clave secreta propia.

```text
FLASK_SECRET_KEY=una-clave-larga-y-aleatoria
FERRENAFE_OWNER_CODE=un-codigo-privado
DATABASE_PATH=database/ferre_alerta.db
SESSION_COOKIE_SECURE=0
```

Inicia la aplicación:

```bash
python app.py
```

Abre `http://127.0.0.1:5000`.

## Identificación de cuentas

Cada usuario tiene un `users.id` interno generado por SQLite y separado del DNI. El ID interno se utiliza para relaciones técnicas y administración; el DNI se trata como dato personal y no se publica en vistas comunitarias.

## Mapa y GPS

La página Mapa utiliza Leaflet sobre OpenStreetMap. Todos los usuarios autenticados pueden consultar los reportes y ayudas activas que tengan ubicación disponible. Las posiciones de reportes y ayudas se muestran de forma aproximada en la vista comunitaria.

El botón **Ubicarme** usa el GPS del navegador para centrar el mapa y mostrar tu posición exacta en tu propio dispositivo. No la publica por sí solo.

El botón **Compartir ubicación** activa `watchPosition` para recibir actualizaciones de GPS y publicar temporalmente la posición exacta dentro del flujo autorizado de ayuda. El usuario puede detener el seguimiento y el sistema deja de compartir la ubicación al finalizar o cancelar la ayuda.

La geolocalización del navegador requiere permiso del usuario y, para acceso por Internet desde un celular, un contexto seguro como HTTPS.

Si el GPS no está disponible, los reportes y solicitudes pueden seleccionar el punto manualmente sobre el mapa.

## Reportes

Los reportes comunican incidencias de la comunidad. Pueden incluir categoría, descripción, prioridad, ubicación y una fotografía como evidencia opcional. No se utilizan como repositorio de documentos administrativos.

## Chat y administración

La interfaz utiliza botones y acciones visuales; no es necesario escribir comandos con `/`. En los chats administrativos, sólo el Owner puede eliminar un chat completo o eliminar una cantidad determinada de mensajes recientes.

## Contraseñas

Las contraseñas se guardan mediante `hashlib.scrypt`. Ningún usuario, incluido el Owner, puede recuperar o visualizar la contraseña actual. Desde **Ver ficha** el Owner puede reemplazar la contraseña de un miembro y, en la ficha del Owner, establecer una nueva contraseña para la propia cuenta. También puede generar una contraseña temporal y verla antes de guardarla. El código de acceso Owner es independiente de la contraseña de la cuenta.

## Owner

El Owner se inicializa mediante `FERRENAFE_OWNER_CODE`. Nunca se debe publicar ese valor ni dejar el código de ejemplo en producción.

## Render

El proyecto incluye `render.yaml` y `Procfile`. En Render se recomienda crear un Web Service desde el repositorio.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

Variables de entorno mínimas:

```text
FLASK_SECRET_KEY=<secreto-largo>
FERRENAFE_OWNER_CODE=<codigo-owner>
SESSION_COOKIE_SECURE=1
```

SQLite funciona para una instalación pequeña o de demostración. El almacenamiento de archivos y la base de datos local de un servicio web sin disco persistente pueden perderse al redeployar o reiniciar. Para una instalación permanente se debe contratar almacenamiento persistente o migrar a una base de datos administrada.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Seguridad

- Contraseñas con `hashlib.scrypt`.
- Sesiones HTTPOnly y SameSite.
- CSRF para operaciones mutables de API.
- Consultas SQLite parametrizadas.
- Validación de archivos y límite de tamaño.
- Permisos administrativos en backend.
- Registro de auditoría para acciones sensibles.
- Ubicación temporal y consentimiento explícito.
- No se publican DNI ni documentos privados en las vistas comunitarias.

## Alcance

FerreñafeX no reemplaza a Policía, Bomberos, servicios de salud, ambulancias ni otros servicios oficiales. La ayuda es voluntaria y comunitaria. Ante una emergencia grave, se deben utilizar los canales oficiales correspondientes.

## Estructura

```text
FerreñafeX/
├── app.py
├── config.py
├── database.py
├── requirements.txt
├── render.yaml
├── Procfile
├── README.md
├── database/
├── routes/
├── services/
├── templates/
├── static/
├── uploads/
└── tests/
```


## Actualización: chat en tiempo real y Herramientas → OCR

- Chat privado y salas usan Socket.IO para entregar mensajes sin recargar la página.
- Se conserva una consulta periódica de respaldo para reconexiones y recuperación de mensajes.
- Los mensajes se identifican por ID para evitar duplicados en el DOM.
- Se agregó `Herramientas → OCR` con PDF, PNG, JPG/JPEG, TIFF, BMP y GIF.
- La integración OCR usa exclusivamente el REST API oficial de OCR Web Service.
- Configura `ONLINEOCR_USERNAME` y `ONLINEOCR_LICENSE_CODE` únicamente como variables de entorno del servidor.
- Los archivos OCR no se guardan en SQLite ni en almacenamiento permanente.
- La página permite copiar y exportar el texto reconocido a TXT, DOCX, PDF y XLSX.
- En Render, el servicio se ejecuta con Gunicorn `gthread` para soportar Socket.IO en modo threading.
