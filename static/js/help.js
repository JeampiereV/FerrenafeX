let HELP_LOC = null;
let HELP_LIVE_ID = null;
let HELP_WATCH_ID = null;
let HELP_LIVE_TIMER = null;
let HELP_LIVE_DEADLINE = 0;

function updateHelpPreview() {
  const form = document.getElementById('helpForm');
  const preview = document.getElementById('helpPreview');
  if (!form || !preview) return;
  const type = form.help_type.value;
  const description = form.description.value.trim() || 'Sin descripción';
  const minutes = form.location_minutes.value;
  const location = HELP_LOC ? 'Ubicación lista' : 'Sin ubicación';
  preview.innerHTML = `<strong>Vista previa</strong><br><span class="help-pin">●</span> ${FA.escape(type)} · <strong>Necesita:</strong> ${FA.escape(description.slice(0, 220))}<br><small>${location} · publicación comunitaria${HELP_LOC ? ` · ubicación temporal ${FA.escape(minutes)} min` : ''}</small>`;
}

function geoError(error) {
  if (!error) return 'No se pudo obtener la ubicación.';
  if (error.code === 1) return 'Permiso de ubicación denegado. Actívalo en el navegador.';
  if (error.code === 2) return 'No se pudo determinar la ubicación. Comprueba el GPS o la señal.';
  if (error.code === 3) return 'El GPS tardó demasiado en responder. Inténtalo nuevamente.';
  return 'No se pudo obtener la ubicación.';
}

function getHelpPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Tu navegador no permite geolocalización.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 20000,
      maximumAge: 0
    });
  });
}

async function getHelpLocation() {
  const consent = document.getElementById('locationConsent');
  if (!consent?.checked) {
    FA.toast('Activa el consentimiento para compartir ubicación.', 'err');
    return;
  }

  const button = document.getElementById('getHelpLocation');
  if (button) {
    button.disabled = true;
    button.textContent = 'Obteniendo GPS…';
  }

  try {
    const position = await getHelpPosition();
    HELP_LOC = {
      lat: position.coords.latitude,
      lon: position.coords.longitude,
      accuracy: position.coords.accuracy
    };
    const status = document.getElementById('helpLocStatus');
    if (status) status.textContent = `Ubicación lista · precisión aproximada ${Math.round(position.coords.accuracy || 0)} m.`;
    updateHelpPreview();
    FA.toast('Ubicación obtenida y lista para publicar.', 'ok');
  } catch (error) {
    const status = document.getElementById('helpLocStatus');
    if (status) status.textContent = 'No se obtuvo la ubicación.';
    FA.toast(geoError(error) + ' Desde celular por Internet utiliza HTTPS.', 'err');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = HELP_LOC ? 'Actualizar ubicación' : 'Reintentar ubicación';
    }
  }
}

async function postHelpLivePoint(hid, position, renew = false) {
  const minutes = Number(document.getElementById('helpLiveDuration')?.value || 10);
  const response = await FA.api('/api/help/' + Number(hid) + '/live', {
    method: 'POST',
    body: JSON.stringify({
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy,
      minutes,
      renew
    })
  });
  if (!response.ok) {
    FA.toast(response.message || 'No se pudo actualizar tu ubicación.', 'err');
    return false;
  }
  return true;
}

