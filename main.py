# This is a sample Python script.
import csv
import os
import sys

import chardet
from PyQt5.QtCore import QStringListModel, QThread, pyqtSignal, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QMainWindow, QDialog, QApplication, QMessageBox, QFileDialog

import UiMainDialog
from coordTransform_utils import *
from build_config import version


def detect_file_encoding(file_path):
    """
    获取文件编码
    :param file_path:
    :return:
    """
    with open(file_path, 'rb') as f:
        code = chardet.detect(f.read(512))  # 根据前512个字符进行检测
        encoding = code['encoding']
        if encoding in ['GB2312', 'GBK']:  # 如果是GB2312或GBK，则使用其超集字符集GB18030
            encoding = 'GB18030'
        return encoding
    pass


def read_csv_top100(file_path):
    """
    读取CSV文件前100条记录，并返回列的数量
    :param file_path:
    :return:
    """
    rows = []
    col_length = 0
    encoding = detect_file_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        csv_reader = csv.reader(f)
        for index, row in enumerate(csv_reader):
            if index > 100:
                break
            rows.append(row)
            if len(row) > col_length:
                col_length = len(row)
    return rows, col_length


def fetch_xy(row: list, lon_index: int, lat_index: int, samecol: bool, sep: str):
    """
    从CSV行数据中获取经度值和纬度值
    :param row: CSV行数据
    :param lon_index: 经度所在列的索引值
    :param lat_index: 纬度所在列的索引值
    :param samecol: 经度和纬度是否在同一列
    :param sep: 经纬度分隔符
    :return: (lon,lat)
    """
    length = len(row)
    if not samecol:
        if lon_index >= length or lat_index >= length:
            raise Exception('不存在的列')
        lon, lat = row[lon_index], row[lat_index]
        if isinstance(lon, str):
            lon = float(lon)
        if isinstance(lat, str):
            lat = float(lat)
        return lon, lat
    else:
        if lon_index >= length:
            raise Exception('不存在的列')
        lonlat = row[lon_index]
        lonlat = lonlat.split(sep)
        lon, lat = float(lonlat[0]), float(lonlat[1])
        return lon, lat


def convert_lonlat(lon: float, lat: float, input_crs: str, output_bd09: bool, output_gcj02: bool, output_wgs84: bool):
    """
    转换经纬度坐标
    :param lon: 经度
    :param lat: 纬度
    :param input_crs: 源坐标系
    :param output_bd09: 输出BD09坐标
    :param output_gcj02: 输出GCJ02坐标
    :param output_wgs84: 输出WGS84坐标
    :return: 返回转换后的坐标数组，结果为 [bd09_x,bd09_y,gcj02_x,gcj02_y,wgs84_x,wgs84_y]
    """
    result = []
    if input_crs == 'BD09':
        if output_bd09:
            result.extend([lon, lat])
        if output_gcj02:
            result.extend(bd09_to_gcj02(lon, lat))
        if output_wgs84:
            result.extend(bd09_to_wgs84(lon, lat))
    elif input_crs == 'GCJ02':
        if output_bd09:
            result.extend(gcj02_to_bd09(lon, lat))
        if output_gcj02:
            result.extend([lon, lat])
        if output_wgs84:
            result.extend(gcj02_to_wgs84(lon, lat))
    elif input_crs == 'WGS84':
        if output_bd09:
            result.extend(wgs84_to_bd09(lon, lat))
        if output_gcj02:
            result.extend(wgs84_to_gcj02(lon, lat))
        if output_wgs84:
            result.extend([lon, lat])
    return result


def convert_header(output_bd09: bool, output_gcj02: bool, output_wgs84: bool):
    """
    转换后的数据标题
    :param output_bd09:
    :param output_gcj02:
    :param output_wgs84:
    :return:
    """
    headers = []
    if output_bd09:
        headers.extend(['bd09_x', 'bd09_y'])
    if output_gcj02:
        headers.extend(['gcj02_x', 'gcj02_y'])
    if output_wgs84:
        headers.extend(['wgs84_x', 'wgs84_y'])
    return headers


