/* Address matching stays local; background tiles come from OpenStreetMap. */
(() => {
  'use strict';
  const data = window.REVIEW_DATA, model = window.ReviewModel;
  const routes = window.REVIEW_ROUTES;
  const vehicleProfiles=new Map((data.vehicles||[]).map(v=>[v.id,v]));
  let enabledVehicles=new Set(vehicleProfiles.keys());
  const vehicleName=id=>vehicleProfiles.get(id)?.label||id;
  const vehicleColor=id=>vehicleProfiles.get(id)?.color||'#285b83';
  const byId = id => document.getElementById(id);
  if (!data || !window.L) { byId('map-summary').textContent = 'Kartdata eller Leaflet saknas. Bygg om enligt README.'; return; }
  const nf = new Intl.NumberFormat('sv-SE', {maximumFractionDigits: 1});
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const asLatLng = coordinates => [coordinates[1], coordinates[0]];
  const map = L.map('map', {scrollWheelZoom:true,zoomControl:false,maxZoom:19}).setView([60.65, 14.8], 8);
  L.control.zoom({zoomInTitle:'Zooma in',zoomOutTitle:'Zooma ut'}).addTo(map);
  map.attributionControl.addAttribution('Ortankare: SCB 2023 / lokala paketnoder 2026');
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  L.control.scale({imperial:false}).addTo(map);
  let geography;
  if (window.REVIEW_GEOGRAPHY) {
    geography=L.geoJSON(window.REVIEW_GEOGRAPHY, {interactive:false, style:{color:'#c5d2b8', weight:.6, fillColor:'#dce5ce', fillOpacity:.44}}).addTo(map);
    map.attributionControl.addAttribution('Bakgrund: SCB DeSO 2025');
  }
  const marks = L.featureGroup().addTo(map), lines = L.layerGroup().addTo(map);
  map.createPane('relations'); map.getPane('relations').style.zIndex = '390';
  const services = L.layerGroup(), selected = L.layerGroup().addTo(map), roadLines=L.featureGroup().addTo(map), stops=L.layerGroup().addTo(map);
  const routeArrows=L.layerGroup().addTo(map);
  const vehicleLayers=new Map([...vehicleProfiles.keys()].map(id=>[id,L.featureGroup()]));
  let roadDrawings=[],selectedDrawing=null;
  if(routes)map.attributionControl.addAttribution('Vägrutter: Trafikverket NVDB 2026-08-18 · CC0');
  const background = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'});
  map.attributionControl.addAttribution('Adressmatchningar: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>');
  let tileErrors=0;
  background.on('loading',()=>{byId('basemap-status').textContent='Laddar bakgrundskarta…';});
  background.on('tileerror',()=>{tileErrors++;if(geography){geography.addTo(map);geography.eachLayer(layer=>layer.bringToBack?.());}byId('basemap-status').textContent='Bakgrundskartan kunde inte hämtas. Lokal SCB-bakgrund visas.';});
  background.on('load',()=>{if(!tileErrors)byId('basemap-status').textContent='OpenStreetMap · internet';});
  const markers = new Map();
  let current = [], groups, fred = false;
  const mode = () => byId('map-mode').value;
  const roadsOn = () => byId('route-mode').value==='roads';
  const vehicleColors=()=>byId('map-colors').value==='vehicle';
  const roadColor = klass => klass<=3?'#285b83':klass<=6?'#4b887f':'#ab8a53';
  const routeFor = trip => routes?.trips[trip.id];
  const pathFor = trip => routes?.paths[routeFor(trip)?.path];
  function routeLabel(trip) {
    const r=routeFor(trip),p=pathFor(trip);
    return p?`${nf.format(p.distance_km)} km · ${nf.format(p.travel_minutes)} min beräknat`:r?.status==='same_point'?'Samma kartpunkt · ingen rutt beräknas':r?.status==='outside_network'?'Utanför tillgängligt vägnät':r?.status==='no_path'?'Ingen sammanhängande väg hittad':'Ruttdata saknas';
  }
  function routeDetails(trip) {
    const p=pathFor(trip),ends=[trip.origin,trip.destination].map(a=>routes?.addresses[a]);
    return `<p><strong>${esc(routeLabel(trip))}</strong></p>${p?`<p>Funktionell vägklass: ${Object.entries(p.class_km).map(([k,v])=>`${k}: ${nf.format(v)} km`).join(' · ')}</p>`:`<p>${esc(routeFor(trip)?.reason)}</p>`}<p class="popup-source">Anslutning till bilväg: ${ends.map(a=>a?.status==='snapped'?`${nf.format(a.distance_m)} m (${esc(a.precision)})`:'saknas').join(' / ')}. Beräknat vägförslag, inte GPS-spår. Osäkra gatu-/ortpunkter påverkar rutten.</p>`;
  }
  function drawRoad(path, layer, emphasized=false, trip=null) {
    const drawing={path,emphasized,lines:[],sections:[],color:vehicleColors()?vehicleColor(trip?.vehicle):'#285b83'};
    for(const section of path.sections){
      const line=L.polyline(section.coordinates.map(asLatLng),{pane:'relations',color:emphasized?'#c27422':vehicleColors()?drawing.color:roadColor(section.class),weight:emphasized?6:3,opacity:emphasized ? .95 : .65});
      if(trip)line.bindPopup(`<h3>${esc(vehicleName(trip.vehicle))} · ${esc(trip.start.slice(0,16).replace('T',' '))}</h3><p>${esc(trip.origin)} → ${esc(trip.destination)}</p><p>${nf.format(trip.distance_km)} km enligt Excel.</p>${routeDetails(trip)}`);
      line.addTo(layer);
      drawing.lines.push(line);
    }
    if(emphasized)selectedDrawing=drawing;else roadDrawings.push(drawing);
  }
  function refreshRoads() {
    const zoom=map.getZoom(),offset=zoom<10?2:zoom<13?3:4;
    for(const drawing of [...roadDrawings,...(selectedDrawing?[selectedDrawing]:[])]){
      const points=drawing.path.sections.flatMap(s=>s.coordinates.map(c=>map.project(asLatLng(c),zoom)));
      // Offset to the left in the direction of travel. Reverse routes appear on
      // the opposite side, with a constant visual separation at each zoom level.
      const shifted=points.map((point,index)=>{
        let before=index-1,after=index+1;
        while(before>=0&&points[before].distanceTo(point)<.01)before--;
        while(after<points.length&&points[after].distanceTo(point)<.01)after++;
        const a=before>=0?points[before]:point,b=after<points.length?points[after]:point;
        const incoming=point.subtract(a),outgoing=b.subtract(point),il=Math.hypot(incoming.x,incoming.y),ol=Math.hypot(outgoing.x,outgoing.y);
        const n1=il?L.point(incoming.y/il,-incoming.x/il):null,n2=ol?L.point(outgoing.y/ol,-outgoing.x/ol):null;
        if(!n1&&!n2)return map.unproject(point,zoom);
        let normal=n1&&n2?n1.add(n2):n1||n2,length=Math.hypot(normal.x,normal.y);
        if(length<.1){normal=n2||n1;length=1;}
        normal=normal.divideBy(length);
        const reference=n2||n1,miter=Math.min(offset*2,offset/Math.max(.5,normal.x*reference.x+normal.y*reference.y));
        return map.unproject(point.add(normal.multiplyBy(miter)),zoom);
      });
      let cursor=0;
      drawing.sections=drawing.path.sections.map((section,index)=>{
        const coordinates=shifted.slice(cursor,cursor+section.coordinates.length);cursor+=section.coordinates.length;
        drawing.lines[index].setLatLngs(coordinates);return coordinates;
      });
    }
    refreshArrows();
  }
  function visibleSegment(a,b,size) {
    let start=0,end=1;
    const dx=b.x-a.x,dy=b.y-a.y;
    for(const [p,q] of [[-dx,a.x-16],[dx,size.x-16-a.x],[-dy,a.y-16],[dy,size.y-16-a.y]]){
      if(!p){if(q<0)return null;continue;}
      const ratio=q/p;if(p<0)start=Math.max(start,ratio);else end=Math.min(end,ratio);
      if(start>end)return null;
    }
    return [start,end];
  }
  function refreshArrows() {
    routeArrows.clearLayers();
    if(!roadsOn()||!byId('relations').checked||!byId('direction-arrows').checked)return;
    const zoom=map.getZoom(),size=map.getSize(),spacing=zoom<10?120:zoom<13?96:76,fontSize=zoom<10?13:zoom<13?15:zoom<16?17:19;
    const occupied=[],pointPixels=groups?[...groups.points.values()].map(p=>map.latLngToContainerPoint(asLatLng(p.coordinate))):[];
    // Selected trip gets first choice of arrow positions. Other routes share a
    // screen-space collision check so overlapping trips cannot pile up arrows.
    for(const drawing of [...(selectedDrawing?[selectedDrawing]:[]),...roadDrawings]){
      let travelled=0;
      for(const section of drawing.sections){
        for(let i=1;i<section.length;i++){
          const a=map.latLngToContainerPoint(section[i-1]),b=map.latLngToContainerPoint(section[i]),length=a.distanceTo(b);
          if(length<.01)continue;
          const visible=visibleSegment(a,b,size);
          if(visible){
            const step=spacing/2,first=Math.ceil((travelled+length*visible[0]-step/2)/step);
            for(let n=first;n*step+step/2<=travelled+length*visible[1];n++){
              const fraction=(n*step+step/2-travelled)/length,pixel=a.add(b.subtract(a).multiplyBy(fraction));
              const angle=Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI,arrowSize=fontSize+(drawing.emphasized?2:0);
              if(occupied.some(p=>p.pixel.distanceTo(pixel)<(Math.cos((p.angle-angle)*Math.PI/180)<-.8?fontSize*1.7:spacing*.72))||pointPixels.some(p=>p.distanceTo(pixel)<25))continue;
              occupied.push({pixel,angle});
              L.marker(map.containerPointToLatLng(pixel),{pane:'relations',interactive:false,keyboard:false,icon:L.divIcon({className:'',html:`<span class="route-arrow" style="display:block;color:${drawing.emphasized?'#c27422':drawing.color};font-size:${arrowSize}px;line-height:${arrowSize}px;transform:rotate(${angle}deg)">➜</span>`,iconSize:[arrowSize,arrowSize],iconAnchor:[arrowSize/2,arrowSize/2]})}).addTo(routeArrows);
            }
          }
          travelled+=length;
        }
      }
    }
  }
  const position = address => model.locationFor(data,address,mode());
  const precisionLabel = location => location.status==='fallback' ? ((location.source||'').includes('medelpunkt')?'Ortankare · reservpunkt':'Ortcentroid · reservpunkt') : location.precision==='locality' ? 'Ortankare · ungefärligt' : !location.coordinate ? 'Kartpunkt saknas' : location.precision==='poi' ? (location.status==='matched'?'Verksamhetsträff · officiell källa':'Platsträff · behöver granskas') : location.precision==='street' ? 'Gatuträff · ungefärlig' : location.precision==='building' ? 'Husträff · entré behöver verifieras' : location.status==='review' ? 'Adressmatchning · behöver granskas' : 'Adressmatchning';
  function fillSelect(id, values, labels = x => x) {
    for (const value of [...new Set(values)].sort((a,b) => a.localeCompare(b,'sv-SE'))) {
      const option = document.createElement('option'); option.value = value; option.textContent = labels(value); byId(id).append(option);
    }
  }
  fillSelect('date', data.trips.map(t => t.date), value => new Intl.DateTimeFormat('sv-SE', {weekday:'short', day:'numeric', month:'short', timeZone:'UTC'}).format(new Date(value+'T12:00:00Z')));
  fillSelect('vehicle', data.trips.map(t => t.vehicle),vehicleName);
  fillSelect('locality', Object.values(data.addresses).map(a => a.locality).filter(Boolean));
  byId('vehicle-layers').innerHTML=[...vehicleProfiles.values()].map(v=>`<label class="vehicle-layer" data-layer-id="${esc(v.id)}"><input type="checkbox" data-vehicle-layer="${esc(v.id)}" checked><i class="vehicle-swatch" style="background:${esc(v.color)}"></i><span class="vehicle-name">${esc(v.label)}</span><small></small></label>`).join('');
  function renderVehicleLayers(filters) {
    const counts=new Map();
    for(const t of model.filterTrips(data,{...filters,vehicle:'',vehicles:undefined}))counts.set(t.vehicle,(counts.get(t.vehicle)||0)+1);
    for(const label of byId('vehicle-layers').children){const id=label.dataset.layerId,count=counts.get(id)||0;label.dataset.count=String(count);label.querySelector('input').checked=enabledVehicles.has(id);label.querySelector('small').textContent=String(count);label.title=`${vehicleName(id)} · ${count} resor med aktuella datum-/orts-/sökfilter`;}
    byId('vehicle-layer-count').textContent=`${enabledVehicles.size} / ${vehicleProfiles.size} tända`;
  }
  for (const node of data.nodes) {
    L.circleMarker(asLatLng(node.coordinate), {radius:4, color:'#fff', weight:1.5, fillColor:'#416c8b', fillOpacity:.95})
      .bindPopup(`<h3>${esc(node.name.trim())}</h3><p>${esc(node.address)}, ${esc(node.locality)}</p><p>${esc(node.actors)}</p><p class="popup-source">Observerad paketservicenod 2026. Visar inte att en resa eller paketleverans stannat här.</p>`).addTo(services);
  }
  function fit() {
    if (marks.getLayers().length) {
      const bounds=marks.getBounds();if(roadLines.getLayers().length)bounds.extend(roadLines.getBounds());
      map.fitBounds(bounds.pad(.15), {maxZoom:mode()==='address'?17:11});
    }
    else {
      const anchors=current.flatMap(t=>[t.origin,t.destination]).map(a=>model.locationFor(data,a,'locality').coordinate).filter(Boolean);
      if(anchors.length)map.fitBounds(L.latLngBounds(anchors.map(asLatLng)).pad(.15),{maxZoom:11});
    }
  }
  function drawMap() {
    marks.clearLayers(); lines.clearLayers(); roadLines.clearLayers(); stops.clearLayers(); selected.clearLayers(); markers.clear();
    for(const layer of vehicleLayers.values())layer.clearLayers();
    roadDrawings=[];selectedDrawing=null;routeArrows.clearLayers();
    map.closePopup();
    groups = model.mapGroups(data, current,mode());
    for (const p of groups.points.values()) {
      const focus = /fredriksberg/i.test(p.locality);
      const marker = L.circleMarker(asLatLng(p.coordinate), {radius:mode()==='address'?Math.min(13,4+Math.sqrt(p.trips.size)*.5):Math.min(21,5+Math.sqrt(p.trips.size)*.7),
        color:focus?'#735929':'#fff', weight:focus?2.5:1.8, fillColor:p.status==='fallback'?'#7e8790':p.status==='review'?'#b48735':'#628649', fillOpacity:.87,dashArray:p.status==='fallback'?'3 2':null});
      marker.bindTooltip(esc(p.name), {permanent:false, direction:'right', offset:[9,0], className:'place-label'});
      marker.bindPopup(`<h3>${esc(p.name)}</h3><p>${esc(p.locality)} · <strong>${nf.format(p.trips.size)}</strong> detaljresor med start eller stopp här.</p><p>${[...p.vehicles].map(id=>`<span class="popup-vehicle"><i style="background:${esc(vehicleColor(id))}"></i>${esc(vehicleName(id))}</span>`).join('')}</p><p>${esc(precisionLabel({...p,coordinate:p.coordinate}))}. ${esc(p.reason)}</p><ul class="popup-addresses">${[...p.addresses].sort().map(a=>`<li>${esc(a)}</li>`).join('')}</ul><p class="popup-source">Källa: ${[...p.sources].map(esc).join('; ')}</p>`);
      marker.addTo(marks); markers.set(p.key, marker);
    }
    if (byId('relations').checked && !roadsOn()) {
      const relationGroups=vehicleColors()?[...new Set(current.map(t=>t.vehicle))].map(id=>({id,groups:model.mapGroups(data,current.filter(t=>t.vehicle===id),mode())})):[{id:null,groups}];
      for (const group of relationGroups)for (const relation of group.groups.relations.values()) {
        const a = group.groups.points.get(relation.origin), b = group.groups.points.get(relation.destination);
        L.polyline([asLatLng(a.coordinate),asLatLng(b.coordinate)], {pane:'relations',color:group.id?vehicleColor(group.id):'#71865c', weight:Math.min(5,1+Math.log2(relation.count+1)*.4), opacity:.4, dashArray:'5 7'})
          .bindPopup(`<strong>${esc(a.name)} ↔ ${esc(b.name)}</strong><p>${nf.format(relation.count)} observerade resor i båda riktningarna.</p><p>Schematisk relation mellan ankare, inte körväg.</p>`).addTo(lines);
      }
    }
    if(byId('relations').checked && roadsOn() && routes){
      const drawn=new Set();
      for(const trip of current){const r=routeFor(trip),path=pathFor(trip),key=trip.vehicle+':'+r?.path;if(path&&!drawn.has(key)){drawRoad(path,vehicleLayers.get(trip.vehicle),false,trip);drawn.add(key);}}
      for(const layer of vehicleLayers.values())if(layer.getLayers().length)layer.addTo(roadLines);
    }
    byId('road-legend').hidden=!roadsOn();byId('schematic-legend').hidden=roadsOn();
    byId('road-legend').innerHTML=vehicleColors()?'<span>Linjer och pilar följer fordonslagrens färger i sidpanelen.</span><span>Färdriktningar visas parallellt · pilar anpassas efter zoom</span>':'<span><i style="background:#285b83"></i> Vägklass 0–3</span><span><i style="background:#4b887f"></i> Vägklass 4–6</span><span><i style="background:#ab8a53"></i> Vägklass 7–9</span><span>Färdriktningar visas parallellt · pilar anpassas efter zoom</span>';
    const routed=current.filter(t=>routeFor(t)?.status==='routed').length,same=current.filter(t=>routeFor(t)?.status==='same_point').length;
    byId('route-note').textContent=roadsOn()?`${nf.format(routed)} av ${nf.format(current.length)} resor har beräknad vägrutt. ${nf.format(same)} har samma kartpunkt; ${nf.format(current.length-routed-same)} saknar möjlig rutt i länsuttaget. Klass 0 är högst prioriterad, 9 lägst. Ruttning från adress-/reservpunkter, även i ortvyn. Modell för lätt motorfordon; tungfordonskrav och tidsvillkor behöver granskas. Ingen faktisk körväg eller depå antas.`:'Schematiska relationer slår ihop resor i båda riktningarna. Linjerna följer inte vägnätet.';
    updateLabels();
    byId('map-summary').textContent = mode()==='address'?`${nf.format(groups.locatedAddresses.size)} adresser på ${nf.format(groups.points.size)} punkter · ${nf.format(groups.relations.size)} schematiska resrelationer`:`${nf.format(groups.points.size)} ortankare · ${nf.format(groups.relations.size)} schematiska resrelationer`;
    if(roadsOn())byId('map-summary').textContent=`${nf.format(groups.points.size)} ${mode()==='address'?'adress-/platspunkter':'ortankare'} · ${nf.format(routed)} resor med beräknad vägrutt`;
    byId('unmapped-label').textContent = groups.missingAddresses.size ? `${nf.format(groups.missingAddresses.size)} adresser saknar kartpunkt · ${nf.format(groups.unmapped)} resor berörs` : groups.fallbackAddresses.size?`Alla adresser kan visas · ${nf.format(groups.fallbackAddresses.size)} vid ortcentroid/ortankare`:'Alla valda adresser har kartpunkt';
    byId('point-legend').textContent=mode()==='address'?'Adress-/platsmatchning':'Ortankare · ungefärligt';
    byId('review-legend').hidden=mode()!=='address';
    byId('fallback-legend').hidden=mode()!=='address';
    byId('precision-text').textContent=mode()==='address'?(groups.points.size?'Grönt: adress- eller verifierad verksamhetsträff. Orange: ungefärlig gatu-/platsträff eller uppgift att granska. Grått: ortcentroid/ortankare när adressen inte hittats. Punkterna är inte GPS-positioner.':'Inga kartpunkter i utsnittet.'):'Flera adresser på samma ort delar ett ungefärligt ankare. Linjer visar schematiska samband, inte körvägar. Körsträckan hämtas från Excel.';
    byId('mode-hint').textContent=mode()==='address'?'Gröna matchningar, orange osäkra träffar. Grå reservpunkter ligger vid ortens centrum.':'En gemensam, ungefärlig kartpunkt per ort.';
    byId('map').setAttribute('aria-label',mode()==='address'?'Karta med adresspunkter':'Karta med ortankare');
    renderItinerary();
    refreshRoads();
  }
  function updateLabels() {
    if (!groups) return;
    const occupied = [], size = map.getSize();
    const ordered = [...groups.points.values()].sort((a,b) => (Number(/fredriksberg/i.test(b.locality))-Number(/fredriksberg/i.test(a.locality))) || b.trips.size-a.trips.size);
    for (const point of ordered) {
      const marker = markers.get(point.key), pixel = map.latLngToContainerPoint(marker.getLatLng());
      const box = {left:pixel.x+14,right:pixel.x+point.name.length*6+32,top:pixel.y-15,bottom:pixel.y+15};
      const visible = pixel.x>0 && pixel.x<size.x && pixel.y>0 && pixel.y<size.y && !occupied.some(b=>box.left<b.right && box.right>b.left && box.top<b.bottom && box.bottom>b.top);
      marker.getTooltip().options.permanent=visible;
      if (visible) {marker.openTooltip();occupied.push(box);} else marker.closeTooltip();
    }
  }
  map.on('zoomend moveend resize',updateLabels);
  map.on('zoomstart',()=>routeArrows.clearLayers());
  map.on('zoomend',refreshRoads);
  let arrowFrame;
  map.on('moveend resize',()=>{cancelAnimationFrame(arrowFrame);arrowFrame=requestAnimationFrame(refreshArrows);});
  let previousMapSize=[byId('map').clientWidth,byId('map').clientHeight];
  window.addEventListener('resize',()=>{
    const size=[byId('map').clientWidth,byId('map').clientHeight];
    if(size.some((value,index)=>value!==previousMapSize[index])){previousMapSize=size;map.invalidateSize();fit();}
  });
  function showTrip(id, row) {
    const trip = current.find(t => t.id === id); if (!trip) return;
    document.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected')); row?.classList.add('selected'); selected.clearLayers();
    selectedDrawing=null;
    document.querySelectorAll('.itinerary-row').forEach(r=>r.classList.toggle('active',r.dataset.trip===id));
    const locations=[position(trip.origin),position(trip.destination)];
    const coordinates = [...new Map(locations.map(a=>[JSON.stringify(a.coordinate),a.coordinate])).values()].filter(Boolean);
    for (const coordinate of coordinates) {
      L.circleMarker(asLatLng(coordinate), {radius:22,color:'#a77d29',fillOpacity:.1,weight:3}).addTo(selected);
    }
    const path=pathFor(trip);
    if(roadsOn()&&path)drawRoad(path,selected,true,trip);
    refreshRoads();
    if (coordinates.length) {const bounds=L.latLngBounds(coordinates.map(asLatLng));if(roadsOn()&&path)for(const section of path.sections)bounds.extend(L.latLngBounds(section.coordinates.map(asLatLng)));map.fitBounds(bounds.pad(.2), {maxZoom:mode()==='address'?17:12});}
    const place = locations[1].coordinate ? locations[1] : locations[0];
    if (place.coordinate) {
      L.popup().setLatLng(asLatLng(place.coordinate)).setContent(`<h3>${esc(vehicleName(trip.vehicle))} · ${esc(trip.date)}</h3><p>${esc(trip.origin)} → ${esc(trip.destination)}</p><p>${nf.format(trip.distance_km)} km · ${nf.format((trip.travel_seconds || 0)/60)} min enligt Excel.</p>${roadsOn()?routeDetails(trip):''}<p><strong>${esc(precisionLabel(place))}.</strong> ${locations.some(a=>!a.coordinate)?'En eller båda adresspunkterna saknas.':''}</p><p class="popup-source">Kartkälla: ${esc(place.source)}. Resa: ${esc(trip.source_id)}, blad ${esc(vehicleName(trip.source_sheet))}, rad ${trip.source_row}.</p>`).openOn(map);
    } else {
      fit();
      byId('precision-text').textContent='Den valda resans adresspunkter saknar säker träff. Välj Ortankare för att se resans orter.';
    }
  }
  function renderItinerary() {
    const date=byId('date').value,vehicle=byId('vehicle').value;
    if(!date||!vehicle){byId('itinerary-summary').textContent='Välj ett fordon och ett datum, eller öppna pilotdagen.';byId('itinerary-context').textContent='';byId('itinerary-rows').innerHTML='';return;}
    const complete=model.filterTrips(data,{date,vehicle}),chain=model.chronology(current),full=model.chronology(complete);
    byId('itinerary-summary').textContent=`${vehicleName(vehicle)} · ${date} · ${current.length} av ${complete.length} detaljresor visas`;
    if(!full.length){byId('itinerary-context').textContent='Inga registrerade detaljresor för detta fordon och datum.';byId('itinerary-rows').innerHTML='';return;}
    const differences=data.flags.filter(f=>f.type==='summary_difference'&&f.vehicle===vehicle&&f.source_id.startsWith(date)),missing=differences.reduce((n,f)=>n+f.difference,0);
    byId('itinerary-context').innerHTML=`<p><strong>Första registrerade start:</strong> ${esc(full[0].trip.origin)} · ${esc(full[0].trip.start.slice(11,16))}<br><strong>Sista registrerade ankomst:</strong> ${esc(full.at(-1).trip.destination)} · ${esc(full.at(-1).trip.end.slice(11,16))}</p><p>Ordning enligt starttid i detaljbladen. ${missing?`${missing} resa/resor saknas jämfört med dagssummeringen. `:''}Fredriksberg läggs aldrig till som extra start eller återresa.${current.length!==complete.length?' Ytterligare filter döljer delar av dagen.':''}</p>`;
    const numbers=new Map(full.map(e=>[e.trip.id,e.number]));
    byId('itinerary-rows').innerHTML=chain.map(e=>`${e.gap?`<div class="itinerary-gap">Lucka: föregående resa slutar på ${esc(e.previous.destination)}. Nästa startar på en annan adress; ingen förbindelse har lagts till.</div>`:''}${e.overlap?'<div class="itinerary-gap">Tiderna överlappar enligt underlaget.</div>':''}<button type="button" class="itinerary-row" data-trip="${esc(e.trip.id)}"><span class="itinerary-number">${numbers.get(e.trip.id)}</span><span class="itinerary-time">${esc(e.trip.start.slice(11,16))}<br>↓ ${esc(e.trip.end.slice(11,16))}</span><span class="itinerary-address">${esc(e.trip.origin)} → ${esc(e.trip.destination)}<small>Excel: ${nf.format(e.trip.distance_km)} km · ${nf.format((e.trip.travel_seconds||0)/60)} min<br>NVDB: ${esc(routeLabel(e.trip))}</small></span></button>`).join('');
    if(roadsOn()){
      const visits=[];
      for(const e of chain){if(e.number===1||e.gap)visits.push({address:e.trip.origin,label:e.number===1?'S':`${numbers.get(e.trip.id)}↗`,trip:e.trip});visits.push({address:e.trip.destination,label:String(numbers.get(e.trip.id)),trip:e.trip});}
      const places=new Map();
      for(const visit of visits){const loc=model.locationFor(data,visit.address,'address');if(!loc.coordinate)continue;const key=JSON.stringify(loc.coordinate);if(!places.has(key))places.set(key,{loc,visits:[]});places.get(key).visits.push(visit);}
      for(const place of places.values()){
        const labels=place.visits.map(v=>v.label),numbers=labels.filter(v=>/^\d+$/.test(v)).map(Number),prefix=labels.includes('S')?'S·':'';
        const label=prefix+(numbers.length>1?`${Math.min(...numbers)}–${Math.max(...numbers)}`:numbers.join(''))||labels.join('·');
        L.marker(asLatLng(place.loc.coordinate),{icon:L.divIcon({className:'route-stop',html:esc(label),iconSize:[label.length>3?43:33,29],iconAnchor:[16,14]})}).bindPopup(`<h3>Besök vid samma kartpunkt</h3>${place.visits.map(v=>`<p><strong>${esc(v.label)}</strong> · ${esc(v.trip.start.slice(11,16))} → ${esc(v.trip.end.slice(11,16))}<br>${esc(v.address)}</p>`).join('')}<p>${esc(precisionLabel(place.loc))}</p>`).addTo(stops);
      }
    }
  }
  function renderTrips() {
    byId('table-count').textContent = nf.format(current.length);
    byId('trip-rows').innerHTML = current.map(t => {
      const locations=[position(t.origin),position(t.destination)];
      const missing=locations.some(a=>!a.coordinate),needsReview=locations.some(a=>['review','fallback'].includes(a.status));
      const label=missing?'Kartpunkt saknas':mode()==='locality'?'Ortankare':locations.some(a=>a.status==='fallback')?'Ortcentroid/ortankare · reserv':locations.some(a=>a.precision==='poi')?'Plats-/verksamhetsträff':locations.some(a=>a.precision==='street')?'Gatunivå · ungefärlig':locations.some(a=>a.precision==='building')?'Husträff · granska entré':needsReview?'Träff att granska':'Adressmatchning';
      return `<tr data-trip="${esc(t.id)}"><td><button class="trip-link" data-trip-button="${esc(t.id)}" type="button">${esc(t.start.substring(0,10))} <strong>${esc(t.start.substring(11,16))}</strong></button></td><td>${esc(vehicleName(t.vehicle))}</td><td>${esc(t.origin)}</td><td>${esc(t.destination)}</td><td class="numeric">${t.distance_km===null?'—':nf.format(t.distance_km)}</td><td class="numeric">${t.travel_seconds===null?'—':nf.format(t.travel_seconds/60)+' min'}</td><td><span class="precision-tag ${missing?'missing':needsReview?'review':mode()==='address'?'address':''}">${label}</span></td></tr>`;
    }).join('') || '<tr><td colspan="7" class="empty-row">Inga resor matchar dina filter. Prova att återställa utsnittet.</td></tr>';
    byId('trip-footer').textContent = `${nf.format(current.length)} detaljresor · klicka på en resa för att visa dess ${mode()==='address'?'adresspunkter':'ortankare'}. Tider återges enligt Excel, med tidsreferens Europe/Stockholm; källan anger ingen tidszon.`;
  }
  function renderReports(filters) {
    const allDaily = data.reports.filter(r=>r.kind==='day');
    const totalReported = allDaily.reduce((n,r)=>n+r.trip_count,0);
    const qa = data.flags.filter(f=>f.type==='summary_difference' && enabledVehicles.has(f.vehicle) && (!filters.date||f.source_id.startsWith(filters.date)) && (!filters.vehicle||f.vehicle===filters.vehicle));
    byId('quality-count').textContent = nf.format(qa.length);
    byId('qa-intro').textContent = `Totalt anger dagssummeringarna ${nf.format(totalReported)} resor; ${nf.format(data.trips.length)} finns på detaljbladen. Skillnaden är ${nf.format(totalReported-data.trips.length)}. Tabellen följer datum- och fordonsfilter. Orts- och sökfilter kan inte tillämpas på summeringarna.`;
    const addresses=[...new Set(current.flatMap(t=>[t.origin,t.destination]))].map(a=>data.addresses[a]);
    const missing=addresses.filter(a=>!a.address_coordinate),review=addresses.filter(a=>['review','fallback'].includes(a.geocoding?.status));
    const approximate=addresses.filter(a=>['street','building'].includes(a.geocoding?.precision));
    const places=addresses.filter(a=>a.geocoding?.precision==='poi'),fallback=addresses.filter(a=>a.geocoding?.status==='fallback');
    byId('qa-geography').textContent = `${nf.format(addresses.length)} adresser i utsnittet: ${nf.format(addresses.length-missing.length-approximate.length-places.length-fallback.length)} adressmatchningar, ${nf.format(approximate.length)} gatu-/husträffar, ${nf.format(places.length)} plats-/verksamhetsträffar, ${nf.format(fallback.length)} reservpunkter vid ortcentroid/ortankare. ${nf.format(missing.length)} utan kartpunkt. ${data.meta.address_match_method||''}`;
    byId('address-quality-rows').innerHTML=review.map(a=>`<tr><td>${esc(a.address)}</td><td>${esc(precisionLabel(model.locationFor(data,a.address,'address')))}</td><td>${esc(a.geocoding?.reason||'Ingen matchning')}</td></tr>`).join('')||'<tr><td colspan="3" class="empty-row">Inga adressmatchningar att granska i detta utsnitt.</td></tr>';
    byId('quality-rows').innerHTML = qa.map(f=>`<tr><td>${esc(f.source_id.substring(0,10))}</td><td>${esc(vehicleName(f.vehicle))}</td><td class="numeric">${nf.format(f.reported)}</td><td class="numeric">${nf.format(f.imported)}</td><td class="numeric">${nf.format(f.difference)}</td></tr>`).join('') || '<tr><td colspan="5" class="empty-row">Inga summeringsavvikelser för valda datum och fordon.</td></tr>';
    const month = data.reports.filter(r=>r.kind==='month' && enabledVehicles.has(r.vehicle) && (!filters.vehicle||r.vehicle===filters.vehicle));
    byId('month-summary').textContent = `${nf.format(month.reduce((n,r)=>n+r.trip_count,0))} rapporterade resor · ${nf.format(month.reduce((n,r)=>n+(r.distance_km||0),0))} km · ${nf.format(month.length)} fordon.`;
    byId('month-rows').innerHTML = month.map(r=>`<tr><td>${esc(vehicleName(r.vehicle))}</td><td class="numeric">${nf.format(r.trip_count)}</td><td class="numeric">${nf.format(r.distance_km)}</td><td class="numeric">${nf.format(r.co2_source)}</td></tr>`).join('');
  }
  function update(autoFit = true) {
    const filters = {date:byId('date').value,vehicle:byId('vehicle').value,vehicles:[...enabledVehicles],locality:byId('locality').value,search:byId('search').value,fred};
    current = model.filterTrips(data,filters);
    const summary = model.summarize(current);
    byId('trip-count').textContent = nf.format(summary.count); byId('distance').textContent = nf.format(summary.distance);
    byId('vehicle-count').textContent = nf.format(summary.vehicles); byId('fred-count').textContent = nf.format(summary.fred);
    byId('period-label').textContent = filters.date || '21–27 september 2026';
    byId('fredriksberg').setAttribute('aria-pressed',String(fred));
    renderVehicleLayers(filters);renderTrips(); renderReports(filters); drawMap(); if (autoFit) fit();
  }
  byId('filters').addEventListener('submit',event=>event.preventDefault());
  ['date','locality'].forEach(id=>byId(id).addEventListener('change',()=>update()));
  let timer; byId('search').addEventListener('input',()=>{clearTimeout(timer); timer=setTimeout(()=>update(),150);});
  byId('fredriksberg').addEventListener('click',()=>{fred=!fred; if(fred){byId('filters').reset();enabledVehicles=new Set(vehicleProfiles.keys());}update();});
  byId('reset-filters').addEventListener('click',()=>{byId('filters').reset();fred=false;enabledVehicles=new Set(vehicleProfiles.keys());update();});
  byId('pilot-day').addEventListener('click',()=>{const pilot=[...vehicleProfiles.values()].find(v=>v.fredriksberg);if(!pilot)return;byId('filters').reset();fred=false;enabledVehicles=new Set([pilot.id]);byId('date').value='2026-09-23';byId('vehicle').value=pilot.id;byId('route-mode').value='roads';byId('map-mode').value='address';byId('relations').checked=true;update();});
  byId('vehicle-layers').addEventListener('change',event=>{const id=event.target.dataset.vehicleLayer;if(!id)return;if(event.target.checked)enabledVehicles.add(id);else enabledVehicles.delete(id);byId('vehicle').value='';update(false);});
  byId('all-vehicles').addEventListener('click',()=>{enabledVehicles=new Set(vehicleProfiles.keys());byId('vehicle').value='';update(false);});
  byId('no-vehicles').addEventListener('click',()=>{enabledVehicles.clear();byId('vehicle').value='';update(false);});
  byId('vehicle').addEventListener('change',()=>{if(byId('vehicle').value)enabledVehicles.add(byId('vehicle').value);update();});
  byId('map-colors').addEventListener('change',()=>drawMap());
  byId('route-mode').addEventListener('change',()=>{drawMap();fit();});
  byId('relations').addEventListener('change',()=>drawMap());
  byId('direction-arrows').addEventListener('change',refreshArrows);
  byId('nodes').addEventListener('change',()=>{if(byId('nodes').checked)services.addTo(map);else map.removeLayer(services);});
  function toggleBasemap() {
    if(byId('basemap').checked){tileErrors=0;if(geography)map.removeLayer(geography);background.addTo(map);}
    else {map.removeLayer(background);if(geography)geography.addTo(map);byId('basemap-status').textContent='Lokal SCB-bakgrund · utan internet';}
  }
  byId('basemap').addEventListener('change',toggleBasemap);
  byId('map-mode').addEventListener('change',()=>update());
  byId('fit').addEventListener('click',fit);
  byId('trip-rows').addEventListener('click',event=>{const row=event.target.closest('tr[data-trip]');if(row)showTrip(row.dataset.trip,row);});
  byId('itinerary-rows').addEventListener('click',event=>{const row=event.target.closest('[data-trip]');if(row)showTrip(row.dataset.trip);});
  const tabs = [...document.querySelectorAll('[data-tab]')];
  function activateTab(tab) {
    tabs.forEach(button=>{const active=button===tab;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;byId('panel-'+button.dataset.tab).hidden=!active;});
  }
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',()=>activateTab(tab));
    tab.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;activateTab(tabs[next]);tabs[next].focus();}});
  });
  byId('export').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([model.toCSV(current,data.vehicles)],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='resor-granskning.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  toggleBasemap();
  update();
})();
