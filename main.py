import sys
import os
import logging
import datetime

import program.library.helpers as helpers

from program.library.helpers import get

class Main:
    def run(self):
        logging.info('Starting')

        inputRows = []

        for i, inputRow in enumerate(inputRows):
            try:
                logging.info(f'Line {i + 1} of {len(inputRows)}: {inputRow}')
            except Exception as e:
                helpers.handleException(e)
        
        self.cleanUp()

    def cleanUp(self):
        logging.info('Done')

    def __init__(self, siteToRun='', modeToRun=''):
        helpers.setUpLogging('user-data/logs')

        # set default options
        self.options = {
            'inputFile': 'user-data/input/input.txt',
            'outputDirectory': 'user-data/output'
        }

        optionsFileName = helpers.getParameter('--optionsFile', False, 'user-data/options.ini')
        
        # read the options file
        helpers.setOptions(optionsFileName, self.options)

        helpers.makeDirectory(self.options['outputDirectory'])

if __name__ == '__main__':
    main = Main()
    main.run()