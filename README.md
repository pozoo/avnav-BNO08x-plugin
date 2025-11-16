# avnav-BNO08x-plugin

This plugin can read the Bosch BNO080/BNO085/BNO086 sensor and generate NMEA sentences for Roll, pitch and HDM (heading magnetic).

Currently in developement and only tested with BNO086 on a Raspberry Pi5.

It is based on the [Sparkfun Arduino library for BNO08x sensors](https://github.com/sparkfun/SparkFun_BNO08x_Arduino_Library) that is ported to [Raspberry Pi](https://github.com/pozoo/SparkFun_BNO08x_RaspberryPi_Library). Since it has a nicely made hardware abstraction layer, just the HAL is ported. 

## Wiring
The sensor must be connected to SPI and and 2 GPIOs for RST (output) and INT (input).
Make sure the sensor is configured to the SPI interface (typically PSO+PS1 must be high).

## Install
-Download this repository
-Make sure you have pybind11 and pybind11-dev installed (pip or e.g. as debian package). This is required to generate the Python bindings to the C++ driver library.
-Run make. This will Compile the C++ code and Python bindings that the plugin code needs. 
-Drop the BNO08x folder into Avnav plugin directory.
-Restart Avnav


