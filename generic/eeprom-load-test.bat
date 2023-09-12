@echo off

:START

echo running 10 iterations
py multispec-util.py --eeprom-load-test --loop 10 

echo sleeping 5sec...
sleep 5

goto START
