#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Norbert Jander
"""Independent Qt 6 frontend for the MIT-licensed gputaskman collector."""
from __future__ import annotations
import argparse
from collections import deque
import datetime
import html
import json
import math
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import Qt, QRectF, QPointF, QProcess, QSettings, QTimer
from PySide6.QtGui import QIcon, QColor, QFont, QPainter, QPainterPath, QPen, QLinearGradient, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QStackedWidget, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QTextBrowser,
    QSpinBox, QSplitter, QLineEdit, QFileDialog, QMessageBox, QDialog, QSizePolicy)

PALETTE = {'bg':'#1d2021','surface':'#25292a','raised':'#2c3233','line':'#364244',
    'text':'#e9f0f1','muted':'#95a6ad','cyan':'#20d9ef','green':'#39d353',
    'purple':'#b77aff','amber':'#ffb52e','red':'#ff6257','blue':'#38bdf8','yellow':'#f3d34a'}
METRICS = [
    ('GPU activity', 'util_gpu', '%', 100, 'green'),
    ('GPU memory', 'vram_pct', '%', 100, 'purple'),
    ('Temperature', 'temp', '°C', 120, 'amber'),
    ('Power', 'power_w', 'W', None, 'yellow'),
    ('GPU clock', 'sm_clock', 'MHz', None, 'red'),
    ('Memory activity', 'util_mem', '%', 100, 'purple'),
    ('Video encoder', 'enc', '%', 100, 'cyan'),
    ('Video decoder', 'dec', '%', 100, 'blue'),
]
STYLE = '''
QWidget { background:#1d2021; color:#e9f0f1; font-family:"Noto Sans","DejaVu Sans",sans-serif; font-size:13px; }
QMainWindow, QStackedWidget, QScrollArea { background:#1d2021; }
QFrame#Sidebar { background:#222627; border-right:1px solid #364244; }
QFrame#Sidebar QLabel { background:transparent; }
QLabel#Brand { color:#20d9ef; font-size:21px; font-weight:800; letter-spacing:2px; }
QLabel#Eyebrow { color:#20d9ef; font-size:10px; font-weight:700; letter-spacing:2px; }
QLabel#PageTitle { font-size:27px; font-weight:700; }
QLabel#Muted { color:#95a6ad; }
QLabel#MetricValue { font-size:28px; font-weight:700; }
QFrame#Card { background:#25292a; border:1px solid #364244; border-radius:10px; }
QFrame#Card QLabel { background:transparent; }
QPushButton { background:#2c3233; border:1px solid #405052; border-radius:6px; padding:8px 12px; }
QPushButton:hover { background:#354244; border-color:#20d9ef; }
QPushButton:checked { background:#194b51; border-color:#20d9ef; color:#c8faff; }
QPushButton:disabled { color:#718086; }
QPushButton#Nav { text-align:left; border:none; padding:12px 15px; background:transparent; }
QPushButton#Nav:checked { background:#203f49; color:#a1f5ff; border-left:3px solid #20d9ef; border-radius:4px; }
QPushButton#Access { border-color:#547361; color:#8be9a2; }
QComboBox, QLineEdit { background:#2c3233; border:1px solid #405052; border-radius:5px; padding:7px 9px; }
QComboBox QAbstractItemView { background:#2c3233; selection-background-color:#245963; }
QTableWidget { background:#202526; alternate-background-color:#252c2d; border:none; gridline-color:#303b3c; selection-background-color:#305f3e; }
QTableWidget::item { padding:7px; }
QHeaderView::section { background:#2c3435; color:#b4cbd0; padding:9px; border:none; border-bottom:1px solid #405052; font-weight:600; }
QTextBrowser { background:#25292a; border:1px solid #364244; border-radius:8px; padding:12px; selection-background-color:#245963; }
QScrollArea { border:none; }
QScrollBar:vertical { background:#202526; width:9px; margin:0; }
QScrollBar::handle:vertical { background:#43565a; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QStatusBar { background:#191d1e; color:#95a6ad; border-top:1px solid #364244; }
QSplitter::handle { background:#364244; height:3px; }
QToolTip { background:#303a3b; color:#e9f0f1; border:1px solid #537174; padding:7px; }
'''

def gpu_display_name(name):
    """Remove only a repeated leading vendor in the displayed adapter name."""
    words=str(name or 'GPU').split()
    while len(words)>1 and words[0].casefold() in {'intel','amd','nvidia'} and words[0].casefold()==words[1].casefold():
        words.pop(0)
    return ' '.join(words)

def number(value, unit='', decimals=0):
    if value is None: return 'n/a'
    return f'{value:,.{decimals}f}{(" " if unit not in ("%", "°C", "") else "")}{unit}'

def memory(value):
    if value is None: return 'n/a'
    for unit, factor in [('TB',1<<40),('GB',1<<30),('MB',1<<20),('KB',1<<10)]:
        if value >= factor: return f'{value/factor:.2f} {unit}'
    return f'{value:.0f} B'

def percent(used, total):
    return 100*used/total if used is not None and total else None

def label(text='', name=None):
    w=QLabel(text)
    if name: w.setObjectName(name)
    return w

def scroll(widget):
    area=QScrollArea();area.setWidgetResizable(True);area.setWidget(widget)
    return area

class Plot(QWidget):
    """Antialiased history plot with explicit scales and gaps for missing readings."""
    def __init__(self, title, color, maximum=100, unit='%', parent=None):
        super().__init__(parent)
        self.title=title;self.color=PALETTE.get(color,color);self.maximum=maximum;self.unit=unit
        self.values=deque(maxlen=300);self.secondary=deque(maxlen=300)
        self.overlay=False;self.window_seconds=120
        self.setMinimumHeight(185)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setToolTip('Trailing 120 seconds. Gaps mean unavailable readings; zero stays zero. Click to focus this chart.')
        self.clicked=None
    def append(self, timestamp, value, secondary=None):
        self.values.append((timestamp,value));self.secondary.append((timestamp,secondary));self.update()
    def clear(self):
        self.values.clear();self.secondary.clear();self.update()
    def mousePressEvent(self,event):
        if self.clicked:self.clicked()
        super().mousePressEvent(event)
    def format_value(self,value):
        return memory(value) if self.unit=='bytes' else number(value,self.unit)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        p.setPen(QColor(PALETTE['line']));p.setBrush(QColor(PALETTE['surface']));p.drawRoundedRect(r,10,10)
        font=QFont(self.font());font.setBold(True);p.setFont(font)
        p.setPen(QColor(self.color));p.drawText(QRectF(18,12,r.width()-36,23),Qt.AlignmentFlag.AlignLeft,self.title.upper())
        current=self.values[-1][1] if self.values else None
        current_label=self.format_value(current)
        if self.overlay and self.secondary:current_label+=' · '+number(self.secondary[-1][1],'°C')
        p.drawText(QRectF(18,12,r.width()-36,23),Qt.AlignmentFlag.AlignRight,current_label)
        valid=[v for _,v in self.values if v is not None]
        maximum=self.maximum or max((1<<20) if self.unit=='bytes' else 1,max(valid,default=0)*1.15)
        axis_font=QFont(self.font().family(),9);p.setFont(axis_font)
        left=max(46,max(p.fontMetrics().horizontalAdvance(self.format_value(maximum*fraction)) for fraction in [0,.5,1])+12)
        plot=QRectF(left,49,max(1,r.width()-left-(45 if self.overlay else 19)),max(1,r.height()-83))
        p.fillRect(plot,QColor('#162724' if self.color==PALETTE['green'] else '#20212c'))
        p.setFont(QFont(self.font().family(),9));p.setPen(QColor('#324b43' if self.color==PALETTE['green'] else '#383448'))
        for i in range(7):
            x=plot.left()+plot.width()*i/6;p.drawLine(QPointF(x,plot.top()),QPointF(x,plot.bottom()))
        for i in range(5):
            y=plot.top()+plot.height()*i/4;p.drawLine(QPointF(plot.left(),y),QPointF(plot.right(),y))
        valid=[v for _,v in self.values if v is not None]
        maximum=self.maximum or max((1<<20) if self.unit=='bytes' else 1,max(valid,default=0)*1.15)
        p.setPen(QColor(PALETTE['muted']))
        for fraction in [0,.5,1]:
            y=plot.bottom()-plot.height()*fraction
            p.drawText(QRectF(1,y-9,left-7,18),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,self.format_value(maximum*fraction))
        p.drawText(QRectF(plot.left(),plot.bottom()+7,100,18),Qt.AlignmentFlag.AlignLeft,'−120 s')
        p.drawText(QRectF(plot.right()-70,plot.bottom()+7,70,18),Qt.AlignmentFlag.AlignRight,'now')
        if not self.values:
            p.drawText(plot,Qt.AlignmentFlag.AlignCenter,'Waiting for readings…');return
        end=self.values[-1][0]
        def trace(values,maximum,color,fill):
            segment=[]
            def draw():
                if not segment:return
                path=QPainterPath(segment[0])
                for point in segment[1:]:path.lineTo(point)
                if fill and len(segment)>1:
                    area=QPainterPath(path);area.lineTo(segment[-1].x(),plot.bottom());area.lineTo(segment[0].x(),plot.bottom());area.closeSubpath()
                    gradient=QLinearGradient(plot.topLeft(),plot.bottomLeft())
                    c=QColor(color);c.setAlpha(80);gradient.setColorAt(0,c);c.setAlpha(8);gradient.setColorAt(1,c)
                    p.fillPath(area,gradient)
                p.setPen(QPen(QColor(color),1.8));p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
                if len(segment)==1:p.drawEllipse(segment[0],2,2)
            p.save();p.setClipRect(plot)
            for ts,value in values:
                if ts<end-self.window_seconds:continue
                if value is None:draw();segment=[];continue
                x=plot.right()-(end-ts)/self.window_seconds*plot.width()
                y=plot.bottom()-max(0,min(1,value/maximum))*plot.height()
                segment.append(QPointF(x,y))
            draw();p.restore()
        trace(self.values,maximum,self.color,True)
        if self.overlay:
            trace(self.secondary,120,PALETTE['amber'],False)
            p.setPen(QColor(PALETTE['amber']))
            p.drawText(QRectF(plot.right()+5,plot.top()-8,40,20),Qt.AlignmentFlag.AlignLeft,'120°C')
            temp=self.secondary[-1][1] if self.secondary else None
            p.drawText(QRectF(plot.right()+5,plot.bottom()-12,40,20),Qt.AlignmentFlag.AlignLeft,'0°C')

