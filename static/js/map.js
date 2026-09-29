let mapInstance = null;
let userLocation = null;
let userMarker = null;
let layers = [];
let liveWatchId = null;
let livePostingTimer = null;
let liveRefreshTimer = null;
let liveLayers = [];
let liveActive = false;
let liveDeadline = 0;
let liveRenew = false;
let mapFirstLoad = true;
const defaultCenter = [-6.6397, -79.7885];

function clearLayers() {
  layers.forEach(layer => {
    try { mapInstance.removeLayer(layer); } catch (_) {}
  });
  layers = [];
}

function clearLiveLayers() {
  liveLayers.forEach(layer => {
    try { mapInstance.removeLayer(layer); } catch (_) {}
  });
  liveLayers = [];
}

function escapeVal(value) {
  return FA.escape(value == null ? '' : String(value));
}

function setUserMarker(lat, lon, accuracy) {
  if (!mapInstance) return;
  const popup = `<strong>Tu ubicación exacta</strong><br><small>Precisión aproximada: ${Math.round(Number(accuracy || 0))} m.</small><br><small>Esta ubicación sólo se comparte si activas “Compartir”.</small>`;
  if (userMarker) {
    userMarker.setLatLng([lat, lon]).bindPopup(popup);
    return;
  }
  userMarker = L.circleMarker([lat, lon], {
    radius: 9,
    weight: 3,
    fillOpacity: 0.95,
    className: 'marker-me'
  }).addTo(mapInstance).bindPopup(popup);
}

function marker(lat, lon, html, kind) {
  const parsedLat = Number(lat);
  const parsedLon = Number(lon);
  if (!Number.isFinite(parsedLat) || !Number.isFinite(parsedLon)) return null;
  const m = L.circleMarker([parsedLat, parsedLon], {
    radius: 8,
    weight: 2,
    fillOpacity: 0.9,
    className: 'marker-' + kind
  }).addTo(mapInstance).bindPopup(html);
  layers.push(m);
  return m;
}

function geoErrorMessage(error) {
  if (!error) return 'No se pudo obtener la ubicación.';
  if (error.code === 1) return 'Permiso de ubicación denegado. Actívalo en el navegador.';
  if (error.code === 2) return 'No se pudo determinar la ubicación. Comprueba el GPS o la señal.';
  if (error.code === 3) return 'El GPS tardó demasiado en responder. Inténtalo nuevamente.';
  return 'No se pudo obtener la ubicación.';
}

function getPosition(options = {}) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Tu navegador no permite geolocalización.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 20000,
      maximumAge: 0,
      ...options
    });
  });
}

async function updateGeoStatus() {
  const status = document.getElementById('geoPermissionStatus');
  if (!status) return;
  if (!navigator.geolocation) {
    status.textContent = 'GPS no disponible en este navegador.';
    return;
  }
  if (!navigator.permissions?.query) {
    status.textContent = 'GPS disponible. El navegador solicitará permiso al usarlo.';
    return;
  }
  try {
    const permission = await navigator.permissions.query({ name: 'geolocation' });
    const labels = { granted: 'GPS autorizado.', denied: 'GPS bloqueado por el navegador.', prompt: 'GPS listo: al activarlo se solicitará permiso.' };
    status.textContent = labels[permission.state] || 'GPS disponible.';
    permission.onchange = () => { status.textContent = labels[permission.state] || 'GPS disponible.'; };
  } catch (_) {
    status.textContent = 'GPS disponible. El navegador solicitará permiso al usarlo.';
  }
}

async function loadLeafletFallback() {
  if (window.L) return true;

  const existing = document.querySelector('script[data-leaflet-fallback]');
  if (existing) {
    return new Promise(resolve => {
      existing.addEventListener('load', () => resolve(true), { once: true });
      existing.addEventListener('error', () => resolve(false), { once: true });
    });
  }

  await new Promise(resolve => {
    const cssExists = document.querySelector('link[data-leaflet-fallback-css]');
    if (!cssExists) {
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css';
      css.dataset.leafletFallbackCss = '1';
      document.head.appendChild(css);
    }
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js';
    script.dataset.leafletFallback = '1';
    script.onload = () => resolve();
    script.onerror = () => resolve();
    document.head.appendChild(script);
  });

  return !!window.L;
}

