const assert=require('node:assert/strict'),fs=require('node:fs');
const model=require('../prototypes/fredriksberg_resor/waste-model.js');
const waste=JSON.parse(fs.readFileSync('prototypes/fredriksberg_resor/data/waste-data.json','utf8'));
const data=JSON.parse(fs.readFileSync('prototypes/fredriksberg_resor/data/review-data.json','utf8'));
assert.equal(model.visibleTracts(waste,{}).length,35);
assert.equal(model.visibleTracts(waste,{tracts:[]}).length,0);
assert.equal(model.visibleTracts(waste,{municipality:'Vansbro'}).length,7);
assert(model.visibleTracts(waste,{date:'2026-09-21',wasteType:'Matavfall'}).every(t=>t.dates.Matavfall.includes('2026-09-21')));
const groups=model.pointGroups(waste.tracts);assert(groups.size>100);
const matches=model.overlaps(data,waste,waste.tracts,data.trips);
assert(matches.length>0);
assert(matches.every(m=>m.date>='2026-09-21'&&m.date<='2026-09-27'));
assert.equal(model.overlaps(data,waste,waste.tracts,[]).length,0);
// Multiple waste types on one date and both endpoints of a same-place trip
// must not multiply trips, vehicles or collection appearances.
const sample={addresses:{A:{locality:'Nås'},B:{locality:'Nås'}}};
const sampleWaste={address_municipalities:{A:'Vansbro',B:'Vansbro'}};
const tract={label:'Vansbro · trakt 4',municipality:'Vansbro',dates:{Matavfall:['2026-09-21'],Restavfall:['2026-09-21']},
 points:[{name:'Nås',precision:'locality',status:'matched',coordinate:[14.5,60.4]},
         {name:'Nås',precision:'tract_anchor',status:'fallback',coordinate:[14.5,60.4]}]};
const trip={id:'a',date:'2026-09-21',vehicle:'transport-01',origin:'A',destination:'B'};
let result=model.overlaps(sample,sampleWaste,[tract],[trip]);
assert.equal(result.length,1);assert.equal(result[0].trips.size,1);assert.equal(result[0].vehicles.size,1);
assert.equal(model.overlaps(sample,sampleWaste,[{...tract,points:[tract.points[1]]}],[trip]).length,0);
assert.equal(model.overlaps(sample,sampleWaste,[tract],[{...trip,date:'2026-09-22'}]).length,0);
assert.equal(model.filterMunicipality([trip],sampleWaste,'Rättvik').length,0);
assert.equal(model.pointsCSV([tract]).split('\r\n').length,3);
console.log(`Waste layers, fallback exclusions and deduplicated overlaps passed (${matches.length} actual place/date matches).`);
