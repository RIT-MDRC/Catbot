from potentiometer.pot import Potentiometer
from pneumatics.pressure import Pressure

class Receiver():
    current_data : list[int]
    potentiometers : list[Potentiometer]
    pressure : Pressure

    ...

