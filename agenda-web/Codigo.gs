/**
 * Agenda de camiones · Alzatec (app web de Google Apps Script)
 *
 * Muestra la hoja "Agenda" como un calendario semanal y deja marcar qué pasó con cada camión.
 * La hoja la llena el clasificador de correos; esta app solo cambia Estado, Nota de bodega e Historial.
 * Si alguien marca "No llegó", el clasificador avisa a pendientes en los minutos siguientes.
 *
 * Implementar como app web con:
 *   Ejecutar como: "Usuario que accede a la aplicación web"
 *   Quién tiene acceso: "Cualquier usuario con cuenta de Google"
 * Así solo la ve quien tiene la planilla compartida, y solo los editores pueden marcar.
 * Instrucciones completas: docs/12-agenda.md del repositorio.
 */

var AGENDA_ID = '1E_-OoaJFamsrI8Nlhr-J7qNSXuWpoAYkNYJQiwugXMA';
var HOJA = 'Agenda';
var ESTADOS = ['Agendado', 'Llegó', 'No llegó', 'Reagendado', 'Anulado', 'Revisar'];
var CAMPOS = {
  'Fecha': 'fecha', 'Hora': 'hora', 'Tipo': 'tipo', 'Cliente': 'cliente', 'Obra': 'obra',
  'Cotización': 'cotizacion', 'Camión': 'camion', 'Estado': 'estado', 'Nota de bodega': 'nota',
  'Resumen': 'resumen', 'Correo': 'correo', 'Historial': 'historial', 'UID': 'uid', 'Aviso': 'aviso'
};
var NECESARIAS = ['Fecha', 'Hora', 'Tipo', 'Estado', 'Nota de bodega', 'Historial', 'UID'];
var LARGO_NOTA = 500;
var DIAS_ATRASO = 14;  // lo sin marcar de hasta 2 semanas antes se avisa arriba

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
      .setTitle('Agenda de camiones · Alzatec')
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/** Movimientos con fecha entre desde y hasta (texto AAAA-MM-DD, ambos incluidos; vacíos = sin límite),
 *  más los que no tienen fecha (salvo anulados), que siempre van para que nadie los pierda de vista. */
function leer(desde, hasta) {
  var x = abrir_();
  var ahora = new Date();
  var salida = {
    hoy: Utilities.formatDate(ahora, x.zona, 'yyyy-MM-dd'),
    ahora: Utilities.formatDate(ahora, x.zona, 'HH:mm'),
    usuario: usuario_(),
    movimientos: []
  };
  var limite = Utilities.formatDate(new Date(ahora.getTime() - DIAS_ATRASO * 86400000), x.zona, 'yyyy-MM-dd');
  salida.atrasados = {cantidad: 0, ultima: ''};
  todos_(x).forEach(function (m) {
    if (m.fecha) {
      if (desde && m.fecha < desde && m.estado === 'Agendado' && m.fecha >= limite) {
        salida.atrasados.cantidad++;  // de semanas anteriores y nadie marcó si llegó
        if (m.fecha > salida.atrasados.ultima) salida.atrasados.ultima = m.fecha;
      }
      if ((desde && m.fecha < desde) || (hasta && m.fecha > hasta)) return;
    } else if (m.estado === 'Anulado') {
      return;
    }
    salida.movimientos.push(m);
  });
  return salida;
}

/** Cambia el estado y/o la nota de un movimiento y lo anota en el Historial.
 *  c = {fila, clave, estado?, nota?}. La fila es solo una pista: el movimiento se busca por su clave
 *  (UID, fecha y tipo) por si alguien ordenó la hoja. Devuelve el movimiento como quedó. */
function cambiar(c) {
  if (!c || !c.clave) throw new Error('Falta indicar el movimiento.');
  if (c.estado !== undefined && ESTADOS.indexOf(c.estado) < 0) throw new Error('Estado no válido: ' + c.estado);
  if (c.nota !== undefined && String(c.nota).length > LARGO_NOTA) {
    throw new Error('La nota es muy larga (máximo ' + LARGO_NOTA + ' caracteres).');
  }
  var candado = LockService.getScriptLock();
  candado.waitLock(20000);
  try {
    var x = abrir_();
    var fila = ubicar_(x, c);
    if (!fila) throw new Error('No encontré ese movimiento en la planilla (puede que lo hayan borrado). Actualiza la página.');
    var actual = leerFila_(x, fila);
    var cambios = [];
    if (c.estado !== undefined && c.estado !== actual.estado) {
      x.hoja.getRange(fila, x.col['Estado'] + 1).setValue(c.estado);
      cambios.push((actual.estado || 'sin estado') + ' → ' + c.estado);
    }
    if (c.nota !== undefined) {
      var nota = String(c.nota).replace(/\s+$/, '');
      if (nota !== actual.nota) {
        x.hoja.getRange(fila, x.col['Nota de bodega'] + 1).setValue(seguro_(nota));
        cambios.push(nota ? 'nota: "' + recortar_(nota, 60) + '"' : 'borró la nota');
      }
    }
    if (cambios.length) {
      var linea = Utilities.formatDate(new Date(), x.zona, 'dd-MM HH:mm') + ' ' + (quien_() || 'app') + ': ' + cambios.join(', ');
      var historial = actual.historial ? actual.historial + ' | ' + linea : linea;
      x.hoja.getRange(fila, x.col['Historial'] + 1).setValue(seguro_(historial));
      SpreadsheetApp.flush();
    }
    return releer_(x, fila);
  } finally {
    candado.releaseLock();
  }
}

