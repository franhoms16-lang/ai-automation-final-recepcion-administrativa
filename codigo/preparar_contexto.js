const exigir=(c,m)=>{if(!c) throw new Error(m);};
const origen=$('Normalizar entrada').item.json;
const rangos=$json.valueRanges;
exigir(Array.isArray(rangos)&&rangos.length===2,'Lectura incompleta');
const admin=rangos[0].values, filas=rangos[1].values;
const cabecera=['evento_id','entrada_canonica','fecha_recepcion','telefono','mensaje','tipo','accion','nombre','preferencia_turno','faltantes','alertas','derivar_profesional','borrador','estado','config_version','ejecucion_id','version_flujo','temas_consultados','origen','prioridad'];
exigir(Array.isArray(admin)&&JSON.stringify(admin[0])===JSON.stringify(['tema','estado','valor','version']),'Cabecera administrativa inválida');
exigir(Array.isArray(filas)&&JSON.stringify(filas[0])===JSON.stringify(cabecera),'Cabecera de solicitudes inválida');
const config={};
for(const r of admin.slice(1)) {
  if(!r.some(Boolean)) continue;
  exigir(r.length===4&&['modalidad','honorarios','horarios','requisitos'].includes(r[0])&&!config[r[0]],'Tema ausente/duplicado');
  exigir(r[3]==='ADMIN_DEMO_R01','Versión administrativa no admitida');
  if(r[0]==='requisitos') {
    exigir(r[1]==='verificado_para_recepcion'&&r[2]==='["nombre","preferencia_turno"]','Requisitos no admitidos');
    config[r[0]]={estado:r[1],valor:JSON.parse(r[2]),version:r[3]};
  } else {
    exigir(r[1]==='no_verificado'&&r[2]==='null','Dato administrativo no aprobado');
    config[r[0]]={estado:r[1],valor:null,version:r[3]};
  }
}
exigir(Object.keys(config).length===4,'Configuración incompleta');
const registros=filas.slice(1).filter(r=>r.some(Boolean));
const encontrados=registros.filter(r=>r[0]===origen.evento_id);
if(encontrados.length) {
  const r=encontrados[0];
  const igual=Boolean(encontrados.length===1&&r.length===20&&r[1]===origen.entrada_canonica&&r[13]==='pendiente_revision'&&r[14]==='ADMIN_DEMO_R01'&&r[16]==='FINAL_R01'&&r[18]==='whatsapp_simulado'&&typeof r[12]==='string'&&r[12].trim()&&typeof r[15]==='string'&&r[15].trim());
  return {json:{...origen,continuar:false,http:igual?200:409,ok:igual,
    error:igual?null:'EVENTO_CONFLICTIVO',duplicado:igual,registro_persistido:igual?true:null,
    respuesta_enviada_whatsapp:false,detalle:igual?'Evento ya registrado; no se volvió a ejecutar IA ni escritura.':'ID repetido con contenido distinto o registros inconsistentes. Revisión manual.'}};
}
exigir(registros.length<1000,'Capacidad de prototipo alcanzada; archivar con revisión antes de continuar');
return {json:{...origen,continuar:true,config,config_version:'ADMIN_DEMO_R01',cabecera}};
