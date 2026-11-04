// Prueba de punta a punta de la app web de la agenda, sin Google: corre Codigo.gs con una planilla falsa
// (simulador.js + datos.js inventados) y maneja Index.html en Chromium.
//   node agenda-web/prueba/probar.js [carpeta-para-capturas]
// Sale con código 1 si algo falla.
const fs = require('fs');
const path = require('path');
const {chromium, devices} = require('playwright');

const dir = __dirname;
const leer = (f) => fs.readFileSync(path.join(dir, f), 'utf8');
const HTML = leer('../Index.html');
// Codigo.gs se evalúa en el ámbito global (como en Apps Script): Playwright envuelve los scripts en una función
const SCRIPTS = [leer('datos.js'), '(0, eval)(' + JSON.stringify(leer('../Codigo.gs')) + ');', leer('simulador.js')];
const CAPTURAS = process.argv[2] || '';
const MIERCOLES = new Date('2026-11-04T11:20:00-03:00');
const DOMINGO = new Date('2026-11-08T10:00:00-03:00');

let fallas = 0, pasadas = 0;
function ok(cond, texto) {
  if (cond) { pasadas++; console.log('  ✓ ' + texto); } else { fallas++; console.log('  ✗ ' + texto); }
}

async function abrir(browser, opciones, hora) {
  const contexto = await browser.newContext({timezoneId: 'America/Santiago', locale: 'es-CL', ...opciones});
  const page = await contexto.newPage();
  const errores = [];
  page.on('pageerror', (e) => errores.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errores.push(m.text()); });
  page.on('dialog', async (d) => { errores.push('diálogo inesperado: ' + d.message()); await d.dismiss(); });
  await page.clock.setFixedTime(hora || MIERCOLES);
  for (const s of SCRIPTS) await page.addInitScript({content: s});
  await page.route('https://agenda.prueba/**', (r) => r.fulfill({status: 200, contentType: 'text/html; charset=utf-8', body: HTML}));
  await page.goto('https://agenda.prueba/');
  await page.waitForSelector('.mov', {state: 'attached', timeout: 8000});
  return {page, contexto, errores};
}

const hoja = (page, uid) => page.evaluate((uid) => {
  const p = window.__PLANILLA__, i = p.titulos.indexOf('UID');
  const f = p.filas.find((x) => String(x[i].valor) === uid);
  const o = {};
  p.titulos.forEach((t, k) => { o[t] = f[k].valor; o[t + ':formula'] = !!f[k].formula; });
  return o;
}, uid);
const tarjeta = (page, uid, fecha) => page.locator(`#grilla .mov[data-abrir^="${uid}|${fecha}|"]`);
const toast = (page) => page.locator('#toast.ver');
async function esperarGuardado(page) {
  await page.waitForFunction(() => !document.querySelector('.mov.guardando') && /Actualizado/.test(document.getElementById('sync').textContent));
}
async function captura(page, nombre) {
  if (CAPTURAS) await page.screenshot({path: path.join(CAPTURAS, nombre), fullPage: false});
}