// --- Internas --------------------------------------------------------------------------------------

function abrir_() {
  var ss = SpreadsheetApp.openById(AGENDA_ID);
  var hoja = ss.getSheetByName(HOJA);
  if (!hoja) throw new Error('No encuentro la hoja "' + HOJA + '" en la planilla.');
  var ancho = hoja.getLastColumn();
  var titulos = hoja.getRange(1, 1, 1, ancho).getValues()[0];
  var col = {};
  for (var i = 0; i < titulos.length; i++) col[String(titulos[i]).trim()] = i;
  for (var k = 0; k < NECESARIAS.length; k++) {
    if (!(NECESARIAS[k] in col)) throw new Error('A la hoja Agenda le falta la columna "' + NECESARIAS[k] + '".');
  }
  return {ss: ss, hoja: hoja, col: col, ancho: ancho, zona: ss.getSpreadsheetTimeZone() || 'America/Santiago'};
}

function leerFila_(x, fila) {
  var r = x.hoja.getRange(fila, 1, 1, x.ancho);
  return movimiento_(r.getValues()[0], r.getDisplayValues()[0], x) || {};
}

/** El movimiento como quedó, con la misma clave que le da leer(). */
function releer_(x, fila) {
  var todos = todos_(x);
  for (var i = 0; i < todos.length; i++) if (todos[i].fila === fila) return todos[i];
  return leerFila_(x, fila);
}

function movimiento_(valores, vistos, x) {
  var m = {};
  for (var nombre in CAMPOS) {
    var i = x.col[nombre];
    m[CAMPOS[nombre]] = i === undefined ? '' : texto_(valores[i], vistos[i], nombre, x.zona);
  }
  if (!m.fecha && !m.tipo && !m.cliente && !m.estado) return null;  // fila vacía
  if (m.fecha && !/^\d{4}-\d{2}-\d{2}$/.test(m.fecha)) {  // fecha escrita a mano que no se entiende
    m.fechaTexto = m.fecha;
    m.fecha = '';
  }
  m.clave = clave_(m);
  return m;
}

function clave_(m) {
  return [m.uid, m.fecha, m.tipo, m.uid ? '' : m.cliente + '·' + m.hora].join('|');
}

function ubicar_(x, c) {
  var todos = todos_(x);
  for (var i = 0; i < todos.length; i++) if (todos[i].clave === c.clave) return todos[i].fila;
  return 0;
}

/** Todas las filas con su clave. Si dos filas tienen el mismo UID, fecha y tipo (puede pasar), la segunda
 *  lleva "#2" en la clave: así la app nunca confunde una con otra. */
function todos_(x) {
  var n = x.hoja.getLastRow();
  if (n < 2) return [];
  var rango = x.hoja.getRange(2, 1, n - 1, x.ancho);
  var valores = rango.getValues(), vistos = rango.getDisplayValues(), vistas = {}, salida = [];
  for (var i = 0; i < valores.length; i++) {
    var m = movimiento_(valores[i], vistos[i], x);
    if (!m) continue;
    vistas[m.clave] = (vistas[m.clave] || 0) + 1;
    if (vistas[m.clave] > 1) m.clave += '#' + vistas[m.clave];
    m.fila = i + 2;
    salida.push(m);
  }
  return salida;
}

/** Texto de una celda. La fecha va como AAAA-MM-DD y la hora como HH:MM, se vean como se vean. */
function texto_(valor, visto, nombre, zona) {
  if (valor === null || valor === undefined || valor === '') return '';
  if (nombre === 'Fecha') {
    if (Object.prototype.toString.call(valor) === '[object Date]') {
      return isNaN(valor.getTime()) ? '' : Utilities.formatDate(valor, zona, 'yyyy-MM-dd');
    }
    if (typeof valor === 'number') return isoDeSerial_(valor);
    var t = String(valor).trim(), iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(t);
    return iso ? iso[0] : t;
  }
  if (nombre === 'Hora') {
    // Lo que se ve: una hora escrita a mano se guarda como fecha de 1899 y convertirla da minutos raros
    var h = /^(\d{1,2}):(\d{2})/.exec(String(visto || valor).trim());
    return h ? ('0' + h[1]).slice(-2) + ':' + h[2] : String(visto || valor).trim();
  }
  if (typeof valor === 'number' || Object.prototype.toString.call(valor) === '[object Date]') {
    return String(visto || valor).trim();  // lo que se ve: "14:30" y no "Sat Dec 30 1899…"
  }
  return String(valor).trim();
}

function isoDeSerial_(n) {
  var d = new Date(Date.UTC(1899, 11, 30) + Math.floor(n) * 86400000);
  return d.toISOString().slice(0, 10);
}

/** Se guarda siempre como texto: una nota nunca es fórmula, y "14:30" o "3/4" no se vuelven hora ni fecha. */
function seguro_(t) {
  t = String(t);
  return t ? "'" + t : t;
}

function recortar_(t, n) {
  return t.length > n ? t.slice(0, n - 1) + '…' : t;
}

function usuario_() {
  try {
    return Session.getActiveUser().getEmail() || '';
  } catch (e) {
    return '';
  }
}

function quien_() {
  return usuario_().split('@')[0];
}
