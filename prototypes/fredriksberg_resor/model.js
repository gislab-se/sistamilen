(function (root) {
  'use strict';
  function isFred(trip) { return /fredriksberg/i.test(trip.origin + ' ' + trip.destination); }
  function filterTrips(data, filters) {
    const query = (filters.search || '').trim().toLocaleLowerCase('sv-SE');
    const names=new Map((data.vehicles||[]).map(v=>[v.id,v.label]));
    return data.trips.filter(t => (!filters.date || t.date === filters.date)
      && (!filters.vehicle || t.vehicle === filters.vehicle)
      && (!filters.vehicles || filters.vehicles.includes(t.vehicle))
      && (!filters.fred || isFred(t))
      && (!filters.locality || [t.origin, t.destination].some(a => data.addresses[a].locality === filters.locality))
      && (!query || [names.get(t.vehicle)||t.vehicle, t.origin, t.destination, t.date].join(' ').toLocaleLowerCase('sv-SE').includes(query)));
  }
  function summarize(trips) {
    return {count: trips.length, distance: trips.reduce((n, t) => n + (t.distance_km || 0), 0),
      vehicles: new Set(trips.map(t => t.vehicle)).size, fred: trips.filter(isFred).length};
  }
  function locationFor(data, address, mode = 'locality') {
    const a = data.addresses[address];
    if (mode === 'address') {
      const g = a.geocoding || {};
      return {coordinate:a.address_coordinate || null, precision:g.precision || 'address', status:g.status || 'unmatched',
        source:g.source, sourceURL:g.source_url, reason:g.reason,geometry:g.geometry};
    }
    return {coordinate:a.locality_coordinate || a.coordinate, precision:'locality', status:'locality',
      source:a.locality_source || a.source, reason:'Ungefärligt ortankare'};
  }
  function mapGroups(data, trips, mode = 'locality') {
    const points = new Map(), relations = new Map();
    const missingAddresses = new Set(),locatedAddresses=new Set(),fallbackAddresses=new Set();
    let unmapped = 0;
    function add(address, trip) {
      const a = data.addresses[address];
      const location = locationFor(data,address,mode);
      if (!location.coordinate) {missingAddresses.add(address);return null;}
      locatedAddresses.add(address);
      if(location.status==='fallback')fallbackAddresses.add(address);
      const approximate=['street','building','poi','locality'].includes(location.precision);
      const key = mode === 'address' ? (location.geometry==='official_facility_point'?'official:'+JSON.stringify(location.coordinate):approximate?location.precision+':'+JSON.stringify(location.coordinate)+':'+a.locality:address) : a.locality;
      const name=mode==='address'?(location.status==='fallback'?a.locality+' · reserv':a.geocoding?.place_name|| (location.precision==='street'?a.street.replace(/\s+\d+\s*[A-Za-zÅÄÖåäö]?$/u,''):a.street)):(a.locality||address);
      if (!points.has(key)) points.set(key, {key, name, locality:a.locality,
        coordinate:location.coordinate, precision:location.precision, status:location.status, reason:location.reason,
        sources:new Set(), addresses:new Set(), trips:new Set(),vehicles:new Set()});
      const p = points.get(key); p.sources.add(location.source); p.addresses.add(address); p.trips.add(trip.id);p.vehicles.add(trip.vehicle);
      return key;
    }
    for (const t of trips) {
      const origin = add(t.origin, t), destination = add(t.destination, t);
      if (!origin || !destination) unmapped++;
      if (origin && destination && origin !== destination) {
        const key = [origin, destination].sort().join('|');
        if (!relations.has(key)) relations.set(key, {origin, destination, count: 0});
        relations.get(key).count++;
      }
    }
    return {points, relations, unmapped, missingAddresses,locatedAddresses,fallbackAddresses};
  }
  function csvCell(value) {
    let text = String(value ?? '');
    if (/^[\s]*[=+@-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }
  function toCSV(trips, vehicles = []) {
    const names=new Map(vehicles.map(v=>[v.id,v.label]));
    const fields = ['id', 'date', 'vehicle', 'vehicle_name', 'start', 'end', 'origin', 'destination', 'distance_km',
      'travel_seconds', 'stop_seconds', 'source_id', 'source_sheet', 'source_row'];
    return '\uFEFF' + [fields, ...trips.map(t => fields.map(f => f==='vehicle_name'?names.get(t.vehicle)||t.vehicle:t[f]))].map(row => row.map(csvCell).join(';')).join('\r\n');
  }
  function chronology(trips) {
    const sorted = [...trips].sort((a,b)=>a.start.localeCompare(b.start)||a.id.localeCompare(b.id));
    return sorted.map((trip,index)=>({trip,number:index+1,
      gap:index>0 && sorted[index-1].destination!==trip.origin,
      overlap:index>0 && sorted[index-1].end>trip.start,
      previous:index>0?sorted[index-1]:null}));
  }
  const model = {isFred, filterTrips, summarize, mapGroups, locationFor, toCSV, chronology};
  if (typeof module !== 'undefined' && module.exports) module.exports = model;
  else root.ReviewModel = model;
})(typeof window === 'undefined' ? globalThis : window);
