
class LaserSourceDevice:

    def turnOn(self):
        self.doTurnOn()

    def turnOff(self):
        self.doTurnOff()

    def setPower(self, power:float):
        self.doSetPower(power)

    def power(self) -> float:
        return self.doGetPower()

    def interlock(self) -> bool:
        return self.doGetInterlock()