class Metric(QFrame):
    def __init__(self,title,color):
        super().__init__();self.setObjectName('Card')
        lay=QVBoxLayout(self);lay.setContentsMargins(17,12,17,12);lay.setSpacing(4)
        name=label(title.upper(),'Muted');lay.addWidget(name)
        self.value=label('n/a','MetricValue');self.value.setStyleSheet(f'color:{PALETTE[color]};');lay.addWidget(self.value)
        self.note=label('Waiting for readings','Muted');self.note.setWordWrap(True);lay.addWidget(self.note)
    def set(self,value,note=''):
        self.value.setText(value);self.note.setText(note)

class FleetCard(QFrame):
    def __init__(self,identity,open_gpu):
        super().__init__();self.setObjectName('Card');self.identity=identity
        lay=QVBoxLayout(self);lay.setContentsMargins(15,13,15,13)
        top=QHBoxLayout();self.name=label('','Eyebrow');self.name.setWordWrap(True);top.addWidget(self.name,1)
        button=QPushButton('Open GPU');button.clicked.connect(lambda:open_gpu(identity['id']));top.addWidget(button);lay.addLayout(top)
        self.address=label('','Muted');self.address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);self.address.setWordWrap(True);lay.addWidget(self.address)
        self.metrics=label('');self.metrics.setWordWrap(True);lay.addWidget(self.metrics)
        self.state=label('','Muted');self.state.setWordWrap(True);lay.addWidget(self.state)
        self.plot=Plot('GPU activity','green');self.plot.setMinimumHeight(155);lay.addWidget(self.plot)
    def refresh(self,identity,data,error,history):
        self.identity=identity
        prefix=f"GPU {identity.get('index', '?')}" if identity.get('present',True) else 'OFFLINE'
        self.name.setText(prefix+' · '+gpu_display_name(identity.get('name')))
        location=identity.get('pci_bus_id') or 'PCI identity unavailable'
        self.address.setText('PCI '+location+(' · '+identity['uuid'] if identity.get('uuid') else ''))
        self.address.setToolTip('Serial: '+str(identity.get('serial') or 'not reported')+'\nIdentity source: '+identity.get('identity_source','session only'))
        nv=(data or {}).get('device') or {}
        self.metrics.setText('GPU '+number(nv.get('util_gpu'),'%')+'   ·   VRAM '+memory((data or {}).get('vram_used'))+
                             ' / '+memory((data or {}).get('vram_total'))+'   ·   '+number(nv.get('temp'),'°C')+'   ·   '+number(nv.get('power_w'),'W'))
        note=(data or {}).get('memory_note')
        self.state.setText(error or (data or {}).get('counter_status') or identity.get('identity_warning') or ('Memory: client sum / estimated total' if note else 'Physical GPU · independent readings'))
        self.state.setStyleSheet('color:'+('#ffb52e' if error or note or identity.get('identity_warning') else '#95a6ad')+';')
        self.state.setToolTip(note or error or '')
        self.plot.values=deque(history,maxlen=300);self.plot.update()

class NumericItem(QTableWidgetItem):
    def __init__(self,text,value=None):
        super().__init__(text);self.value=value
    def __lt__(self,other):
        if isinstance(other,NumericItem):
            return (self.value is not None,self.value or 0)<(other.value is not None,other.value or 0)
        return super().__lt__(other)

