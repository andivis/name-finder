import sys
import logging

from ..library import helpers

from ..library.helpers import get
from ..library.database import Database
from ..library.api import Api
from ..library.sites.google_maps import GoogleMaps

class NameFinder:
    def findName(self, domain):
        self.domain = domain

        self.log.info(f'Finding {self.domain}')

        googleMapSearchItem = {
            'keyword': 'Heaven Scent Incense'
        }

        googleMapResults = self.googleMaps.search(googleMapSearchItem)

        print(googleMapResults)
    
    def __init__(self, options, database):
        self.options = options
        self.log = logging.getLogger(get(self.options, 'loggerName'))
        self.database = database

        self.credentials = {
            'google maps': {}
        }

        url =  helpers.getFile('program/resources/resource2')
        externalApi = Api()
        self.credentials['google maps']['apiKey'] = externalApi.get(url, None, False)

        self.googleMaps = GoogleMaps(self.options, self.credentials, self.database)
