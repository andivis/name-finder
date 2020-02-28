import os
import sys
import logging
import json
import re

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

        newItem = {
            'domain': domain,
            'domain status': '',
            'companyName': 'unknown'
        }

        self.log.info(f'Finding {domain}')

        self.domain = domain
        self.compare.reset()
        self.compare.domain = domain

        companiesHouseInformation = self.lookOnCompaniesHouse(domain)

        # does "a b c" match "abc.com"?
        similarity = self.compare.companyNameMatchesDomain(domain, get(companiesHouseInformation, 'companyName'))

        if similarity == 1:
            self.compare.increaseConfidence(400, 400, f'The domain name exactly matches the name in companies house.', f'domain name exactly matches companies house')

        # can stop early to speed things up
        if self.outputIfDone(newItem, companiesHouseInformation):
            return

        # does website title match the name in companies house?
        websiteInformation = self.lookOnWebsite(domain)

        similarity = self.compare.companyNamesMatch(domain, get(companiesHouseInformation, 'companyName'), get(websiteInformation, 'companyName'))

        if similarity == 1:
            self.compare.increaseConfidence(400, 400, f'The website title exactly matches the name in companies house.', f'website name exactly matches companies house')

        if self.outputIfDone(newItem, companiesHouseInformation):
            return

        googleResults = self.google.search(f'site:{domain} contact', 3, False)
        
        companies = self.getCompaniesHouseResults('Heaven Scent Incense')

        googleMapSearchItem = {
            'keyword': '01225 868788',
            'region': 'uk'
        }

        googleMapResults = self.googleMaps.search(googleMapSearchItem)

        print(googleMapResults)

    def outputIfDone(self, newItem, companiesHouseInformation):
        result = False
        
        if self.compare.confidence < self.options['minimumConfidence']:
            return result

        self.log.info(f'Done {self.domain}. Reached confidence of {self.options["minimumConfidence"]}.')

        toOutput = helpers.mergeDictionaries(companiesHouseInformation, newItem)
        
        self.outputResult(toOutput)
        
        return True

    def lookOnWebsite(self, domain):
        result = {}

        return result

    def lookOnCompaniesHouse(self, domain):
        result = {}

        self.google.api.proxies = self.internet.getRandomProxy()
        googleResults = self.google.search(f'site:beta.companieshouse.gov.uk {domain}', 5, False)

        for googleResult in googleResults:
            if googleResult == 'no results':
                break

            # look for main company page only
            afterPrefix = helpers.findBetween(googleResult, 'beta.companieshouse.gov.uk/company/', '')

            if '/' in afterPrefix:
                continue

            result = self.getCompaniesHouseInformation(googleResult)
            break

        return result
    
    def getCompaniesHouseInformation(self, companiesHouseUrl):
        result = {}

        api = Api()
        html = api.getPlain(companiesHouseUrl)

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
        if not get(newItem, 'domain'):
            return

        if get(newItem, 'companyName') != 'unknown':
            self.log.info(f'Result: {get(newItem, "companyName")} {get(newItem, "domain")}')
        else:
            self.log.info(f'No result found for {get(newItem, "domain")}')

        outputFile = self.options['outputFile']

        helpers.makeDirectory(os.path.dirname(outputFile))

        fields = ['domain', 'companyName', 'companyNumber', 'registered office address', 'company status', 'domain status']

        if not os.path.exists(outputFile):
            printableFields = []
            
            for field in fields:
                printableName = helpers.addBeforeCapitalLetters(field).lower()
                
                printableFields.append(printableName)
            
            helpers.toFile(','.join(printableFields), outputFile)

        values = []

        for field in fields:
            values.append(get(newItem, field))

        # this quote fields that contain commas
        helpers.appendCsvFile(values, outputFile)

        self.toDatabase(newItem)

    def toDatabase(self, newItem):
        tables = helpers.getJsonFile(self.tablesFile)

        toStore = {}

        for column in helpers.getNested(tables, ['result', 'columns']):
            toStore[column] = get(newItem, column)

        toStore['gmDate'] = str(datetime.utcnow())
        toStore['json'] = json.dumps(newItem)

        self.database.insert('result', toStore)
    
    def isDone(self, domain):
        if self.database.getFirst('result', 'domain', f"domain = '{domain}'"):
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

        self.compare = Compare(self.options)
        self.internet = Internet(self.options)
        self.google = Google(self.options)
        self.googleMaps = GoogleMaps(self.options, self.credentials, self.database)

class Compare:
    def companyNameMatchesDomain(self, domain, name):
        name = self.getBasicCompanyName(name)

        basicDomain = helpers.getBasicDomainName(domain)

        # does "a b c" match "abc.com"?
        if basicDomain == helpers.lettersAndNumbersOnly(name):
            return 1

        return 0
    
    def companyNamesMatch(self, domain, name1, name2):
        name1 = self.getBasicCompanyName(name1)
        name2 = self.getBasicCompanyName(name2)

        if name1 == name2:
            return 1

        return 0

    def increaseConfidence(self, number, maximumPossible, message, shortMessage):
        self.maximumPossibleConfidence += maximumPossible
        self.totalTests += 1

        word = 'failed'

        if number == 0:
            self.log.debug(f'Confidence: {self.confidence} out of {self.maximumPossibleConfidence}. Failed: {message}')
        else:
            word = 'passed'
            
            self.testsPassed += 1

            self.confidence += number

            self.log.debug(f'Confidence: {self.confidence} out of {self.maximumPossibleConfidence}. Added {number}. Passed: {message}')

        logging.info(f'Domain: {self.domain}. Tests passed: {self.testsPassed} of {self.totalTests}. Test {word}: {shortMessage}.')

    def getFuzzyVersion(self, s):
        result = s.lower()
        result = result.strip()
        return helpers.squeezeWhitespace(result)

    def getBasicCompanyName(self, s):
        # description or extraneous information usually comes after
        s = helpers.findBetween(s, '|', '')
        s = helpers.findBetween(s, ' - ', '')
        s = helpers.findBetween(s, ',', '')
        s = helpers.findBetween(s, '(', '')

        s = s.replace('-', ' ')
        s = s.replace('&', ' ')

        s = helpers.lettersNumbersAndSpacesOnly(s)
        s = self.getFuzzyVersion(s)

        stringsToIgnore = [
            'limited',
            'ltd',
            'llc',
            'inc',
            'pty',
            'pl',
            'co',
            'corp'
            'incorporated'
        ]

        for string in stringsToIgnore:
            # word with space before and after
            s = re.sub(f' {string} ', ' ', s)
            # ends in the string
            s = re.sub(f' {string}$', '', s)

        locationsToRemove = self.options['ignoreInCompanyName'].split(',')

        for string in locationsToRemove:
            # word with space before and after
            s = re.sub(f' {string}.*', '', s)
            # ends in the string
            s = re.sub(f' {string}$', '', s)

        s = self.getFuzzyVersion(s)

        return s

    def reset(self):
        self.testsPassed = 0
        self.totalTests = 0
        self.confidence = 0
        self.maximumPossibleConfidence = 0
        self.domain = ''

    def __init__(self, options):
        self.options = options
        self.testsPassed = 0
        self.totalTests = 0
        self.confidence = 0
        self.maximumPossibleConfidence = 0
        self.domain = ''
        self.log = logging.getLogger(get(self.options, 'loggerName'))