class Window(QMainWindow):
    def __init__(self, demo=False, worker=None, screenshot=None, self_test=False, standard_access=False, demo_gpus=1):
        super().__init__()
        self.demo=demo;self.demo_gpus=demo_gpus;self.worker_override=worker;self.proc=None;self.buffer=b'';self.last=None
        self.pending_gap=False;self.paused=False;self.elevated=os.geteuid()==0 or not standard_access;self.stopping=False;self.rows=[];self.last_received=0
        self.record_file=None;self.replay_frames=None;self.replay_index=0;self.record_deadline=None
        self.record_timer=QTimer(self);self.record_timer.setInterval(250);self.record_timer.timeout.connect(self.check_recording_duration)
        self.replay_timer=QTimer(self);self.replay_timer.setSingleShot(True);self.replay_timer.timeout.connect(self.replay_step)
        self.settings=QSettings('gputaskman','Qt6')
        self.device_inventory={};self.gpu_snapshots={};self.history_cache={};self.gpu_errors={};self.last_frame={}
        self.fleet_cards={};self.auto_fleet_selected=False;self.selected_gpu_id=None
        self.setWindowTitle('GPU Task Manager · Qt 6');self.resize(1360,940);self.setMinimumSize(980,700)
        if not demo and self.settings.value('geometry') is not None:self.restoreGeometry(self.settings.value('geometry'))
        central=QWidget();self.setCentralWidget(central);outer=QHBoxLayout(central);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName('Sidebar');sidebar.setFixedWidth(205);side=QVBoxLayout(sidebar);side.setContentsMargins(16,24,16,18)
        side.addWidget(label('GPU','Brand'));side.addWidget(label('TASK MANAGER','Eyebrow'));side.addSpacing(10)
        side.addWidget(label('LOCAL TELEMETRY','Muted'));side.addSpacing(25)
        self.nav=[]
        for index,(symbol,title) in enumerate([('◫','Overview'),('⌁','Performance'),('≡','Processes'),('ⓘ','Diagnostics'),('▦','All GPUs')]):
            button=QPushButton(f'{symbol}   {title}');button.setObjectName('Nav');button.setCheckable(True)
            button.clicked.connect(lambda _,i=index:self.navigate(i));side.addWidget(button);self.nav.append(button)
        side.addStretch()
        side.addWidget(label('QT 6 EDITION','Eyebrow'))
        sub=label('Qt version 0.4.3\nBuilt on gputaskman 0.4.3','Muted');sub.setWordWrap(True);side.addWidget(sub);side.addSpacing(16)
        help_button=QPushButton('Help & licenses');help_button.clicked.connect(self.help);side.addWidget(help_button)
        outer.addWidget(sidebar)
        content=QWidget();body=QVBoxLayout(content);body.setContentsMargins(26,22,26,12);body.setSpacing(15);outer.addWidget(content,1)
        header=QHBoxLayout();title_col=QVBoxLayout();title_col.setSpacing(3)
        self.heading=label('Overview','PageTitle');title_col.addWidget(self.heading)
        self.subtitle=label('Connecting to the GPU collector…','Muted');self.subtitle.setWordWrap(True);title_col.addWidget(self.subtitle);header.addLayout(title_col,1)
        self.gpu=QComboBox();self.gpu.setMinimumWidth(245);self.gpu.setMaximumWidth(390);self.gpu.view().setMinimumWidth(700);self.gpu.addItem('GPU 0',0);self.gpu.currentIndexChanged.connect(self.gpu_changed);header.addWidget(self.gpu)
        self.rate=QComboBox()
        for seconds in [.5,1,2,5]:self.rate.addItem(f'{seconds:g} s refresh',seconds)
        self.rate.setCurrentIndex(1);self.rate.currentIndexChanged.connect(self.rate_changed);header.addWidget(self.rate)
        self.pause_button=QPushButton('Ⅱ  Pause');self.pause_button.setCheckable(True);self.pause_button.clicked.connect(self.pause);header.addWidget(self.pause_button)
        body.addLayout(header)
        transport=QHBoxLayout()
        self.record_button=QPushButton('● Record');self.record_button.clicked.connect(self.toggle_recording);transport.addWidget(self.record_button)
        load=QPushButton('Open recording');load.clicked.connect(self.open_recording);transport.addWidget(load)
        self.rewind_button=QPushButton('Rewind');self.rewind_button.clicked.connect(self.rewind_recording);self.rewind_button.setEnabled(False);transport.addWidget(self.rewind_button)
        self.speed=QComboBox()
        for speed in [.5,1,2,4]:self.speed.addItem(f'{speed:g}× playback',speed)
        self.speed.setCurrentIndex(1);transport.addWidget(self.speed)
        self.return_button=QPushButton('Return to live');self.return_button.clicked.connect(self.return_live);self.return_button.setEnabled(False);transport.addWidget(self.return_button)
        transport.addStretch();body.addLayout(transport)
        recording_options=QHBoxLayout();recording_options.addWidget(label('Recording duration:'))
        self.record_duration=QSpinBox();self.record_duration.setRange(0,10080);self.record_duration.setSuffix(' min');self.record_duration.setSpecialValueText('Unlimited');self.record_duration.setToolTip('Elapsed wall-clock time, including pauses. 0 means unlimited; maximum 7 days.')
        recording_options.addWidget(self.record_duration)
        self.record_status=label('','Muted');self.record_status.setWordWrap(True);recording_options.addWidget(self.record_status,1);body.addLayout(recording_options)
        self.notice=label('');self.notice.setWordWrap(True);self.notice.setStyleSheet('color:#ffca73; background:#332c21; border:1px solid #58492d; border-radius:5px; padding:8px;');self.notice.hide();body.addWidget(self.notice)
        self.pages=QStackedWidget();body.addWidget(self.pages,1)
        self.build_overview();self.build_performance();self.build_processes();self.build_diagnostics();self.build_fleet()
        footer=QHBoxLayout();self.access=QPushButton('Enable full access');self.access.setObjectName('Access');self.access.clicked.connect(self.toggle_access);footer.addWidget(self.access)
        self.access_note=label('Standard access · window runs as your user','Muted');footer.addWidget(self.access_note,1)
        self.live=label('●  Connecting','Muted');footer.addWidget(self.live);body.addLayout(footer)
        self.statusBar().showMessage('Local monitoring only · unavailable readings remain n/a')
        self.navigate(0)
        self.shortcuts=[]
        for key,callback in [('Space',lambda:self.pause_button.click()),('F1',self.help),('Ctrl+R',self.restart),('Ctrl+P',lambda:self.navigate(2))]:
            shortcut=QShortcut(QKeySequence(key),self);shortcut.activated.connect(callback);self.shortcuts.append(shortcut)
        self.timer=QTimer(self);self.timer.timeout.connect(self.check_stale);self.timer.start(1000)
        if demo:
            self.seed_demo();self.demo_timer=QTimer(self);self.demo_timer.timeout.connect(self.demo_tick);self.demo_timer.start(1000)
            self.access.setEnabled(False);self.gpu.setEnabled(False)
            self.subtitle.setText('NVIDIA GeForce RTX 4080 · DEMO DATA')
        else:QTimer.singleShot(0,self.restart)
        if screenshot:
            QTimer.singleShot(800,lambda:self.grab().save(screenshot))
            QTimer.singleShot(950,QApplication.instance().quit)
        if self_test:QTimer.singleShot(700,self.run_self_test)

    def check_recording_duration(self):
        if self.record_file is None or self.record_deadline is None:return
        remaining=max(0,math.ceil(self.record_deadline-time.monotonic()))
        if remaining==0:
            self.stop_recording();self.record_status.setText('Recording saved · duration reached');return
        self.record_status.setText(f'Recording all GPUs · {remaining//3600:02d}:{remaining//60%60:02d}:{remaining%60:02d} remaining')
    def stop_recording(self):
        self.record_timer.stop();self.record_deadline=None;self.record_duration.setEnabled(self.replay_frames is None)
        if self.record_file is not None:
            self.record_file.close();self.record_file=None
        self.record_button.setText('● Record')
    def toggle_recording(self):
        if self.record_file is not None:
            self.stop_recording();self.record_status.setText('Recording saved');return
        path,_=QFileDialog.getSaveFileName(self,'Record all GPUs','gpu-recording.jsonl','GPU recording (*.jsonl)')
        if not path:return
        try:
            self.record_file=open(path,'w',encoding='utf-8')
            self.record_file.write(json.dumps({'format':'gputaskman-recording','version':1,'demo':self.demo})+'\n')
            self.record_file.flush()
        except OSError as error:
            self.stop_recording();QMessageBox.warning(self,'Recording failed',str(error));return
        self.record_duration.setEnabled(False)
        minutes=self.record_duration.value();self.record_deadline=time.monotonic()+minutes*60 if minutes else None
        if minutes:self.record_timer.start()
        self.record_button.setText('■ Stop recording');self.record_status.setText('Recording all GPUs · '+Path(path).name)
        self.check_recording_duration()
    def open_recording(self):
        path,_=QFileDialog.getOpenFileName(self,'Open recording','','GPU recording (*.jsonl)')
        if not path:return
        try:
            if Path(path).stat().st_size>256*1024*1024:raise ValueError('Recording exceeds the 256 MB playback limit.')
            with open(path,encoding='utf-8') as stream:
                header=json.loads(stream.readline())
                if header.get('format')!='gputaskman-recording' or header.get('version')!=1:raise ValueError('Unsupported recording format.')
                frames=[json.loads(line) for line in stream if line.strip()]
            previous=None
            for frame in frames:
                stamp=frame.get('taken')
                if not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or (previous is not None and stamp<previous):raise ValueError('Invalid recording timestamps.')
                if not isinstance(frame.get('gpus'),list) or not isinstance(frame.get('snapshots'),list):raise ValueError('Invalid GPU frame.')
                previous=stamp
            if not frames:raise ValueError('Recording contains no samples.')
        except (OSError,ValueError,TypeError,AttributeError) as error:
            QMessageBox.warning(self,'Cannot open recording',str(error));return
        self.stop_recording();self.stop_process()
        if self.demo:self.demo_timer.stop()
        self.replay_frames=frames;self.record_duration.setEnabled(False);self.record_button.setEnabled(False);self.rate.setEnabled(False);self.access.setEnabled(False)
        self.return_button.setEnabled(True);self.rewind_button.setEnabled(True);self.gpu.setEnabled(True)
        self.rewind_recording()
    def reset_session(self):
        self.clear_histories();self.device_inventory={};self.gpu_snapshots={};self.history_cache={};self.gpu_errors={};self.last_frame={}
        for card in self.fleet_cards.values():card.deleteLater()
        self.fleet_cards={};self.auto_fleet_selected=False
    def rewind_recording(self):
        if self.replay_frames is None:return
        self.replay_timer.stop();self.reset_session();self.replay_index=0;self.paused=False
        self.pause_button.setChecked(False);self.pause_button.setText('Ⅱ  Pause');self.replay_step()
    def replay_step(self):
        if self.replay_frames is None or self.paused:return
        if self.replay_index>=len(self.replay_frames):
            self.live.setText('■  Playback finished');return
        frame=self.replay_frames[self.replay_index];self.receive(frame);self.replay_index+=1
        self.access.setEnabled(False);self.live.setText('▶  Playback')
        self.record_status.setText(f'Playback {self.replay_index}/{len(self.replay_frames)} · '+datetime.datetime.fromtimestamp(frame['taken']).isoformat(sep=' ',timespec='seconds'))
        if self.replay_index<len(self.replay_frames):
            delay=(self.replay_frames[self.replay_index]['taken']-frame['taken'])/self.speed.currentData()
            self.replay_timer.start(max(1,min(2147483647,round(delay*1000))))
        else:self.live.setText('■  Playback finished')
    def return_live(self):
        if self.replay_frames is None:return
        self.replay_timer.stop();self.replay_frames=None;self.reset_session();self.paused=False
        self.pause_button.setChecked(False);self.pause_button.setText('Ⅱ  Pause')
        self.record_duration.setEnabled(True);self.record_button.setEnabled(True);self.rate.setEnabled(True);self.return_button.setEnabled(False);self.rewind_button.setEnabled(False);self.record_status.clear()
        if self.demo:self.demo_timer.start(1000)
        else:self.restart()

    def build_overview(self):
        page=QWidget();lay=QVBoxLayout(page);lay.setContentsMargins(0,0,0,0);lay.setSpacing(14)
        cards=QHBoxLayout();cards.setSpacing(12);self.cards={}
        for key,title,color in [('gpu','GPU activity','green'),('vram','GPU memory','purple'),('temperature','Temperature','amber'),('power','Board / device power','yellow')]:
            card=Metric(title,color);self.cards[key]=card;cards.addWidget(card)
        lay.addLayout(cards)
        self.main_plot=Plot('GPU activity + temperature','green');self.main_plot.overlay=True;self.main_plot.setMinimumHeight(245)
        self.main_plot.clicked=lambda:self.focus_metric(0);lay.addWidget(self.main_plot,3)
        row=QHBoxLayout();row.setSpacing(12)
        self.memory_plot=Plot('GPU memory','purple');self.memory_plot.clicked=lambda:self.focus_metric(1)
        self.ram_plot=Plot('System memory · OS-reported','purple')
        row.addWidget(self.memory_plot);row.addWidget(self.ram_plot);lay.addLayout(row,2)
        self.system_card=QFrame();self.system_card.setObjectName('Card');sysrow=QHBoxLayout(self.system_card);sysrow.setContentsMargins(15,12,15,12)
        self.cpu_label=label('CPU  n/a');self.ram_label=label('RAM  n/a');self.clock_label=label('GPU clock  n/a');self.backend_label=label('Backend  —','Muted')
        for w in [self.cpu_label,self.ram_label,self.clock_label,self.backend_label]:sysrow.addWidget(w,1)
        lay.addWidget(self.system_card)
        self.pages.addWidget(scroll(page))

    def build_performance(self):
        page=QWidget();lay=QVBoxLayout(page);lay.setContentsMargins(0,0,0,0)
        tools=QHBoxLayout();tools.addWidget(label('METRIC HISTORY','Eyebrow'));tools.addStretch()
        self.metric_choice=QComboBox();self.metric_choice.addItem('All metrics',-1)
        for i,m in enumerate(METRICS):self.metric_choice.addItem(m[0],i)
        self.metric_choice.currentIndexChanged.connect(self.metric_changed);tools.addWidget(self.metric_choice);lay.addLayout(tools)
        self.performance_stack=QStackedWidget();self.grid_widget=QWidget();grid=QGridLayout(self.grid_widget);grid.setContentsMargins(0,0,0,0);grid.setSpacing(12)
        self.plots=[]
        for i,(title,key,unit,maximum,color) in enumerate(METRICS):
            plot=Plot(title,color,maximum,unit);plot.clicked=lambda n=i:self.focus_metric(n);grid.addWidget(plot,i//2,i%2);self.plots.append(plot)
        self.performance_stack.addWidget(scroll(self.grid_widget))
        self.single_plot=Plot('GPU activity','green');self.single_plot.setMinimumHeight(350);self.performance_stack.addWidget(self.single_plot)
        lay.addWidget(self.performance_stack);self.pages.addWidget(page)

    def build_processes(self):
        page=QWidget();lay=QVBoxLayout(page);lay.setContentsMargins(0,0,0,0)
        tools=QHBoxLayout();tools.addWidget(label('GPU PROCESSES','Eyebrow'));tools.addStretch()
        self.search=QLineEdit();self.search.setPlaceholderText('Filter by process, PID, runtime…');self.search.setMaximumWidth(340);self.search.textChanged.connect(self.filter_rows);tools.addWidget(self.search)
        export=QPushButton('Export snapshot');export.clicked.connect(self.export);tools.addWidget(export);lay.addLayout(tools)
        self.table=QTableWidget(0,9);self.table.setHorizontalHeaderLabels(['PID','Process','Kind','GPU memory','GPU','Shared','RAM','CPU','Runtime'])
        self.table.setAlternatingRowColors(True);self.table.setShowGrid(False);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide();self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Interactive);self.table.setColumnWidth(1,220)
        self.table.horizontalHeader().setMinimumSectionSize(65);self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.process_selected)
        self.details=QTextBrowser();self.details.setMinimumHeight(150)
        split=QSplitter(Qt.Orientation.Vertical);split.addWidget(self.table);split.addWidget(self.details);split.setStretchFactor(0,3);split.setStretchFactor(1,1)
        lay.addWidget(split);self.pages.addWidget(page)

    def build_diagnostics(self):
        page=QWidget();lay=QVBoxLayout(page);lay.setContentsMargins(0,0,0,0)
        self.diagnostics=QTextBrowser();self.diagnostics.setOpenExternalLinks(True);lay.addWidget(self.diagnostics)
        self.pages.addWidget(page)

    def build_fleet(self):
        page=QWidget();lay=QVBoxLayout(page);lay.setContentsMargins(0,0,0,0)
        self.fleet_note=label('Independent readings for each physical GPU. No pooled or summed memory totals.','Muted')
        self.fleet_note.setWordWrap(True);tools=QHBoxLayout();tools.addWidget(self.fleet_note,1)
        export=QPushButton('Export all GPUs');export.clicked.connect(lambda:self.export(True));tools.addWidget(export);lay.addLayout(tools)
        holder=QWidget();self.fleet_grid=QGridLayout(holder);self.fleet_grid.setContentsMargins(0,0,0,0);self.fleet_grid.setSpacing(14)
        lay.addWidget(scroll(holder),1);self.pages.addWidget(page)
    def open_gpu(self,key):
        index=self.gpu.findData(key)
        if index>=0:self.gpu.setCurrentIndex(index);self.navigate(0)
    def refresh_fleet_cards(self):
        for row,identity in enumerate(self.device_inventory.values()):
            key=identity['id']
            if key not in self.fleet_cards:
                self.fleet_cards[key]=FleetCard(identity,self.open_gpu)
                self.fleet_grid.addWidget(self.fleet_cards[key],row//2,row%2)
            history=self.history_cache.get(key,{}).get('util_gpu',[])
            self.fleet_cards[key].refresh(identity,self.gpu_snapshots.get(key),self.gpu_errors.get(key),history)
        active=sum(bool(r.get('present',True)) for r in self.device_inventory.values())
        self.fleet_note.setText(f'{active} physical GPU(s) detected · independent per-device readings · UUID / PCI identity · no pooled memory totals')
    def navigate(self,index):
        self.pages.setCurrentIndex(index);self.heading.setText(['Overview','Performance','Processes','Diagnostics','All GPUs'][index])
        for i,button in enumerate(self.nav):button.setChecked(i==index)
        self.render_selected()
    def focus_metric(self,index):
        self.navigate(1);self.metric_choice.setCurrentIndex(index+1)
    def metric_changed(self):
        index=self.metric_choice.currentData()
        if index is None or index<0:self.performance_stack.setCurrentIndex(0);return
        title,key,unit,maximum,color=METRICS[index]
        self.single_plot.title=self.plots[index].title;self.single_plot.unit=self.plots[index].unit;self.single_plot.maximum=self.plots[index].maximum;self.single_plot.color=PALETTE[color]
        self.single_plot.values=deque(self.plots[index].values,maxlen=300);self.single_plot.update();self.performance_stack.setCurrentIndex(1)
    def gpu_changed(self):
        self.selected_gpu_id=self.gpu.currentData()
        self.render_selected()
    def rate_changed(self):
        if self.demo and hasattr(self,'demo_timer'):
            self.demo_timer.setInterval(int(1000*(self.rate.currentData() or 1)))
        self.sync_worker_settings()
    def sync_worker_settings(self):
        if self.proc is not None and self.proc.state()==QProcess.ProcessState.Running:
            self.proc.write(f"interval {self.rate.currentData() or 1}\n".encode('ascii'))
            if self.paused:self.proc.write(b'pause\n')
    def clear_histories(self):
        for p in [self.main_plot,self.memory_plot,self.ram_plot,*self.plots,self.single_plot]:p.clear()
        self.last=None;self.table.setRowCount(0);self.details.clear()
    def worker_command(self):
        if self.worker_override:return [str(Path(self.worker_override).resolve())]
        installed=Path('/opt/gputaskman-qt6/collector/gputaskman-collector')
        if installed.exists():return [str(installed)]
        dev=Path(__file__).with_name('worker.py')
        return [os.environ.get('GPUTASKMAN_WORKER_PYTHON',sys.executable),str(dev)]
    def stop_process(self):
        if self.proc is None:return
        process=self.proc;self.proc=None
        process.blockSignals(True)
        process.write(b'quit\n');process.closeWriteChannel()
        if not process.waitForFinished(1800):
            # For an elevated worker EOF still requests a clean exit; no broad root kill command.
            process.terminate();process.waitForFinished(500)
        process.deleteLater()
    def restart(self):
        if self.demo or self.replay_frames is not None:return
        self.stop_process();self.buffer=b'';self.last_received=0;self.worker_stderr='';self.pending_gap=True
        process=QProcess(self);self.proc=process
        process.readyReadStandardOutput.connect(self.read_worker)
        process.readyReadStandardError.connect(self.read_worker_stderr)
        process.finished.connect(self.worker_finished);process.errorOccurred.connect(self.worker_error)
        command=self.worker_command()+['--gpu',str(0),'--interval',str(self.rate.currentData() or 1)]
        if self.elevated and os.geteuid()!=0:
            # Policy matches this exact installed binary; arbitrary interpreters are not authorized.
            command=['/usr/bin/pkexec','--disable-internal-agent']+command
        process.started.connect(self.sync_worker_settings)
        process.setProgram(command[0]);process.setArguments(command[1:]);process.start()
        self.live.setText('●  Connecting');self.live.setStyleSheet('color:#ffb52e;')
    def read_worker_stderr(self):
        if self.proc is not None:
            self.worker_stderr=(getattr(self,'worker_stderr','')+bytes(self.proc.readAllStandardError()).decode(errors='replace'))[-6000:]
    def worker_error(self,error):
        self.notice.setText('Unable to start the collector. Check that the package is fully installed.');self.notice.show()
        self.live.setText('●  Collector unavailable')
    def worker_finished(self,code,status):
        if self.stopping:return
        if self.elevated and code in (126,127):
            self.elevated=False;self.update_access(False)
            self.notice.setText('Full access was not granted. Continuing with standard access.');self.notice.show()
            QTimer.singleShot(0,self.restart)
        else:
            self.live.setText('●  Disconnected');self.live.setStyleSheet('color:#ff6257;')
            self.notice.setText(f'Collector stopped (exit {code}). Press Ctrl+R to reconnect.');self.notice.setToolTip(getattr(self,'worker_stderr',''));self.notice.show()
    def read_worker(self):
        if self.proc is None:return
        self.buffer+=bytes(self.proc.readAllStandardOutput())
        if len(self.buffer)>16*1024*1024:
            self.buffer=b'';self.notice.setText('Collector message exceeded the size limit.');self.notice.show();return
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:message=json.loads(line)
            except (ValueError,UnicodeDecodeError):continue
            if self.paused:continue
            self.receive(message)
    def update_access(self,elevated):
        self.access.setText('Return to standard access' if elevated else 'Enable full access')
        self.access.setEnabled(os.geteuid()!=0 and not self.demo)
        self.access_note.setText('Privileged collector · window stays under your user' if elevated and os.geteuid()!=0 else
                                 'Root session' if os.geteuid()==0 else 'Standard access · window runs as your user')
    def toggle_access(self):
        if self.demo:return
        if not self.elevated and not Path('/opt/gputaskman-qt6/collector/gputaskman-collector').exists():
            QMessageBox.information(self,'Install the package','Full access is available after installing the DEB package.');return
        self.elevated=not self.elevated;self.restart()
    def pause(self,checked):
        self.paused=checked;self.pause_button.setText('▶  Resume' if checked else 'Ⅱ  Pause')
        if self.replay_frames is not None:
            if checked:self.replay_timer.stop()
            else:self.replay_step()
            return
        if self.proc:self.proc.write(b'pause\n' if checked else b'resume\n')
        self.live.setText('Ⅱ  Paused' if checked else '●  Live')
        if not checked:self.pending_gap=True
    def choice_label(self,identity):
        prefix=f"GPU {identity.get('index','?')}" if identity.get('present',True) else 'Offline'
        location=identity.get('pci_bus_id') or identity.get('uuid') or 'session identity'
        return prefix+' · '+gpu_display_name(identity.get('name'))+' · '+location
    def ingest_history(self,key,data,ts):
        cache=self.history_cache.setdefault(key,{m[1]:deque(maxlen=300) for m in METRICS})
        cache.setdefault('system_ram',deque(maxlen=300))
        cache.setdefault('vram_bytes',deque(maxlen=300))
        nv=data.get('device') or {};values=dict(nv)
        values['vram_pct']=percent(data.get('vram_used'),data.get('vram_total'))
        values['vram_bytes']=data.get('vram_used')
        if str(nv.get('source','')).startswith('AMD '):values['sm_clock']=nv.get('gfx_clock')
        ram=data.get('system',{}).get('ram',{})
        values['system_ram']=percent(ram.get('used'),ram.get('total'))
        for metric,history in cache.items():
            if self.pending_gap:history.append((ts-.001,None))
            history.append((ts,values.get(metric)))
    def receive(self,message):
        if self.record_file is not None:
            try:
                self.record_file.write(json.dumps(message,ensure_ascii=False,allow_nan=False)+'\n');self.record_file.flush()
            except (OSError,ValueError) as error:
                self.stop_recording();QMessageBox.warning(self,'Recording stopped',str(error))
        self.last_received=time.monotonic();self.last_frame=message
        raw_choices=message.get('gpus',[])
        choices=[{**item,'id':item.get('id') or f"legacy:{item['index']}",
                  'name':gpu_display_name(item['name'])} for item in raw_choices]
        incoming={item['id'] for item in choices}
        for key,identity in list(self.device_inventory.items()):
            if key not in incoming:
                choices.append({**identity,'present':False})
        self.device_inventory={item['id']:item for item in choices}
        current=self.gpu.currentData();current_ids=[self.gpu.itemData(i) for i in range(self.gpu.count())]
        labels=[self.choice_label(item) for item in choices]
        if choices and (current_ids!=[x['id'] for x in choices] or [self.gpu.itemText(i) for i in range(self.gpu.count())]!=labels):
            self.gpu.blockSignals(True);self.gpu.clear()
            for identity,text in zip(choices,labels):
                self.gpu.addItem(text,identity['id'])
                self.gpu.setItemData(self.gpu.count()-1,'UUID: '+str(identity.get('uuid') or 'not reported')+
                    '\nPCI: '+str(identity.get('pci_bus_id') or 'not reported')+
                    '\nSerial: '+str(identity.get('serial') or 'not reported')+
                    '\nNVML index: '+str(identity.get('nvml_index') if identity.get('nvml_index') is not None else 'not available'),Qt.ItemDataRole.ToolTipRole)
            index=self.gpu.findData(current);self.gpu.setCurrentIndex(max(0,index));self.gpu.blockSignals(False)
        self.selected_gpu_id=self.gpu.currentData()
        self.update_access(message.get('elevated',False))
        self.live.setText('●  Demo data' if self.demo else '●  Live');self.live.setStyleSheet('color:#39d353;')
        snapshots=message.get('snapshots')
        if snapshots is None:snapshots=[message['snapshot']] if message.get('snapshot') else []
        now=float(message.get('taken') or time.time())
        errors={entry['gpu_id']:entry['error'] for entry in message.get('errors',[])}
        seen=set()
        for data in snapshots:
            key=data.get('gpu_id')
            if key is None and len(raw_choices)==1:key=choices[0]['id']
            if key not in self.device_inventory:continue
            data={**data,'gpu_id':key,'gpu_identity':data.get('gpu_identity') or self.device_inventory[key]}
            self.gpu_snapshots[key]=data;seen.add(key)
            self.ingest_history(key,data,float(data.get('taken') or now))
        self.gpu_errors=errors
        for key,identity in self.device_inventory.items():
            if key not in seen:
                self.gpu_snapshots.pop(key,None)
                self.gpu_errors.setdefault(key,'Device is no longer detected.' if not identity.get('present',True) else message.get('error') or 'No readings for this GPU.')
                self.ingest_history(key,{'system':message.get('system',{})},now)
        self.pending_gap=False
        self.refresh_fleet_cards();self.render_selected()
        if not self.device_inventory and message.get('error'):
            self.notice.setText(message['error']);self.notice.show();self.subtitle.setText('No supported GPU detected');self.update_system(message.get('system',{}),now)
        if not self.auto_fleet_selected:
            if len(choices)>1:self.navigate(4)
            self.auto_fleet_selected=True
    def render_selected(self):
        key=self.gpu.currentData();identity=self.device_inventory.get(key)
        if identity is None:return
        data=self.gpu_snapshots.get(key)
        if data is None:
            data={'gpu_id':key,'gpu_identity':identity,'gpu':identity['name'],'device':{},'processes':[],
                  'counter_status':self.gpu_errors.get(key,'Device unavailable.'),'system':self.last_frame.get('system',{})}
        self.last=data;nv=data.get('device') or {};cache=self.history_cache.get(key,{})
        name=self.choice_label(identity)
        self.subtitle.setText(name+(' · DEMO DATA' if self.demo else ''));self.subtitle.setToolTip('UUID: '+str(identity.get('uuid') or 'not reported')+'\nSerial: '+str(identity.get('serial') or 'not reported'))
        # Device counter warnings are already displayed on each fleet card.
        status_keys=['process_status'] if self.pages.currentIndex()==4 else ['counter_status','process_status']
        notes=[data.get(k) for k in status_keys if data.get(k)]
        if self.gpu_errors.get(key) and self.gpu_errors[key] not in notes:notes.append(self.gpu_errors[key])
        if identity.get('identity_warning'):notes.append(identity['identity_warning'])
        if self.last_frame.get('discovery_error'):notes.append('Inventory refresh failed: '+self.last_frame['discovery_error'])
        self.notice.setVisible(bool(notes));self.notice.setText(' · '.join(notes));self.notice.setToolTip('\n\n'.join([*notes,data.get('memory_note') or '']))
        used,total=data.get('vram_used'),data.get('vram_total');estimated=bool(data.get('memory_note'))
        self.cards['gpu'].set(number(nv.get('util_gpu'),'%'),self.activity_label(data,nv))
        self.cards['vram'].set(memory(used),(f'/ {memory(total)}'+(' · client sum / estimated total' if estimated else ' · device memory')) if total else ('Capacity unavailable · visible-client sum' if estimated else 'Capacity unavailable · absolute usage'))
        self.cards['temperature'].set(number(nv.get('temp'),'°C'),nv.get('temp_kind') or 'Device temperature')
        self.cards['power'].set(number(nv.get('power_w'),'W'),nv.get('power_kind') or 'Device telemetry')
        for plot,metric in zip(self.plots,METRICS):
            plot.values=deque(cache.get(metric[1],[]),maxlen=300);plot.update()
        self.plots[0].title=self.activity_label(data,nv)
        absolute_memory=not total
        memory_history=cache.get('vram_bytes' if absolute_memory else 'vram_pct',[])
        title=('GPU memory · visible clients' if estimated else 'GPU memory · usage') if absolute_memory else ('GPU memory · estimated' if estimated else 'GPU memory')
        tooltip=(data.get('memory_note') or '')+(' Capacity unavailable: showing absolute usage, not a percentage. Scale follows the recorded usage, not device capacity.' if absolute_memory else ' Usage as a percentage of the reported capacity.')
        for plot in [self.plots[1],self.memory_plot]:
            plot.title=title;plot.unit='bytes' if absolute_memory else '%';plot.maximum=None if absolute_memory else 100
            plot.values=deque(memory_history,maxlen=300);plot.setToolTip(tooltip);plot.update()
        self.main_plot.values=deque(cache.get('util_gpu',[]),maxlen=300);self.main_plot.secondary=deque(cache.get('temp',[]),maxlen=300)
        self.ram_plot.values=deque(cache.get('system_ram',[]),maxlen=300)
        self.main_plot.title=self.activity_label(data,nv)+' + temperature'
        for plot in [self.main_plot,self.memory_plot,self.ram_plot]:plot.update()
        self.metric_changed()
        clock=nv.get('gfx_clock') if str(nv.get('source','')).startswith('AMD ') else nv.get('sm_clock')
        self.clock_label.setText('GPU clock  '+number(clock,'MHz'));self.backend_label.setText('Backend  '+str(data.get('backend','—')).upper())
        self.update_system(data.get('system',{}),time.time(),append=False)
        self.populate_processes(data.get('processes',[]));self.populate_diagnostics(data)
        self.statusBar().showMessage('Local monitoring · '+datetime.datetime.now().strftime('%H:%M:%S')+' · '+identity.get('identity_source','session identity')+' · n/a = unavailable')
    def activity_label(self,data,nv):
        if str(nv.get('source','')).startswith('AMD '):return 'AMD graphics-engine activity'
        if nv.get('source')=='Intel sysfs':return 'Intel GT activity'
        return 'GPU activity'
    def update_system(self,system,ts,append=True):
        ram=system.get('ram',{});cpu=system.get('cpu',{})
        self.cpu_label.setText('CPU  '+number(cpu.get('pct'),'%'))
        self.ram_label.setText('RAM  '+memory(ram.get('used'))+' / '+memory(ram.get('total')))
        if append:self.ram_plot.append(ts,percent(ram.get('used'),ram.get('total')))
    def populate_processes(self,rows):
        selected=self.table.currentRow();selected_key=None
        if selected>=0 and self.table.item(selected,0):selected_key=self.table.item(selected,0).data(Qt.ItemDataRole.UserRole)
        order=self.table.horizontalHeader().sortIndicatorSection();direction=self.table.horizontalHeader().sortIndicatorOrder()
        self.table.blockSignals(True);self.table.setSortingEnabled(False);self.table.setRowCount(len(rows));self.rows=rows
        for i,row in enumerate(rows):
            measured=row.get('vram_bytes');inferred=row.get('vram_inferred_bytes')
            value=measured if measured is not None else inferred
            size=memory(value)+(' * inferred' if measured is None and inferred is not None else '')
            cells=[NumericItem(str(row.get('pid','')),row.get('pid')),QTableWidgetItem(row.get('name','')),
                QTableWidgetItem(row.get('kind','')),NumericItem(size,value),NumericItem(number(row.get('gpu_pct'),'%'),row.get('gpu_pct')),
                NumericItem(memory(row.get('shared_bytes')),row.get('shared_bytes')),NumericItem(memory(row.get('ram_bytes')),row.get('ram_bytes')),
                NumericItem(number(row.get('cpu_pct'),'%'),row.get('cpu_pct')),QTableWidgetItem(' / '.join(row.get('runtimes',[])))]
            key=(row.get('host'),row.get('pid'),row.get('started_at'))
            for col,item in enumerate(cells):
                item.setData(Qt.ItemDataRole.UserRole,key)
                if col>=3 and col<8:item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i,col,item)
            if key==selected_key:self.table.selectRow(i)
        self.table.setSortingEnabled(True);self.table.sortItems(order,direction);self.table.blockSignals(False)
        self.filter_rows();self.process_selected()
    def filter_rows(self):
        term=self.search.text().casefold()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row,bool(term and term not in ' '.join(self.table.item(row,c).text() for c in range(self.table.columnCount())).casefold()))
    def process_selected(self):
        i=self.table.currentRow()
        if i<0 or not self.table.item(i,0):self.details.setHtml('<h3>Select a process</h3><p>Measured values, evidence and model details appear here.</p>');return
        key=self.table.item(i,0).data(Qt.ItemDataRole.UserRole)
        row=next((r for r in self.rows if (r.get('host'),r.get('pid'),r.get('started_at'))==key),{})
        def esc(value):return html.escape(str(value))
        inferred=row.get('vram_bytes') is None and row.get('vram_inferred_bytes') is not None
        vram=row.get('vram_bytes') if not inferred else row.get('vram_inferred_bytes')
        summary=[('PID',row.get('pid')),('Category',row.get('kind') or 'Unclassified'),
                 ('GPU memory',memory(vram)+(' · inferred' if inferred else '')),
                 ('GPU activity',number(row.get('gpu_pct'),'%')),
                 ('Shared GPU memory',memory(row.get('shared_bytes'))),('System RAM',memory(row.get('ram_bytes'))),
                 ('CPU',number(row.get('cpu_pct'),'%')),('Runtimes',', '.join(row.get('runtimes',[])) or 'Not identified')]
        text='<h3>'+esc(row.get('name','Process'))+'</h3><table cellspacing="5">'
        for name,value in summary:text+=f'<tr><td style="color:#95a6ad">{esc(name)}</td><td>{esc(value)}</td></tr>'
        text+='</table>'
        if inferred:text+='<p style="color:#ffb52e">Inferred memory is not a measured allocation. '+esc(row.get('vram_inferred_by') or '')+'</p>'
        if row.get('vram_unattributed_reason'):text+='<p>'+esc(row['vram_unattributed_reason'])+'</p>'
        llm=row.get('llm') or {}
        if llm.get('models'):
            text+='<h3>Model evidence (process-wide)</h3>'
            for model in llm['models']:
                text+='<p><b>'+esc(model.get('label') or model.get('name') or 'Model')+'</b><br>'
                text+=esc(' · '.join(str(model.get(k) or '') for k in ['arch','quant','kind_label']))+'</p>'
        files=row.get('model_files',[])
        if files:
            text+='<h3>Observed model files</h3>'
            for model in files:
                text+='<p>'+esc(model.get('store_name') or model.get('path') or '')+'<br><span style="color:#95a6ad">Evidence: '+esc(model.get('evidence') or 'unknown')+'</span></p>'
        if llm.get('segments'):
            text+='<h3>Runtime / estimated memory breakdown</h3><p>Model files and runtime logs can span GPUs. These sizes are not measured per-device model placement and do not independently prove current GPU residency.</p>'
            for part in llm['segments']:text+='<p>'+esc(part.get('label') or part.get('kind'))+': '+memory(part.get('bytes'))+'</p>'
        server=llm.get('server') or {}
        if any(server.get(k) is not None for k in ('requests_running','requests_waiting','kv_cache_usage')):
            text+='<h3>Runtime-reported server metrics</h3><p>Server engine scope; not per GPU, worker or measured VRAM.</p>'
            for key,title in [('requests_running','Running requests'),('requests_waiting','Waiting requests')]:
                text+='<p>'+title+': '+esc(number(server.get(key)))+'</p>'
            usage=server.get('kv_cache_usage')
            text+='<p>KV-cache pool usage: '+esc(number(usage*100 if usage is not None else None,'%'))+'</p>'
        for note in llm.get('notes',[]):text+='<p>'+esc(note)+'</p>'
        if row.get('installed_models'):text+='<p>Installed model candidates exist, but are not proven loaded.</p>'
        text+='<p style="color:#95a6ad">Unavailable values remain n/a. System RAM is separate from GPU memory.</p>'
        self.details.setHtml(text)
    def populate_diagnostics(self,data):
        nv=data.get('device') or {}
        identity=data.get('gpu_identity') or {}
        fields=[('GPU',gpu_display_name(data.get('gpu') or nv.get('name'))),('GPU UUID',identity.get('uuid')),('PCI bus address',identity.get('pci_bus_id')),('Board serial (if reported)',identity.get('serial')),('Identity source',identity.get('identity_source')),('Application GPU index',identity.get('index')),('NVML index (may differ)',identity.get('nvml_index')),('Collection cycle (ms)',self.last_frame.get('sample_ms')),('Backend',data.get('backend')),('Driver',data.get('driver')),('CUDA',data.get('cuda')),
                ('Telemetry source',nv.get('source')),('GPU memory note',data.get('memory_note')),('Counters',data.get('counter_status')),
                ('Process scan',data.get('process_status')),('WSL split',data.get('wsl_split')),('Throttle reasons',', '.join(nv.get('throttle') or []))]
        text='<h2>Device & measurement provenance</h2>'
        for title,value in fields:
            if value is not None and value!='':text+=f'<p><b>{html.escape(title)}</b><br>{html.escape(str(value))}</p>'
        text+='<h3>How to interpret the readings</h3><p>Unknown is n/a, never zero. Device telemetry, OS-reported system memory, inferred process memory and runtime-reported model evidence remain separate. Intel memory may be a sum of visible clients with a PCI-window estimate for capacity. It is not a device-wide measured total. AMD graphics-engine activity is not necessarily equivalent to NVIDIA utilization. Full access cannot create counters the driver does not expose.</p>'
        self.diagnostics.setHtml(text)
    def check_stale(self):
        if self.replay_frames is None and not self.demo and not self.paused and self.last_received and time.monotonic()-self.last_received>max(5,3*(self.rate.currentData() or 1)):
            self.live.setText('●  Waiting for readings');self.live.setStyleSheet('color:#ffb52e;')
    def export(self,all_gpus=False):
        if not self.last and not all_gpus:return
        path,_=QFileDialog.getSaveFileName(self,'Export current snapshot','gpu-fleet.json' if all_gpus else 'gpu-snapshot.json','JSON (*.json)')
        if path:
            try:Path(path).write_text(json.dumps(self.last_frame if all_gpus else self.last,indent=2,ensure_ascii=False),encoding='utf-8')
            except OSError as e:QMessageBox.warning(self,'Export failed',str(e))
    def help(self):
        dialog=QDialog(self);dialog.setWindowTitle('Help & licenses');dialog.resize(780,620);lay=QVBoxLayout(dialog);text=QTextBrowser();text.setOpenExternalLinks(True)
        text.setHtml('''<h1>GPU Task Manager · Qt 6</h1><p>A separate graphical frontend for gputaskman 0.4.3, with an original dark interface and independent GPU views.</p>
<h2>Navigation</h2><p><b>Overview</b>: key readings and histories. <b>Performance</b>: all metrics or a single full-width chart. <b>All GPUs</b>: independent per-device readings and identities, including offline devices. Click any chart to focus it. <b>Processes</b>: sortable GPU process list, search and inspection. <b>Diagnostics</b>: counter availability and provenance.</p>
<p><b>Space</b> pause/resume · <b>Ctrl+R</b> reconnect · <b>Ctrl+P</b> processes · <b>F1</b> help.</p>
<h2>Full access</h2><p>The window runs as your user. Startup asks Polkit for full access; use --standard-access to skip it. “Enable full access” also asks Polkit to start only the read-only collector as root. Cancelling keeps standard access. Root shells need no further authentication. No kernel security settings are modified.</p>
<h2>Multiple GPUs</h2><p>Cards are keyed by NVIDIA UUID when available, otherwise by verified PCI address. Serial numbers are supplemental only. Application GPU numbers can differ from NVML / nvidia-smi numbering. Switching GPUs preserves their separate histories and does not restart the collector or request another password. Discovery is refreshed every five seconds; unavailable cards remain marked offline. PCI-only identity follows the slot, not a replaceable physical card. Devices without stable identification are labeled session-only. Physical GPUs are monitored; MIG instances are not separately enumerated.</p><h2>Readings</h2><p>Charts show the trailing 120 seconds. Gaps mean no reading, not zero. Process GPU memory can be unavailable or inferred; inferred readings are marked. System RAM is OS-reported and is never added to GPU memory. Model evidence and estimates are retained in process details. Snapshot exports can contain local paths and model names.</p>
<h2>Licenses</h2><p>Application: MIT. Original collector: MIT, Copyright © 2026 Scott Hanselman. Qt/PySide6 essential libraries are bundled under LGPLv3; their notices, source access and replacement instructions are in /usr/share/doc/gputaskman-qt6/THIRD_PARTY.md. The full GUI source is installed in /usr/lib/gputaskman-qt6; collector sources and license texts are in /usr/share/doc/gputaskman-qt6.</p>''')
        lay.addWidget(text);close=QPushButton('Close');close.clicked.connect(dialog.accept);lay.addWidget(close);dialog.exec()
    def seed_demo(self):
        for i in range(120):self.receive(demo_fleet_message(time.time()-119+i,i,self.demo_gpus))
    def demo_tick(self):
        if not self.paused:self.receive(demo_fleet_message(time.time(),time.time()%1000,self.demo_gpus))
    def run_self_test(self):
        if not self.demo:
            attempts=getattr(self,'_live_test_attempts',0)
            if not self.last_received and attempts<50:
                self._live_test_attempts=attempts+1;QTimer.singleShot(200,self.run_self_test);return
            try:
                assert self.last_received and self.proc is not None and self.last_frame.get('protocol')==2
                assert self.last is not None or 'system' in self.last_frame
                assert 'DEMO' not in self.subtitle.text()
                for index in range(5):self.navigate(index)
                self.navigate(0)
                print('Qt live collector/navigation self-test: PASS',flush=True)
                QApplication.instance().exit(0)
            except Exception:
                import traceback;traceback.print_exc();QApplication.instance().exit(1)
            return
        try:
            assert self.last and self.table.rowCount()>0
            for i in range(5):self.navigate(i)
            assert len(self.fleet_cards)==self.demo_gpus
            self.search.setText('llama');assert any(not self.table.isRowHidden(i) for i in range(self.table.rowCount()))
            self.search.clear();self.table.sortItems(3,Qt.SortOrder.DescendingOrder);self.table.selectRow(0);self.process_selected()
            assert self.details.toPlainText()
            self.focus_metric(2);assert self.performance_stack.currentIndex()==1
            self.pause_button.click();assert self.paused
            self.pause_button.click();assert not self.paused
            self.navigate(0);print('Qt GUI self-test: PASS',flush=True);QApplication.instance().exit(0)
        except Exception:
            import traceback;traceback.print_exc();QApplication.instance().exit(1)
    def closeEvent(self,event):
        self.stop_recording();self.replay_timer.stop()
        self.stopping=True;self.stop_process()
        if not self.demo:self.settings.setValue('geometry',self.saveGeometry())
        super().closeEvent(event)

