const cuerpo = $json.body;
const obj = v => v && typeof v === 'object' && !Array.isArray(v);
const texto = v => typeof v === 'string' ? v.trim() : '';
const errores = [];
if (!obj(cuerpo)) errores.push('cuerpo_invalido');
const evento_id = texto(cuerpo?.evento_id);
const original = texto(cuerpo?.from);
const telefono = original.replace(/[\s()+-]/g, '');
const bruto = cuerpo?.text?.body;
const mensaje = texto(bruto).replace(/\s+/g, ' ');
if (!/^[A-Za-z0-9_-]{1,120}$/.test(evento_id)) errores.push('evento_id_invalido');
if (!/^[1-9]\d{7,14}$/.test(telefono)) errores.push('telefono_invalido');
if (!obj(cuerpo?.text) || typeof bruto !== 'string' || !mensaje || bruto.length > 2000)
  errores.push('mensaje_invalido');
if (typeof bruto === 'string' && /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F\uFFFD\u202A-\u202E\u2066-\u2069]/u.test(bruto))
  errores.push('texto_corrupto');
if (cuerpo?.attachments !== undefined || (obj(cuerpo) && Object.hasOwn(cuerpo,'type') && cuerpo.type !== 'text'))
  errores.push('contenido_no_textual');
if (errores.length) return {json:{ok:false,valido:false,error:'ENTRADA_INVALIDA',errores,
  registro_persistido:false,respuesta_enviada_whatsapp:false}};
return {json:{valido:true,evento_id,telefono,mensaje,
  entrada_canonica:JSON.stringify([telefono,mensaje]),fecha_recepcion:$now.toISO(),
  canal:'whatsapp_simulado',ejecucion_id:String($execution.id),
  version_flujo:'FINAL_R01',entrada_ia:{mensaje}}};
