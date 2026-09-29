let REPORT_LOC = null;
let reportMap = null;
let reportMarker = null;
const REPORT_CENTER = [-6.6397, -79.7885];

function setReportLocation(lat, lon, accuracy) {
  REPORT_LOC = { lat, lon, accuracy };
  const status = document.getElementById('locStatus');
  if (status) {
    status.textContent = `Ubicación lista · ${accuracy ? `precisión aproximada ${Math.round(accuracy)} m` : 'punto elegido en el mapa'}.`;
  }

  if (!reportMap) return;
  if (reportMarker) {
    reportMarker.setLatLng([lat, lon]);
  } else {
    reportMarker = L.marker([lat, lon], { draggable: true })
      .addTo(reportMap)
      .bindPopup('Ubicación del reporte')
      .openPopup();
    reportMarker.on('dragend', () => {
      const point = reportMarker.getLatLng();
      setReportLocation(point.lat, point.lng, null);
    });
  }
  reportMap.setView([lat, lon], 17, { animate: true });
}

async function loadReportLeaflet() {
  if (window.L) return true;

  const css = document.querySelector('link[data-leaflet-report-fallback]');
  if (!css) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css';
    link.dataset.leafletReportFallback = '1';
    document.head.appendChild(link);
  }

  const existing = document.querySelector('script[data-leaflet-report-fallback]');
  if (existing) {
    return new Promise(resolve => {
      existing.addEventListener('load', () => resolve(true), { once: true });
      existing.addEventListener('error', () => resolve(false), { once: true });
    });
  }

  return new Promise(resolve => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js';
    script.dataset.leafletReportFallback = '1';
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.head.appendChild(script);
  });
}

async function initReportMap() {
  const element = document.getElementById('reportMiniMap');
  if (!element || reportMap) return;
  const ready = await loadReportLeaflet();
  if (!ready) {
    element.innerHTML = '<div class="empty-state">El mapa no pudo cargarse. Puedes reintentar o publicar el reporte sin ubicación.</div>';
    return;
  }

  reportMap = L.map(element, {
    zoomControl: true,
    preferCanvas: true
  }).setView(REPORT_CENTER, 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    minZoom: 3,
    attribution: '© OpenStreetMap contributors'
  }).addTo(reportMap);

  reportMap.on('click', event => {
    setReportLocation(event.latlng.lat, event.latlng.lng, null);
    FA.toast('Punto seleccionado para el reporte.', 'ok');
  });

  setTimeout(() => reportMap.invalidateSize(), 150);
}

