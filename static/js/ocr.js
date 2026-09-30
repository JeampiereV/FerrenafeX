(() => {
  const $ = id => document.getElementById(id);
  const file = $('ocrFile');
  const drop = $('ocrDrop');
  const meta = $('ocrMeta');
  const form = $('ocrForm');
  const progress = $('ocrProgress');
  const result = $('ocrResult');
  const text = $('ocrText');
  let selected = null;

  function setProgress(percent, message) {
    $('ocrStatus').textContent = message;
    $('ocrPercent').textContent = `${percent}%`;
    $('ocrProgressBar').style.width = `${percent}%`;
  }

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  }

  function showFile(f) {
    selected = f || null;
    if (!selected) return;
    meta.classList.remove('hidden');
    meta.textContent = `${selected.name} · ${formatSize(selected.size)} · ${selected.type || 'tipo no declarado'}`;
  }

  $('ocrPick')?.addEventListener('click', () => file.click());
  file?.addEventListener('change', () => showFile(file.files?.[0]));
  ['dragenter', 'dragover'].forEach(eventName => drop.addEventListener(eventName, event => {
    event.preventDefault();
    drop.classList.add('is-dragging');
  }));
  ['dragleave', 'drop'].forEach(eventName => drop.addEventListener(eventName, event => {
    event.preventDefault();
    drop.classList.remove('is-dragging');
  }));
  drop.addEventListener('drop', event => showFile(event.dataTransfer.files?.[0]));

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!selected) {
      FA.toast('Selecciona un archivo.', 'err');
      return;
    }
    const formData = new FormData();
    formData.append('file', selected);
    formData.append('language', $('ocrLanguage').value);
    progress.classList.remove('hidden');
    result.classList.add('hidden');
    setProgress(15, 'Subiendo documento…');
    const timer = setInterval(() => {
      const current = parseInt($('ocrPercent').textContent, 10) || 15;
      if (current < 90) setProgress(current + 5, 'Procesando documento…');
    }, 700);
    try {
      const response = await fetch('/api/tools/ocr', {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRF-Token': document.querySelector('meta[name=csrf-token]')?.content || '' }
      });
      let data = {};
      try { data = await response.json(); } catch (_) {}
      clearInterval(timer);
      if (!response.ok || !data.ok) {
        setProgress(0, data.message || 'No se pudo procesar el documento.');
        FA.toast(data.message || 'No se pudo procesar el documento.', 'err');
        return;
      }
      setProgress(100, 'Procesamiento completado');
      text.value = data.text || '';
      $('ocrPages').textContent = `Páginas procesadas: ${data.processed_pages ?? '—'}`;
      result.classList.remove('hidden');
    } catch (_) {
      clearInterval(timer);
      FA.toast('No se pudo conectar con el servicio OCR.', 'err');
      setProgress(0, 'Error de conexión');
    }
  });

  $('copyOcr')?.addEventListener('click', async () => {
    await navigator.clipboard.writeText(text.value);
    FA.toast('Texto copiado.', 'ok');
  });

  document.querySelectorAll('[data-export]').forEach(button => button.addEventListener('click', async () => {
    const response = await fetch('/api/tools/ocr/export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': document.querySelector('meta[name=csrf-token]')?.content || ''
      },
      body: JSON.stringify({ text: text.value, format: button.dataset.export })
    });
    if (!response.ok) {
      let data = {};
      try { data = await response.json(); } catch (_) {}
      FA.toast(data.message || 'No se pudo exportar.', 'err');
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ocr_resultado.${button.dataset.export}`;
    link.click();
    URL.revokeObjectURL(url);
  }));
})();
