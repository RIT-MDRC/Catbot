from potentiometer.pot import Potentiometer

from raspi.io_controller.pneumatics.pressure.pressure import Pressure

current_data: list[int]
potentiometers: list[Potentiometer]
pressure: Pressure
