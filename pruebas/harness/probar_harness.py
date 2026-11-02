"""Batería HTTP de fallos SINTÉTICOS. Ejecutar solo contra el clone local.

El servidor de fixtures y n8n deben estar iniciados por el ejecutor. La batería
no arranca servicios. Una recuperación es un paso explícito del escenario y
solo se ejecuta si el snapshot anterior confirmó el resultado esperado. Ante
cualquier resultado inesperado se detiene, conserva evidencia y no reintenta.
"""
from __future__ import annotations

import argparse
import copy
import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

WEBHOOK = "http://localhost:5678/webhook/final-prueba-fallos"
SNAPSHOT = "http://127.0.0.1:5682/snapshot"
MENSAJE = "Soy Persona Demo Harness. Quiero una primera consulta para el 24/11/2026 por la tarde."


def guardar(path: Path, body: object) -> None:
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request(url: str, payload: dict | None = None) -> tuple[int, object, str]:
    req = urllib.request.Request(url, method="GET" if payload is None else "POST",
          data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8"),
          headers={} if payload is None else {"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=40)
    except urllib.error.HTTPError as err:
        response = err
    with response:
        status = response.code
        raw = response.read().decode("utf-8")
        return status, json.loads(raw), raw


def fila_desde_solicitud(s: dict) -> list[str]:
    j = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return [s["evento_id"], j([s["telefono"], s["mensaje"]]), s["fecha_recepcion"], s["telefono"], s["mensaje"],
            s["tipo"], s["accion"], s["nombre"] or "", s["preferencia_turno"] or "", j(s["faltantes"]), j(s["alertas"]),
            str(s["derivar_profesional"]).lower(), s["borrador"], s["estado"], s["config_version"], s["ejecucion_id"],
            s["version_flujo"], j(s["temas_consultados"]), s["canal"], s["prioridad"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="Directorio de evidencia NUEVO.")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    try:
        status, inicial, raw = request(SNAPSHOT)
        guardar(args.out / "00_snapshot_inicial.json", {"http": status, "respuesta": inicial, "texto": raw})
        if status != 200 or not isinstance(inicial, dict) or inicial.get("tipo") != "SERVIDOR_SINTETICO_NO_GOOGLE" or inicial.get("total_filas") != 0 or inicial.get("read_por_evento") or inicial.get("append_por_evento"):
            raise ValueError("La batería exige un servidor sintético nuevo, sin operaciones ni filas previas.")
    except Exception as err:
        guardar(args.out / "resumen.json", {"tipo": "PRUEBA_SINTETICA_NO_NEGOCIO", "completa": False,
                "ejecutados": 0, "fallo": type(err).__name__ + ": " + str(err), "sin_reintentos": True})
        return 1
    sufijo = uuid.uuid4().hex
    telefono = "54911" + f"{int(uuid.uuid4().hex[:12], 16) % 10_000_000:07d}" + "0"
    eventos = {prefijo: prefijo + "-" + sufijo for prefijo in ("falla-lectura", "fallo-ia", "fallo-json", "normal", "fallo-escritura", "acuse-perdido", "acuse-incompleto")}
    payloads = {key: {"evento_id": evento, "from": telefono, "text": {"body": MENSAJE}} for key, evento in eventos.items()}
    # nombre, evento, HTTP, error, registro_persistido, filas, appends, reads,
    # duplicado. Las recuperaciones usan EXACTAMENTE el mismo payload.
    escenarios = [
        ("lectura_no_disponible", "falla-lectura", 503, "FUENTE_NO_DISPONIBLE", None, 0, 0, 1, False),
        ("ia_no_disponible", "fallo-ia", 502, "IA_NO_VALIDADA", False, 0, 0, 1, False),
        ("ia_json_invalido", "fallo-json", 502, "IA_NO_VALIDADA", False, 0, 0, 1, False),
        ("control_sintetico_completo", "normal", 200, None, True, 1, 1, 1, False),
        ("escritura_falla_sin_guardar", "fallo-escritura", 503, "REGISTRO_INCIERTO", None, 0, 1, 1, False),
        ("recuperacion_tras_ausencia_comprobada", "fallo-escritura", 200, None, True, 1, 2, 2, False),
        ("fila_guardada_acuse_de_exito_perdido", "acuse-perdido", 503, "REGISTRO_INCIERTO", None, 1, 1, 1, False),
        ("recuperacion_tras_existencia_comprobada", "acuse-perdido", 200, None, True, 1, 1, 2, True),
        ("fila_guardada_acuse_incompleto", "acuse-incompleto", 503, "REGISTRO_INCIERTO", None, 1, 1, 1, False),
        ("recuperacion_tras_acuse_incompleto", "acuse-incompleto", 200, None, True, 1, 1, 2, True),
        ("conflicto_tras_registro", "normal", 409, "EVENTO_CONFLICTIVO", None, 1, 1, 2, False),
    ]
    guardar(args.out / "plan.json", {"tipo": "PRUEBA_SINTETICA_NO_NEGOCIO", "webhook": WEBHOOK,
            "snapshot": SNAPSHOT, "payloads_ficticios": payloads, "escenarios": escenarios,
            "recuperacion_controlada": "Los pasos de recuperación solo siguen a snapshot conforme; no son reintentos por una falla inesperada.",
            "limite": "No hay Google, Gemini, memoria ni tool calls reales en esta copia."})
    resultados = []
    for i, (nombre, key, esperado, error, persistido, filas, appends, reads, duplicado) in enumerate(escenarios, 1):
        payload = copy.deepcopy(payloads[key])
        if nombre == "conflicto_tras_registro":
            payload["text"]["body"] = "Este texto es distinto al contenido que ya usó el mismo evento."
        tick = time.monotonic()
        result = {"tipo": "PRUEBA_SINTETICA_NO_NEGOCIO", "caso": nombre,
                  "fecha_utc": datetime.now(timezone.utc).isoformat(), "entrada_ficticia": payload,
                  "esperado": {"http": esperado, "error": error, "registro_persistido": persistido,
                               "filas_en_destino": filas, "append_acumulados": appends, "lecturas_acumuladas": reads, "duplicado": duplicado}}
        checks = {}
        try:
            status, body, raw = request(WEBHOOK, payload)
            result.update(http=status, respuesta=body, respuesta_http_texto=raw)
            checks.update(http=status == esperado, respuesta_objeto=isinstance(body, dict))
            if not isinstance(body, dict):
                raise ValueError("Respuesta del workflow no objeto.")
            checks.update(registro_persistido=body.get("registro_persistido") is persistido,
                          sin_envio=body.get("respuesta_enviada_whatsapp") is False,
                          ok_coherente=body.get("ok") is (esperado == 200))
            if error:
                checks["error_controlado"] = body.get("error") == error
            if esperado in (502, 503):
                checks["sin_retry_automatico"] = body.get("reintento_automatico") is False
            if esperado == 200:
                checks["duplicado"] = body.get("duplicado") is duplicado
                if not duplicado:
                    checks["borrador_pendiente"] = body.get("solicitud", {}).get("estado") == "pendiente_revision"
            # Esta consulta no usa el output del append: lee el estado del
            # servidor de fixtures por una ruta independiente y queda guardada.
            snap_status, snapshot, snap_raw = request(SNAPSHOT)
            result["lectura_independiente"] = {"http": snap_status, "respuesta": snapshot, "texto": snap_raw}
            checks["snapshot_200"] = snap_status == 200 and isinstance(snapshot, dict)
            if not isinstance(snapshot, dict):
                raise ValueError("Snapshot no objeto.")
            evento = payload["evento_id"]
            rows = [r for r in snapshot["filas"] if r[0] == evento]
            checks.update(filas_exactas=len(rows) == filas,
                          append_sin_reintentos_ciegos=snapshot["append_por_evento"].get(evento, 0) == appends,
                          lecturas_esperadas=snapshot["read_por_evento"].get(evento, 0) == reads)
            if esperado == 200 and not duplicado and isinstance(body.get("solicitud"), dict):
                checks["cotejo_20_campos"] = rows == [fila_desde_solicitud(body["solicitud"])]
            if nombre == "conflicto_tras_registro":
                checks["fila_original_preservada"] = len(rows) == 1 and rows[0][4] == MENSAJE
        except Exception as err:
            checks["operacion_completa"] = False
            result["fallo_cliente"] = type(err).__name__ + ": " + str(err)
        result.update(duracion_http_y_snapshot_ms=round((time.monotonic() - tick) * 1000),
                      comprobaciones=checks, diferencias=[key for key, ok in checks.items() if not ok],
                      correcto=bool(checks) and all(checks.values()))
        guardar(args.out / f"{i:02d}_{nombre}.json", result)
        resultados.append(result)
        resumen = {"tipo": "PRUEBA_SINTETICA_NO_NEGOCIO", "seleccionados": len(escenarios),
                   "ejecutados": len(resultados), "correctos": sum(r["correcto"] for r in resultados),
                   "completa": len(resultados) == len(escenarios), "sin_reintentos_ante_inesperados": True,
                   "casos": [{key: r[key] for key in ("caso", "correcto", "diferencias")} for r in resultados],
                   "limite": "Solo evidencia rutas de controles compartidos frente a fallos inyectados. No acredita modelo, tools, memoria o Sheets reales."}
        guardar(args.out / "resumen.json", resumen)
        print(json.dumps({"caso": nombre, "correcto": result["correcto"], "diferencias": result["diferencias"]}, ensure_ascii=True), flush=True)
        if not result["correcto"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
