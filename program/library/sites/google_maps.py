import sys
import logging
import time
import datetime

from .. import helpers

from ..helpers import get
from ..api import Api
from ..other import ContactHelpers
from ..other import LocationHelper
from .site import SiteHelpers

class GoogleMaps:
    def search(self, searchItem):
        results = []

        keyword = searchItem.get('keyword', '')
        keyword += ' ' + self.locationHelper.getLocationString(searchItem)
        keyword = keyword.strip()

        places = self.getPages(searchItem, f'/maps/api/place/textsearch/json?query={keyword}&key={self.apiKey}')

        names = []

        for item in places:
            if SiteHelpers.inDatabase(searchItem, item.get('place_id', ''), self.database):
                continue

            details = self.getPlaceDetails(item)
            
            phone = details.get('international_phone_number', '')

            name = item.get('name', '')

            # to avoid duplicates
            if name in names:
                continue
            
            names.append(name)                

            if not phone:
                continue

            result = {
                'id': item.get('place_id', ''),
                'site': helpers.getDomainName(self.url),
                'name': name,
                'email': '',
                'phone': phone,
                'website': details.get('website', ''),
                'location': get(item, 'formatted_address'),
                'address_components': get(details, 'address_components'),
                'country': helpers.getLastAfterSplit(get(item, 'formatted_address'), ', '),
                'industry': '; '.join(item.get('types', [])),
                'google maps url': 'https://www.google.com/maps/place/?q=place_id:' + item.get('place_id', ''),
                'gmDate': str(datetime.datetime.utcnow())
            }

            results.append(result)

            if self.shouldOutputResults:
                self.log.info(f'New result: {name}, {phone}')

                self.contactHelpers.toDatabase(searchItem, result, self.database)

                if get(self.options, 'contactUploader'):
                    self.options['contactUploader'].upload(searchItem, [result])
                
                maximum = searchItem.get('maximumNewResults', self.options['maximumNewResults'])
                maximum = int(maximum)

                if len(results) >= maximum:
                    self.log.debug(f'Reached the maximum of {len(results)} new results.')
                    break

                if self.contactHelpers.enoughForOneDay(self.options, searchItem, self.database, self.options['defaultTimezone']):
                    break

        return results

    def getPlaceDetails(self, place):
        placeId = place.get('place_id', '')

        j = self.api.get(f'/maps/api/place/details/json?place_id={placeId}&fields=name,international_phone_number,website,address_component&key={self.apiKey}')

        self.handleError(j)

        return j.get('result', {})

    def getPages(self, searchItem, url):
        results = []
        
        nextPageToken = ''
        
        for i in range(0, 1000):
            self.log.info(f'Getting page {i + 1} of Google Maps search results')

            nextPageTokenPart = ''
    
            if i > 0:
                nextPageTokenPart = f'&pagetoken={nextPageToken}'

            for attempt in range(0, 10):
                j = self.api.get(f'{url}{nextPageTokenPart}')

                # might need to wait for next page to be ready
                if j.get('status', '') == 'INVALID_REQUEST':
                    time.sleep(5)
                    continue
                
                break

            self.handleError(j)
    
            nextPageToken = j.get('next_page_token', '')

            results += j.get('results', [])

            self.log.info(f'Found {len(results)} search results so far')

            maximum = searchItem.get('maximumSearchResults', self.options['maximumSearchResults'])
            maximum = int(maximum)

            if len(results) >= maximum:
                self.log.info(f'Reached search result limit: {maximum}')
                break

            if not nextPageToken:
                # no more results
                break

            # give time for next page to get ready
            time.sleep(1)

        return results
    
    def handleError(self, j):
        if j.get('status', '') != 'OK' and j.get('status', '') != 'ZERO_RESULTS':
            error = j.get('error_message', '')
            self.log.error(f'Google Maps: {error}')

    def __init__(self, options, credentials, database):
        self.options = options
        self.database = database
        self.log = logging.getLogger(get(self.options, 'loggerName'))

        self.shouldOutputResults = False
        self.apiKey = helpers.getNested(credentials, ['google maps', 'apiKey'])

        if not self.apiKey:
            self.log.error('You must put your Google Maps API key into credentials.ini')
            input("Press enter to exit...")
            exit()
        
        self.url = 'https://maps.google.com'
        self.api = Api('https://maps.googleapis.com')
        self.api.headers = {}

        self.contactHelpers = ContactHelpers(self.options)
        self.locationHelper = LocationHelper(self.options)
