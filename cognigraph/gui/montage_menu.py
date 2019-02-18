from PyQt5 import QtCore, QtWidgets
from PyQt5 import QtGui
from PyQt5.QtWidgets import QDialog

class MontageMenu(QDialog):
    def __init__(self, source_ch_names, forward_ch_names, source_controls, source_bads=[], forward_bads=[]):
        super().__init__()

        self.source_controls = source_controls

        self.title = 'Change channels'
        self.left = 20
        self.top = 20
        self.width = 340
        self.height = 480

        self.source_ch_names = source_ch_names
        self.forward_ch_names = forward_ch_names

        self.source_bads = source_bads
        self.forward_bads = forward_bads

        self.initUI()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)


    def initUI(self):
        self.setWindowTitle(self.title)

        self.setGeometry(self.left, self.top, self.width, self.height)
        grid_layout = QtWidgets.QGridLayout()
        self.setLayout(grid_layout)

        self.table = QtWidgets.QTableWidget(self)  # Создаём таблицу
        self.table.setColumnCount(2)  # Устанавливаем три колонки
        self.max_ch_names = max(len(self.source_ch_names), len(self.forward_ch_names))
        self.table.setRowCount(self.max_ch_names)

        self.table.setHorizontalHeaderLabels(["EEG", "Forward"])
        for k in range(self.max_ch_names):
            if k<len(self.source_ch_names):
                sitem = QtWidgets.QTableWidgetItem(self.source_ch_names[k])
                if k<len(self.forward_ch_names):
                    if self.source_ch_names[k] not in self.forward_ch_names:
                        sitem.setBackground(QtGui.QBrush(QtGui.QColor(250,250,0)))
                else:
                    sitem.setBackground(QtGui.QBrush(QtGui.QColor(250, 125, 0)))

                if self.source_ch_names[k] in self.source_bads:
                    sitem.setBackground(QtGui.QBrush(QtGui.QColor(250, 0, 0)))

                self.table.setItem(k, 0, QtWidgets.QTableWidgetItem(sitem))

            if k<len(self.forward_ch_names):
                fitem = QtWidgets.QTableWidgetItem(self.forward_ch_names[k])
                fitem.setFlags(QtCore.Qt.ItemIsUserCheckable|QtCore.Qt.ItemIsEnabled)
                self.table.setItem(k, 1, fitem)

        grid_layout.addWidget(self.table, 0, 0)

        okButton = QtWidgets.QPushButton('Ok')
        okButton.clicked[bool].connect(self.reset_ch_names)
        grid_layout.addWidget(okButton,1,0)

    def reset_ch_names(self):
        self.source_controls._pipeline._mapping = {self.source_ch_names[k]:str(self.table.item(k,0).data(0)) for k in range(len(self.forward_ch_names))}
        self.close()