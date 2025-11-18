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
SOURCE = "BNO08x"

# todo:
# -prio 1
#   -convert yaw to HDM => done
#   -add clean start and shutdown on config changes => done
#   -make heading direction configurable (yaw/pitch/roll)
#   -priority settings for generated NMEA => done
#   -check roll/pitch zero cal (after mounting on HAT)
#   -check if PSO/Wake usage can wake sensor after sh2_open and no HW reset is needed
#   -check long term stability of heading
#     -with active dynamic cal for magnetometer, heading jumps every 10min between 0-8° => not really good ennough
#     -w/o dynamic cal, heading: todo
#   
# 
# -prio 2
#   -maybe change to i2c interface
#   -check influence of active cooler fan on heading
#   -turn off compass dynamic cal and add deviation table
#   -add turn rate to NMEA



class Plugin(object):
    PATH = "gps.test"
    INTERVAL = "intervals"
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
    ENABLE_DYN_MAG_CAL = "enable_dyn_mag_cal"
    PRIORITY = "nmea_priority"
    TALKER_ID = "nmea_id"

    CONFIG = [
        {
            "name": INTERVAL,
            "description": "reporting time interval in milliseconds (10-1000)",
            "type": "NUMBER",
            "default": 250,
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
            "description": "GPIO pin number for interrupt (INT, 0-27)",
            "type": "NUMBER",
            "default": 27,
        },
        {
            "name": RST_PIN,
            "description": "GPIO pin number for reset (RST, 0-27)",
            "type": "NUMBER",
            "default": 22,
        },
        {
            "name": CS_PIN,
            "description": "GPIO pin number for chip select (CS, -1 or 0-27), -1 uses default SPI CS pin",
            "type": "NUMBER",
            "default": -1,
        },
        {
            "name": SPI_SPEED,
            "description": "SPI speed in Hz (100000-3000000)",
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
        {
            "name": ENABLE_DYN_MAGs_CAL,
            "description": "enable dynamic magnetometer calibration",
            "default": "True",
            "type": "BOOLEAN",
        },
        {
            "name": PRIORITY,
            "description": "NMEA source priority (0-100)",
            "type": "NUMBER",
            "default": 10,
        },
        {
            "name": TALKER_ID,
            "description": "NMEA talker ID for emitted sentences (2 uppercase letters)",
            "type": "STRING",
            "default": "II",
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
        self.changeSequence=0
        self.startSequence=0
        self.initializeSensor = True # used in loop to indicate initialization is necessary 
        self.connectionUp = False # indicates sensor is currently connected
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
        self.api.log("_apiRestart() called")

    def _changeConfig(self, newValues):
        self.api.saveConfigValues(newValues)
        self.changeSequence += 1
        self.initializeSensor = True
        self.api.log("_changeConfig() called")

    def getConfigValue(self, name):
        if name in self.configDefaults:
            return self.api.getConfigValue(name, self.configDefaults[name])
        return self.api.getConfigValue(name)

    def validateConfig(self):
        """Validate all configuration values and raise exception if invalid"""
        
        # Validate INTERVAL (must be positive)
        interval = int(self.getConfigValue(self.INTERVAL))  
        if interval < 100 or interval > 1000:
            raise ValueError(f"Invalid {self.INTERVAL}: must be between 10 and 1000 ms, got {interval}")
        
        # Validate SPI_DEVICE (must exist)
        spi_device = self.getConfigValue(self.SPI_DEVICE)
        if not isinstance(spi_device, str) or not spi_device:
            raise ValueError(f"Invalid {self.SPI_DEVICE}: must be a non-empty string, got {spi_device}")
        if not os.path.exists(spi_device):
            raise ValueError(f"Invalid {self.SPI_DEVICE}: device {spi_device} does not exist")
        
        # Validate GPIOCHIP
        gpiochip = self.getConfigValue(self.GPIOCHIP)
        if not isinstance(gpiochip, str) or not gpiochip:
            raise ValueError(f"Invalid {self.GPIOCHIP}: must be a non-empty string, got {gpiochip}")
        gpiochip_path = f"/dev/{gpiochip}" if not gpiochip.startswith("/dev/") else gpiochip
        if not os.path.exists(gpiochip_path):
            raise ValueError(f"Invalid {self.GPIOCHIP}: {gpiochip_path} does not exist")
        
        # Validate INT_PIN (must be valid GPIO number)
        int_pin = int(self.getConfigValue(self.INT_PIN))
        if int_pin < 0 or int_pin > 27:
            raise ValueError(f"Invalid {self.INT_PIN}: must be between 0 and 27, got {int_pin}")
        
        # Validate RST_PIN (must be valid GPIO number)
        rst_pin = int(self.getConfigValue(self.RST_PIN))
        if rst_pin < 0 or rst_pin > 27:
            raise ValueError(f"Invalid {self.RST_PIN}: must be between 0 and 27, got {rst_pin}")
        
        # Validate CS_PIN (must be valid GPIO number or -1)
        cs_pin = int(self.getConfigValue(self.CS_PIN))
        if cs_pin < -1 or cs_pin > 27:
            raise ValueError(f"Invalid {self.CS_PIN}: must be -1 or between 0 and 27, got {cs_pin}")
        
        # Validate SPI_SPEED (must be reasonable)
        spi_speed = int(self.getConfigValue(self.SPI_SPEED))
        if spi_speed < 100000 or spi_speed > 3000000:
            raise ValueError(f"Invalid {self.SPI_SPEED}: must be between 100kHz and 3MHz, got {spi_speed}")
        
        # Validate PRIORITY (must be reasonable)
        priority = int(self.getConfigValue(self.PRIORITY))
        if priority < 0 or priority > 100:
            raise ValueError(f"Invalid {self.PRIORITY}: must be between 0 and 100, got {priority}")
        
        # Validate TALKER_ID (must be 2 uppercase letters)
        talker_id = self.getConfigValue(self.TALKER_ID)
        if not isinstance(talker_id, str):
            raise ValueError(f"Invalid {self.TALKER_ID}: must be a string, got {talker_id}")
        if len(talker_id) != 2:
            raise ValueError(f"Invalid {self.TALKER_ID}: must be exactly 2 characters, got '{talker_id}'")
        if not talker_id.isalpha() or not talker_id.isupper():
            raise ValueError(f"Invalid {self.TALKER_ID}: must be 2 uppercase letters, got '{talker_id}'")

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
        SH2_CAL_ACCEL = 0x01
        SH2_CAL_GYRO  = 0x02
        SH2_CAL_MAG   = 0x04
        SH2_CAL_PLANAR = 0x08

        cal_type = SH2_CAL_ACCEL | SH2_CAL_GYRO
        if self.getConfigValue(self.ENABLE_DYN_MAG_CAL):
            cal_type |= SH2_CAL_MAG

        if not self.imu.enableRotationVector(interval_ms):
            self.api.log("Failed to enable BNO086 rotation vector report")
            return False
        if not self.imu.enableMagnetometer(interval_ms):
            self.api.log("Failed to enable BNO086 magnetometer report")
            return False
        if not self.imu.setCalibrationConfig(cal_type):
            self.api.log("Failed to set BNO08x calibration configuration")
            return False
        return True

    def _close(self):
        self.imu.close()

    def _generateNMEA(self):
        enable_hdm = self.getConfigValue(self.ENABLE_HDM)
        enable_xdr_hdm = self.getConfigValue(self.ENABLE_XDR_HDM)
        enable_roll = self.getConfigValue(self.ENABLE_ROLL)
        enable_pitch = self.getConfigValue(self.ENABLE_PITCH)
        nmea_priority = int(self.getConfigValue(self.PRIORITY))
        nmea_id = self.getConfigValue(self.TALKER_ID)

        SENSOR_REPORTID_GAME_ROTATION_VECTOR = 0x08
        SENSOR_REPORTID_ROTATION_VECTOR = 0x05
        if (self.imu.getSensorEventID() == SENSOR_REPORTID_ROTATION_VECTOR or self.imu.getSensorEventID() == SENSOR_REPORTID_GAME_ROTATION_VECTOR):
            roll = self.imu.getRoll() * 180.0 / math.pi
            pitch = self.imu.getPitch() * 180.0 / math.pi
            yaw = self.imu.getYaw() * 180.0 / math.pi
            if (yaw < 0):
                heading = yaw + 360.0
            else:
                heading = yaw   
            self.api.debug(f"Roll: {roll:.2f}, Pitch: {pitch:.2f}, Heading: {heading:.2f}")   

            if enable_roll:
                nmea = f"${nmea_id}XDR,A,{roll:.1f},D,ROLL"
                self.api.addNMEA(nmea, addCheckSum=True, omitDecode=False, sourcePriority=nmea_priority, source=SOURCE)
            if enable_pitch:
                nmea = f"${nmea_id}XDR,A,{pitch:.1f},D,PITCH"
                self.api.addNMEA(nmea, addCheckSum=True, omitDecode=False, sourcePriority=nmea_priority, source=SOURCE)
            if enable_hdm:
                nmea = f"${nmea_id}HDM,{heading:05.1f},M"
                self.api.addNMEA(nmea, addCheckSum=True, omitDecode=False, sourcePriority=nmea_priority, source=SOURCE)
            if enable_xdr_hdm:
                nmea = f"${nmea_id}XDR,A,{heading:.1f},D,HDM"
                self.api.addNMEA(nmea, addCheckSum=True, omitDecode=False, sourcePriority=nmea_priority, source=SOURCE)   
       
        SH2_MAGNETIC_FIELD_CALIBRATED = 0x03
        if (self.imu.getSensorEventID() == SH2_MAGNETIC_FIELD_CALIBRATED):
            mag_cal_accuracy = self.imu.getMagAccuracy()
            self.api.debug(f"Mag_cal_acc {mag_cal_accuracy:.0f}") 
            if enable_hdm or enable_xdr_hdm:
                nmea = f"${nmea_id}XDR,A,{mag_cal_accuracy:.1f},D,MAG_ACC"
                self.api.addNMEA(nmea, addCheckSum=True, omitDecode=False, sourcePriority=nmea_priority, source=SOURCE)

    
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
        interval_ms = int(self.getConfigValue(self.INTERVAL))

        while not self.api.shouldStopMainThread():
            if self.initializeSensor:
                if self.connectionUp:
                    self.imu.close()
                    self.api.log("BNO08x connection closed")
                self.api.setStatus('STARTED', 'initializing')
                self.validateConfig()
                if not self._setup():
                    self.api.setStatus('ERROR', 'initialization failed')
                    return
                self.api.log("BNO08x initialized successfully") 
                interval_ms = int(self.getConfigValue(self.INTERVAL))
                self.api.log(f"Using report interval: {interval_ms} ms")    
                if not self._setReports(interval_ms):
                    self.api.error("Failed to set reports on BNO08x.")
                    self.api.setStatus('ERROR', 'failed to set reports')
                    return
                self.api.log("BNO08x reports set successfully")
                self.api.setStatus('NMEA', 'running')
                self.connectionUp = True
                self.initializeSensor = False

            if self.imu.wasReset():
                self.api.error("Sensor was reset.")
                if not self._setReports(interval_ms):
                    self.api.error("Failed to set reports on BNO08x after reset.")
                    self.api.setStatus('ERROR', 'failed to set reports after reset')
                    return
            
            try:
                if self.imu.getSensorEvent():
                    self._generateNMEA()
                time.sleep(0.01)
            except Exception as e:
                self.api.error(f"Error reading BNO08x data: {e}")

        self.imu.close()
        self.api.log("BNO08x plugin stopped")
