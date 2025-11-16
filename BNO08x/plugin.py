# the following import is optional
# it only allows "intelligent" IDEs (like PyCharm) to support you in using it
import sys
import os
import time
import math

# Add current directory to Python path to find bno08x module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bno08x

from avnav_api import AVNApi

PLUGIN_VERSION = 20251115


class Plugin(object):
    PATH = "gps.test"
    INTERVAL = "interval"
    SPI_DEVICE = "spi_device"
    GPIOCHIP = "gpiochip"
    INT_PIN = "int_pin"
    RST_PIN = "rst_pin"
    CS_PIN = "cs_pin"
    SPI_SPEED = "spi_speed"
    ENABLE_HDM = "enable_hdm"
    ENABLE_XDR_HDM = "enable_xdr_hdm"
    ENABLE_ROLL = "enable_roll"
    ENABLE_PITCH = "enable_pitch"

    CONFIG = [
        {
            "name": INTERVAL,
            "description": "reporting time interval in seconds",
            "type": "FLOAT",
            "default": 0.25,
        },
        {
            "name": SPI_DEVICE,
            "description": "SPI device path (e.g., /dev/spidev0.0)",
            "type": "STRING",
            "default": "/dev/spidev0.0",
        },
        {
            "name": GPIOCHIP,
            "description": "GPIO chip device (e.g., gpiochip0)",
            "type": "STRING",
            "default": "gpiochip0",
        },
        {
            "name": INT_PIN,
            "description": "GPIO pin number for interrupt (INT)",
            "type": "NUMBER",
            "default": 27,
        },
        {
            "name": RST_PIN,
            "description": "GPIO pin number for reset (RST)",
            "type": "NUMBER",
            "default": 22,
        },
        {
            "name": CS_PIN,
            "description": "GPIO pin number for chip select (CS), -1 uses default SPI CS pin",
            "type": "NUMBER",
            "default": -1,
        },
        {
            "name": SPI_SPEED,
            "description": "SPI speed in Hz",
            "type": "NUMBER",
            "default": 1000000,
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

    def _setup(self) -> bool:
        self.imu = bno08x.BNO08x()
        self.imu.enableDebugging(False)

        spi_device = self.getConfigValue(self.SPI_DEVICE)
        gpiochip = self.getConfigValue(self.GPIOCHIP)
        int_pin = int(self.getConfigValue(self.INT_PIN))
        rst_pin = int(self.getConfigValue(self.RST_PIN))
        cs_pin = int(self.getConfigValue(self.CS_PIN))
        spi_speed = int(self.getConfigValue(self.SPI_SPEED))

        self.api.log(f"Opening SPI: {spi_device} cs={cs_pin} int={int_pin} rst={rst_pin} speed={spi_speed}")
        ok = self.imu.beginSPI(int_pin, rst_pin, cs_pin, spi_speed, spi_device, gpiochip)
        if not ok:
            self.api.error("Failed to initialize BNO08x over SPI. Check wiring and permissions.")
            return False
        else:
            self.api.log("BNO08x initialized successfully over SPI.")
            time.sleep(1)
            return True

    def _setReports(self, interval_ms: int) -> bool:
        if not self.imu.enableRotationVector(interval_ms):
            self.api.log("Failed to enable BNO086 report")
            return False
        return True

    def _close(self):
        self.imu.close()

    def _generateNMEA(self, roll: float, pitch: float, heading: float):
        self.api.debug(f"Roll: {roll:.2f}, Pitch: {pitch:.2f}, Heading: {heading:.2f}")   
        enable_hdm = self.getConfigValue(self.ENABLE_HDM)
        enable_xdr_hdm = self.getConfigValue(self.ENABLE_XDR_HDM)
        enable_roll = self.getConfigValue(self.ENABLE_ROLL)
        enable_pitch = self.getConfigValue(self.ENABLE_PITCH)

        if enable_roll:
            nmea = f"$IIXDR,A,{roll:.1f},D,ROLL"
            self.api.addNMEA(nmea, addCheckSum=True, omitDecode=True)
        if enable_pitch:
            nmea = f"$IIXDR,A,{pitch:.1f},D,PITCH"
            self.api.addNMEA(nmea, addCheckSum=True, omitDecode=True)
        if enable_hdm:
            nmea = f"$IIHDM,{heading:05.1f},M"
            self.api.addNMEA(nmea, addCheckSum=True, omitDecode=True)
        if enable_xdr_hdm:
            nmea = f"$IIXDR,A,{heading:.1f},D,HDM"
            self.api.addNMEA(nmea, addCheckSum=True, omitDecode=True)   


    
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
        self.api.setStatus('STARTED', 'initializing')
        if not self._setup():
            self.api.setStatus('ERROR', 'initialization failed')
            return 
        
        interval_ms = int(self.getConfigValue(self.INTERVAL)*1000)
        self.api.log(f"Using report interval: {interval_ms} ms")    
        if not self._setReports(interval_ms):
            self.api.error("Failed to set reports on BNO08x.")
            self.api.setStatus('ERROR', 'failed to set reports')
            return
        self.api.setStatus('NMEA', 'running')
        while not self.api.shouldStopMainThread():
            if self.imu.wasReset():
                self.api.error("Sensor was reset.")
                if not self._setReports(interval_ms):
                    self.api.error("Failed to set reports on BNO08x after reset.")
                    self.api.setStatus('ERROR', 'failed to set reports after reset')
                    return
            
            try:
                if self.imu.getSensorEvent():
                    roll = self.imu.getRoll() * 180.0 / math.pi
                    pitch = self.imu.getPitch() * 180.0 / math.pi
                    heading = self.imu.getYaw() * 180.0 / math.pi
                    self._generateNMEA(roll, pitch, heading)
                time.sleep(0.01)
            except Exception as e:
                self.api.error(f"Error reading BNO08x data: {e}")