from PyQt5 import QtCore, QtWidgets
from PyQt5 import QtGui
from PyQt5.QtWidgets import QDialog


class MontageMenu(QDialog):
    montage_changed_signal = QtCore.pyqtSignal(dict)

    def __init__(self, source_ch_names, forward_ch_names,
                 reciever, source_bads=[]):
        super().__init__()

        self.title = 'Change channels'
        self.left = 20
        self.top = 20
        self.width = 340
        self.height = 480

        self.source_ch_names = source_ch_names
        self.forward_ch_names = forward_ch_names

        self.source_bads = source_bads

        self.reciever = reciever

        self.initUI()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def initUI(self):
        self.setWindowTitle(self.title)

        self.setGeometry(self.left, self.top, self.width, self.height)
        grid_layout = QtWidgets.QGridLayout()
        self.setLayout(grid_layout)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(2)
        self.max_ch_names = max(
            len(self.source_ch_names), len(self.forward_ch_names))
        self.table.setRowCount(self.max_ch_names)

        self.table.setHorizontalHeaderLabels(["EEG", "Forward"])
        for k in range(self.max_ch_names):
            if k < len(self.source_ch_names):
                sitem = QtWidgets.QTableWidgetItem(self.source_ch_names[k])
                if k < len(self.forward_ch_names):
                    if self.source_ch_names[k] not in self.forward_ch_names:
                        sitem.setBackground(
                            QtGui.QBrush(QtGui.QColor(250, 250, 0)))
                else:
                    sitem.setBackground(
                        QtGui.QBrush(QtGui.QColor(250, 125, 0)))

                if self.source_ch_names[k] in self.source_bads:
                    sitem.setBackground(QtGui.QBrush(QtGui.QColor(250, 75, 0)))

                self.table.setItem(k, 0, QtWidgets.QTableWidgetItem(sitem))

            if k < len(self.forward_ch_names):
                fitem = QtWidgets.QTableWidgetItem(self.forward_ch_names[k])
                fitem.setFlags(
                    QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                self.table.setItem(k, 1, fitem)

        self.table.cellChanged.connect(self.redraw_table)

        grid_layout.addWidget(self.table, 0, 0)

        moveButton = QtWidgets.QPushButton('<<')
        moveButton.clicked[bool].connect(self.move_ch_names)
        grid_layout.addWidget(moveButton, 1, 0)

        okButton = QtWidgets.QPushButton('Ok')
        okButton.clicked[bool].connect(self.reset_ch_names)
        grid_layout.addWidget(okButton, 2, 0)

        self.montage_changed_signal.connect(self.reciever.changeMontage)

    def reset_ch_names(self):
        if len(self.check_duplicate) == 0:
            montage_mapping = {
                self.source_ch_names[k]: str(self.table.item(k, 0).data(0))
                for k in
                range(len(self.forward_ch_names))}
            self.montage_changed_signal.emit(montage_mapping)
            self.close()

    def move_ch_names(self):
        for k in range(
                min(len(self.source_ch_names), len(self.forward_ch_names))):
            self.table.item(k, 0).setText(str(self.table.item(k, 1).data(0)))
        self.redraw_table()

    def redraw_table(self):
        for k in range(
                min(len(self.source_ch_names), len(self.forward_ch_names))):
            if str(self.table.item(k, 0).data(0)) in self.source_bads:
                self.table.item(k, 0).setBackground(
                    QtGui.QBrush(QtGui.QColor(250, 0, 0)))
            elif str(self.table.item(k, 0).data(0))\
                    == str(self.table.item(k, 1).data(0)):
                self.table.item(k, 0).setBackground(
                    QtGui.QBrush(QtGui.QColor(250, 250, 250)))
            else:
                self.table.item(k, 0).setBackground(
                    QtGui.QBrush(QtGui.QColor(250, 250, 0)))

    def check_duplicate(self):
        ch_names_lst = [str(self.table.item(k, 0).data(0))
                        for k in range(len(self.source_ch_names))]
        return set([ch_name for ch_name in ch_names_lst
                    if ch_names_lst.count(ch_name) > 1]) # noqa