async function startHelpLive(hid) {
  if (!navigator.geolocation) {
    FA.toast('Tu navegador no permite geolocalización.', 'err');
    return;
  }
  if (HELP_WATCH_ID !== null && HELP_LIVE_ID === Number(hid)) return;

  try {
    if (!document.getElementById('locationConsent')?.checked && !HELP_LOC) {
      FA.toast('Primero activa el consentimiento para compartir ubicación.', 'err');
      return;
    }

    const minutes = Number(document.getElementById('helpLiveDuration')?.value || 10);
    HELP_LIVE_DEADLINE = Date.now() + minutes * 60 * 1000;
    HELP_LIVE_ID = Number(hid);

    const first = await getHelpPosition();
    if (!(await postHelpLivePoint(hid, first, true))) return;

    HELP_WATCH_ID = navigator.geolocation.watchPosition(
      async position => {
        if (Date.now() >= HELP_LIVE_DEADLINE) {
          await stopHelpLive(hid, true, 'Se terminó el tiempo de ubicación elegido.');
          return;
        }
        await postHelpLivePoint(hid, position, false);
        document.querySelector(`[data-live-status="${hid}"]`)?.replaceChildren(document.createTextNode(`GPS activo · precisión ${Math.round(position.coords.accuracy || 0)} m · actualizado ahora`));
      },
      error => {
        FA.toast(geoError(error), 'err');
        stopHelpLive(hid, false);
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
    );

    if (HELP_LIVE_TIMER) clearInterval(HELP_LIVE_TIMER);
    HELP_LIVE_TIMER = setInterval(async () => {
      if (Date.now() >= HELP_LIVE_DEADLINE) {
        await stopHelpLive(hid, true, 'Se terminó el tiempo de ubicación elegido.');
        return;
      }
      loadHelpTracking(hid);
    }, 3000);

    await loadHelpTracking(hid);
    FA.toast('GPS exacto en tiempo real activado.', 'ok');
  } catch (error) {
    FA.toast(geoError(error), 'err');
    await stopHelpLive(hid, false);
  }
}

async function stopHelpLive(hid, show = true, customMessage = '') {
  if (HELP_WATCH_ID !== null) {
    navigator.geolocation.clearWatch(HELP_WATCH_ID);
    HELP_WATCH_ID = null;
  }
  if (HELP_LIVE_TIMER) {
    clearInterval(HELP_LIVE_TIMER);
    HELP_LIVE_TIMER = null;
  }
  HELP_LIVE_ID = null;
  HELP_LIVE_DEADLINE = 0;

  const response = await FA.api('/api/location/stop', { method: 'POST', body: '{}' });
  if (show) FA.toast(customMessage || response.message || 'GPS detenido.', response.ok ? 'ok' : 'err');
  document.querySelector(`[data-live-status="${hid}"]`)?.replaceChildren(document.createTextNode('Ubicación detenida'));
}

async function loadHelpTracking(hid) {
  const response = await FA.api('/api/help/' + Number(hid) + '/tracking');
  if (!response.ok) return;
  const box = document.getElementById('track-' + hid);
  if (!box) return;
  const locations = response.live_locations || [];
  if (!locations.length) {
    box.innerHTML = '<span class="muted">Sin ubicación exacta activa.</span>';
    return;
  }
  box.innerHTML = locations.map(location => `
    <div>
      <b>${FA.escape(Number(location.user_id) === Number(window.CURRENT_USER_ID || 0) ? 'Tú' : ((location.names || '') + ' ' + (location.last_names || '')))}</b>
      <span>${FA.escape(Number(location.latitude).toFixed(6))}, ${FA.escape(Number(location.longitude).toFixed(6))}</span>
      <small>Actualizado ${FA.escape(location.updated_at)}</small>
    </div>
  `).join('');
}

document.querySelectorAll('.help-tabs .tab-btn').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.help-tabs .tab-btn').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.help-tab').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    document.getElementById(button.dataset.tab)?.classList.add('active');
    if (button.dataset.tab === 'mapa' && window.initCommunityMap) window.initCommunityMap();
  });
});

document.getElementById('helpForm')?.addEventListener('input', updateHelpPreview);
document.getElementById('liveAfterCreate')?.addEventListener('change', event => {
  if (event.target.checked && !document.getElementById('locationConsent')?.checked) {
    event.target.checked = false;
    FA.toast('Primero activa el consentimiento para compartir tu ubicación.', 'err');
  }
});
document.getElementById('locationConsent')?.addEventListener('change', event => {
  const live = document.getElementById('liveAfterCreate');
  if (live && !event.target.checked) live.checked = false;
});
document.getElementById('getHelpLocation')?.addEventListener('click', getHelpLocation);