def convert_common(file_path, include_title: bool, lon_index: int, lat_index: int, samecol: bool, sep: str,
                   input_crs: str, output_bd09: bool, output_gcj02: bool, output_wgs84: bool, cb=None):
    """
    将CSV文件中的GCJ02坐标转换为WGS84坐标
    :param file_path: CSV坐标文件
    :param x_col: GCJ02经度列序号
    :param y_col: GCJ02纬度列序号
    :return:
    """
    if cb is not None:
        cb('开始转换：%s' % file_path)
    result_file_path = convert_result_file_path(file_path)
    encoding = detect_file_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as fr:
        csv_reader = csv.reader(fr)
        for n, row in enumerate(csv_reader):
            try:
                if n == 0 and include_title:
                    row.extend(convert_header(output_bd09, output_gcj02, output_wgs84))
                else:
                    lon, lat = fetch_xy(row, lon_index, lat_index, samecol, sep)
                    lonlat_list = convert_lonlat(lon, lat, input_crs, output_bd09, output_gcj02, output_wgs84)
                    row.extend(lonlat_list)
                
                with open(result_file_path, 'a', encoding=encoding, newline='\n') as fw:
                    csv_writer = csv.writer(fw)
                    csv_writer.writerow(row)
                
                if cb is not None and n % 100 == 0:
                    cb('%d 条已转换' % n)
            except Exception as e:
                if cb is not None:
                    cb('第 %d 行 转换失败，%s' % (n, str(e)))
        if cb is not None:
            cb('%d 条已转换' % n)
            cb('转换完成，保存路径：%s' % result_file_path)


def convert_result_file_path(file_path):
    """
    获取转换后的文件路径
    :param file_path: 转换前的文件路径
    :return:
    """
    file_root = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    file_name_ext = os.path.splitext(file_path)[-1]
    file_name_alone = os.path.splitext(file_name)[0]
    result_file_path = os.path.join(file_root, file_name_alone + "_result" + file_name_ext)
    return result_file_path


class ConvertThread(QThread):
    """
    坐标文件转换线程，解决转换时界面卡的问题
    """
    
    # 自定义信号对象。参数str就代表这个信号可以传一个字符串
    logger = pyqtSignal(str)  # 记录日志信号
    completed = pyqtSignal(bool)  # 线程执行完成信号
    
    def __int__(self, ):
        # 初始化函数
        super(ConvertThread, self).__init__()
        self.file_path_list = None
        self.include_title = None
        self.lon_index = None
        self.lat_index = None
        self.samecol = None
        self.sep = None
        self.input_crs = None
        self.output_bd09 = None
        self.output_gcj02 = None
        self.output_wgs84 = None
    
    def init(self, file_path_list: str, include_title: bool, lon_index: int, lat_index: int, samecol: bool, sep: str,
             input_crs: str, output_bd09: bool, output_gcj02: bool, output_wgs84: bool):
        """
        初始化转换参数
        :param file_path_list: 待转换文件，可以是list也或以str
        :param include_title: 数据是否包含标题
        :param lon_index: 经度所在列索引值
        :param lat_index: 纬度所在列索引值
        :param samecol: 经度和纬度是否在同一个字段中
        :param sep: 经度和纬度的分隔符号
        :param input_crs: 源坐标系
        :param output_bd09: 是否输出BD09坐标系
        :param output_gcj02: 是否输出GCJ02坐标系
        :param output_wgs84: 是否输出WGS84坐标系
        :return:
        """
        if isinstance(file_path_list, list):
            self.file_path_list = file_path_list
        else:
            self.file_path_list = [file_path_list]
        self.include_title = include_title
        self.lon_index = lon_index
        self.lat_index = lat_index
        self.samecol = samecol
        self.sep = sep
        self.input_crs = input_crs
        self.output_bd09 = output_bd09
        self.output_gcj02 = output_gcj02
        self.output_wgs84 = output_wgs84
    
    def run(self):
        """
        执行坐标转换线程
        :return:
        """
        for file_path in self.file_path_list:
            try:
                convert_common(file_path, self.include_title, self.lon_index, self.lat_index, self.samecol, self.sep,
                               self.input_crs, self.output_bd09, self.output_gcj02, self.output_wgs84, self.log)
            except Exception as e:
                self.log(str(e))
                self.log('文件 %s 转换失败' % file_path)
            finally:
                self.completed.emit(True)
    
    def log(self, text):
        self.logger.emit(text)


