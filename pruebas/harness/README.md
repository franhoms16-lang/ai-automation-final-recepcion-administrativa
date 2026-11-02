# Harness de fallos sintéticos de FINAL_R01

Esta copia prueba rutas de control y recuperación. **No usa Google Sheets, Gemini, memoria ni herramientas reales y no demuestra éxito del caso de negocio.** El AI Agent se sustituye por un Code fixture; los `intermediateSteps` de ese nodo son datos sintéticos declarados.

`construir_harness.py` lee `../../workflow-recepcion-administrativa.json`, crea `workflow_harness.json` inactivo con ID `finalFaultHarnessR01` y guarda `metadata.json`: parent ID, hash del JSON fuente y hashes de los cuatro Code compartidos. Normalización, contexto, validación y confirmación se copian sin cambiar su texto. Se eliminan las credenciales y los subnodos de IA; el webhook es `/webhook/final-prueba-fallos`, separado del final.

El servidor solo escucha `127.0.0.1:5682`. No hace conexiones salientes. Requiere `--out` nuevo y conserva `estado.json` con filas, contadores y operaciones. `GET /snapshot` consulta esas filas por un recorrido independiente del append.

| Prefijo de evento | Falla inyectada en la primera operación pertinente |
| --- | --- |
| `falla-lectura` / `fallo-lectura` | GET de lectura responde 503, sin llegar a IA ni append |
| `fallo-ia` | Code fixture arroja error controlado; sin append |
| `fallo-json` | Fixture devuelve JSON inválido; validador rechaza antes del append |
| `fallo-escritura` | Primer append responde 503 sin guardar; un paso de recuperación posterior puede escribir después de comprobar ausencia |
| `acuse-perdido` | Guarda la fila, pero responde 503 en lugar del acuse de éxito |
| `acuse-incompleto` | Guarda la fila y responde 200 con `updates` sin los valores, para que el Code de confirmación lo rechace |

El servidor no deduplica. Si el workflow vuelve a ejecutar append indebidamente, se verá otra fila y el contador lo detectará. En los casos de confirmación perdida/incompleta, después del snapshot que localiza una fila se repite exactamente el evento: la copia del workflow debe responder duplicado sin otro append. No se simula un timeout de red literal: se simula la pérdida del acuse de éxito mediante un HTTP 503 posterior al guardado. Tampoco se simulan atomicidad o concurrencia.

Preparación y ejecución a cargo del ejecutor principal, con el Python existente:

```powershell
python -B construir_harness.py
# Importar y habilitar solo workflow_harness.json en n8n local.
python -B servidor.py --out <directorio_nuevo_estado>
# En otra terminal, con el servidor ya iniciado:
python -B probar_harness.py --out <directorio_nuevo_evidencia>
```

El cliente exige estado inicial vacío y realiza once peticiones de escenario, incluidas las recuperaciones explícitas y un conflicto por mismo ID. Guarda petición, HTTP, respuesta y snapshot después de cada caso. Se detiene ante cualquier diferencia, sin reintentos por resultados inesperados. Los pasos de recuperación solo se habilitan por haber obtenido el snapshot conforme del paso anterior.

Antes de usar los resultados, cotejar también las ejecuciones guardadas por n8n: rama recorrida, versión del clone y ausencia de nodos que no debían ejecutarse. Un rótulo `Succeeded` en una rama de error no es éxito del negocio. El ejecutor debe detener este servidor temporal al terminar.
