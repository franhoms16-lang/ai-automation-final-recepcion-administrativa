const tema=query.tema;
const config=$('Preparar contexto').item.json.config;
if(!['requisitos','modalidad','honorarios','horarios'].includes(tema)) throw new Error('Tema no admitido');
return JSON.stringify({tema,...config[tema],origen:'Google Sheets / Administracion',
  alcance:'Prototipo ficticio. No acredita disponibilidad ni autoriza reservas.'});
