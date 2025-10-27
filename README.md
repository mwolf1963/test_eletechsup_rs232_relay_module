# test_eletechsup_rs232_relay_module
A simple gui to test the functions of DC 24V Relay Module 2-Channel Relay RS232 COM DB9 Serial Port Baud Rate 9600kbps. App allows for input of hex values, binary values, and 32 bit long values that can then be sent via RS232.
Built for Windows 11 using python 3.10. build.bat will build the exe and put it in the dist directory (assuming that dependencies are in the \.venv\Lib\site-packages directory). 

Baud rate, stop bits, and parity are set to constant values since the device only supports these.
All other values that are sent to the device are independent of each other to allow experimentation.

Know issue: the COM port drop down does not update when a new COM port is added.

