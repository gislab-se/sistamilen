const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const model = require('../prototypes/fredriksberg_resor/model.js');
const data = JSON.parse(fs.readFileSync(path.join(__dirname,'../prototypes/fredriksberg_resor/data/review-data.json'),'utf8'));

assert.equal(model.filterTrips(data,{}).length,1116);
const fred = model.filterTrips(data,{fred:true});
assert.equal(fred.length,14);
assert.equal(model.summarize(fred).fred,14);
assert(model.filterTrips(data,{date:'2026-09-22',fred:true}).every(t=>t.date==='2026-09-22' && model.isFred(t)));
assert(model.filterTrips(data,{locality:'Fredriksberg'}).every(model.isFred));
assert.equal(model.filterTrips(data,{search:'FILIPSTADSVÄGEN 36'}).length,14);
assert.equal(model.filterTrips(data,{search:'ingen match alls'}).length,0);
const groups = model.mapGroups(data,data.trips);
assert.equal(groups.unmapped,0);
assert.equal(groups.points.size,39);
assert.equal(groups.points.get('Fredriksberg').trips.size,14);
assert.equal(model.mapGroups(data,[]).points.size,0);
const addressGroups = model.mapGroups(data,data.trips,'address');
assert.equal(addressGroups.locatedAddresses.size+addressGroups.missingAddresses.size,272);
assert([...addressGroups.points.values()].every(p=>['address','street','building','poi','locality'].includes(p.precision)));
assert.equal(addressGroups.missingAddresses.size,0);
assert.equal(addressGroups.unmapped,0);
assert(addressGroups.fallbackAddresses.size>0);
assert(addressGroups.points.size>=80);
const sample={addresses:{A:{locality:'Ort',coordinate:[15,60],locality_coordinate:[15,60],street:'Gatan 1',address_coordinate:[15.01,60.01],geocoding:{status:'matched'}},B:{locality:'Ort',coordinate:[15,60],street:'Gatan 2',address_coordinate:null,geocoding:{status:'unmatched'}}}};
const sameTownTrips=[{id:'test',origin:'A',destination:'B'}];
assert.equal(model.mapGroups(sample,sameTownTrips,'locality').points.size,1);
assert.equal(model.mapGroups(sample,sameTownTrips,'address').points.size,1);
assert.equal(model.mapGroups(sample,sameTownTrips,'address').unmapped,1);
assert.equal(model.locationFor(sample,'B','address').coordinate,null);
assert.deepEqual(model.locationFor(sample,'A','address').coordinate,[15.01,60.01]);
const approximateSample={addresses:{
 A:{locality:'Ort',coordinate:[15,60],street:'Gatan 1',address_coordinate:[15.01,60.01],geocoding:{status:'review',precision:'street'}},
 B:{locality:'Ort',coordinate:[15,60],street:'Gatan 2',address_coordinate:[15.01,60.01],geocoding:{status:'review',precision:'street'}}}};
const approximateGroups=model.mapGroups(approximateSample,sameTownTrips,'address');
assert.equal(approximateGroups.points.size,1);
assert.equal(approximateGroups.locatedAddresses.size,2);
assert.equal([...approximateGroups.points.values()][0].precision,'street');
assert.equal([...approximateGroups.points.values()][0].name,'Gatan');
assert.equal([...approximateGroups.points.values()][0].addresses.size,2);
assert.equal(approximateGroups.relations.size,0);
const fallbackSample={addresses:{A:{...sample.addresses.A},B:{...sample.addresses.B,address_coordinate:[15,60],geocoding:{status:'fallback',precision:'locality'}}}};
const fallbackGroups=model.mapGroups(fallbackSample,sameTownTrips,'address');
assert.equal(fallbackGroups.points.size,2);
assert.equal(fallbackGroups.fallbackAddresses.size,1);
assert.equal(fallbackGroups.unmapped,0);
assert.equal(model.locationFor(fallbackSample,'B','address').status,'fallback');
const clinic=data.addresses['Vårdcentralen Sunnansjö, 770 12 Sunnansjö'];
assert.equal(clinic.geocoding.status,'matched');
assert.equal(clinic.geocoding.precision,'poi');
assert.equal(clinic.geocoding.source_url,'https://www.1177.se/hitta-vard/kontaktkort/Vardcentral-Sunnansjo/');
assert.deepEqual(clinic.address_coordinate,data.addresses['Sjukstugevägen 3, 770 12 Sunnansjö'].address_coordinate);
assert([...groups.relations.values()].every(r=>r.origin!==r.destination));
assert.equal(model.summarize(data.trips).distance,15161);
assert.equal(model.toCSV(fred).split('\r\n').length,15);
assert(model.toCSV([{origin:'=HYPERLINK("evil")'}]).includes("'=HYPERLINK"));
console.log('Filter, reconciliation display, map grouping and CSV export checks passed.');
const chain=model.chronology([
 {id:'b',start:'2026-09-23T09:00',end:'2026-09-23T10:00',origin:'Different start',destination:'C'},
 {id:'a',start:'2026-09-23T08:00',end:'2026-09-23T08:30',origin:'A',destination:'B'}
]);
assert.equal(chain[0].trip.id,'a');
assert.equal(chain[1].number,2);
assert.equal(chain[1].gap,true);
assert.equal(chain[1].overlap,false);
assert.equal(chain.length,2); // Gaps do not create fictional transfers.
const pilotVehicle=data.vehicles.find(v=>v.fredriksberg);
const jjw22=model.chronology(model.filterTrips(data,{vehicle:pilotVehicle.id,date:'2026-09-22'}));
assert(jjw22[0].trip.origin.startsWith('Vasagatan 12'));
assert.equal(data.vehicles.length,20);
assert.equal(new Set(data.vehicles.map(v=>v.label)).size,20);
assert.equal(model.filterTrips(data,{vehicles:[]}).length,0);
const selected=model.filterTrips(data,{vehicles:[pilotVehicle.id]});
assert.equal(selected.length,pilotVehicle.trip_count);
assert(selected.every(t=>t.vehicle===pilotVehicle.id));
assert(model.filterTrips(data,{vehicles:[pilotVehicle.id],search:pilotVehicle.short_name}).length>0);
assert(model.toCSV(selected,data.vehicles).includes(pilotVehicle.label));
