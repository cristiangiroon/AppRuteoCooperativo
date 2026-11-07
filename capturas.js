// Genera capturas de la app para el artículo: node app/capturas.js
const { chromium } = require('playwright');
const OUT = process.argv[2] || 'figuras';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.setDefaultTimeout(600000);
  await page.goto('http://localhost:8501');
  await page.getByText('RutaDron Cauca').first().waitFor();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/app_1_datos.png`, fullPage: false });

  async function optimizar(nombre, lluvias, esperar = null) {
    const inp = page.getByLabel('Nombre del escenario');
    await inp.fill(nombre); await inp.press('Enter');
    await page.getByText(lluvias ? 'Lluvias' : 'Seca', { exact: true }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole('tab', { name: /Optimizar/ }).click();
    await page.getByRole('button', { name: /Optimizar plan/ }).click();
    await page.getByText(esperar || `${nombre} – temporada`).first().waitFor();
    await page.waitForTimeout(2500);
  }
  await optimizar('Camión + dron', true);
  await page.screenshot({ path: `${OUT}/app_2_resultado_lluvias.png` });
  await page.getByRole('button', { name: /Guardar para comparar/ }).scrollIntoViewIfNeeded();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${OUT}/app_2b_tabla_rutas.png` });
  await page.getByRole('button', { name: /Guardar para comparar/ }).click();
  await page.waitForTimeout(1500);

  // Escenario solo camión en lluvias
  await page.getByText('Permitir entregas con dron').click();
  await page.waitForTimeout(1000);
  await optimizar('Solo camión', true);
  await page.getByRole('button', { name: /Guardar para comparar/ }).click();
  await page.waitForTimeout(1500);

  // Infactible: solo camión, flota 2, lluvias
  const flota = page.getByLabel('Camiones disponibles');
  await flota.fill('2'); await flota.press('Enter');
  await page.waitForTimeout(1000);
  await optimizar('Solo camión, 2 camiones', true, 'No existe un plan');
  await page.screenshot({ path: `${OUT}/app_4_infactible.png`, fullPage: false });
  await page.getByRole('tab', { name: /Comparar/ }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/app_3_comparacion.png` });
  await browser.close();
})();