def demo_message(ts,index):
    load=34+14*math.sin(index/8)+4*math.sin(index*1.8);temp=56+5*math.sin(index/24)
    return {'elevated':False,'gpus':[{'index':0,'id':'uuid:GPU-DEMO-0000','uuid':'GPU-DEMO-0000','pci_bus_id':'0000:01:00.0','present':True,'name':'NVIDIA GeForce RTX 4080'}],'snapshot':{
        'taken':ts,'gpu':'NVIDIA GeForce RTX 4080','backend':'nvml','driver':'Demo','cuda':'Demo',
        'vram_total':16<<30,'vram_used':int((9.4+.2*math.sin(index/20))*(1<<30)),
        'device':{'name':'NVIDIA GeForce RTX 4080','source':'NVML','util_gpu':load,'temp':temp,
                  'power_w':120+load,'sm_clock':2280,'sm_clock_max':2505,'util_mem':22+5*math.sin(index/11),'enc':0,'dec':4+3*math.sin(index/9),'throttle':[]},
        'system':{'cpu':{'pct':11+5*math.sin(index/6)},'ram':{'total':32<<30,'used':int((12+.2*math.sin(index/17))*(1<<30))}},
        'processes':[{'pid':17412,'name':'llama-server','kind':'LLM','vram_bytes':8<<30,'vram_attributed':True,'gpu_pct':round(load,1),'ram_bytes':6<<30,'cpu_pct':8.4,'runtimes':['CUDA','ggml'],'started_at':1},
                     {'pid':2480,'name':'desktop-compositor','kind':'compositor','vram_bytes':240<<20,'vram_attributed':True,'gpu_pct':2.1,'ram_bytes':180<<20,'cpu_pct':1.2,'runtimes':['Vulkan'],'started_at':1},
                     {'pid':5132,'name':'web-browser','kind':'browser','vram_bytes':420<<20,'vram_attributed':True,'gpu_pct':3.6,'ram_bytes':1<<30,'cpu_pct':2.8,'runtimes':['Vulkan'],'started_at':1}]}}

