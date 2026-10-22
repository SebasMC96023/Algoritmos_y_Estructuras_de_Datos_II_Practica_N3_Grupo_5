const $=s=>document.querySelector(s);let modo='async',cfg={pago:3,timeout:10},esperando=new Set(),vigilar=new Set();
const t0=()=>performance.now(),sec=a=>((performance.now()-a)/1000);
function log(m,c='inf'){const d=document.createElement('div');d.className=c;d.textContent=new Date().toLocaleTimeString()+'  '+m;$('#log').prepend(d)}
async function api(m,u,b){const t=t0();const r=await fetch(u,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});let j={};try{j=await r.json()}catch{}return{r,j,dt:sec(t)}}

async function comprar(a,silencio){
 if(modo==='async'){
  const {r,j,dt}=await api('POST','/comprar/'+a);
  if(!silencio){$('#tResp').textContent=dt.toFixed(3)+' s';$('#tTotal').textContent='…'}
  if(r.status===202){log(`POST /comprar/${a} → 202 Accepted en ${(dt*1000).toFixed(0)} ms (el cliente queda libre)`,'ok');vigilar.add(j.id_compra);seguir(j.id_compra,a,silencio)}
  else log(`POST /comprar/${a} → ${r.status} ${j.detail}`,'err');
  return r.status;
 }
 esperando.add(a);pintar();log(`POST /comprar-sincrono/${a} … el cliente queda BLOQUEADO esperando`,'mut');
 const {r,j,dt}=await api('POST','/comprar-sincrono/'+a);esperando.delete(a);
 if(!silencio){$('#tResp').textContent=dt.toFixed(2)+' s';$('#tTotal').textContent=dt.toFixed(2)+' s'}
 log(r.status===200?`→ 200 ${j.estado} tras ${dt.toFixed(2)} s de espera`:`→ ${r.status} ${j.detail||''}`,r.status===200&&j.estado==='COMPLETADO'?'ok':'err');
 return r.status;
}
async function seguir(id,a,silencio){const ini=t0();let ult='';
 while(true){await new Promise(r=>setTimeout(r,1000));const {j}=await api('GET','/compras/'+id);
  if(j.estado!==ult){log(`GET /compras/${id.slice(0,8)} (polling) → ${j.estado}`,j.estado==='COMPLETADO'?'ok':j.estado==='PROCESANDO_PAGO'?'mut':'err');ult=j.estado}
  if(j.estado!=='PROCESANDO_PAGO'){if(!silencio)$('#tTotal').textContent=sec(ini).toFixed(2)+' s';return}}}

let estado={asientos:{},compras:[]};
function pintar(){const h=Object.entries(estado.asientos).map(([a,e])=>{const w=esperando.has(a);const c=w?'esperando':e;
 return `<div class="seat ${c}" data-a="${a}">${a}<small>${w?'esperando…':e}</small></div>`}).join('');
 if($('#seats').dataset.h!==h){$('#seats').innerHTML=h;$('#seats').dataset.h=h}}
function pintarCompras(){const c=estado.compras;if(!c.length){$('#compras').innerHTML='<span class="hint">Aún no hay compras.</span>';return}
 $('#compras').innerHTML=c.map(x=>{const p=x.estado==='PROCESANDO_PAGO'?Math.min(100,x.transcurrido/cfg.timeout*100):100;
 return `<div class="compra"><div class="t"><span><b>${x.asiento}</b> · ${x.id.slice(0,8)}</span><span class="badge ${x.estado}">${x.estado}</span></div>
 <div class="bar ${x.estado}"><i style="width:${p}%"></i></div></div>`}).join('')}
async function refrescar(){try{const r=await fetch('/estado');estado=await r.json();cfg=estado.config;pintar();pintarCompras();
 if(document.activeElement.type!=='range'){$('#rPago').value=cfg.pago;$('#rTo').value=cfg.timeout}hint()}catch{}}
function hint(){$('#vPago').textContent=cfg.pago+' s';$('#vTo').textContent=cfg.timeout+' s';
 $('#hint').textContent=cfg.pago>cfg.timeout?`⚠ El banco (${cfg.pago}s) tarda más que el timeout (${cfg.timeout}s): la compra se cancelará y el asiento se liberará.`:`El banco responde a tiempo: la compra se completará.`}
async function enviarCfg(){await api('POST','/config',{pago_segundos:+$('#rPago').value,timeout_segundos:+$('#rTo').value})}

$('#seats').onclick=e=>{const s=e.target.closest('.seat.libre');if(s)comprar(s.dataset.a)};
const setModo=m=>{modo=m;$('#m-async').classList.toggle('on',m==='async');$('#m-sync').classList.toggle('on',m==='sync')};
$('#m-async').onclick=()=>setModo('async');$('#m-sync').onclick=()=>setModo('sync');
$('#rPago').oninput=$('#rTo').oninput=()=>{cfg.pago=+$('#rPago').value;cfg.timeout=+$('#rTo').value;hint()};
$('#rPago').onchange=$('#rTo').onchange=enviarCfg;
$('#b-reset').onclick=async()=>{await api('POST','/reiniciar');$('#log').innerHTML='';$('#tResp').textContent=$('#tTotal').textContent='—';log('Estado reiniciado','mut');refrescar()};
$('#b-same').onclick=async()=>{const a=Object.keys(estado.asientos).find(k=>estado.asientos[k]==='libre');if(!a)return log('No hay asientos libres: reinicia','err');
 log(`5 clientes piden ${a} al mismo tiempo…`,'inf');const rs=await Promise.all([1,2,3,4,5].map(()=>comprar(a,true)));
 log(`Resultado: ${rs.join(', ')} → solo uno gana, el resto recibe 409 Conflict`,'inf')};
$('#b-diff').onclick=async()=>{const l=Object.keys(estado.asientos).filter(k=>estado.asientos[k]==='libre').slice(0,5);
 log(`5 clientes compran ${l.join(', ')} a la vez (se cobran en paralelo)`,'inf');const t=t0();await Promise.all(l.map(a=>comprar(a,true)));log(`Las 5 respuestas llegaron en ${(sec(t)*1000).toFixed(0)} ms`,'ok')};
log('Listo. Elige un asiento verde 👆','mut');refrescar();setInterval(refrescar,500);
