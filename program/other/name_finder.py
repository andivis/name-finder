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

        self.domain = domain
        self.domainStatus = 'unknown'
        self.compare.reset()
        self.compare.domain = domain

        companiesHouseInformation = self.lookOnCompaniesHouse(domain)

        if self.google.captcha:
            return

        if not companiesHouseInformation:
            self.outputUnknown(newItem, companiesHouseInformation)
            return

        # does "a b c" match "abc.com"?
        similarity = self.compare.companyNameMatchesDomain(domain, get(companiesHouseInformation, 'companyName'), 'by words')
        self.compare.increaseConfidence(similarity * 400, 400, f'The domain name matches the words in companies house name.', f'domain name matches words in companies house name')

        noSpacesSimilarity = self.compare.companyNameMatchesDomain(domain, get(companiesHouseInformation, 'companyName'), 'by no spaces')
        self.compare.increaseConfidence(noSpacesSimilarity * 400, 400, f'The domain name matches the name in companies house.', f'domain name matches companies house')

        # can stop early to speed things up
        if self.outputIfDone(newItem, companiesHouseInformation):
            return

        # does website title match the name in companies house?
        websiteInformation = self.lookOnWebsite(domain)

        if self.google.captcha:
            self.captcha = True
            return

        if self.domainStatus != 'active':
            self.outputUnknown(newItem, companiesHouseInformation)
            return

        modes = [
            'by words',
            'by no spaces'
        ]

        for mode in modes:
            maximumSimilarity = -1

            for name in get(websiteInformation, 'possibleNames'):
                similarity = self.compare.companyNamesMatch(get(companiesHouseInformation, 'companyName'), name, mode)

                if similarity > maximumSimilarity:
                    maximumSimilarity = similarity
                    websiteInformation['companyName'] = name

            self.compare.increaseConfidence(maximumSimilarity * 400, 400, f'The website title matches the name in companies house.', f'website title matches companies house')

        if self.outputIfDone(newItem, companiesHouseInformation):
            return

        self.outputUnknown(newItem, companiesHouseInformation)

    def outputUnknown(self, newItem, companiesHouseInformation):
        toOutput = helpers.mergeDictionaries(companiesHouseInformation, newItem)
        
        toOutput['domainStatus'] = self.domainStatus
        
        toOutput['confidence'] = self.compare.confidence / self.compare.maximumPossibleConfidence
        toOutput['confidence'] = int(round(toOutput['confidence'] * 100))
        
        self.outputResult(toOutput)

    def outputIfDone(self, newItem, companiesHouseInformation):
        result = False
        
        if self.compare.confidence < self.options['minimumConfidence']:
            return result

        self.log.info(f'Done {self.domain}. Reached confidence of {self.options["minimumConfidence"]}.')

        toOutput = helpers.mergeDictionaries(companiesHouseInformation, newItem)

        toOutput['domainStatus'] = self.domainStatus
        
        toOutput['confidence'] = self.compare.confidence / self.compare.maximumPossibleConfidence
        toOutput['confidence'] = int(round(toOutput['confidence'] * 100))        
        
        self.outputResult(toOutput)
        
        return True

    def lookOnWebsite(self, domain):
        result = {}

        url = domain

        if not domain.startswith('https://') and not domain.startswith('http://'):
            url = 'http://' + url
        
        response = self.api.get(url, None, False, True)
        
        toAvoid = [
            'page not found',
            'cannot be found',
            'can\'t be found',
            'does not exist',
            'not found'
        ]

        if not response or not response.text:
            self.domainStatus = 'offline'
        elif response.status_code == 404:
            self.domainStatus = '404 error'
        elif helpers.substringIsInList(toAvoid, response.text):
            self.log.debug(f'{domain} contains string to avoid')
            self.domainStatus = 'parked'
        elif not self.hasResultsOnGoogle(domain):
            self.log.debug(f'{domain} only has 1 or 0 results on Google')
            self.domainStatus = 'parked'            
        else:
            self.domainStatus = 'active'

            document = lh.fromstring(response.text)
            title = self.website.getXpath('', "//title", True, None, document)

            # name can be before or after splitter
            # before splitter
            name1 = helpers.findBetween(title, '', ' - ')
            name1 = helpers.findBetween(name1, '', '|')
            name1 = name1.strip()

            if not get(result, 'possibleNames'):
                result['possibleNames'] = []

            result['possibleNames'].append(name1)

            # after splitter
            name2 = helpers.findBetween(title, ' - ', '')
            name2 = helpers.findBetween(name2, '|', '')
            name2 = name2.strip()

            result['possibleNames'].append(name2)

            self.log.info(f'Website title: {title}')

        self.log.info(f'{domain} status: {self.domainStatus}')

        return result

    def lookOnCompaniesHouse(self, domain):
        result = {}

        googleResults = self.google.search(f'site:beta.companieshouse.gov.uk {domain}', 5, False)

        for googleResult in googleResults:
            if googleResult == 'no results':
                break

            # look for main company page only
            companyId = helpers.findBetween(googleResult, 'beta.companieshouse.gov.uk/company/', '/', True)

            if not companyId:
                companyId = helpers.findBetween(googleResult, 'beta.companieshouse.gov.uk/company/', '', True)

            if not companyId:
                continue

            url = 'https://beta.companieshouse.gov.uk/company/' + companyId

            result = self.getCompaniesHouseInformation(url)

            break

        self.log.info(f'Name from Companies House: {get(result, "companyName")}')
        
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
        html = api.get('https://beta.companieshouse.gov.uk/search/companies?q=' + query, None, False)

        if not html:
            return results

        website = Website(self.options)

        searchResults = website.getXpath(html, "//li[@class = 'type-company']")

        for searchResult in searchResults:
            url = website.getXpathInElement(searchResult, ".//a[contains(@href, '/company/')]", True, 'href')

            results.append(url)

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

        fields = ['domain', 'companyName', 'confidence', 'companyNumber', 'registered office address', 'company status', 'domainStatus']

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

    def hasResultsOnGoogle(self, domain):
        results = self.google.search(f'site:{domain}')

        return len(results) > 1
    
    def isDone(self, domain):
        if self.database.getFirst('result', 'domain', f"domain = '{domain}'"):
            self.log.info(f'Skipping. Already done {domain}.')
            return True

        return False

    def __init__(self, options, database):
        self.options = options
        self.log = logging.getLogger(get(self.options, 'loggerName'))
        self.database = database
        self.captcha = False
        
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
        self.api = Api('', self.options)
        self.api.timeout = 5
        self.website = Website(self.options)
        self.google = Google(self.options)
        self.google.internet = self.internet
        self.googleMaps = GoogleMaps(self.options, self.credentials, self.database)

