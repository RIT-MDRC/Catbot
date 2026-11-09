# SAMPLE MODULES

This directory contains many sample code to test different parts of the hardware.

`odrive_position_test.py` uses the configured logical `actuator` entries while
preserving motor names and CAN axis IDs in its command syntax. Absolute `mp`,
relative `mr`, read, and speed commands are converted through each actuator's
named motion profile, so an inverted profile reverses raw motor direction
without changing logical signs. The sample uses a Textual interface with a
scrollable output log, command-history input, and live configured-axis CAN error
indicator.
