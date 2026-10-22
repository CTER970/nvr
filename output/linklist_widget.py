# -*- coding: utf-8 -*-
"""链表日进度板 - Windows 桌面悬浮小组件（纯 WPF，无框架混用）
置顶无边框圆角小卡，贴屏幕右上角；可拖动；每 5 秒读 progress_state.json 自动刷新。

操作：
  隐藏    标题栏「—」：收缩成右上角小药丸（只剩 进度），不再占地方
  恢复    点一下小药丸
  菜单    右键小药丸或右键卡片：显示板子 / 退出
  退出    右键菜单 → 退出（或任务管理器结束 python.exe）
  重复启动 不会开第二个，只会把现有板子弹出来
"""
import os, sys, json, time, ctypes, traceback, faulthandler

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, "progress_state.json")
LOG = os.path.join(BASE, "widget_error.log")
SHOW_SIGNAL = os.path.join(BASE, "show_signal.file")

def log_err():
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
    except Exception:
        pass

try:
    _lf = open(LOG, "a", encoding="utf-8")
    faulthandler.enable(_lf)
except Exception:
    pass

# ---- 单实例：已在运行则通知其显示，然后自己退出 ----
ERROR_ALREADY_EXISTS = 183
_mutex = ctypes.windll.kernel32.CreateMutexW(None, 0, u"Local\\EdgeFusionLinklistWidget")
if ctypes.GetLastError() == ERROR_ALREADY_EXISTS:
    try:
        with open(SHOW_SIGNAL, "w") as f:
            f.write("show")
    except Exception:
        pass
    sys.exit(0)

try:
    import clr
    WPF_DIR = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\WPF"
    clr.AddReference(WPF_DIR + r"\PresentationFramework.dll")
    clr.AddReference(WPF_DIR + r"\PresentationCore.dll")
    clr.AddReference(WPF_DIR + r"\WindowsBase.dll")
    from System.Windows import (Window, Application, Thickness, HorizontalAlignment,
        SizeToContent, SystemParameters, WindowStyle, ResizeMode,
        GridLength, GridUnitType, FontWeights, TextWrapping, CornerRadius)
    from System.Windows.Controls import (Border, StackPanel, TextBlock, Grid,
        ColumnDefinition, Button, Orientation, ContextMenu, MenuItem)
    from System.Windows.Media import SolidColorBrush, Color, Brushes
    from System.Windows.Media.Effects import DropShadowEffect
    from System.Windows.Shapes import Rectangle
    from System.Windows.Threading import DispatcherTimer
    from System import TimeSpan, Double
    from System.Windows.Input import Cursors
    from System.Threading import Thread, ThreadStart, ApartmentState
except Exception:
    log_err(); sys.exit(1)

def C(r, g, b, a=255):
    return Color.FromArgb(a, r, g, b)

INK    = C(44, 44, 42)
SUB    = C(95, 94, 90)
GREEN  = C(15, 110, 86)
AMBER  = C(133, 79, 11)
RED    = C(153, 60, 29)
INDIGO = C(60, 52, 137)
TRACK  = C(229, 227, 218)
LINE   = C(238, 236, 229)
BORD   = C(211, 209, 199)
TONE = {"done": GREEN, "doing": AMBER, "todo": SUB, "debt": RED}
BAR_W = 232.0

def tb(text, size=11.5, color=None, bold=False, wrap=False):
    t = TextBlock()
    t.Text = text
    t.FontSize = float(size)
    t.Foreground = SolidColorBrush(color if color is not None else INK)
    if bold:
        t.FontWeight = FontWeights.Bold
    if wrap:
        t.TextWrapping = TextWrapping.Wrap
    return t