class Compare:
    def companyNameMatchesDomain(self, domain, name, mode):
        name = self.getBasicCompanyName(name)

        basicDomain = helpers.getBasicDomainName(domain)

        # does "a b c" match "abc.com"?
        if helpers.lettersAndNumbersOnly(basicDomain) == helpers.lettersAndNumbersOnly(name):
            return 1
        elif mode == 'by words':
            # does "a b c" match "ab.com"
            return self.percentageOfMaximumRun(name, basicDomain)
        elif mode == 'by no spaces':
            # does "b c d" match "abc.com"
            return self.percentageSameWithoutSpaces(name, basicDomain)

        return 0
    
    def companyNamesMatch(self, name1, name2):
        name1 = self.getBasicCompanyName(name1)
        name2 = self.getBasicCompanyName(name2)

        if not name1 or not name2:
            return 0

        if name1 == name2:
            return 1
        else:
            return self.percentageOfMaximumRun(name1, name2)

        return 0

    def percentageOfMaximumRun(self, name1, name2):
        words = self.getWordsInName(name1)
        maximumRun = self.wordsInARowTheSame(words, name2, ' ', False)
        
        if len(words):
            result = maximumRun / len(words)
        else:
            result = 0
            
        return result

    def percentageSameWithoutSpaces(self, name1, name2):
        name1 = helpers.lettersAndNumbersOnly(name1)
        name2 = helpers.lettersAndNumbersOnly(name2)
        
        maximumRun = self.charactersInARowTheSame(name1, name2)
        
        if len(name2):
            result = maximumRun / len(name2)
        else:
            result = 0
            
        return result

    def increaseConfidence(self, number, maximumPossible, message, shortMessage):
        number = int(number)

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

        self.log.debug(f'Adding {number} out of {maximumPossible}')
        
        self.log.info(f'Domain: {self.domain}. Adding: {number} of {maximumPossible}. Tests passed: {self.testsPassed} of {self.totalTests}. Test {word}: {shortMessage}.')

    def getFuzzyVersion(self, s):
        result = s.lower()
        result = result.strip()
        return helpers.squeezeWhitespace(result)

    def getBasicCompanyName(self, s):
        # description or extraneous information usually comes after
        s = helpers.findBetween(s, '', '|')
        s = helpers.findBetween(s, '', ' - ')
        s = helpers.findBetween(s, '', ',')
        s = helpers.findBetween(s, '', '(')

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

    def wordsInARowTheSame(self, words, toCompare, joinString, mustStartWith):
        result = 0

        toCompare = toCompare.lower()

        # go from left to right
        # try longest run first, then try smaller ones
        for i in range(len(words), -1, -1):
            line = joinString.join(words[0:i])

            if mustStartWith:
                if toCompare.startswith(line) and i > result:
                    result = i
                    break            
            else:
                if line in toCompare and i > result:
                    result = i
                    break

        if not result:
            # go from right to left
            for i in range(len(words), -1, -1):
                line = joinString.join(words[-i:len(words)])

                if mustStartWith:
                    if toCompare.startswith(line) and i > result:
                        result = i
                        break            
                else:
                    if line in toCompare and i > result:
                        result = i
                        break

        return result

    def charactersInARowTheSame(self, string1, string2):
        result = 0

        string1 = string1.lower()
        string2 = string2.lower()

        # try longest run first, then try smaller ones
        for i in range(len(string2), -1, -1):
            run = ''.join(string1[0:i])

            if run in string2:
                result = i
                break

        return result

    def getWordsInName(self, name):
        wordsToIgnore = [
            'limited',
            'ltd',
            'llc',
            'inc',
            'incorporated'
        ]

        words = re.sub(r'[^\w]', ' ',  name).split()

        for word in wordsToIgnore:
            if word in words:
                words.remove(word)

        return words

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
