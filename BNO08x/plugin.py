# the following import is optional
# it only allows "intelligent" IDEs (like PyCharm) to support you in using it
from avnav_api import AVNApi

PLUGIN_VERSION = 20251115


class Plugin(object):
    PATH = "gps.test"
    PERIOD = "period"
    ENABLE_HDM = "enable_hdm"
    ENABLE_XDR_HDM = "enable_xdr_hdm"
    ENABLE_ROLL = "enable_roll"
    ENABLE_PITCH = "enable_pitch"

    CONFIG = [
        {
            "name": PERIOD,
            "description": "reporting time interval in seconds",
            "type": "FLOAT",
            "default": 0.25,
        },
        {
            "name": ENABLE_HDM,
            "description": "enable writing of HDM NMEA sentences",
            "default": "True",
            "type": "BOOLEAN",
        },
        {
            "name": ENABLE_XDR_HDM,
            "description": "writes HDM as XDR HDM instead of direct HDM sentence to allow running it in parallel to anoher compass",
            "default": "True",
            "type": "BOOLEAN",
        },
        {
            "name": ENABLE_ROLL,
            "description": "write NMEA XDR sentence for ROLL",
            "default": "True",
            "type": "BOOLEAN",
        },
        {
            "name": ENABLE_PITCH,
            "description": "write NMEA XDR sentence for PITCH",
            "default": "True",
            "type": "BOOLEAN",
        },
    ]

    @classmethod
    def pluginInfo(cls):
        """
        the description for the module
        @return: a dict with the content described below
                parts:
                   * description (mandatory)
                   * data: list of keys to be stored (optional)
                     * path - the key - see AVNApi.addData, all pathes starting with "gps." will be sent to the GUI
                     * description
        """
        return {
            'description': 'BNO08x 9-DOF plugin, provides roll, pitch, HDM',
            'version': PLUGIN_VERSION,
            'config': cls.CONFIG,
            'data': [
            ]
        }

    def __init__(self, api):
        """
            initialize a plugins
            do any checks here and throw an exception on error
            do not yet start any threads!
            @param api: the api to communicate with avnav
            @type  api: AVNApi
        """
        self.api = api  # type: AVNApi
        # Create a lookup dictionary for config defaults
        self.configDefaults = {cf['name']: cf.get('default') for cf in self.CONFIG}
        if hasattr(self.api, 'registerEditableParameters'):
            self.api.registerEditableParameters(
                self.CONFIG, self._changeConfig)
            self.canEdit = True
        if hasattr(self.api, 'registerRestart'):
            self.api.registerRestart(self._apiRestart)

        # we register an handler for API requests
        # self.api.registerRequestHandler(self.handleApiRequest)
        # self.count=0

        # if hasattr(self.api,'registerCommand'):
        # here we could register a command that can be triggered via the API
        # self.api.registerCommand('test','testCmd.sh',['dummy'],client='all')
        #  pass

    def _apiRestart(self):
        self.startSequence += 1
        self.changeSequence += 1

    def _changeConfig(self, newValues):
        self.api.saveConfigValues(newValues)
        self.changeSequence += 1

    def getConfigValue(self, name):
        if name in self.configDefaults:
            return self.api.getConfigValue(name, self.configDefaults[name])
        return self.api.getConfigValue(name)

    def run(self):
        """
        the run method
        this will be called after successfully instantiating an instance
        this method will be called in a separate Thread
        The example simply counts the number of NMEA records that are flowing through avnav
        and writes them to the store every 10 records
        @return:
        """
        seq = 0
        self.api.log("started")
        self.api.setStatus('NMEA', 'running')
        while not self.api.shouldStopMainThread():
            seq, data = self.api.fetchFromQueue(seq, 10)
            if len(data) > 0:
                for line in data:
                    # do something
                    self.count += 1
                    if self.count % 10 == 0:
                        self.api.addData(self.PATH, self.count)
                        # self.api.addData("wrong.path",count) #this would be ignored as we did not announce our path - and will write to the log

    
