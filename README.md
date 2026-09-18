# FerreñafeX

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
python -m pip install --upgrade pip
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

## Identificación por DNI

El DNI es el identificador público de cuenta. El registro exige un DNI peruano de 8 dígitos y no permite duplicados. El inicio de sesión acepta DNI o nombre de usuario.

Los comandos administrativos que requieren identificar a otra persona utilizan DNI, no el ID interno de SQLite. El campo entero `users.id` se conserva únicamente como clave técnica para las relaciones de la base de datos.

## Mapa

La página Mapa utiliza Leaflet sobre OpenStreetMap. El backend entrega reportes y solicitudes de ayuda que poseen coordenadas. Las coordenadas se aproximan antes de enviarse al navegador para reducir exposición de ubicación.

Para probar geolocalización en producción el sitio debe funcionar con HTTPS y el usuario debe conceder permiso al navegador. En desarrollo local, los navegadores permiten geolocalización en `localhost`/`127.0.0.1`.

El mapa no realiza seguimiento permanente. La ubicación personal sólo se solicita cuando el usuario pulsa `Usar mi ubicación`.

## Reportes

Los reportes se muestran en la sección Reportes y también pueden aparecer en el Mapa cuando cuentan con coordenadas. El identificador público tiene formato `FX-XXXXXXXXXX`.

## Aprendizaje

Aprendizaje es una sección informativa. Sólo presenta contenidos publicados por la plataforma; no muestra puntos, rangos ni botones para completar módulos.

## Chat Local

La antigua sección Local se denomina Chat Local. La ruta `/local` se conserva para no romper enlaces existentes.

## Comandos

El sistema procesa comandos en backend.

```text
/help
/rango list
/rango set RANGO DNI
/rango remove DNI
/party add DNI
/party remove DNI
/party invite DNI
/party members
/party info
/party leave
```

Los permisos se verifican en Python y no se confía en el navegador para autorizar operaciones.

Ejemplo:

```text
/rango set Colaborador 12345678
/party add 12345678
```

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
