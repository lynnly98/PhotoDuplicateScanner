"""Small original line icons, drawn with Qt for crisp high-DPI rendering."""
import math
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPainterPath, QPolygonF

ASSETS = Path(__file__).resolve().parent / 'assets'


def pixmap(name, color='#334155', size=24):
    image=QPixmap(size,size)
    image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size/24,size/24)
    p.setPen(QPen(QColor(color),1.7,Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    def line(x,y,a,b):p.drawLine(QPointF(x,y),QPointF(a,b))
    def rect(x,y,w,h):p.drawRoundedRect(QRectF(x,y,w,h),2,2)
    def poly(points):p.drawPolyline(QPolygonF([QPointF(x,y) for x,y in points]))
    if name=='logo':
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#2563eb'))
        p.drawRoundedRect(QRectF(0,0,24,24),5,5)
        p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor('white'),1.35))
        p.save();p.translate(10,10);p.rotate(-12);rect(-5,-5,11,12)
        poly([(-3,4),(0,0),(3,3),(5,1)])
        p.drawEllipse(QRectF(-2.5,-3,1.5,1.5));p.restore()
        poly([(16,8),(20,9),(18,20),(8,18)])
    elif name=='scan':
        p.drawEllipse(QRectF(3,3,12,12));line(13.5,13.5,21,21)
    elif name=='duplicates':
        rect(8,3,13,14);poly([(5,7),(3,7),(3,21),(16,21),(16,19)])
    elif name=='photo':
        rect(3,3,18,18);poly([(4,17),(10,10),(14,15),(18,11),(21,14)])
        p.drawEllipse(QRectF(7,6,2.5,2.5))
    elif name=='history':
        p.drawEllipse(QRectF(3,3,18,18));poly([(12,6),(12,12),(16,14)])
    elif name=='settings':
        path=QPainterPath()
        for i in range(48):
            angle=math.pi*i/24
            radius=9.5 if i%6 in (1,2,3,4) else 7.7
            point=QPointF(12+radius*math.cos(angle),12+radius*math.sin(angle))
            path.moveTo(point) if i==0 else path.lineTo(point)
        path.closeSubpath();p.drawPath(path);p.drawEllipse(QRectF(8.5,8.5,7,7))
    elif name in ('folder','add','open'):
        poly([(3,7),(3,4),(9,4),(11,7),(21,7),(21,20),(3,20),(3,7)])
        line(3,9,21,9)
        if name=='add':line(12,12,12,17);line(9.5,14.5,14.5,14.5)
    elif name=='export':
        poly([(14,3),(5,3),(5,21),(19,21),(19,8),(14,3),(14,8),(19,8)])
        poly([(9,14),(12,17),(15,14)]);line(12,11,12,17)
    elif name=='recycle':
        line(3,6,21,6);poly([(9,6),(9,3),(15,3),(15,6)])
        poly([(5,6),(6,21),(18,21),(19,6)]);line(10,10,10,17);line(14,10,14,17)
    elif name=='refresh':
        p.drawArc(QRectF(4,4,16,16),40*16,290*16);poly([(20,3),(20,9),(14,9)])
    elif name=='globe':
        p.drawEllipse(QRectF(3,3,18,18));p.drawEllipse(QRectF(8,3,8,18))
        line(3,12,21,12)
    elif name=='play':poly([(8,4),(20,12),(8,20),(8,4)])
    elif name=='clear':line(6,6,18,18);line(18,6,6,18)
    elif name=='down':poly([(6,9),(12,15),(18,9)])
    elif name=='up':poly([(6,15),(12,9),(18,15)])
    p.end()
    return image


def icon(name, color='#334155', selected=None):
    result=QIcon()
    for size in (16,20,24,32,48):
        for state,c in ((QIcon.State.Off,color),(QIcon.State.On,selected or color)):
            image=pixmap(name,c,size*2);image.setDevicePixelRatio(2)
            result.addPixmap(image,QIcon.Mode.Normal,state)
            result.addPixmap(image,QIcon.Mode.Selected,state)
            disabled=pixmap(name,'#8290a6',size*2);disabled.setDevicePixelRatio(2)
            result.addPixmap(disabled,QIcon.Mode.Disabled,state)
    return result


def dropdown_style(theme):
    down=(ASSETS/f'chevron-down-{theme}.png').as_posix()
    up=(ASSETS/f'chevron-up-{theme}.png').as_posix()
    return '''
    QComboBox {border-radius:8px; padding:9px 36px 9px 12px;}
    QComboBox:hover, QComboBox:focus, QComboBox:on {border:1px solid #2563eb;}
    QComboBox::drop-down {subcontrol-origin:padding;subcontrol-position:top right;
        width:32px;border:0;background:transparent;}
    QComboBox::down-arrow {image:url("%s");width:16px;height:16px;}
    QComboBox::down-arrow:on {image:url("%s");}
    QComboBox::down-arrow:disabled {image:url("%s");}
    ''' % (down,up,(ASSETS/'chevron-down-disabled.png').as_posix())


def refresh_icons(window):
    dark=window.theme=='dark'
    color='#cbd5e1' if dark else '#475569'
    accent='#9bc5ff' if dark else '#2563eb'
    for button,name in zip(window.nav_buttons,('scan','duplicates','history','settings')):
        button.setIcon(icon(name,color,accent))
    for attr,name in (('add_button','add'),('folder_button','folder'),('export_button','export'),
                      ('history_button','refresh'),('refresh_button','refresh'),
                      ('open_button','open'),('play_button','play'),('clear_button','clear')):
        getattr(window,attr).setIcon(icon(name,color))
    window.recycle_button.setIcon(icon('recycle','#ffffff'))
    window.result_tabs.setTabIcon(0,icon('duplicates',color,'#ffffff'))
    window.result_tabs.setTabIcon(1,icon('play',color,'#ffffff'))


if __name__=='__main__':
    # Build-time assets; the installed app only reads these bundled files.
    from PySide6.QtWidgets import QApplication
    app=QApplication([])
    ASSETS.mkdir(exist_ok=True)
    for theme,color in (('light','#475569'),('dark','#e3eaf6'),('disabled','#8290a6')):
        for direction in ('down','up'):
            assert pixmap(direction,color,64).save(str(ASSETS/f'chevron-{direction}-{theme}.png'))
    from PIL import Image
    logo=pixmap('logo',size=256).toImage()
    logo.save(str(ASSETS/'app.png'))
    with Image.open(ASSETS/'app.png') as image:
        image.save(ASSETS/'app.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
