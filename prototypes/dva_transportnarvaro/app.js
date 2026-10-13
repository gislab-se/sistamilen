(() => {
  'use strict';
  const data=window.DVA_DATA,model=window.WasteModel,byId=id=>document.getElementById(id);
  if(!data||!model||!window.L){byId('map-status').textContent='Kartunderlag saknas. Bygg enligt metodbeskrivningen.';return;}
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const latLng=c=>[c[1],c[0]],nf=new Intl.NumberFormat('sv-SE');
  const map=L.map('map',{scrollWheelZoom:true,maxZoom:19}).setView([60.73,14.85],9);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  map.attributionControl.addAttribution('Platser: SCB 2023 / © OpenStreetMap · DVA schema 2026');
  L.control.scale({imperial:false}).addTo(map);
  const places=L.featureGroup().addTo(map),rings=L.layerGroup().addTo(map),nodes=L.featureGroup().addTo(map);
  let geography,errors=0,enabled=new Set(data.tracts.map(t=>t.tract_id)),visible=[];
  if(window.REVIEW_GEOGRAPHY)geography=L.geoJSON(window.REVIEW_GEOGRAPHY,{interactive:false,style:{color:'#c5d2b8',weight:.6,fillColor:'#dce5ce',fillOpacity:.44}}).addTo(map);
  const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'});
  tiles.on('tileerror',()=>{errors++;geography?.addTo(map);geography?.eachLayer(l=>l.bringToBack?.());byId('map-status').textContent='Bakgrundskartan kunde inte hämtas. Lokal SCB-bakgrund visas.';});
  tiles.on('load',()=>{if(!errors)byId('map-status').textContent='OpenStreetMap · internet';});
  function basemap(){if(byId('basemap').checked){errors=0;if(geography)map.removeLayer(geography);tiles.addTo(map);}else{map.removeLayer(tiles);geography?.addTo(map);byId('map-status').textContent='Lokal SCB-bakgrund · utan internet';}}
  for(const m of data.municipalities)byId('municipality').add(new Option(m,m));
  for(const type of data.waste_types)byId('waste-type').add(new Option(type,type));
  byId('waste-type').value='Matavfall';
  for(const day of ['Måndag','Tisdag','Onsdag','Torsdag','Fredag']){const b=document.createElement('button');b.type='button';b.textContent=day.slice(0,3);b.title=day;b.dataset.weekday=day;b.setAttribute('aria-pressed','false');byId('weekdays').append(b);}
  byId('tract-layers').innerHTML=data.municipalities.map(m=>`<details><summary>${esc(m)}</summary><label class="check"><input type="checkbox" data-municipality-layer="${esc(m)}" checked><span>Alla trakter i ${esc(m)}</span></label>${data.tracts.filter(t=>t.municipality===m).map(t=>`<label class="check"><input type="checkbox" data-tract-layer="${esc(t.tract_id)}" checked><i style="background:${esc(t.color)}"></i><span>${esc(t.label)} · ${esc(t.weekday.slice(0,3))}</span></label>`).join('')}</details>`).join('');
  function fit(){const bounds=L.latLngBounds([]);if(places.getLayers().length)bounds.extend(places.getBounds());if(nodes.getLayers().length)bounds.extend(nodes.getBounds());if(bounds.isValid())map.fitBounds(bounds.pad(.12),{maxZoom:14});}
  function render(autoFit=false){
    places.clearLayers();rings.clearLayers();nodes.clearLayers();map.closePopup();
    const days=[...byId('weekdays').querySelectorAll('[aria-pressed="true"]')].map(b=>b.dataset.weekday);
    visible=model.visibleTracts(data,{tracts:[...enabled],municipality:byId('municipality').value,wasteType:byId('waste-type').value,date:byId('pickup-date').value}).filter(t=>!days.length||days.includes(t.weekday));
    for(const input of document.querySelectorAll('[data-tract-layer]'))input.checked=enabled.has(input.dataset.tractLayer);
    for(const input of document.querySelectorAll('[data-municipality-layer]')){const ids=data.tracts.filter(t=>t.municipality===input.dataset.municipalityLayer).map(t=>t.tract_id),n=ids.filter(id=>enabled.has(id)).length;input.checked=n===ids.length;input.indeterminate=n>0&&n<ids.length;}
    const points=visible.flatMap(t=>t.points),groups=model.pointGroups(visible),reserves=points.filter(p=>p.status==='fallback');
    for(const group of groups.values()){
      const content=`<h3>${group.status==='fallback'?'Reserv vid traktankare':'Sophämtningsplats'}</h3><ul class="popup-list">${group.points.map(({point:p,tract:t})=>{const dates=byId('waste-type').value?t.dates[byId('waste-type').value]||[]:[...new Set(Object.values(t.dates).flat())].sort();const reference=byId('pickup-date').value||new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Stockholm',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());return `<li><strong>${esc(p.name)}</strong> · ${esc(t.label)}<br>${esc(t.weekday)}, ${esc(t.week_parity.toLowerCase())} veckor<br>${esc(p.reason)}<br>Källdatum från ${esc(reference)}: ${dates.filter(d=>d>=reference).slice(0,5).map(esc).join(', ')||'inga'}<br><small>Kartkälla: ${esc(p.source)}</small>${t.source_flags.length?`<br><small>Schemakontroll: ${esc(t.source_flags.join('; '))}</small>`:''}</li>`;}).join('')}</ul><p>Ort-/gatupunkt, inte hämtställe eller körväg.</p>`;
      L.circleMarker(latLng(group.coordinate),{radius:6,weight:2.5,color:group.status==='fallback'?'#7e8790':group.status==='review'?'#ad7a24':group.color,fillColor:'#fff',fillOpacity:.85,dashArray:group.status==='fallback'?'3 3':null}).bindTooltip(esc(group.points.slice(0,3).map(p=>p.point.name).join(' / '))).bindPopup(content,{maxWidth:390}).addTo(places);
    }
    if(byId('show-rings').checked)for(const t of visible)if(t.anchor?.lat!=null)L.circle([t.anchor.lat,t.anchor.lon],{radius:7000,color:t.color,weight:1,dashArray:'5 7',fillOpacity:.02,interactive:false}).addTo(rings);
    const shownNodes=byId('show-nodes').checked?data.nodes.filter(n=>(!byId('municipality').value||n.municipality===byId('municipality').value)&&(!byId('single-nodes').checked||n.one_operator)):[];
    for(const n of shownNodes)L.circleMarker([n.lat,n.lon],{radius:n.one_operator?4.5:6,color:'#fff',weight:1.5,fillColor:n.one_operator?'#d0643b':'#23669b',fillOpacity:.95}).bindPopup(`<h3>${esc(n.name.trim())}</h3><p>${esc(n.address)} · ${esc(n.municipality)}</p><p>${esc(n.operators)}</p><p><strong>Servicetyp:</strong> ${esc(n.service_types || 'Uppgift saknas')}</p><p>${n.operator_count} observerade aktörer<br>${n.median_delivery_days==null?'Leveransfrekvens saknas':nf.format(n.median_delivery_days)+' leveransdagar/vecka (median)'}</p><p>Referensnod 2026. Visar inte att sophämtningen stannar här.</p>`).addTo(nodes);
    byId('tract-count').textContent=nf.format(visible.length);byId('place-count').textContent=nf.format(points.length);byId('located-count').textContent=nf.format(points.length-reserves.length);byId('reserve-count').textContent=nf.format(reserves.length);byId('layer-count').textContent=`${enabled.size} / 35 tända`;
    byId('selection-summary').textContent=`${points.length} platsbeskrivningar på ${groups.size} kartpunkter · ${shownNodes.length} paketnoder som referens. Ringarna är illustrativa och visar inte täckning eller hämtningsområde.`;
    const review=visible.flatMap(t=>t.points.filter(p=>p.status!=='matched').map(p=>({t,p})));
    byId('quality-summary').textContent=`Platsmatchningar att granska · ${review.length}`;
    byId('quality-rows').innerHTML=review.map(({t,p})=>`<tr><td>${esc(t.label)}<br><strong>${esc(p.name)}</strong>${p.interpreted?`<br>Källtext: ${esc(p.source_text)}`:''}</td><td>${esc(p.reason)}<br><small>${esc(p.source)}</small></td></tr>`).join('')||'<tr><td colspan="2">Inga platsmatchningar att granska i urvalet.</td></tr>';
    if(autoFit)fit();
  }
  ['municipality','waste-type','pickup-date','show-nodes','single-nodes','show-rings'].forEach(id=>byId(id).addEventListener('change',()=>render(id==='municipality')));
  byId('weekdays').addEventListener('click',e=>{const b=e.target.closest('[data-weekday]');if(b){b.setAttribute('aria-pressed',String(b.getAttribute('aria-pressed')!=='true'));render();}});
  byId('tract-layers').addEventListener('change',e=>{const input=e.target,ids=input.dataset.tractLayer?[input.dataset.tractLayer]:data.tracts.filter(t=>t.municipality===input.dataset.municipalityLayer).map(t=>t.tract_id);for(const id of ids)if(input.checked)enabled.add(id);else enabled.delete(id);render();});
  byId('all-tracts').addEventListener('click',()=>{enabled=new Set(data.tracts.map(t=>t.tract_id));render();});
  byId('no-tracts').addEventListener('click',()=>{enabled.clear();render();});
  byId('reset').addEventListener('click',()=>{enabled=new Set(data.tracts.map(t=>t.tract_id));byId('municipality').value='';byId('waste-type').value='Matavfall';byId('pickup-date').value='';for(const b of byId('weekdays').children)b.setAttribute('aria-pressed','false');render(true);});
  byId('export').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([model.pointsCSV(visible)],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='sophamtningsplatser-granskning.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  byId('basemap').addEventListener('change',basemap);byId('fit').addEventListener('click',fit);
  basemap();render(true);
})();
