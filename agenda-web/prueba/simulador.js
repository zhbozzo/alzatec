// Simula los servicios de Apps Script en el navegador para probar Codigo.gs + Index.html sin Google.
// Datos de ejemplo inventados (prueba/datos.js). La planilla falsa queda en window.__PLANILLA__.
(function () {
  'use strict';
  var TZ = 'America/Santiago';
  var COLUMNAS = ['Fecha', 'Hora', 'Tipo', 'Cliente', 'Obra', 'Cotización', 'Camión', 'Estado', 'Nota de bodega',
    'Resumen', 'Correo', 'Historial', 'Hilo', 'UID', 'Aviso'];
  var ESTADOS = ['Agendado', 'Llegó', 'No llegó', 'Reagendado', 'Anulado', 'Revisar'];

  function partes(fecha, tz) {
    var f = new Intl.DateTimeFormat('en-CA', {timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false}).formatToParts(fecha);
    var p = {};
    f.forEach(function (x) { p[x.type] = x.value; });
    if (p.hour === '24') p.hour = '00';
    return p;
  }
  // Una celda de fecha de Sheets vuelve como Date a medianoche en la zona de la planilla
  function fechaCelda(iso) { return new Date(iso + 'T00:00:00-03:00'); }
  function verFecha(iso) {
    var d = new Date(iso + 'T12:00:00Z'), dn = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'][d.getUTCDay()];
    return dn + ' ' + iso.slice(8, 10) + '-' + iso.slice(5, 7) + '-' + iso.slice(0, 4);
  }

  // celdas: {valor, texto?, formula?}
  var planilla = {titulos: COLUMNAS.slice(), filas: [], escrituras: []};
  (window.__FILAS__ || []).forEach(function (f) {
    planilla.filas.push(COLUMNAS.map(function (c) {
      var v = f[c] === undefined ? '' : f[c];
      if (c === 'Fecha' && /^\d{4}-\d{2}-\d{2}$/.test(v)) return {valor: fechaCelda(v), visto: verFecha(v)};  // si no, texto escrito a mano
      return {valor: v, visto: String(v)};
    }));
  });
  window.__PLANILLA__ = planilla;
  window.__SIM__ = {fallar: null, usuario: 'pfarias@alzatec.com'};

  function celda(r, c) {
    if (r === 1) return {valor: planilla.titulos[c - 1] || '', visto: planilla.titulos[c - 1] || ''};
    var fila = planilla.filas[r - 2];
    return (fila && fila[c - 1]) || {valor: '', visto: ''};
  }
  function rango(r, c, nr, nc) {
    nr = nr || 1; nc = nc || 1;
    function mapa(fn) {
      var out = [];
      for (var i = 0; i < nr; i++) { var fila = []; for (var j = 0; j < nc; j++) fila.push(fn(celda(r + i, c + j))); out.push(fila); }
      return out;
    }
    return {
      getValues: function () { return mapa(function (x) { return x.valor; }); },
      getDisplayValues: function () { return mapa(function (x) { return x.visto; }); },
      setValue: function (v) {
        if (window.__SIM__.fallar) throw new Error(window.__SIM__.fallar);
        if (nr !== 1 || nc !== 1) throw new Error('setValue en un rango de varias celdas');
        var t = String(v), nueva;
        if (t.charAt(0) === "'") nueva = {valor: t.slice(1), visto: t.slice(1), comoTexto: true};
        else if (t.charAt(0) === '=') nueva = {valor: '#FORMULA', visto: '#FORMULA', formula: t};
        else nueva = {valor: v, visto: t};
        if (planilla.titulos[c - 1] === 'Estado' && ESTADOS.indexOf(t) < 0) throw new Error('Validación: estado no permitido');
        planilla.filas[r - 2][c - 1] = nueva;
        planilla.escrituras.push({fila: r, columna: planilla.titulos[c - 1], valor: t});
      }
    };
  }
  var hoja = {
    getName: function () { return 'Agenda'; },
    getLastRow: function () { return planilla.filas.length + 1; },
    getLastColumn: function () { return planilla.titulos.length; },
    getRange: rango
  };
  window.SpreadsheetApp = {
    openById: function (id) {
      if (id !== AGENDA_ID) throw new Error('openById con otro id: ' + id);
      return {getSheetByName: function (n) { return n === 'Agenda' ? hoja : null; },
        getSpreadsheetTimeZone: function () { return TZ; }};
    },
    flush: function () {}
  };
  window.Utilities = {
    formatDate: function (fecha, tz, patron) {
      var p = partes(fecha, tz);
      return patron.replace('yyyy', p.year).replace('MM', p.month).replace('dd', p.day).replace('HH', p.hour).replace('mm', p.minute);
    }
  };
  window.LockService = {getScriptLock: function () { return {waitLock: function () {}, releaseLock: function () {}}; }};
  window.Session = {getActiveUser: function () { return {getEmail: function () { return window.__SIM__.usuario; }}; }};
  window.HtmlService = {};

  function run(ok, mal) {
    return new Proxy({}, {get: function (_, nombre) {
      if (nombre === 'withSuccessHandler') return function (f) { return run(f, mal); };
      if (nombre === 'withFailureHandler') return function (f) { return run(ok, f); };
      return function () {
        // Como el servidor real: se ejecuta al pedir (lee la planilla en ese momento) y la respuesta llega después
        var args = JSON.parse(JSON.stringify([].slice.call(arguments))), r, error = null;
        try { r = JSON.parse(JSON.stringify(window[nombre].apply(null, args))); } catch (e) { error = e; }
        var demora = (window.__LATENCIA__ || {})[nombre] || 80;
        setTimeout(function () { if (error) { if (mal) mal(error); } else if (ok) ok(r); }, demora);
      };
    }});
  }
  window.google = {script: {run: run(null, null)}};
})();
