from vl53 import VL53L0X
from portas import Portas

distanciaFrente = VL53L0X(Portas.I2C1)


def leDistanciaFrente(): 
    """retorna o valor de distancia em mm"""

    return distanciaFrente.read_range_single_millimeters()