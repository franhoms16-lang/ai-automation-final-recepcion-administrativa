"""Crea una copia de prueba sintética; nunca escribe el workflow de negocio.

No inicia n8n, no lo importa, no abre puertos ni realiza peticiones HTTP.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_DEFAULT = HERE.parents[1] / "workflow-recepcion-administrativa.json"
COMMON = ("Normalizar entrada", "Preparar contexto", "Validar y preparar registro", "Confirmar registro")
REMOVED = {"Google Gemini Chat Model", "Memoria por telefono", "Consultar_datos_administrativos"}

FIXTURE = '''// SOLO PRUEBA SINTÉTICA: reemplazo del AI Agent, sin modelo ni memoria.
// intermediateSteps es una fixture, NO evidencia de llamadas reales a tools.
const o=$('Preparar contexto').item.json;
if(o.evento_id.startsWith('fallo-ia')) throw new Error('FALLO_IA_INYECTADO_SINTETICO');
if(o.evento_id.startsWith('fallo-json')) return {json:{output:'{json-invalido-inyectado'}};
const salida={tipo:'solicitud_primera_consulta',accion:'gestion_administrativa',
  nombre:'Persona Demo Harness',preferencia_turno:'24/11/2026 por la tarde',
  faltantes:[],alertas:[],derivar_profesional:false,
  temas_administrativos:['requisitos'],estado:'pendiente_revision'};
return {json:{output:JSON.stringify(salida),intermediateSteps:[{
  action:{tool:'Consultar_datos_administrativos',toolInput:{tema:'requisitos'}},
  observation:JSON.stringify({tema:'requisitos',...o.config.requisitos,
    origen:'FIXTURE SINTETICA: NO ES GOOGLE NI LLAMADA REAL DE AGENTE'})
}]}};
'''


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    args = ap.parse_args()
    raw = args.source.read_bytes()
    parent = json.loads(raw.decode("utf-8-sig"))
    by_name = {n["name"]: n for n in parent["nodes"]}
    if parent.get("id") not in (None,"finalRecepcionR01") or parent.get('name')!='Final - Recepcion administrativa - WhatsApp SIMULADO y Sheets':
        raise ValueError("La fuente no corresponde al workflow de negocio esperado.")
    parent_id=parent.get('id') or 'finalRecepcionR01'
    for name in COMMON:
        if by_name[name]["type"] != "n8n-nodes-base.code":
            raise ValueError("El nodo compartido dejó de ser Code: " + name)
    clone = copy.deepcopy(parent)
    clone.update(id="finalFaultHarnessR01", name="Final - SOLO PRUEBA SINTETICA - Fallos y recuperacion", active=False, pinData={}, tags=[])
    clone.pop("versionId", None)
    clone.pop("activeVersionId", None)
    clone["nodes"] = [n for n in clone["nodes"] if n["name"] not in REMOVED]
    for node in clone["nodes"]:
        node["id"] = str(uuid.uuid4())
        node.pop("credentials", None)
        name = node["name"]
        if node["type"] == "n8n-nodes-base.webhook":
            node["webhookId"] = str(uuid.uuid4())
            node["parameters"]["path"] = "final-prueba-fallos"
        elif name == "Destino fijo":
            node["parameters"]["jsCode"] = "return {json:{...$json,spreadsheet_id:'HARNESS_SINTETICO_NO_GOOGLE'}};"
        elif name == "Leer Sheets - segunda fuente":
            node["parameters"] = {"method": "GET", "url": "={{ 'http://127.0.0.1:5682/read?evento_id=' + encodeURIComponent($('Normalizar entrada').item.json.evento_id) }}", "authentication": "none", "options": {"timeout": 5000}}
        elif name == "Registrar solicitud RAW":
            node["parameters"] = {"method": "POST", "url": "http://127.0.0.1:5682/append", "authentication": "none", "sendBody": True, "specifyBody": "json", "jsonBody": '={{ {majorDimension:"ROWS",values:[$json.fila]} }}', "options": {"timeout": 5000}}
        elif name == "Asistente de recepcion":
            node.update(type="n8n-nodes-base.code", typeVersion=2, onError="continueErrorOutput", retryOnFail=False)
            node["parameters"] = {"mode": "runOnceForEachItem", "jsCode": FIXTURE}
            node["notes"] = "Fixture determinista: no se ejecutan IA, memoria ni herramientas. No acredita éxito de negocio real."
        elif node["type"] == "n8n-nodes-base.stickyNote":
            node["parameters"]["content"] = "## SOLO PRUEBA SINTÉTICA\nCopia de controles FINAL_R01. HTTP localhost:5682 simula Sheets; Code fixture sustituye IA y tools. Sin Google/Gemini, sin memoria real. No es evidencia del flujo de negocio."
    names = {n["name"] for n in clone["nodes"]}
    clone["connections"] = {name: {kind: [[edge for edge in output if edge["node"] in names] for output in outputs]
                                     for kind, outputs in connections.items() if kind == "main"}
                            for name, connections in clone["connections"].items() if name in names}
    child = {n["name"]: n for n in clone["nodes"]}
    common_hashes = {}
    for name in COMMON:
        original = by_name[name]["parameters"]["jsCode"]
        copied = child[name]["parameters"]["jsCode"]
        if original != copied:
            raise AssertionError("Se alteró un Code compartido: " + name)
        common_hashes[name] = {"sha256_parent": sha(original.encode("utf-8")),
                               "sha256_harness": sha(copied.encode("utf-8")), "identico": True}
    if any(n.get("credentials") for n in clone["nodes"]):
        raise AssertionError("El harness debe carecer de referencias a credenciales.")
    meta = {"tipo": "PRUEBA_SINTETICA_NO_NEGOCIO", "fecha_utc": datetime.now(timezone.utc).isoformat(),
            "parent_id": parent_id, "parent_name": parent["name"], "parent_version_id": parent.get("versionId"),
            "parent_workflow_sha256": sha(raw), "harness_id": clone["id"],
            "webhook_local": "http://localhost:5678/webhook/final-prueba-fallos", "servidor_local": "http://127.0.0.1:5682",
            "codigo_compartido": common_hashes,
            "sustituciones": ["HTTP Sheets por servidor local", "AI Agent por Code fixture", "Destino por ID ficticio", "Subnodos IA/memoria/tool eliminados"],
            "limite": "Los intermediateSteps son fixtures. Esta copia no prueba Gemini, Google Sheets, memoria real ni clasificación semántica."}
    clone["meta"] = {"harnessSintetico": True, "parent_id": parent_id, "parent_workflow_sha256": sha(raw)}
    payload = (json.dumps(clone, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    meta["harness_workflow_sha256"] = sha(payload)
    (HERE / "workflow_harness.json").write_bytes(payload)
    (HERE / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"creado": "workflow_harness.json", "id": clone["id"], "nodos": len(clone["nodes"]), "Code_compartidos_identicos": len(common_hashes), "servicios_iniciados": 0}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
