"""Servidor efímero de fallos SINTÉTICOS. Solo escucha 127.0.0.1:5682.

No se conecta a Internet, n8n, Gemini ni Google. Persiste cada operación en
--out NUEVO. El snapshot es una lectura independiente del estado simulado.
No reintenta operaciones. Detener con Ctrl+C después de guardar evidencia.
"""
from __future__ import annotations

import argparse
import copy
import json
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HEAD = ["evento_id", "entrada_canonica", "fecha_recepcion", "telefono", "mensaje", "tipo", "accion", "nombre", "preferencia_turno", "faltantes", "alertas", "derivar_profesional", "borrador", "estado", "config_version", "ejecucion_id", "version_flujo", "temas_consultados", "origen", "prioridad"]
ADMIN = [["tema", "estado", "valor", "version"], ["requisitos", "verificado_para_recepcion", '["nombre","preferencia_turno"]', "ADMIN_DEMO_R01"]] + [[tema, "no_verificado", "null", "ADMIN_DEMO_R01"] for tema in ("modalidad", "honorarios", "horarios")]


class Estado:
    """Estado testeable sin abrir sockets. Las fallas son únicas por evento."""
    def __init__(self, out: Path):
        self.out = out
        self.lock = threading.RLock()
        self.data = {"tipo": "SERVIDOR_SINTETICO_NO_GOOGLE", "inicio_utc": datetime.now(timezone.utc).isoformat(),
                     "filas": [], "read_por_evento": {}, "append_por_evento": {}, "snapshots": 0, "operaciones": []}
        self.persistir()

    def persistir(self) -> None:
        self.data["actualizado_utc"] = datetime.now(timezone.utc).isoformat()
        temp = self.out / "estado.tmp"
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.out / "estado.json")

    def log(self, metodo: str, evento: str | None, status: int, guardado: bool | None) -> None:
        self.data["operaciones"].append({"orden": len(self.data["operaciones"]) + 1,
             "fecha_utc": datetime.now(timezone.utc).isoformat(), "operacion": metodo,
             "evento_id": evento, "http_servidor": status, "fila_guardada_en_operacion": guardado})
        self.persistir()

    def read(self, evento: str) -> tuple[int, dict]:
        with self.lock:
            cantidad = self.data["read_por_evento"].get(evento, 0) + 1
            self.data["read_por_evento"][evento] = cantidad
            if evento.startswith(("falla-lectura", "fallo-lectura")) and cantidad == 1:
                self.log("read", evento, 503, False)
                return 503, {"error": "FALLO_LECTURA_INYECTADO_SINTETICO"}
            body = {"spreadsheetId": "HARNESS_SINTETICO_NO_GOOGLE", "valueRanges": [
                {"range": "Administracion!A1:D10", "majorDimension": "ROWS", "values": copy.deepcopy(ADMIN)},
                {"range": "Solicitudes!A1:T1002", "majorDimension": "ROWS", "values": [HEAD[:]] + copy.deepcopy(self.data["filas"])}]}
            self.log("read", evento, 200, False)
            return 200, body

    def append(self, body: object) -> tuple[int, dict]:
        with self.lock:
            values = body.get("values") if isinstance(body, dict) else None
            if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], list) or len(values[0]) != 20 or not all(isinstance(v, str) for v in values[0]):
                self.log("append_invalido", None, 400, False)
                return 400, {"error": "Fixture espera una fila de veinte textos."}
            fila = values[0][:]
            evento = fila[0]
            cantidad = self.data["append_por_evento"].get(evento, 0) + 1
            self.data["append_por_evento"][evento] = cantidad
            if evento.startswith("fallo-escritura") and cantidad == 1:
                self.log("append", evento, 503, False)
                return 503, {"error": "FALLO_ESCRITURA_ANTES_DE_GUARDAR_SINTETICO"}
            # No deduplicar aquí: la copia del workflow debe impedir un segundo
            # append después de descubrir la fila por la lectura previa.
            self.data["filas"].append(fila)
            numero = len(self.data["filas"]) + 1
            rango = f"Solicitudes!A{numero}:T{numero}"
            if evento.startswith("acuse-perdido") and cantidad == 1:
                self.log("append", evento, 503, True)
                return 503, {"error": "FILA_GUARDADA_ACUSE_DE_EXITO_PERDIDO_SINTETICO"}
            updates = {"updatedRange": rango, "updatedRows": 1, "updatedColumns": 20, "updatedCells": 20,
                       "updatedData": {"range": rango, "majorDimension": "ROWS", "values": [fila]}}
            if evento.startswith("acuse-incompleto") and cantidad == 1:
                updates.pop("updatedData")
            self.log("append", evento, 200, True)
            return 200, {"spreadsheetId": "HARNESS_SINTETICO_NO_GOOGLE", "updates": updates}

    def snapshot(self) -> dict:
        with self.lock:
            self.data["snapshots"] += 1
            self.log("snapshot", None, 200, None)
            result = copy.deepcopy(self.data)
            result["filas_por_evento"] = {}
            for fila in result["filas"]:
                result["filas_por_evento"][fila[0]] = result["filas_por_evento"].get(fila[0], 0) + 1
            result["total_filas"] = len(result["filas"])
            return result


def handler(estado: Estado):
    class Handler(BaseHTTPRequestHandler):
        server_version = "HarnessSintetico/1"

        def responder(self, status: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/healthz":
                return self.responder(200, {"ok": True, "sintetico": True})
            if parsed.path == "/snapshot":
                return self.responder(200, estado.snapshot())
            if parsed.path == "/read":
                evento = urllib.parse.parse_qs(parsed.query).get("evento_id", [""])[0]
                if not evento:
                    return self.responder(400, {"error": "Falta evento_id de prueba."})
                status, body = estado.read(evento)
                return self.responder(status, body)
            self.responder(404, {"error": "Ruta no disponible."})

        def do_POST(self) -> None:
            if urllib.parse.urlsplit(self.path).path != "/append":
                return self.responder(404, {"error": "Ruta no disponible."})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 65536:
                    raise ValueError("Tamaño inválido")
                body = json.loads(self.rfile.read(size).decode("utf-8"))
            except (ValueError, UnicodeError):
                return self.responder(400, {"error": "JSON de fixture inválido."})
            status, result = estado.append(body)
            self.responder(status, result)

        def log_message(self, format: str, *args) -> None:
            # No registrar cabeceras, cookies ni datos ajenos. El estado.json
            # conserva las operaciones sintéticas con sus IDs y resultados.
            print(format % args, flush=True)
    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="Directorio NUEVO para estado y operaciones.")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    estado = Estado(args.out)
    server = ThreadingHTTPServer(("127.0.0.1", 5682), handler(estado))
    print("HARNESS SINTETICO escuchando solo en http://127.0.0.1:5682", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        with estado.lock:
            estado.data["detenido_utc"] = datetime.now(timezone.utc).isoformat()
            estado.persistir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