async function getReportLocation() {
  const button = document.getElementById('locBtn');
  if (button) {
    button.disabled = true;
    button.textContent = 'Obteniendo GPS…';
  }

  if (!navigator.geolocation) {
    FA.toast('Este navegador no permite geolocalización.', 'err');
    if (button) {
      button.disabled = false;
      button.textContent = 'Usar mi ubicación';
    }
    return;
  }

  navigator.geolocation.getCurrentPosition(
    position => {
      setReportLocation(
        position.coords.latitude,
        position.coords.longitude,
        position.coords.accuracy
      );
      FA.toast('Ubicación obtenida y lista para publicar.', 'ok');
      if (button) {
        button.disabled = false;
        button.textContent = 'Actualizar ubicación';
      }
    },
    error => {
      const message = error?.code === 1
        ? 'Permiso de ubicación denegado. Actívalo en el navegador.'
        : error?.code === 2
          ? 'No se pudo determinar la ubicación. Comprueba el GPS o la señal.'
          : 'El GPS tardó demasiado en responder. Inténtalo nuevamente.';
      FA.toast(message + ' Para celulares por Internet utiliza HTTPS.', 'err');
      if (button) {
        button.disabled = false;
        button.textContent = 'Reintentar ubicación';
      }
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
  );
}

async function loadReports() {
  const element = document.getElementById('reports');
  if (!element) return;

  const response = await FA.api('/api/reports');
  if (!response.ok) {
    element.innerHTML = `<div class="notice danger">${FA.escape(response.message || 'No se pudieron cargar los reportes.')}</div>`;
    return;
  }

  element.innerHTML = (response.reports || []).map(report => `
    <article class="row report-row">
      <div>
        <b>${FA.escape(report.public_id)} · ${FA.escape(report.category)}</b>
        <span>${FA.escape(report.names || report.username || 'Usuario')} · ${FA.escape(report.status)} · ${FA.escape(report.created_at)}</span>
        <p>${FA.escape((report.description || '').slice(0, 180))}</p>
      </div>
      <button class="btn dark" type="button" onclick="openReport(${Number(report.id)})">Abrir</button>
    </article>
  `).join('') || '<div class="row">No hay reportes todavía.</div>';
}

async function openReport(id) {
  const response = await FA.api('/api/reports/' + Number(id));
  if (!response.ok) {
    FA.toast(response.message, 'err');
    return;
  }

  const report = response.report;
  const detail = document.getElementById('reportDetail');
  if (!detail) return;

  detail.innerHTML = `
    <div class="detail-grid">
      <div><small>ID</small><b>${FA.escape(report.public_id)}</b></div>
      <div><small>Autor</small><b>${FA.escape(report.names || report.username)} · ID ${FA.escape(report.user_id)}</b></div>
      <div><small>Categoría</small><b>${FA.escape(report.category)}</b></div>
      <div><small>Estado</small><b>${FA.escape(report.status)}</b></div>
    </div>
    <hr>
    <p><strong>Descripción</strong><br>${FA.escape(report.description)}</p>
    <p><strong>Ubicación</strong><br>${report.latitude != null && report.longitude != null ? FA.escape(report.latitude) + ', ' + FA.escape(report.longitude) : 'No compartida'}</p>
    <div class="timeline">
      ${(response.timeline || []).map(item => `
        <div class="timeline-item">
          <b>${FA.escape(item.status)}</b>
          <span>${FA.escape(item.notes || '')}</span>
          <small>${FA.escape(item.created_at)}</small>
        </div>
      `).join('')}
    </div>
  `;
  document.getElementById('reportModal')?.classList.remove('hidden');
}

function closeReport() {
  document.getElementById('reportModal')?.classList.add('hidden');
}

window.closeReport = closeReport;
window.openReport = openReport;

document.getElementById('locBtn')?.addEventListener('click', getReportLocation);
document.getElementById('clearLocBtn')?.addEventListener('click', () => {
  REPORT_LOC = null;
  if (reportMarker && reportMap) {
    reportMap.removeLayer(reportMarker);
    reportMarker = null;
  }
  const status = document.getElementById('locStatus');
  if (status) status.textContent = 'Sin ubicación. También puedes hacer clic en el mapa.';
  FA.toast('Ubicación quitada.', 'ok');
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeReport();
});

document.getElementById('reportModal')?.addEventListener('click', event => {
  if (event.target.id === 'reportModal') closeReport();
});

document.getElementById('reportForm')?.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  if (REPORT_LOC) {
    formData.set('latitude', REPORT_LOC.lat);
    formData.set('longitude', REPORT_LOC.lon);
    if (REPORT_LOC.accuracy != null) formData.set('accuracy', REPORT_LOC.accuracy);
  }

  const response = await FA.upload('/api/reports', formData);
  FA.toast(response.message, response.ok ? 'ok' : 'err');
  if (!response.ok) return;

  form.reset();
  REPORT_LOC = null;
  if (reportMarker && reportMap) {
    reportMap.removeLayer(reportMarker);
    reportMarker = null;
  }
  const status = document.getElementById('locStatus');
  if (status) status.textContent = 'Sin ubicación';
});

document.addEventListener('DOMContentLoaded', async () => {
  await initReportMap();
  await loadReports();
});