document.getElementById('helpForm')?.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  const consent = document.getElementById('locationConsent')?.checked;
  const startLiveAfterCreate = document.getElementById('liveAfterCreate')?.checked;
  if (startLiveAfterCreate && !consent) {
    FA.toast('Para activar GPS en vivo debes aceptar el consentimiento.', 'err');
    return;
  }

  const response = await FA.api('/api/help', {
    method: 'POST',
    body: JSON.stringify({
      help_type: form.help_type.value,
      priority: form.priority.value,
      radius_m: form.radius_m.value,
      location_minutes: form.location_minutes.value,
      description: form.description.value,
      latitude: HELP_LOC?.lat ?? null,
      longitude: HELP_LOC?.lon ?? null
    })
  });

  FA.toast(response.message, response.ok ? 'ok' : 'err');
  if (!response.ok) return;

  const hid = response.id;
  form.reset();
  HELP_LOC = null;
  document.getElementById('helpLocStatus').textContent = 'Sin ubicación.';
  updateHelpPreview();
  await loadMyHelp();
  if (startLiveAfterCreate && hid) await startHelpLive(hid);
});

async function loadMyHelp() {
  const element = document.getElementById('myHelpRequests');
  if (!element) return;
  const response = await FA.api('/api/help/mine');
  if (!response.ok) return;

  element.innerHTML = (response.requests || []).slice(0, 15).map(help => `
    <div class="row">
      <div>
        <b>${FA.escape(help.help_type)}</b>
        <span>${FA.escape((help.description || '').slice(0, 100))} · ${FA.escape(help.status)}</span>
        ${help.latitude !== null ? `<small data-live-status="${help.id}">${FA.escape(help.sharing_location ? 'Ubicación temporal disponible' : 'Ubicación detenida')}</small><div id="track-${help.id}" class="live-track-box"></div>` : ''}
      </div>
      ${help.status === 'active' ? `<div class="actions">
        <button class="btn dark" type="button" onclick="editMyHelp(${help.id})">Editar</button>
        <button class="btn light" type="button" onclick="startHelpLive(${help.id})">Ubicación en vivo</button>
        <button class="btn danger" type="button" onclick="stopHelpLive(${help.id})">Detener GPS</button>
        <button class="btn light" type="button" onclick="completeMyHelp(${help.id})">Solucionado</button>
      </div>` : ''}
    </div>
  `).join('') || '<p class="muted">No tienes solicitudes.</p>';
}

async function editMyHelp(id) {
  const response = await FA.api('/api/help/mine');
  const help = (response.requests || []).find(item => Number(item.id) === Number(id));
  if (!help) return;

  const description = window.prompt('Descripción', help.description || '');
  if (description === null) return;
  const type = window.prompt('Qué necesitas', help.help_type || 'Otro') || help.help_type;
  const minutes = Number(window.prompt('Tiempo de ubicación: 15, 30, 60 o 120 minutos', '30') || 30);
  const update = await FA.api('/api/help/' + Number(id), {
    method: 'PUT',
    body: JSON.stringify({
      description,
      help_type: type,
      location_minutes: minutes,
      priority: help.priority
    })
  });
  FA.toast(update.message, update.ok ? 'ok' : 'err');
  if (update.ok) {
    await loadMyHelp();
    if (window.initCommunityMap) window.initCommunityMap();
  }
}

async function completeMyHelp(id) {
  if (!window.confirm('¿Marcar esta solicitud como solucionada?')) return;
  const response = await FA.api('/api/help/' + Number(id) + '/complete', { method: 'POST', body: '{}' });
  FA.toast(response.message, response.ok ? 'ok' : 'err');
  if (response.ok) {
    await stopHelpLive(id, false);
    await loadMyHelp();
    if (window.loadMapData) window.loadMapData();
  }
}

updateHelpPreview();
loadMyHelp();
setInterval(loadMyHelp, 5000);
