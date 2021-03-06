import sys
import os
import logging
import datetime

import program.library.helpers as helpers

from program.library.helpers import get
from program.library.database import Database
from program.other.name_finder import NameFinder

class Main:
    def run(self):
        logging.info('Starting')

        inputRows = helpers.getCsvFile(self.options['inputFile'], True, '\t')

        while True:
            self.nameFinder.captcha = False
            
            for i, inputRow in enumerate(inputRows):
                try:
                    domain = get(inputRow, 'domain')
                    logging.info(f'Line {i + 1} of {len(inputRows)}: {domain}')

                    self.nameFinder.findName(domain)
                except Exception as e:
                    helpers.handleException(e)

            if not self.nameFinder.captcha:
                break
            else:
                logging.info('A captcha was found. Running again to finish any remaining lines.')
        
        self.cleanUp()

    def cleanUp(self):
        logging.info('Done')

    def __init__(self, siteToRun='', modeToRun=''):
        helpers.setUpLogging('user-data/logs')

        # set default options
        self.options = {
            'inputFile': 'user-data/input/input.csv',
            'outputFile': 'user-data/output/output.csv',
            'maximumSearchResults': 15,
            'proxyListUrl': helpers.getFile('program/resources/resource3'),
            'defaultSearchUrl': '',
            'userAvoidPatterns': '',
            'userAvoidDomains': '',
            'ignoreInCompanyName': '',
            'minimumConfidence': 400,
            'secondsBetweenLines': 0
        }

        optionsFileName = helpers.getParameter('--optionsFile', False, 'user-data/options.ini')
        
        # read the options file
        helpers.setOptions(optionsFileName, self.options)

        helpers.makeDirectory(os.path.dirname(self.options['outputFile']))

        self.database = Database('user-data/database.sqlite')
        
        self.nameFinder = NameFinder(self.options, self.database)

if __name__ == '__main__':
    main = Main()
    main.run()