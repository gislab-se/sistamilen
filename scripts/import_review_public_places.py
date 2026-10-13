"""Extract the named Sunnansjö clinic's public 1177 coordinate and provenance."""
from datetime import datetime, timezone
from html import unescape
import hashlib
import json
import re
from urllib.request import Request, urlopen

from scripts.build_fredriksberg_review import APP

URL='https://www.1177.se/hitta-vard/kontaktkort/Vardcentral-Sunnansjo/'


def import_sunnansjo():
    with urlopen(Request(URL,headers={'User-Agent':'SistaMilen-local-review/1.0'}),timeout=25) as response:
        raw=response.read()
    html=raw.decode('utf-8')
    def meta(name):
        match=re.search(r'<meta\s+property="'+re.escape(name)+r'"\s+content="([^"]+)"',html)
        if not match:raise ValueError('Missing official coordinate metadata: '+name)
        return unescape(match[1])
    lat,lon=float(meta('hsa.latitude')),float(meta('hsa.longitude'))
    address=meta('hsa.visitingaddress')
    if 'Sjukstugevägen 3' not in address or 'Sunnansjö' not in address or not(14<lon<16 and 60<lat<61):
        raise ValueError('Contact card address or coordinate changed; review required')
    record={'coordinate':[lon,lat],'status':'matched','precision':'poi','geometry':'official_facility_point',
            'place_name':'Vårdcentral Sunnansjö','reason':'Verksamhet och besöksadress Sjukstugevägen 3, Sunnansjö verifierade mot 1177:s kontaktkort',
            'source':'1177, Vårdcentral Sunnansjö, offentlig HSA-kartkoordinat','source_url':URL}
    result={'metadata':{'source_url':URL,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                        'source_sha256':hashlib.sha256(raw).hexdigest(),'visiting_address':address},
            'addresses':{'Vårdcentralen Sunnansjö, 770 12 Sunnansjö':record,
                         'Sjukstugevägen 3, 770 12 Sunnansjö':{**record,'precision':'address'}}}
    (APP/'source'/'public_place_coordinates.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source':URL,'coordinate':[lon,lat],'matched_aliases':len(result['addresses'])}))


if __name__=='__main__':import_sunnansjo()