function mapBounds(items) {
  const points = [];
  for (const item of items) {
    const lat = Number(item.public_latitude);
    const lon = Number(item.public_longitude);
    if (Number.isFinite(lat) && Number.isFinite(lon)) points.push([lat, lon]);
  }
  return points;
}

async function loadMapData() {
  if (!mapInstance) return;
  clearLayers();

  try {
    const response = await FA.api('/api/map/markers');
    if (!response.ok) {
      FA.toast(response.message || 'No se pudo cargar el mapa.', 'err');
      return;
    }

    const allPoints = [];

    for (const report of (response.reports || [])) {
      const lat = Number(report.public_latitude);
      const lon = Number(report.public_longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      allPoints.push({ public_latitude: lat, public_longitude: lon });
      marker(
        lat,
        lon,
        `<strong>Reporte ${escapeVal(report.public_id)}</strong><br>` +
        `<b>${escapeVal(report.category)}</b> · ${escapeVal(report.status)}<br>` +
        `${escapeVal((report.description || '').slice(0, 220))}<br>` +
        `<small>Ubicación pública aproximada.</small>`,
        'report'
      );
    }

    for (const help of (response.helps || [])) {
      const lat = Number(help.public_latitude);
      const lon = Number(help.public_longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      allPoints.push({ public_latitude: lat, public_longitude: lon });
      marker(
        lat,
        lon,
        `<strong>AYUDA COMUNITARIA</strong><br>` +
        `<b>Necesita:</b> ${escapeVal(help.help_type)}<br>` +
        `<b>Prioridad:</b> ${escapeVal(help.priority)}<br>` +
        `${escapeVal((help.description || '').slice(0, 250))}<br>` +
        `<small>Ubicación pública aproximada.</small><br>` +
        `<button class="map-help-btn" type="button" onclick="offerHelp(${Number(help.id)})">Quiero ayudar</button>`,
        'help'
      );
    }

    renderItems(response);

    if (mapFirstLoad && allPoints.length > 0 && !userLocation) {
      const points = mapBounds(allPoints);
      if (points.length === 1) {
        mapInstance.setView(points[0], 14);
      } else if (points.length > 1) {
        mapInstance.fitBounds(L.latLngBounds(points), { padding: [30, 30], maxZoom: 15 });
      }
    }
    mapFirstLoad = false;

    await loadAuthorizedLiveLocations();
  } catch (error) {
    console.error(error);
    FA.toast('No pudimos actualizar el mapa. Revisa tu conexión y vuelve a intentarlo.', 'err');
  }
}

async function loadAuthorizedLiveLocations() {
  if (!mapInstance) return;
  clearLiveLayers();

  try {
    const mine = await FA.api('/api/help/mine');
    if (!mine.ok) return;

    const helpIds = new Set();
    (mine.requests || [])
      .filter(help => help.status === 'active')
      .forEach(help => helpIds.add(Number(help.id)));
    (mine.offers || [])
      .filter(offer => ['accepted', 'on_way', 'nearby', 'arrived'].includes(offer.status))
      .forEach(offer => helpIds.add(Number(offer.help_id)));

    // Owner puede revisar el seguimiento exacto de las ayudas activas desde la consola.
    if (window.IS_OWNER) {
      const all = await FA.api('/api/map/markers');
      (all.helps || []).forEach(help => helpIds.add(Number(help.id)));
    }

    for (const hid of helpIds) {
      const response = await FA.api('/api/help/' + hid + '/tracking');
      if (!response.ok) continue;

      for (const location of (response.live_locations || [])) {
        const lat = Number(location.latitude);
        const lon = Number(location.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;

        const mineMarker = Number(location.user_id) === Number(window.CURRENT_USER_ID || 0);
        const point = L.circleMarker([lat, lon], {
          radius: mineMarker ? 11 : 10,
          weight: 3,
          fillOpacity: 0.95,
          className: 'marker-live'
        }).addTo(mapInstance);

        point.bindPopup(
          `<strong>Ubicación exacta en tiempo real</strong><br>` +
          `<b>${mineMarker ? 'Tú' : escapeVal((location.names || '') + ' ' + (location.last_names || ''))}</b><br>` +
          `<span>Latitud: ${escapeVal(lat.toFixed(6))}</span><br>` +
          `<span>Longitud: ${escapeVal(lon.toFixed(6))}</span><br>` +
          `<small>Actualizado: ${escapeVal(location.updated_at)}</small>`
        );
        liveLayers.push(point);
      }
    }
  } catch (error) {
    console.error(error);
  }
}

function renderItems(data) {
  const container = document.getElementById('mapItems');
  if (!container) return;

  const items = [
    ...(data.reports || []).map(item => ({
      type: 'Reporte',
      label: item.category,
      status: item.status,
      name: item.names
    })),
    ...(data.helps || []).map(item => ({
      type: 'Ayuda',
      label: item.help_type,
      status: item.priority,
      name: item.names
    }))
  ];

  container.innerHTML = items.slice(0, 80).map(item => `
    <div class="map-item">
      <small>${escapeVal(item.type)}</small>
      <b>${escapeVal(item.label)}</b>
      <span>${escapeVal(item.name || 'Usuario')} · ${escapeVal(item.status)}</span>
    </div>
  `).join('') || '<div class="card">No hay reportes o ayudas con ubicación disponible.</div>';
}

async function locate() {
  const button = document.getElementById('locate');
  if (button) {
    button.disabled = true;
    button.textContent = 'Obteniendo GPS…';
  }

  try {
    const position = await getPosition();
    userLocation = {
      lat: position.coords.latitude,
      lon: position.coords.longitude,
      accuracy: position.coords.accuracy
    };
    setUserMarker(userLocation.lat, userLocation.lon, userLocation.accuracy);
    mapInstance.setView([userLocation.lat, userLocation.lon], 17, { animate: true });

    const status = document.getElementById('liveLocationStatus');
    if (status && !liveActive) {
      status.textContent = `GPS encontrado · precisión aproximada ${Math.round(userLocation.accuracy || 0)} m.`;
    }
    FA.toast('GPS localizado. “Ubicarme” sólo centra el mapa; no publica tu ubicación.', 'ok');
  } catch (error) {
    FA.toast(geoErrorMessage(error) + ' Para un acceso desde celular por Internet utiliza HTTPS.', 'err');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = 'Ubicarme';
    }
    updateGeoStatus();
  }
}

async function publishLivePoint(lat, lon, accuracy, renew = false) {
  const selectedMinutes = Number(document.getElementById('liveDuration')?.value || 10);
  const payload = {
    latitude: lat,
    longitude: lon,
    accuracy,
    minutes: selectedMinutes,
    renew,
    context: 'self'
  };
  const response = await FA.api('/api/location/live', {
    method: 'POST',
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    FA.toast(response.message || 'No se pudo publicar la ubicación.', 'err');
    return false;
  }

  liveActive = true;
  const status = document.getElementById('liveLocationStatus');
  if (status) {
    status.textContent = `GPS activo · precisión ${Math.round(Number(accuracy || 0))} m · actualizado ahora.`;
  }
  return true;
}

async function startLive() {
  if (!navigator.geolocation) {
    FA.toast('Tu navegador no permite geolocalización.', 'err');
    return;
  }
  if (liveWatchId !== null) return;

  const minutes = Number(document.getElementById('liveDuration')?.value || 10);
  liveDeadline = Date.now() + minutes * 60 * 1000;
  liveRenew = true;

  const status = document.getElementById('liveLocationStatus');
  if (status) status.textContent = 'Solicitando permiso y obteniendo GPS…';

  try {
    const first = await getPosition();
    if (Date.now() >= liveDeadline) throw new Error('El tiempo seleccionado expiró.');

    userLocation = {
      lat: first.coords.latitude,
      lon: first.coords.longitude,
      accuracy: first.coords.accuracy
    };
    setUserMarker(userLocation.lat, userLocation.lon, userLocation.accuracy);
    mapInstance.setView([userLocation.lat, userLocation.lon], 17, { animate: true });

    const published = await publishLivePoint(
      userLocation.lat,
      userLocation.lon,
      userLocation.accuracy,
      true
    );
    if (!published) return;
    liveRenew = false;

    liveWatchId = navigator.geolocation.watchPosition(
      async position => {
        if (Date.now() >= liveDeadline) {
          await stopLive(true, 'Se terminó el tiempo elegido para compartir GPS.');
          return;
        }
        userLocation = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
          accuracy: position.coords.accuracy
        };
        setUserMarker(userLocation.lat, userLocation.lon, userLocation.accuracy);
        mapInstance.setView([userLocation.lat, userLocation.lon], 17, { animate: false });
        await publishLivePoint(userLocation.lat, userLocation.lon, userLocation.accuracy, false);
      },
      error => {
        FA.toast(geoErrorMessage(error), 'err');
        stopLive(false);
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
    );

    if (livePostingTimer) clearInterval(livePostingTimer);
    livePostingTimer = setInterval(async () => {
      if (!liveActive) return;
      if (Date.now() >= liveDeadline) {
        await stopLive(true, 'Se terminó el tiempo elegido para compartir GPS.');
        return;
      }
      if (userLocation) {
        await publishLivePoint(
          userLocation.lat,
          userLocation.lon,
          userLocation.accuracy,
          false
        );
      }
    }, 5000);

    updateGeoStatus();
  } catch (error) {
    liveRenew = false;
    const message = error?.message || geoErrorMessage(error);
    FA.toast(message.includes('tiempo') ? message : geoErrorMessage(error), 'err');
    await stopLive(false);
  }
}

async function stopLive(show = true, customMessage = '') {
  if (liveWatchId !== null) {
    navigator.geolocation.clearWatch(liveWatchId);
    liveWatchId = null;
  }
  if (livePostingTimer) {
    clearInterval(livePostingTimer);
    livePostingTimer = null;
  }
  liveActive = false;
  liveDeadline = 0;
  liveRenew = false;

  const response = await FA.api('/api/location/stop', {
    method: 'POST',
    body: '{}'
  });
  if (show) {
    FA.toast(customMessage || response.message || 'Ubicación detenida.', response.ok ? 'ok' : 'err');
  }

  const status = document.getElementById('liveLocationStatus');
  if (status) status.textContent = 'Desactivada.';
}

window.offerHelp = async function(id) {
  const response = await FA.api('/api/help/' + Number(id) + '/offer', {
    method: 'POST',
    body: '{}'
  });
  FA.toast(response.message || 'No se pudo enviar la oferta.', response.ok ? 'ok' : 'err');
};

window.initCommunityMap = async function() {
  const ready = await loadLeafletFallback();
  if (!ready) {
    const el = document.getElementById('map');
    if (el) {
      el.innerHTML = '<div class="empty-state">No se pudo cargar el mapa. Comprueba tu conexión y vuelve a intentarlo.</div>';
    }
    return;
  }

  if (!mapInstance) {
    const el = document.getElementById('map');
    if (!el) return;

    mapInstance = L.map(el, {
      zoomControl: true,
      worldCopyJump: true,
      preferCanvas: true
    }).setView(defaultCenter, 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      minZoom: 3,
      updateWhenZooming: false,
      attribution: '© OpenStreetMap contributors'
    }).addTo(mapInstance);

    document.getElementById('locate')?.addEventListener('click', locate);
    document.getElementById('refreshMap')?.addEventListener('click', loadMapData);
    document.getElementById('startLiveLocation')?.addEventListener('click', startLive);
    document.getElementById('stopLiveLocation')?.addEventListener('click', () => stopLive(true));
  }

  setTimeout(() => mapInstance.invalidateSize(), 150);
  updateGeoStatus();
  loadMapData();

  if (liveRefreshTimer) clearInterval(liveRefreshTimer);
  liveRefreshTimer = setInterval(loadAuthorizedLiveLocations, 3000);
};

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('map')) window.initCommunityMap();
});

window.addEventListener('beforeunload', () => {
  if (liveWatchId !== null) navigator.geolocation.clearWatch(liveWatchId);
});
