import sys
import logging

# pip packages
import lxml.html as lh

from ..library import helpers

from ..library.helpers import get
from ..library.database import Database
from ..library.website import Website
from ..library.api import Api
from ..library.sites.google_maps import GoogleMaps

class NameFinder:
    def findName(self, domain):
        self.domain = domain

        self.log.info(f'Finding {self.domain}')

        companies = self.getCompaniesHouseResults('Heaven Scent Incense')

        googleMapSearchItem = {
            'keyword': '01225 868788',
            'region': 'uk'
        }

        googleMapResults = self.googleMaps.search(googleMapSearchItem)

        print(googleMapResults)

    def getCompaniesHouseResults(self, query):
        results = []
        
        api = Api()
        html = api.getPlain('https://beta.companieshouse.gov.uk/search/companies?q=' + query)

        if not html:
            return results

        website = Website(self.options)

        searchResults = website.getXpath(html, "//li[@class = 'type-company']")

        for searchResult in searchResults:
            name = website.getXpathInElement(searchResult, ".//a[contains(@href, '/company/')]", True)
            name = name.strip()
            
            address = website.getXpathInElement(searchResult, ".//p[not(@class)]", True)
            address = address.strip()

            result = {
                'name': name,
                'address': address
            }

            results.append(result)

        return results

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