def make_row(task):
    g = Grid()
    cd0 = ColumnDefinition(); cd0.Width = GridLength(18, GridUnitType.Pixel)
    cd1 = ColumnDefinition(); cd1.Width = GridLength(1, GridUnitType.Star)
    cd2 = ColumnDefinition(); cd2.Width = GridLength(0, GridUnitType.Auto)
    g.ColumnDefinitions.Add(cd0); g.ColumnDefinitions.Add(cd1); g.ColumnDefinitions.Add(cd2)
    mark = tb(task.get("mark", "·"), 11, TONE.get(task.get("mt", "todo"), SUB), True)
    label = tb(task.get("label", ""), 11.5)
    label.Margin = Thickness(0, 0, 8, 0)
    note = tb(task.get("note", ""), 10, TONE.get(task.get("nt", "todo"), SUB))
    Grid.SetColumn(mark, 0); Grid.SetColumn(label, 1); Grid.SetColumn(note, 2)
    g.Children.Add(mark); g.Children.Add(label); g.Children.Add(note)
    g.Margin = Thickness(0, 3, 0, 0)
    return g

def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return {}, str(e)

def make_card(app, on_hide):
    """整卡内容"""
    data, err = load_state()
    sp = StackPanel()

    # ---- 标题 + 隐藏 ----
    hg = Grid()
    c1 = ColumnDefinition(); c1.Width = GridLength(1, GridUnitType.Star)
    c2 = ColumnDefinition(); c2.Width = GridLength(0, GridUnitType.Auto)
    hg.ColumnDefinitions.Add(c1); hg.ColumnDefinitions.Add(c2)
    hs = StackPanel()
    hs.Children.Add(tb(data.get("title", "链表日进度板"), 14, INK, True))
    hs.Children.Add(tb(data.get("sub", ""), 10.5, SUB))
    hide = Button()
    hide.Content = "—"
    hide.FontSize = float(11)
    hide.Background = Brushes.Transparent
    hide.BorderThickness = Thickness(0)
    hide.Foreground = SolidColorBrush(SUB)
    hide.Cursor = Cursors.Hand
    hide.Padding = Thickness(4, 0, 2, 0)
    hide.Click += on_hide
    Grid.SetColumn(hs, 0); Grid.SetColumn(hide, 1)
    hg.Children.Add(hs); hg.Children.Add(hide)
    sp.Children.Add(hg)

    # ---- 进度条 ----
    done = data.get("done", 0)
    total = max(1, data.get("total", 1))
    line = StackPanel()
    line.Orientation = Orientation.Horizontal
    p1 = tb("%d / %d" % (done, total), 15, GREEN, True)
    p2 = tb(" 关卡完成", 10.5, SUB); p2.Margin = Thickness(2, 4, 0, 0)
    line.Children.Add(p1); line.Children.Add(p2)
    line.Margin = Thickness(0, 10, 0, 0)
    sp.Children.Add(line)
    barg = Grid()
    track = Rectangle()
    track.Height = 7.0; track.RadiusX = 3.5; track.RadiusY = 3.5
    track.Width = BAR_W
    track.Fill = SolidColorBrush(TRACK)
    track.HorizontalAlignment = HorizontalAlignment.Left
    fill = Rectangle()
    fill.Height = 7.0; fill.RadiusX = 3.5; fill.RadiusY = 3.5
    fill.Width = BAR_W * min(1.0, done / float(total))
    fill.Fill = SolidColorBrush(GREEN)
    fill.HorizontalAlignment = HorizontalAlignment.Left
    barg.Children.Add(track); barg.Children.Add(fill)
    barg.Margin = Thickness(0, 5, 0, 0)
    sp.Children.Add(barg)

    # ---- 分组任务 ----
    for grp in data.get("groups", []):
        name = tb(grp.get("name", ""), 11, INDIGO, True)
        name.Margin = Thickness(0, 9, 0, 0)
        sp.Children.Add(name)
        for t in grp.get("tasks", []):
            sp.Children.Add(make_row(t))

    # ---- 底部备注 ----
    div = Rectangle()
    div.Height = 1.0
    div.Fill = SolidColorBrush(LINE)
    div.Margin = Thickness(0, 10, 0, 0)
    sp.Children.Add(div)
    for f in data.get("footers", []):
        ft = tb(f, 10, SUB, wrap=True)
        ft.Margin = Thickness(0, 5, 0, 0)
        sp.Children.Add(ft)

    # ---- 状态行 ----
    if err:
        st = "状态读取失败: " + err
    else:
        st = "实时刷新 · 每 5 秒 · " + time.strftime("%H:%M:%S") + " 更新"
    s = tb(st, 9.5, SUB)
    s.Margin = Thickness(0, 7, 0, 0)
    sp.Children.Add(s)
    return sp