class MainWindow(QDialog):
    
    def __init__(self, parent=None):
        super(QDialog, self).__init__(parent)
        self.ui = UiMainDialog.Ui_DialogMain()
        self.ui.setupUi(self)
        # 设置标题文本
        self.setWindowTitle('%s V%s' % (self.windowTitle(), version))
        # 禁止缩放窗口大小
        self.setFixedSize(self.width(), self.height())
        # 初始化待转换文件列表
        self.listviewMode = QStringListModel()
        self.listFiles = []
        self.listFilesName = []
        self.listFileSelectedIndex = -1
        self.listviewMode.setStringList(self.listFiles)
        self.ui.listView.setModel(self.listviewMode)
        self.ui.listView.clicked.connect(self.on_listview_clicked)
        # 初始化转换选项
        self.seps = [',', ';', '|', '#', '-', '空格']
        self.ui.comboBoxSep.addItems(self.seps)
        self.ui.comboBoxSep.setDisabled(True)
        self.crss = ['BD09', 'GCJ02', 'WGS84']
        self.ui.comboBoxInputCRS.addItems(self.crss)
        # Github 链接
        self.ui.labelLink.setOpenExternalLinks(True)
        self.ui.labelLink.setText("<a href='https://github.com/xiantuteng' style='color:blue'>https://github.com/xiantuteng</a>")
        self.ui.labelLink.linkActivated.connect(self.on_github_link_clicked)
        
        # 初始化控件事件
        self.ui.pushButtonAdd.clicked.connect(self.add_file)
        self.ui.pushButtonDelete.clicked.connect(self.del_file)
        self.ui.checkBoxIncludeTitle.stateChanged.connect(self.on_checkbox_includetitle_changed)
        self.ui.checkBoxLonLatSame.stateChanged.connect(self.on_checkbox_samecol_changed)
        self.ui.pushButtonConvert.clicked.connect(self.convert)
        self.ui.pushButtonConvertAll.clicked.connect(self.convert_all)
        # 文件转换线程，存为成员变量保证线程不会无故被Kill
        self.convert_thread = None
        # 上次打开文件的目录路径
        self.lastOpenDir = os.getcwd()
    
    def add_file(self):
        """
        添加文件操作
        :return:
        """
        filename, filetype = QFileDialog.getOpenFileName(None, '选择文件', self.lastOpenDir, 'CSV文件(*.csv)')
        if filename == '':
            return
        if filename in self.listFiles:
            self.show_log('%s 文件已经添加，忽略本次操作' % filename)
            return
        
        self.lastOpenDir = os.path.dirname(filename)
        self.listFiles.append(filename)
        self.listFilesName.append(os.path.basename(filename))
        self.listviewMode.setStringList(self.listFilesName)
        
        # 自动选中添加的文件，并预览数据
        self.listFileSelectedIndex = len(self.listFiles) - 1
        self.ui.listView.setCurrentIndex(self.listviewMode.index(self.listFileSelectedIndex))
        self.on_listview_clicked(self.listviewMode.index(self.listFileSelectedIndex))
    
    def del_file(self):
        """
        删除文件
        :return:
        """
        if self.listFileSelectedIndex < 0 or self.listFileSelectedIndex >= len(self.listFilesName):
            return
        self.listFilesName.pop(self.listFileSelectedIndex)
        self.listFiles.pop(self.listFileSelectedIndex)
        self.listviewMode.setStringList(self.listFilesName)
        # 自动选择上一个文件
        self.listFileSelectedIndex -= 1
        self.ui.listView.setCurrentIndex(self.listviewMode.index(self.listFileSelectedIndex))
        self.on_listview_clicked(self.listviewMode.index(self.listFileSelectedIndex))
    
    def on_listview_clicked(self, index):
        """
        文件列表点击事件
        :param index:
        :return:
        """
        self.listFileSelectedIndex = index.row()
        rows, col_length = read_csv_top100(self.listFiles[self.listFileSelectedIndex])
        header_labels = self.show_at_tableview(rows, col_length, self.ui.checkBoxIncludeTitle.isChecked())
        self.init_combobox(header_labels)
    
    def show_at_tableview(self, rows: list, col_length: int, include_title=False):
        """
        预览CSV数据
        :param rows:
        :param col_length:
        :param include_title:
        :return:
        """
        table_view_mode = QStandardItemModel(1, 1)
        self.ui.tableViewPreview.setModel(table_view_mode)
        if col_length == 0 or rows is None or len(rows) == 0:
            return
        
        start_row_index = 0
        if include_title:
            header_labels = rows[0]
            start_row_index = 1
        else:
            header_labels = [('列' + str(x + 1)) for x in range(col_length)]
        # 渲染表格
        table_view_mode = QStandardItemModel(len(rows) - start_row_index, col_length)
        table_view_mode.setHorizontalHeaderLabels(header_labels)
        for row in range(start_row_index, len(rows)):
            for col in range(col_length):
                item = QStandardItem(rows[row][col])
                table_view_mode.setItem(row - start_row_index, col, item)
        self.ui.tableViewPreview.setModel(table_view_mode)
        
        return header_labels
    
    def on_checkbox_includetitle_changed(self):
        """
        数据是否包含标题选择事件
        :return:
        """
        rows, col_length = read_csv_top100(self.listFiles[self.listFileSelectedIndex])
        self.show_at_tableview(rows, col_length, self.ui.checkBoxIncludeTitle.isChecked())
        header_labels = self.show_at_tableview(rows, col_length, self.ui.checkBoxIncludeTitle.isChecked())
        self.init_combobox(header_labels)
    
    def on_checkbox_samecol_changed(self):
        """
        经纬度同列选择事件
        :return:
        """
        samecol = self.ui.checkBoxLonLatSame.isChecked()
        self.ui.comboBoxLat.setDisabled(samecol)
        self.ui.comboBoxSep.setDisabled(not samecol)
    
    def on_convert_completed(self, completed):
        """
        转换完成事件信号槽
        :param completed:
        :return:
        """
        self.ui.pushButtonConvert.setDisabled(False)
        self.ui.pushButtonConvertAll.setDisabled(False)
    
    def convert(self):
        """
        转换单个文件
        :return:
        """
        if self.listFileSelectedIndex < 0:
            QMessageBox.information(self, '提示', '没有选中文件', QMessageBox.Ok)
            return
        
        # 判断转换后的结果文件是否存在
        result_file_path = convert_result_file_path(self.listFiles[self.listFileSelectedIndex])
        if os.path.exists(result_file_path):
            reply = QMessageBox.question(self, '提示', '转换后文件已存在[%s]，是否覆盖？' % result_file_path,
                                         QMessageBox.Yes | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return
            else:
                # 覆盖已转换的文件
                try:
                    os.remove(result_file_path)
                except Exception as e:
                    self.ui.plainTextEdit.appendPlainText(str(e))
        
        # 开始执行转换
        self.ui.pushButtonConvert.setDisabled(True)
        try:
            self.convert_file(self.listFiles[self.listFileSelectedIndex])
        except Exception as e:
            self.ui.plainTextEdit.appendPlainText(str(e))
            self.ui.pushButtonConvert.setDisabled(False)
    
    def convert_all(self):
        """
        转换所有文件
        :return:
        """
        # 判断所文件是否存在
        if len(self.listFiles) == 0:
            return
        exist_result_files = []
        for file_path in self.listFiles:
            result_file_path = convert_result_file_path(file_path)
            if os.path.exists(result_file_path):
                exist_result_files.append(result_file_path)
        # 如果数据文件已在存在，提示是否覆盖
        if len(exist_result_files) > 0:
            reply = QMessageBox.question(self, '提示', '%d 个转换后文件已存在，是否覆盖？' % len(exist_result_files),
                                         QMessageBox.Yes | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return
            else:
                # 删除已转换的文件
                try:
                    [os.remove(result_file_path) for result_file_path in exist_result_files]
                except Exception as e:
                    self.ui.plainTextEdit.appendPlainText(str(e))
        
        self.ui.pushButtonConvertAll.setDisabled(True)
        try:
            self.convert_file(self.listFiles)
        except Exception as e:
            self.ui.plainTextEdit.appendPlainText(str(e))
            self.ui.pushButtonConvertAll.setDisabled(False)
    
    def convert_file(self, file_path):
        """
        开始转换单个文件
        :param file_path:
        :return:
        """
        include_title = self.ui.checkBoxIncludeTitle.isChecked()
        lon_index = self.ui.comboBoxLon.currentIndex()
        lat_index = self.ui.comboBoxLat.currentIndex()
        samecol = self.ui.checkBoxLonLatSame.isChecked()
        sep = self.seps[self.ui.comboBoxSep.currentIndex()]
        sep = ' ' if sep == '空格' else sep  # 处理经纬度分隔符
        input_crs = self.crss[self.ui.comboBoxInputCRS.currentIndex()]
        output_bd09 = self.ui.checkBoxOutputBd.isChecked()
        output_gcj02 = self.ui.checkBoxOutputGCJ.isChecked()
        output_wgs84 = self.ui.checkBoxOutputWGS.isChecked()
        
        # 启动线程进行转换
        self.convert_thread = ConvertThread()
        self.convert_thread.init(file_path, include_title, lon_index, lat_index, samecol, sep,
                                 input_crs, output_bd09, output_gcj02, output_wgs84)
        self.convert_thread.logger.connect(self.show_log)
        self.convert_thread.completed.connect(self.on_convert_completed)
        self.convert_thread.start()
    
    def init_combobox(self, header_labels):
        self.ui.comboBoxLon.clear()
        self.ui.comboBoxLat.clear()
        self.ui.comboBoxLon.addItems(header_labels)
        self.ui.comboBoxLat.addItems(header_labels)
        pass
    
    def on_github_link_clicked(self):
        pass
    
    def show_log(self, text):
        """
        向文本框中追加日志
        :param text:
        :return:
        """
        self.ui.plainTextEdit.appendPlainText(text)


if __name__ == '__main__':
    myapp = QApplication(sys.argv)
    myDlg = MainWindow()
    myDlg.show()
    sys.exit(myapp.exec_())