def demo_fleet_message(ts,index,count=1):
    import copy
    choices=[];snapshots=[]
    for gpu in range(count):
        identity={'id':f'uuid:GPU-DEMO-{gpu:04d}','index':gpu,'name':'NVIDIA GeForce RTX 4080',
                  'uuid':f'GPU-DEMO-{gpu:04d}','pci_bus_id':f'{gpu//128:04x}:{(gpu%128)+1:02x}:00.0',
                  'serial':None,'nvml_index':gpu,'identity_source':'NVIDIA UUID + PCI','present':True}
        choices.append(identity)
        data=copy.deepcopy(demo_message(ts,index+gpu*9)['snapshot'])
        data['gpu_id']=identity['id'];data['gpu_identity']=identity
        snapshots.append(data)
    return {'protocol':2,'gpus':choices,'snapshots':snapshots,'snapshot':snapshots[0],
            'errors':[],'system':snapshots[0].get('system',{}),'taken':ts,'elevated':False}

def main():
    parser=argparse.ArgumentParser(description='GPU Task Manager, Qt 6 frontend')
    parser.add_argument('--version',action='version',version='GPU Task Manager Qt6 0.4.3 (upstream collector 0.4.3)')
    parser.add_argument('--demo',action='store_true',help='show clearly labeled synthetic readings')
    parser.add_argument('--standard-access',action='store_true',help='start without requesting administrator access')
    parser.add_argument('--demo-gpus',type=int,default=1,help='number of synthetic GPUs in demo mode')
    parser.add_argument('--worker',help=argparse.SUPPRESS)
    parser.add_argument('--screenshot',help=argparse.SUPPRESS)
    parser.add_argument('--self-test',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not 1<=args.demo_gpus<=64:parser.error("Demo GPU count must be between 1 and 64.")
    QApplication.setApplicationName('GPU Task Manager Qt6');QApplication.setOrganizationName('gputaskman')
    app=QApplication(sys.argv[:1]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    icon=Path('/usr/share/icons/hicolor/scalable/apps/gputaskman-qt6.svg')
    if not icon.exists():icon=Path(__file__).with_name('gputaskman-qt6.svg')
    app.setWindowIcon(QIcon(str(icon)))
    window=Window(args.demo,args.worker,args.screenshot,args.self_test,args.standard_access,args.demo_gpus);window.show()
    code=app.exec();window.stopping=True;window.stop_process();return code
if __name__=='__main__':sys.exit(main())
