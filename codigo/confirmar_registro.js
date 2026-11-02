const esperado=$('Validar y preparar registro').item.json;
const u=$json.updates;
const rango=/^Solicitudes!A([1-9]\d*):T([1-9]\d*)$/.exec(u?.updatedRange||'');
if(!u||u.updatedRows!==1||u.updatedCells!==20||!rango||rango[1]!==rango[2]||Number(rango[1])<2||JSON.stringify(u.updatedData?.values)!==JSON.stringify([esperado.fila]))
  throw new Error('Acuse de escritura no comprobable; resultado incierto');
return {json:{ok:true,solicitud:esperado.solicitud,registro_persistido:true,rango_registrado:u.updatedRange,
  respuesta_enviada_whatsapp:false,borrador_pendiente_revision:true,duplicado:false}};
