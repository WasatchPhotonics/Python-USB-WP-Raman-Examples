from PySide2 import QtCore
#from PyQt5.QtWidgets import QApplication, QWidget
from PySide2.QtWidgets import QApplication, QWidget, QMainWindow

import time

INTERVALms = 100

class QTimerStudy(QMainWindow):

    def callback(self):
        self.callbackCounts += 1

        # time since start
        elapsedActual = time.time()*1000 - self.startTime

        # number of intervals * INTERVALms
        elapsedExpected = self.callbackCounts * INTERVALms

        # positive sign means intervals are being called LATE
        drift = elapsedActual-elapsedExpected

        # print msg roughly once per second
        if self.callbackCounts % (1000//INTERVALms) == 0:
            print("Drift = %dms. Expected = %dms. Actual = %dms" % (drift, elapsedExpected, elapsedActual))

    def __init__(self):

        super().__init__()

        self.t = QtCore.QTimer()
        self.t.setInterval(INTERVALms)

        # if each trigger causes an offset of x,
        # since we have 100 triggers per second,
        # we should see an offset of 3.6e5*x per hour

        # we have reports of drift ~ 60ms to 6sec per hour
        # for a configuration that triggers once every 10 
        # sec. 

        # this experiment will multiply the hourly drift
        # 1000x, resulting in 6sec to 6000sec offset in
        # one hour

        self.t.timeout.connect(self.callback)

        self.startTime = time.time()*1000
        self.callbackCounts = 0
        self.t.start()

app = QApplication([])
window = QTimerStudy()
window.show()
app.exec_()
