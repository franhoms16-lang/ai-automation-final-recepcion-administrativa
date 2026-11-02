const origen=$('Preparar contexto').item.json;
const exigir=(c,m)=>{if(!c) throw new Error(m);};
let s=$json.output;
if(typeof s==='string') s=JSON.parse(s.trim());
const claves=['tipo','accion','nombre','preferencia_turno','faltantes','alertas','derivar_profesional','temas_administrativos','estado'];
exigir(s&&typeof s==='object'&&!Array.isArray(s)&&Object.keys(s).length===claves.length&&claves.every(k=>Object.hasOwn(s,k)),'Claves de IA inválidas');
exigir(['solicitud_primera_consulta','informacion_administrativa','reprogramacion_turno','consulta_profesional','otro'].includes(s.tipo),'Tipo inválido');
exigir(['gestion_administrativa','pedir_datos','derivar_profesional'].includes(s.accion),'Acción inválida');
for(const k of ['nombre','preferencia_turno']) exigir(s[k]===null||(typeof s[k]==='string'&&s[k].trim()&&s[k].length<=(k==='nombre'?100:200)&&!/[\u0000-\u001F\uFFFD]/u.test(s[k])),'Dato inválido: '+k);
const listas={faltantes:['nombre','preferencia_turno','aclaracion_fecha','aclaracion_datos','separar_solicitudes','aclaracion_pedido'],alertas:['fecha_ambigua','datos_contradictorios','multiples_solicitudes','instruccion_incrustada'],temas_administrativos:['requisitos','modalidad','honorarios','horarios']};
for(const [k,valores] of Object.entries(listas)) exigir(Array.isArray(s[k])&&s[k].every(v=>valores.includes(v))&&new Set(s[k]).size===s[k].length,'Lista inválida: '+k);
exigir(s.estado==='pendiente_revision'&&typeof s.derivar_profesional==='boolean'&&s.derivar_profesional===(s.tipo==='consulta_profesional'),'Estado/derivación incoherentes');
// Refuerzo técnico de señales visibles; no es un detector semántico universal.
const m=origen.mensaje;
if(/\b(mañana|pasado mañana|esta semana|pr[oó]xim[oa]|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b/iu.test(m)&&!s.alertas.includes('fecha_ambigua')) s.alertas.push('fecha_ambigua');
if(/\b(ignor[aá]|system prompt|instrucciones anteriores|otros remitentes)\b/iu.test(m)&&!s.alertas.includes('instruccion_incrustada')) s.alertas.push('instruccion_incrustada');
if(s.alertas.some(a=>['datos_contradictorios','multiples_solicitudes'].includes(a))) {
  s.nombre=null; s.preferencia_turno=null;
}
const faltantes=[];
if(s.tipo==='solicitud_primera_consulta') for(const k of origen.config.requisitos.valor) if(s[k]===null) faltantes.push(k);
if(s.alertas.includes('fecha_ambigua')) faltantes.push('aclaracion_fecha');
if(s.alertas.includes('datos_contradictorios')) faltantes.push('aclaracion_datos');
if(s.alertas.includes('multiples_solicitudes')) faltantes.push('separar_solicitudes');
if(s.tipo==='otro') faltantes.push('aclaracion_pedido');
s.faltantes=[...new Set(faltantes)];
const accion=s.derivar_profesional?'derivar_profesional':s.faltantes.length?'pedir_datos':'gestion_administrativa';
exigir(s.accion===accion,'Acción del agente incompatible con datos/alertas');
const pasos=$json.intermediateSteps||[];
const temas=[...new Set(pasos.filter(p=>p.action?.tool==='Consultar_datos_administrativos').map(p=>p.action.toolInput?.tema))].filter(t=>listas.temas_administrativos.includes(t));
const requeridos=new Set(s.temas_administrativos);
if(s.tipo==='solicitud_primera_consulta') requeridos.add('requisitos');
if(/modalidad|presencial|virtual|videollamada/iu.test(m)) requeridos.add('modalidad');
if(/honorarios|arancel/iu.test(m)) requeridos.add('honorarios');
if(/horarios?/iu.test(m)&&s.tipo==='informacion_administrativa') requeridos.add('horarios');
exigir([...requeridos].every(t=>temas.includes(t)),'Falta consulta real de herramienta');
// La respuesta final usa texto controlado: el modelo decide la acción y extrae
// datos, pero no puede insertar asesoramiento libre en el borrador persistido.
let borrador;
if(accion==='derivar_profesional') borrador='Tu consulta requiere la revisión de Francisco. Este asistente solo organiza la recepción administrativa. No envíes documentos ni datos sensibles por este prototipo.';
else if(accion==='pedir_datos') {
  const pedidos=[];
  if(s.faltantes.includes('nombre')) pedidos.push('tu nombre');
  if(s.faltantes.includes('preferencia_turno')) pedidos.push('tu preferencia de fecha y horario');
  if(s.faltantes.includes('aclaracion_fecha')) pedidos.push('una fecha concreta');
  if(s.faltantes.includes('aclaracion_datos')) pedidos.push('cuál de los datos contradictorios es correcto');
  if(s.faltantes.includes('separar_solicitudes')) pedidos.push('cada solicitud por separado');
  if(s.faltantes.includes('aclaracion_pedido')) pedidos.push('qué gestión administrativa necesitás');
  borrador='Para continuar, indicá '+pedidos.join(' y ')+'. Francisco revisará el pedido; esto no confirma un turno.';
} else if(s.tipo==='informacion_administrativa') {
  const desconocidos=[...requeridos].filter(t=>t!=='requisitos'&&origen.config[t].valor===null);
  borrador=desconocidos.length?'Francisco debe confirmar los datos administrativos consultados. Este borrador no informa disponibilidad, precios ni confirma turnos.':'Para solicitar una primera consulta, indicá tu nombre y preferencia de fecha y horario. Francisco revisará el pedido antes de coordinar.';
} else if(s.tipo==='reprogramacion_turno') borrador='Francisco revisará tu pedido de coordinación. Este asistente no verifica turnos existentes ni confirma cambios.';
else borrador='El pedido queda preparado para revisión de Francisco. La preferencia indicada no supone disponibilidad ni confirma un turno.';
exigir(borrador.split(/\s+/).length<=60,'Borrador extenso');
const prioridad=accion==='derivar_profesional'?'revision_profesional':accion==='pedir_datos'?'completar_datos':'revision_administrativa';
const solicitud={evento_id:origen.evento_id,fecha_recepcion:origen.fecha_recepcion,canal:origen.canal,telefono:origen.telefono,mensaje:origen.mensaje,...s,borrador,prioridad,config_version:origen.config_version,temas_consultados:temas,ejecucion_id:origen.ejecucion_id,version_flujo:origen.version_flujo};
const fila=[origen.evento_id,origen.entrada_canonica,origen.fecha_recepcion,origen.telefono,origen.mensaje,s.tipo,s.accion,s.nombre??'',s.preferencia_turno??'',JSON.stringify(s.faltantes),JSON.stringify(s.alertas),String(s.derivar_profesional),borrador,'pendiente_revision',origen.config_version,origen.ejecucion_id,origen.version_flujo,JSON.stringify(temas),'whatsapp_simulado',prioridad];
return {json:{solicitud,fila,ok:true,registro_persistido:false,respuesta_enviada_whatsapp:false}};
