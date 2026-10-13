"""One-time, explicitly authorized Nominatim lookup for the review dataset.

Single thread, one machine, >=1.2 seconds between request starts, persistent
query cache. Only address strings are sent. The app never calls this service.
Policy: https://operations.osmfoundation.org/policies/nominatim/
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.build_fredriksberg_review import APP, address_parts
from scripts.geocode_review_addresses import MATCH_CACHE, canonical, distance_km, street_number

CACHE = APP / "source" / "nominatim_queries.json"
ENDPOINT = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SistaMilen-Dalarna-local-review/1.0 (https://github.com/gislab-se/sistamilen)"


def select_result(address, results, anchor):
    street, postcode, _ = address_parts(address)
    road, house = street_number(street)
    precise, approximate = [], []
    for result in results:
        detail = result.get("address", {})
        if detail.get("country_code") != "se":
            continue
        coordinate = [float(result["lon"]),float(result["lat"])]
        returned_postcode = canonical(detail.get("postcode", ""))
        radius = distance_km(anchor, coordinate) if anchor else math.inf
        if radius > 30 or (returned_postcode != postcode and radius > 10):
            continue
        returned_road = canonical(detail.get("road", detail.get("pedestrian", detail.get("residential", ""))))
        if returned_road != road:
            continue
        returned_house = canonical(detail.get("house_number", ""))
        exact = bool(house and returned_house == house)
        geometry = "geocoder_address_point"
        reason = "Gatunamn och hela husnumret matchar; geografiskt kontrollerad mot ortankaret"
        precision = "address"
        status = "matched"
        if exact:
            if returned_postcode and returned_postcode != postcode:
                status, reason = "review", "Gatunamn och husnummer matchar men postnumret avviker"
        elif (result.get("category",result.get("class")) == "highway" or result.get("addresstype") == "road") and not returned_house:
            bounds = result.get("boundingbox", [])
            if len(bounds) != 4 or distance_km([float(bounds[2]),float(bounds[0])],[float(bounds[3]),float(bounds[1])]) > 5:
                continue
            status, precision, geometry = "review", "street", "representative_street_point"
            reason = "Gatunivå: hela husnumret saknas i kartträffen; punkten är inte en säker adressposition"
        elif returned_house and house and canonical(re.sub(r"[a-zåäö]+$", "", house)) == returned_house:
            status, precision, geometry = "review", "building", "base_house_number_point"
            reason = "Husets basnummer matchar, men adressens bokstav saknas; entré behöver verifieras"
        else:
            continue
        item = {"coordinate":coordinate,"status":status,"precision":precision,"reason":reason,
                "geometry":geometry,"source":f"OpenStreetMap Nominatim {result.get('osm_type','')}/{result.get('osm_id','')}",
                "source_url":f"https://www.openstreetmap.org/{result.get('osm_type','')}/{result.get('osm_id','')}",
                "display_name":result.get("display_name"),"postcode":returned_postcode,
                "osm_type":result.get("osm_type"),"osm_id":result.get("osm_id")}
        (precise if exact else approximate).append(item)
    candidates = precise or approximate
    if not candidates:
        return None
    if precise and any(distance_km(precise[0]["coordinate"],c["coordinate"]) > .1 for c in precise):
        return {"coordinate":None,"status":"ambiguous","precision":"unmapped","reason":"Flera geografiskt åtskilda adresskandidater", "source":"OpenStreetMap Nominatim"}
    candidates.sort(key=lambda c:(c["precision"]=="street",c["status"]=="review",c["postcode"]!=postcode))
    return candidates[0]


def save_matches(matches):
    MATCH_CACHE.write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding="utf-8")


def expanded_queries(address):
    descriptor,_,locality=address_parts(address)
    parts=[p.strip() for p in descriptor.split(',')]
    cleaned=re.sub(r'\([^)]*\)','',parts[0]).strip()
    cleaned=re.sub(r'\b'+re.escape(locality)+r'\b','',cleaned,flags=re.I).strip()
    cleaned=re.sub(r'vårdcentralen','vårdcentral',cleaned,flags=re.I)
    cleaned=re.sub(r'^P-plats\s+','parkering ',cleaned,flags=re.I)
    queries=[f'{part}, {locality}, Sverige' for part in [parts[-1],cleaned] if part]
    if re.search(r'sjukhusområdet|lasarettsområdet',descriptor,re.I):
        queries.append(f'{locality} sjukhus, Sverige')
    if 'återvinningscentral' in descriptor.casefold():
        queries.append(f'återvinningscentral, {locality}, Sverige')
    if re.search(r'vårdcentral',descriptor,re.I):
        queries.append(f'health centre, {locality}, Sverige')
    # Streets with a missing house number can still provide a street anchor.
    street,_=street_number(parts[-1])
    without_number=re.sub(r'\s+\d+\s*[A-Za-zÅÄÖåäö]?$','',parts[-1]).strip()
    if without_number and without_number!=parts[-1]:
        queries.append(f'{without_number}, {locality}, Sverige')
    return list(dict.fromkeys(queries))


def select_place_result(address,results,anchor):
    descriptor,postcode,locality=address_parts(address)
    target=descriptor.split(',')[0]
    target=re.sub(r'\([^)]*\)','',target)
    target=re.sub(r'\b'+re.escape(locality)+r'\b','',target,flags=re.I).strip()
    tokens={canonical(t) for t in re.findall(r'[\w]+',target) if len(t)>=3 and not t.isdigit()}
    tokens={t.replace('vårdcentralen','vårdcentral') for t in tokens}
    medical=bool(re.search(r'vårdcentral|sjukhusområdet|lasarettsområdet',descriptor,re.I))
    candidates=[]
    for result in results:
        detail=result.get('address',{})
        if detail.get('country_code')!='se' or not anchor:continue
        coordinate=[float(result['lon']),float(result['lat'])]
        radius=distance_km(anchor,coordinate)
        if radius>8:continue
        name=result.get('name') or result.get('display_name','').split(',')[0]
        normalized=canonical(name).replace('vårdcentralen','vårdcentral')
        named=bool(tokens and all(t in normalized for t in tokens))
        type_=result.get('type','')
        category=result.get('category',result.get('class',''))
        healthcare=medical and type_ in ['hospital','clinic','doctors','health_centre'] and (
            canonical(detail.get('postcode',''))==postcode or radius<2)
        if not (named or healthcare) or category=='highway':continue
        # A nearby named POI locates a site, not an unverified house/entrance.
        candidates.append({'coordinate':coordinate,'status':'review','precision':'poi',
                           'reason':f'Plats-/verksamhetsträff: {name}. Ursprunglig adress och entré behöver verifieras',
                           'geometry':'named_place_point','place_name':name,
                           'source':f"OpenStreetMap Nominatim {result.get('osm_type','')}/{result.get('osm_id','')}",
                           'source_url':f"https://www.openstreetmap.org/{result.get('osm_type','')}/{result.get('osm_id','')}",
                           'display_name':result.get('display_name'),'osm_type':result.get('osm_type'),'osm_id':result.get('osm_id'),
                           '_distance':radius,'_medical':healthcare})
    if not candidates:return None
    candidates.sort(key=lambda c:(not c['_medical'],c['_distance']))
    if len(candidates)>1 and candidates[0]['_medical']==candidates[1]['_medical'] and distance_km(candidates[0]['coordinate'],candidates[1]['coordinate'])>.5:
        return None
    chosen=candidates[0];chosen.pop('_distance');chosen.pop('_medical')
    return chosen


def run(limit=None, expand_places=False):
    data=json.loads((APP/"data"/"review-data.json").read_text(encoding="utf-8"))
    matches=json.loads(MATCH_CACHE.read_text(encoding="utf-8"))
    cache=json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"provider":"OpenStreetMap Nominatim","endpoint":ENDPOINT,"license":"ODbL 1.0","queries":{}}
    counts=Counter(a for t in data["trips"] for a in (t["origin"],t["destination"]))
    pending=[a for a,m in matches["addresses"].items() if not m.get("coordinate") or m.get('precision')=='locality']
    pending.sort(key=lambda a:('Fredriksberg' not in a,-counts[a],a))
    if limit:
        pending=pending[:limit]
    last_request=0.0
    for index,address in enumerate(pending,1):
        street,_,locality=address_parts(address)
        queries=[address,f"{street}, {locality}, Sverige"]
        if expand_places:queries+=expanded_queries(address)
        queries=list(dict.fromkeys(queries))
        anchor=data["addresses"][address].get("locality_coordinate") or data["addresses"][address].get("coordinate")
        accepted=None
        for query in queries:
            if query not in cache["queries"]:
                time.sleep(max(0,1.2-(time.monotonic()-last_request)))
                parameters={"q":query,"countrycodes":"se","format":"jsonv2","addressdetails":1,"limit":5}
                url=ENDPOINT+"?"+urlencode(parameters)
                last_request=time.monotonic()
                try:
                    with urlopen(Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json"}),timeout=25) as response:
                        results=json.load(response)
                except HTTPError as error:
                    # Stop on throttling/denial; do not bypass the provider.
                    print(json.dumps({"http_error":error.code,"processed":index-1}),flush=True)
                    save_matches(matches)
                    raise
                except (URLError,TimeoutError) as error:
                    print(json.dumps({"network_error":str(error),"processed":index-1}),flush=True)
                    save_matches(matches)
                    raise
                cache["queries"][query]={"url":url,"retrieved_at_utc":datetime.now(timezone.utc).isoformat(),"results":results}
                CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding="utf-8")
            results=cache["queries"][query]["results"]
            result=select_result(address,results,anchor)
            # For text with an appended street, try the actual last street part.
            if not result and ',' in street:
                result=select_result(f'{street.split(",")[-1].strip()}, {address_parts(address)[1]} {locality}',results,anchor)
            if not result and expand_places:result=select_place_result(address,results,anchor)
            if result and (not accepted or result.get("precision")=="address"):
                accepted=result
                accepted["query"]=query
                accepted["retrieved_at_utc"]=cache["queries"][query]["retrieved_at_utc"]
            if accepted and accepted.get("precision")=="address":
                break
            if accepted and expand_places:break
        if accepted:
            matches["addresses"][address]=accepted
        else:
            matches["addresses"][address]["reason"]="Ingen säker adress- eller gatuträff efter Nominatim-uppslag"
        matches["metadata"]["additional_geocoder"]={"provider":"OpenStreetMap Nominatim","cache":"source/nominatim_queries.json","policy":"https://operations.osmfoundation.org/policies/nominatim/","queries":len(cache["queries"])}
        save_matches(matches)
        if index==1 or index%10==0 or index==len(pending):
            print(json.dumps({"processed":index,"total":len(pending),"statuses":dict(Counter(m["status"] for m in matches["addresses"].values())),"precision":dict(Counter(m.get("precision") for m in matches["addresses"].values()))}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized-lookups",action="store_true",required=True,help="Explicit permission to send only remaining address strings to Nominatim")
    parser.add_argument("--limit",type=int)
    parser.add_argument('--expand-places',action='store_true',help='Try cleaned street names and named local facilities before locality fallback')
    args=parser.parse_args()
    run(args.limit,args.expand_places)
