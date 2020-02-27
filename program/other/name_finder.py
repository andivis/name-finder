import os
import sys
import logging
import json

from datetime import datetime

# pip packages
import lxml.html as lh

from ..library import helpers

from ..library.helpers import get
from ..library.database import Database
from ..library.website import Website
from ..library.api import Api
from ..library.google import Google
from ..library.other import Internet
from ..library.sites.google_maps import GoogleMaps

class NameFinder:
    def findName(self, domain):
        if self.isDone(domain) or not domain:
            return

        self.log.info(f'Finding {domain}')

        self.google.api.proxies = self.internet.getRandomProxy()
        googleResults = self.google.search(f'site:beta.companieshouse.gov.uk {domain}', 5, False)

        companyHouseInformation = {}
        companyHouseUrl = ''

        for googleResult in googleResults:
            # look for main company page only
            afterPrefix = helpers.findBetween(googleResult, 'beta.companieshouse.gov.uk/company/', '')

            if '/' in afterPrefix:
                continue

            companyHouseUrl = googleResult

            companyHouseInformation = self.getCompanyHouseInformation(companyHouseUrl)
            break

        if companyHouseInformation:
            result = companyHouseInformation
            result['domain'] = domain

            self.outputResult(companyHouseInformation)
        
        googleResults = self.google.search(f'site:{domain} contact', 3, False)
        
        companies = self.getCompaniesHouseResults('Heaven Scent Incense')

        googleMapSearchItem = {
            'keyword': '01225 868788',
            'region': 'uk'
        }

        googleMapResults = self.googleMaps.search(googleMapSearchItem)

        print(googleMapResults)

    def getCompanyHouseInformation(self, companyHouseUrl):
        result = {}

        api = Api()
        html = api.getPlain(companyHouseUrl)

        if not html:
            return result

        website = Website(self.options)

        document = lh.fromstring(html)

        name = website.getXpath('', "//div[@class = 'company-header']//p[@class = 'heading-xlarge']", True, None, document)
        companyNumber = website.getXpath('', "//p[@id = 'company-number']/strong", True, None, document)
        
        result = {
            'companyName': name,
            'companyNumber': companyNumber
        }

        pairs = website.getXpath('', "//dl", False, None, document)

        for pair in pairs:
            term = website.getXpathInElement(pair, ".//dt", True)            
            definition = website.getXpathInElement(pair, ".//dd", True)

            if term == 'Registered office address' or term == 'Company status':
                result[term.lower()] = definition

        return result

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

    def outputResult(self, newItem):
        outputFile = self.options['outputFile']

        helpers.makeDirectory(os.path.dirname(outputFile))

        fields = newItem.keys()

        if not os.path.exists(outputFile):
            helpers.toFile(','.join(fields), outputFile)

        helpers.appendCsvFile(newItem, outputFile)

        tables = helpers.getJsonFile(self.tablesFile)

        toStore = {
            'gmDate': str(datetime.utcnow()),
            'json': json.dumps(newItem)
        }

        for column in helpers.getNested(tables, ['result', 'column']):
            toStore[column] = get(newItem, column)

        self.database.insert('result', toStore)

    def isDone(self, domain):
        if self.database.getFirst('result', 'url', f"domain = '{domain}'"):
            self.log.info(f'Skipping. Already done {domain}.')
            return True

        return False

    def __init__(self, options, database):
        self.options = options
        self.log = logging.getLogger(get(self.options, 'loggerName'))
        self.database = database

        self.tablesFile = 'program/resources/tables.json'
        self.database.makeTables(self.tablesFile)

        self.credentials = {
            'google maps': {}
        }

        url =  helpers.getFile('program/resources/resource2')
        externalApi = Api()
        self.credentials['google maps']['apiKey'] = externalApi.get(url, None, False)

        self.internet = Internet(self.options)
        self.google = Google(self.options)
        self.googleMaps = GoogleMaps(self.options, self.credentials, self.database)