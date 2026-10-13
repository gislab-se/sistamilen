(function(root){
  'use strict';
  function normalizePlace(name){return String(name||'').toLocaleLowerCase('sv-SE').replace(/[^\p{L}\p{N}]/gu,'').replace(/^flodadalafloda$/,'dalafloda');}
  function visibleTracts(waste,filters={}){
    return (waste?.tracts||[]).filter(t=>(!filters.tracts||filters.tracts.includes(t.tract_id))
      &&(!filters.municipality||t.municipality===filters.municipality)
      &&(!filters.weekday||t.weekday===filters.weekday)
      &&(!filters.date||(filters.wasteType?t.dates[filters.wasteType]||[]:Object.values(t.dates).flat()).includes(filters.date)));
  }
  function filterMunicipality(trips,waste,municipality){
    return !municipality?trips:trips.filter(t=>[t.origin,t.destination].some(a=>waste.address_municipalities[a]===municipality));
  }
  function pointGroups(tracts){
    const groups=new Map();
    for(const tract of tracts)for(const point of tract.points){
      if(!point.coordinate)continue;
      const key=JSON.stringify(point.coordinate.map(v=>Number(v.toFixed(6))))+(point.status==='fallback'?':fallback':'');
      if(!groups.has(key))groups.set(key,{key,coordinate:point.coordinate,status:point.status,points:[],tracts:new Set(),color:tract.color});
      const group=groups.get(key);group.points.push({point,tract});group.tracts.add(tract.tract_id);
      if(point.status==='review'&&group.status!=='fallback')group.status='review';
    }
    return groups;
  }
  function overlaps(data,waste,tracts,trips,wasteType=''){
    const visits=new Map();
    for(const trip of trips)for(const address of new Set([trip.origin,trip.destination])){
      const locality=data.addresses[address]?.locality,municipality=waste.address_municipalities[address];
      if(!locality||!municipality)continue;
      const area=waste.address_areas?.[address],keys=[municipality+'|'+normalizePlace(locality)+'|'+trip.date];
      if(area)keys.push(municipality+'|scb:'+area.id+'|'+trip.date);
      for(const key of keys){
        if(!visits.has(key))visits.set(key,{trips:new Set(),vehicles:new Set(),locality:key.includes('|scb:')?area.name:locality,
          review:false,method:key.includes('|scb:')?'SCB tätort/småort 2023':'Matchat ortnamn inom kommunen'});
        const visit=visits.get(key);visit.trips.add(trip.id);visit.vehicles.add(trip.vehicle);
        visit.review||=['review','fallback'].includes(data.addresses[address].geocoding?.status);
      }
    }
    const matches=new Map();
    for(const tract of tracts){
      const dates=new Set(wasteType?tract.dates[wasteType]||[]:Object.values(tract.dates).flat());
      for(const point of tract.points){
        // Reserve tract anchors and road passages do not establish presence.
        // Streets can share a named SCB urban area, with uncertainty disclosed.
        if(point.status==='fallback'||(!point.comparison_area&&!['locality','place'].includes(point.precision)))continue;
        for(const date of dates){
          const key=tract.municipality+'|'+(point.comparison_area?'scb:'+point.comparison_area.id:normalizePlace(point.comparison_name||point.name))+'|'+date,visit=visits.get(key);
          if(!visit)continue;
          if(!matches.has(key))matches.set(key,{key,date,municipality:tract.municipality,locality:visit.locality,
            coordinate:point.coordinate,tracts:new Set(),trips:visit.trips,vehicles:visit.vehicles,review:visit.review,method:visit.method});
          const match=matches.get(key);match.tracts.add(tract.label);match.review||=point.status==='review';
        }
      }
    }
    return [...matches.values()].sort((a,b)=>a.date.localeCompare(b.date)||a.locality.localeCompare(b.locality,'sv-SE'));
  }
  function pointsCSV(tracts){
    const rows=[['kommun','trakt','plats','källtext','precision','status','lon','lat','källa','granskningsbehov']];
    for(const t of tracts)for(const p of t.points)rows.push([t.municipality,t.tract,p.name,p.source_text,p.precision,p.status,...(p.coordinate||['','']),p.source,p.reason]);
    return '\uFEFF'+rows.map(row=>row.map(v=>{let text=String(v??'');if(/^[\s]*[=+@-]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';}).join(';')).join('\r\n');
  }
  const model={normalizePlace,visibleTracts,pointGroups,overlaps,filterMunicipality,pointsCSV};
  if(typeof module!=='undefined'&&module.exports)module.exports=model;else root.WasteModel=model;
})(typeof window==='undefined'?globalThis:window);
