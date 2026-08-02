"""Theme pyqtgraph surfaces with the same semantic desktop palette."""

import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtWidgets import QWidget


def apply_plot_theme(root: QWidget, theme: str) -> None:
    background = "#111820" if theme == "dark" else "#ffffff"
    foreground = "#aebfca" if theme == "dark" else "#475569"
    for plot in root.findChildren(pg.PlotWidget):
        plot.setBackground(background)
        plot.showGrid(x=True, y=True, alpha=0.16)
        item = plot.getPlotItem()
        for axis_name in ("left", "bottom"):
            axis = item.getAxis(axis_name)
            axis.setPen(pg.mkPen(foreground))
            axis.setTextPen(pg.mkPen(foreground))
        if item.legend is not None:
            item.legend.setLabelTextColor(foreground)