(async () => {
  const browser = await chromium.launch();

  console.log('Escritorio (miércoles 4-nov 11:20)');
  let {page, contexto, errores} = await abrir(browser, {viewport: {width: 1440, height: 900}, deviceScaleFactor: CAPTURAS ? 2 : 1});
  ok(await page.textContent('#titulo') === '2 – 8 nov 2026', 'título de la semana: 2 – 8 nov 2026');
  ok(await page.textContent('#relativa') === 'Esta semana', 'marca "Esta semana"');
  ok(await page.locator('#grilla .cab').count() === 8, 'muestra lunes a domingo (hay un movimiento el domingo)');
  ok((await page.textContent('#grilla .cab.hoy .num')).trim() === '4', 'el miércoles 4 está marcado como hoy');
  ok(await page.locator('#grilla .mov').count() === 14, '14 movimientos en la semana');
  ok(await page.locator('#grilla img').count() === 0 && (await page.textContent('#grilla')).includes('<img src=x'), 'el texto de un correo no se interpreta como HTML');
  ok(await page.locator('#grilla .gutter.sinhora').count() === 1, 'fila "Sin hora" para "a primera hora"');
  ok(await page.locator('.linea-ahora').count() === 1, 'línea de la hora actual en el día de hoy');
  ok(await tarjeta(page, '1004', '2026-11-03').evaluate((e) => e.classList.contains('falta')), 'lo de ayer sin marcar sale como "¿Llegó?"');
  ok(/1 no llegó/.test(await page.textContent('#resumen')) && /sin marcar/.test(await page.textContent('#resumen')), 'resumen de la semana con no llegaron y sin marcar');
  ok(await page.locator('.sin-fecha .mov').count() === 1, 'lo que no tiene fecha aparece abajo para revisar');
  await captura(page, 'semana.png');

  // ✓ Llegó y desmarcar
  await tarjeta(page, '1006', '2026-11-04').locator('button.ok').click();
  await esperarGuardado(page);
  let f = await hoja(page, '1006');
  ok(f['Estado'] === 'Llegó', '✓ marca "Llegó" en la planilla');
  ok(/pfarias: Agendado → Llegó$/.test(f['Historial']), 'el Historial anota quién y qué cambió');
  ok(await tarjeta(page, '1006', '2026-11-04').evaluate((e) => e.classList.contains('e-llego')), 'la tarjeta queda verde');
  await tarjeta(page, '1006', '2026-11-04').locator('button.ok').click();
  await esperarGuardado(page);
  ok((await hoja(page, '1006'))['Estado'] === 'Agendado', 'tocar ✓ otra vez desmarca (vuelve a Agendado)');

  // Deshacer desde el aviso
  await tarjeta(page, '1008', '2026-11-04').locator('button.ok').click();
  await esperarGuardado(page);
  await page.click('#t-accion');
  await page.waitForFunction(() => /Listo, quedó como Agendado/.test(document.getElementById('toast').textContent));
  await esperarGuardado(page);
  ok((await hoja(page, '1008'))['Estado'] === 'Agendado', '"Deshacer" devuelve el estado anterior');

  // ✗ No llegó con confirmación
  await tarjeta(page, '1007', '2026-11-04').locator('button.no').click();
  ok(await page.isVisible('#modal'), '✗ pide confirmar antes de avisar a pendientes');
  ok(/con copia a Javier/.test(await page.textContent('#m-texto')), 'la confirmación dice a quién se avisa (devolución → Javier)');
  await page.click('#m-no');
  ok((await hoja(page, '1007'))['Estado'] === 'Agendado', 'cancelar no cambia nada');
  await tarjeta(page, '1007', '2026-11-04').locator('button.no').click();
  await page.click('#m-si');
  await esperarGuardado(page);
  ok((await hoja(page, '1007'))['Estado'] === 'No llegó', 'confirmar marca "No llegó"');

  // Llegó en una fecha futura pide confirmación
  await tarjeta(page, '1013', '2026-11-06').locator('button.ok').click();
  ok(await page.isVisible('#modal') && /todavía no llega/.test(await page.textContent('#m-texto')), 'marcar llegó algo futuro pide confirmar');
  await page.keyboard.press('Escape');
  ok(!(await page.isVisible('#modal')) && (await hoja(page, '1013'))['Estado'] === 'Revisar', 'Esc cancela');

  // Panel de detalle y nota
  await tarjeta(page, '1008', '2026-11-04').click({position: {x: 20, y: 30}});
  ok(await page.isVisible('#detalle'), 'tocar la tarjeta abre el detalle');
  ok(/miércoles 4 de noviembre · 14:00/.test(await page.textContent('.d-cuando')), 'el detalle muestra el día y la hora');
  ok(await page.isDisabled('#d-guardar'), '"Guardar nota" parte desactivado');
  await page.fill('#d-nota', '=1+1 llegó tarde');
  await captura(page, 'detalle.png');
  await page.click('#d-guardar');
  await esperarGuardado(page);
  f = await hoja(page, '1008');
  ok(f['Nota de bodega'] === '=1+1 llegó tarde' && !f['Nota de bodega:formula'], 'la nota se guarda como texto, nunca como fórmula');
  await page.click('#detalle [data-estado="No llegó"]');
  await page.click('#m-si');
  await esperarGuardado(page);
  ok((await hoja(page, '1008'))['Estado'] === 'No llegó' && /con copia a Andrea/.test(await page.textContent('#detalle')), 'desde el detalle: No llegó (despacho → Andrea)');
  await page.click('#detalle [data-estado="Agendado"]');
  await esperarGuardado(page);
  ok((await hoja(page, '1008'))['Estado'] === 'Agendado', 'desde el detalle: desmarcar');
  await page.keyboard.press('Escape');
  ok(!(await page.isVisible('#detalle')), 'Esc cierra el detalle');

  // Semanas
  await page.click('#b-sig');
  await page.waitForFunction(() => document.getElementById('titulo').textContent === '9 – 14 nov 2026');
  await page.waitForSelector('#grilla .mov');
  ok(await page.textContent('#relativa') === 'Próxima semana' && await page.locator('#grilla .mov').count() === 2, '› semana siguiente: 9 – 14 nov, 2 movimientos');
  await page.click('#b-ant');
  await page.click('#b-ant');
  await page.waitForFunction(() => document.getElementById('titulo').textContent === '26 – 31 oct 2026');
  await page.waitForSelector('#grilla .mov');
  ok(await page.textContent('#relativa') === 'Semana pasada' && await page.locator('#grilla .mov').count() === 1, '‹ semana anterior: 26 – 31 oct');
  await page.click('#b-hoy');
  await page.waitForFunction(() => document.getElementById('titulo').textContent === '2 – 8 nov 2026');
  ok(true, '"Hoy" vuelve a esta semana');
  await page.keyboard.press('ArrowRight');
  await page.waitForFunction(() => document.getElementById('titulo').textContent === '9 – 14 nov 2026');
  await page.keyboard.press('t');
  await page.waitForFunction(() => document.getElementById('titulo').textContent === '2 – 8 nov 2026');
  ok(true, 'teclas → y T para moverse');

  // Filtros
  await page.uncheck('#f-devo');
  ok(await page.locator('#grilla .mov.devo').count() === 0 && await page.locator('#grilla .mov.desp').count() === 7, 'filtro: solo despachos');
  await page.check('#f-devo');

  // Tabla
  await page.click('[data-vista="tabla"]');
  ok(await page.isVisible('#v-tabla') && await page.locator('#cuerpo-tabla tr').count() === 14, 'vista tabla con los 14 de la semana');
  await page.fill('#buscar', 'andes');
  ok(await page.locator('#cuerpo-tabla tr').count() === 3, 'buscar "andes" deja 3');
  await page.fill('#buscar', '');
  await page.selectOption('#cuerpo-tabla select[data-estado-k^="1005|"]', 'Llegó');
  await esperarGuardado(page);
  ok((await hoja(page, '1005'))['Estado'] === 'Llegó', 'cambiar el estado desde la tabla');
  await page.selectOption('#cuerpo-tabla select[data-estado-k^="1006|"]', 'No llegó');
  await page.click('#m-no');
  await page.waitForTimeout(100);
  ok((await hoja(page, '1006'))['Estado'] === 'Agendado' && await page.inputValue('#cuerpo-tabla select[data-estado-k^="1006|"]') === 'Agendado', 'cancelar en la tabla deja la lista como estaba');
  await page.click('th[data-orden="cliente"]');
  ok((await page.textContent('#cuerpo-tabla tr:first-child td:nth-child(4)')).startsWith('<img'), 'ordenar por cliente');
  await page.check('#todas');
  await page.waitForFunction(() => /18 movimientos/.test(document.getElementById('cuenta').textContent));
  ok(true, '"Todas las fechas" trae todo (18, con el que no tiene fecha)');
  await captura(page, 'tabla.png');
  await page.uncheck('#todas');
  await page.click('[data-vista="semana"]');

  // Error de permiso al guardar
  await page.evaluate(() => { window.__SIM__.fallar = 'Exception: You do not have permission to access the requested document.'; });
  await tarjeta(page, '1009', '2026-11-04').locator('button.ok').click();
  await page.waitForFunction(() => document.getElementById('toast').classList.contains('error'));
  ok(/pidan|Pide que te la compartan como Editor/.test(await page.textContent('#toast')), 'sin permiso: explica que hay que compartirla como Editor');
  ok((await hoja(page, '1009'))['Estado'] === 'Agendado' && !(await tarjeta(page, '1009', '2026-11-04').evaluate((e) => e.classList.contains('e-llego'))), 'y la tarjeta vuelve a como estaba');
  await page.evaluate(() => { window.__SIM__.fallar = null; });

  // Pasa la semana con la página abierta: se mueve sola
  await page.clock.setFixedTime(DOMINGO);
  await page.click('#sync');
  await page.waitForFunction(() => document.getElementById('titulo').textContent === '9 – 14 nov 2026', null, {timeout: 5000});
  ok(true, 'con la página abierta, el domingo pasa sola a la semana siguiente');
  ok(errores.length === 0, 'sin errores en la consola' + (errores.length ? ': ' + errores.join(' | ') : ''));
  await contexto.close();

  console.log('Abrir un domingo');
  ({page, contexto, errores} = await abrir(browser, {viewport: {width: 1280, height: 800}}, DOMINGO));
  ok(await page.textContent('#titulo') === '9 – 14 nov 2026' && await page.textContent('#relativa') === 'Próxima semana', 'el domingo abre en la semana siguiente');
  await contexto.close();

  console.log('Celular (iPhone 13)');
  ({page, contexto, errores} = await abrir(browser, {...devices['iPhone 13']}));
  ok(await page.locator('#dias-movil button').count() === 7, 'tira de días de la semana');
  ok(await page.getAttribute('#dias-movil button[data-dia="2026-11-04"]', 'aria-pressed') === 'true', 'parte en el día de hoy');
  ok(await page.locator('#lista-dia .mov').count() === 5, 'lista de hoy: 5 movimientos');
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), 'sin desplazamiento horizontal');
  const caja = await page.locator('#lista-dia .mov').first().locator('button.ok').boundingBox();
  ok(caja && caja.width >= 32 && caja.height >= 32, 'botones ✓ ✗ de buen tamaño para el dedo');
  await captura(page, 'celular.png');
  await page.tap('#dias-movil button[data-dia="2026-11-05"]');
  ok(await page.locator('#lista-dia .mov').count() === 2 && /Jueves 5 de noviembre/.test(await page.textContent('#lista-dia h3')), 'tocar el jueves muestra ese día');
  await page.locator('#lista-dia .mov').nth(1).tap({position: {x: 30, y: 30}});
  ok(await page.isVisible('#detalle'), 'el detalle se abre desde abajo');
  await captura(page, 'celular-detalle.png');
  await page.tap('#detalle [data-estado="Llegó"]');
  ok(await page.isVisible('#modal'), 'es para mañana: pide confirmar');
  await page.tap('#m-si');
  await page.waitForFunction(() => /Marcado: Llegó/.test(document.getElementById('toast').textContent));
  ok((await hoja(page, '1011'))['Estado'] === 'Llegó', 'marcar desde el celular');
  ok(errores.length === 0, 'sin errores en la consola' + (errores.length ? ': ' + errores.join(' | ') : ''));
  await contexto.close();

  console.log('Fuera de Apps Script');
  const ctx = await browser.newContext();
  const p2 = await ctx.newPage();
  await p2.route('https://agenda.prueba/**', (r) => r.fulfill({status: 200, contentType: 'text/html; charset=utf-8', body: HTML}));
  await p2.goto('https://agenda.prueba/');
  await p2.waitForSelector('#banner:not([hidden])');
  ok(/enlace de la app web/.test(await p2.textContent('#banner')), 'sin Apps Script explica cómo abrirla');
  await ctx.close();

  await browser.close();
  console.log(`\n${pasadas} pasadas, ${fallas} fallas`);
  process.exit(fallas ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
