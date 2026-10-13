import unittest

from scripts.geocode_review_addresses import canonical, match_address, public_index, street_number
from scripts.geocode_review_nominatim import select_result,expanded_queries,select_place_result


class AddressMatchingTests(unittest.TestCase):
    def candidate(self, number='36', postcode='770 10', lon=14.37, lat=60.14):
        return {'type':'node','id':1,'lon':lon,'lat':lat,'tags':{
            'addr:street':'Filipstadsvägen','addr:housenumber':number,'addr:postcode':postcode}}

    def test_house_number_and_postcode_match(self):
        result=match_address('Filipstadsvägen 36, 770 10 Fredriksberg',public_index([self.candidate()]),[14.37,60.14])
        self.assertEqual(result['status'],'matched')
        self.assertEqual(result['coordinate'],[14.37,60.14])

    def test_wrong_house_number_is_not_a_location_for_the_address(self):
        result=match_address('Filipstadsvägen 36, 770 10 Fredriksberg',public_index([self.candidate(number='34')]),[14.37,60.14])
        self.assertIsNone(result['coordinate'])
        self.assertEqual(result['status'],'unmatched')

    def test_house_letter_and_distant_same_named_street_are_rejected(self):
        address='Filipstadsvägen 36B, 770 10 Fredriksberg'
        result=match_address(address,public_index([self.candidate()]),[14.37,60.14])
        self.assertIsNone(result['coordinate'])
        result=match_address('Filipstadsvägen 36, 770 10 Fredriksberg',public_index([self.candidate(lon=18)]),[14.37,60.14])
        self.assertIsNone(result['coordinate'])

    def test_conflicting_postcode_needs_review(self):
        result=match_address('Filipstadsvägen 36, 770 10 Fredriksberg',public_index([self.candidate(postcode='770 12')]),[14.37,60.14])
        self.assertEqual(result['status'],'review')

    def test_separate_candidates_are_not_silently_selected(self):
        result=match_address('Filipstadsvägen 36, 770 10 Fredriksberg',public_index([self.candidate(),self.candidate(lon=14.38)]),[14.37,60.14])
        self.assertEqual(result['status'],'ambiguous')
        self.assertIsNone(result['coordinate'])

    def test_building_center_is_preserved_as_such(self):
        element=self.candidate();element['type']='way';element['center']={'lon':14.37,'lat':60.14}
        result=match_address('Filipstadsvägen 36, 770 10 Fredriksberg',public_index([element]),[14.37,60.14])
        self.assertEqual(result['geometry'],'bounding_box_center')


class NominatimResultTests(unittest.TestCase):
    def candidate(self,house='36',road='Filipstadsvägen',category='building',lon=14.37):
        result={'lat':'60.14','lon':str(lon),'category':category,'osm_type':'node','osm_id':1,
                'address':{'country_code':'se','postcode':'77010','road':road},
                'boundingbox':['60.139','60.141','14.369','14.371']}
        if house is not None:result['address']['house_number']=house
        return result

    def test_precise_address_is_distinct_from_street_level(self):
        address='Filipstadsvägen 36, 770 10 Fredriksberg'
        exact=select_result(address,[self.candidate()],[14.37,60.14])
        approximate=select_result(address,[self.candidate(house=None,category='highway')],[14.37,60.14])
        self.assertEqual(exact['precision'],'address')
        self.assertEqual(exact['status'],'matched')
        self.assertEqual(approximate['precision'],'street')
        self.assertEqual(approximate['status'],'review')

    def test_wrong_road_house_number_and_faraway_candidate_rejected(self):
        address='Filipstadsvägen 36, 770 10 Fredriksberg'
        for candidate in [self.candidate(house='34'),self.candidate(road='Annan gata'),self.candidate(lon=18)]:
            self.assertIsNone(select_result(address,[candidate],[14.37,60.14]))

    def test_missing_house_letter_is_flagged_not_promoted_to_address(self):
        result=select_result('Filipstadsvägen 36B, 770 10 Fredriksberg',[self.candidate()],[14.37,60.14])
        self.assertEqual(result['precision'],'building')
        self.assertEqual(result['status'],'review')

    def test_widely_separated_exact_candidates_are_ambiguous(self):
        result=select_result('Filipstadsvägen 36, 770 10 Fredriksberg',[self.candidate(),self.candidate(lon=14.38)],[14.37,60.14])
        self.assertEqual(result['status'],'ambiguous')
        self.assertIsNone(result['coordinate'])

    def test_named_place_is_not_mistaken_for_a_house_number_match(self):
        candidate=self.candidate(house=None,category='amenity')
        candidate.update(name='Vårdcentral Sunnansjö',type='clinic',lat='60.216',lon='14.956')
        candidate['address']['postcode']='77012'
        result=select_place_result('Vårdcentralen Sunnansjö, 770 12 Sunnansjö',[candidate],[14.95,60.21])
        self.assertEqual(result['precision'],'poi')
        self.assertEqual(result['status'],'review')
        candidate['name']='En annan mottagning';candidate['type']='school'
        self.assertIsNone(select_place_result('Vårdcentralen Sunnansjö, 770 12 Sunnansjö',[candidate],[14.95,60.21]))

    def test_cleaned_queries_retain_locality(self):
        queries=expanded_queries('Vårdcentralen Sunnansjö, 770 12 Sunnansjö')
        self.assertIn('vårdcentral, Sunnansjö, Sverige',queries)
        self.assertIn('Skyfallsvägen, Falun, Sverige',expanded_queries('Kundtjänst och återvinningscentral, Skyfallsvägen 20, 791 77 Falun'))


if __name__=='__main__':
    unittest.main()
