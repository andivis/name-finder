import logging
import json

from .. import helpers

from ..helpers import get
from ..api import Api
from ..database import Database
from ..other import Internet
from ..other import ContactHelpers
from ..google import Google

class Site:
    def search(self, inputRow, profiles):
        domain = get(inputRow, 'site')
        keyword = get(inputRow, 'keyword')

        self.log.info(f'Searching {domain} for {keyword}')

        profileUrls = self.google.search(f'site:{domain} {keyword}', self.getMaximumSearchResults(inputRow))

        baseXpaths = {
            # bio section
            'instagram.com': '(//header/section/div)[3]'
        }

        moreXpaths = {
            'instagram.com': ["//a[contains(@href, '//l.instagram.com/?u=')]", 'href', 'website', ]
        }

        for profileUrl in profileUrls:
            try:
                if helpers.getDomainName(profileUrl) != domain:
                    self.log.debug(f'Skipping {profileUrl}')
                    continue
                
                if self.enough(inputRow, profiles):
                    break

                profile = {}

                self.log.info(f'Checking {profileUrl}')
        
                if domain == 'instagram.com':                
                    profile = self.getProfile(inputRow, profileUrl)
                else:
                    contactInformation = self.contactHelpers.getContactInformation(profile, profileUrl, get(baseXpaths, domain), moreXpaths)
                    profile = helpers.mergeDictionaries(profile, contactInformation)

                if not profile:
                    continue
                
                # so don't parse same profiles over and over
                self.contactHelpers.toDatabase(inputRow, profile, self.database)

                if not self.contactHelpers.hasContactInformation(profile):
                    continue

                profiles.append(profile)

                self.log.info(f'New result: {get(profile, "id")}, {get(profile, "email")}, {get(profile, "phone")}, {get(profile, "website")}')

                self.options['contactUploader'].upload(inputRow, [profile])
            except Exception as e:
                helpers.handleException(e, f'Something went wrong while getting {profileUrl}')

        return profiles

    def getProfile(self, inputRow, profileUrl):
        return {}
        
    def shouldGetProfile(self, inputRow, id, url):
        if not id:
            id = SiteHelpers.getUserName(self.domain, url)

        if SiteHelpers.inDatabase(inputRow, id, self.database):
            return False

        self.api.proxies = self.internet.getRandomProxy()

        return True

    def enough(self, inputRow, newItems):
        result = False
        
        if self.contactHelpers.enoughResults(self.options, inputRow, newItems, 'maximumNewResults'):
            result = True
        elif self.contactHelpers.enoughForOneDay(self.options, inputRow, self.database, self.options['defaultTimezone']):
            result = True

        return result

    def addContactInformationFromWebsites(self, url, result, text):
        fieldsToGet = ['email', 'phone', 'website']

        if self.allHaveAValue(result, fieldsToGet):
            return result
        
        urls = []

        if get(result, 'website'):
            urls.append(get(result, 'website'))

        urls += self.contactHelpers.getUrlsInText(url, text)

        # check websites they mention in their profile
        for i, urlInText in enumerate(urls):
            if not '://' in urlInText:
                urlInText = 'http://' + urlInText

            # to avoid bit.ly and similar
            urlInText = self.api.getFinalUrl(urlInText)

            if not urlInText:
                continue

            domain = helpers.getDomainName(urlInText)

            # try main page first
            self.contactHelpers.getContactInformation(result, urlInText)

            # done?
            if self.allHaveAValue(result, fieldsToGet):
                break

            # search for the contact page on that domain and then get it
            self.google.api.proxies = self.internet.getRandomProxy()    
            result = self.contactHelpers.addContactInformationFromDomain(result, domain, self.google)
            
            # done?
            if self.allHaveAValue(result, fieldsToGet):
                break

            # don't go on too long
            if i > 5:
                break

        return result

    def getMaximumNewResults(self, inputRow):
        maximum = inputRow.get('maximumNewResults', self.options['maximumNewResults'])

        return int(maximum)
        
    def getMaximumSearchResults(self, inputRow):
        maximum = inputRow.get('maximumSearchResults', self.options['maximumSearchResults'])

        return int(maximum)

    def toDatabase(self, inputRow, newItem):
        # so don't parse same profiles over and over
        self.contactHelpers.toDatabase(inputRow, newItem, self.database)

    def allHaveAValue(self, object, fields):
        for field in fields:
            if get(object, field):
                return False

        return True
    
    def decodeLink(self, url, value):
        between = {
            'instagram.com': ['//l.instagram.com/?u=', '&']
        }

        domain = helpers.getDomainName(url)
        
        strings = get(between, domain)

        if not strings:
            return value

        link = helpers.findBetween(value, strings[0], strings[1])
        
        import urllib.parse
        link = urllib.parse.unquote(link)

        return link

    def displayResult(self, newResult):
        self.log.info(f'New result: {self.contactHelpers.getName(newResult)}, {get(newResult, "email")}, {get(newResult, "phone")}')

    def __init__(self, options, database):
        self.options = options
        self.internet = Internet(self.options)
        self.database = database
        self.api = Api('', self.options)
        self.google = Google(self.options)
        self.domain = ''
        self.log = logging.getLogger(get(self.options, 'loggerName'))
        self.contactHelpers = ContactHelpers(self.options)

class SiteHelpers:
    @staticmethod
    def inDatabase(inputRow, id, database):
        result = False
        
        row = database.getFirst('result', 'id', f"site = '{get(inputRow, 'site')}' and id = '{id}' and mode = '{get(inputRow, 'mode')}'")

        if row:
            logging.debug(f'Skipping. Already have {id} in the database.')
            result = True

        return result

    @staticmethod
    def getUserName(domain, url):
        level = 3

        # because can have /user/xyz or /channel/xyz
        if 'youtube' in domain:
            level = 4

        fields = url.split('/')

        if level >= len(fields):
            return ''

        return fields[level]

    @staticmethod
    def getProfileUrl(domain, url):
        level = 1                       

        # because can have /user/xyz or /channel/xyz
        if 'youtube' in domain:
            level = 2
        
        return SiteHelpers.trimUrlToSubdirectory(url, level)

    @staticmethod
    def trimUrlToSubdirectory(url, levels):
        url = helpers.findBetween(url, '', '/?')
        url = helpers.findBetween(url, '', '?')

        # remove subdirectories after the first one
        index = helpers.findOccurence(url, '/', 2 + levels)

        if index >= 0:
            url = url[0:index + 1]
        
        return url