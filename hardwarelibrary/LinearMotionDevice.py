class LinearMotionDevice:

    def __init__():
        self.x = None
        self.y = None
        self.z = None
        self.xMinLimit = None
        self.yMinLimit = None
        self.zMinLimit = None
        self.xMaxLimit = None
        self.yMaxLimit = None
        self.zMaxLimit = None


    def moveTo(self, x=None, y=None, z=None):
        self.doMoveTo(x, y, z)

    def position(self) -> ():
        return self.doGetPosition()

    def move1DTo(self, x):
        self.doMoveTo(x)

    def move2DTo(self, x, y):
        self.doMoveTo(x, y)

    def move3DTo(self, x, y, z):
        self.doMoveTo(x, y, z)

    def position1D(self) -> (float):
        return self.doGetPosition()

    def position3D(self) -> (float, float):
        return self.doGetPosition()

    def position3D(self) -> (float, float, float):
        return self.doGetPosition()