def make_pill(app, on_show):
    """隐藏态小药丸：只剩进度数字，点击弹回"""
    data, _ = load_state()
    done = data.get("done", 0)
    total = max(1, data.get("total", 1))
    sp = StackPanel()
    sp.Orientation = Orientation.Horizontal
    dot = Rectangle()
    dot.Width = 8.0; dot.Height = 8.0
    dot.RadiusX = 4.0; dot.RadiusY = 4.0
    dot.Fill = SolidColorBrush(GREEN)
    dot.Margin = Thickness(0, 2, 7, 0)
    sp.Children.Add(dot)
    txt = tb("%d/%d ▴" % (done, total), 12, INK, True)
    sp.Children.Add(txt)
    tip = tb("  点一下展开", 9.5, SUB)
    sp.Children.Add(tip)
    return sp

def run_main():
    try:
        app = Application()
        win = Window()
        win.Title = "链表日进度板"
        win.WindowStyle = WindowStyle(0)  # None
        win.ResizeMode = ResizeMode.NoResize
        win.AllowsTransparency = True
        win.Background = Brushes.Transparent
        win.Topmost = True
        win.ShowInTaskbar = False
        wa = SystemParameters.WorkArea
        win.Left = wa.Right - 306.0
        win.Top = wa.Top + 28.0

        def frame(child, pad, corner):
            border = Border()
            border.Margin = Thickness(8)
            border.CornerRadius = CornerRadius(corner)
            border.Background = SolidColorBrush(C(255, 255, 255))
            border.BorderBrush = SolidColorBrush(BORD)
            border.BorderThickness = Thickness(1)
            border.Padding = pad
            eff = DropShadowEffect()
            eff.BlurRadius = 16.0
            eff.ShadowDepth = 2.0
            eff.Opacity = 0.26
            eff.Color = C(60, 55, 45)
            border.Effect = eff
            border.Child = child
            return border

        collapsed = [False]

        def show_card(s=None, e=None):
            collapsed[0] = False
            win.Width = 284.0
            win.SizeToContent = SizeToContent.Height
            win.Content = frame(make_card(app, hide_card),
                                Thickness(14, 12, 14, 12), 14)

        def hide_card(s=None, e=None):
            collapsed[0] = True
            win.Width = Double.NaN
            win.SizeToContent = SizeToContent.WidthAndHeight
            win.Content = frame(make_pill(app, show_card),
                                Thickness(12, 8, 12, 8), 12)

        def quit_app(s=None, e=None):
            app.Shutdown()

        # ---- 右键菜单：显示 / 退出 ----
        menu = ContextMenu()
        m_show = MenuItem()
        m_show.Header = "显示板子"
        m_show.Click += show_card
        m_quit = MenuItem()
        m_quit.Header = "退出"
        m_quit.Click += quit_app
        menu.Items.Add(m_show)
        menu.Items.Add(m_quit)
        win.ContextMenu = menu

        def refresh():
            if collapsed[0]:
                win.Content = frame(make_pill(app, show_card),
                                    Thickness(12, 8, 12, 8), 12)
            else:
                win.Content = frame(make_card(app, hide_card),
                                    Thickness(14, 12, 14, 12), 14)

        def on_down(s, e):
            try:
                win.DragMove()
            except Exception:
                pass
        win.MouseLeftButtonDown += on_down

        last = [None]
        def tick(s, e):
            try:
                if os.path.exists(SHOW_SIGNAL):
                    try:
                        os.remove(SHOW_SIGNAL)
                    except Exception:
                        pass
                    show_card()
                    return
                m = os.path.getmtime(STATE)
                if m != last[0]:
                    last[0] = m
                    refresh()
            except Exception:
                pass

        show_card()
        timer = DispatcherTimer()
        timer.Interval = TimeSpan.FromSeconds(5)
        timer.Tick += tick
        timer.Start()
        win.Show()
        app.Run()
    except Exception:
        log_err()

if __name__ == "__main__":
    t = Thread(ThreadStart(run_main))
    t.SetApartmentState(ApartmentState.STA)
    t.Start()
    t.Join()
