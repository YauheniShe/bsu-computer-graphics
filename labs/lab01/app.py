"""Лабораторная №1, вариант 13. Запуск: python3 app.py."""

import tkinter as tk
from tkinter import ttk

from colors import CHANNELS, ColorState, hex_to_rgb, to_rgb


BG = "#F4F5F8"
PAPER = "#FFFFFF"
INK = "#202435"
MUTED = "#697386"
LINE = "#E2E5ED"
ACCENT = "#7256E8"
ERROR = "#B4233A"
FONT = "Helvetica Neue"
MONO = "Menlo"


def number(value):
    """Короткая подпись. Само состояние при этом не округляется."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


class ModelPanel(tk.Frame):
    """Поля, ползунки и двумерная палитра одной цветовой модели."""

    WIDTH, HEIGHT = 288, 120

    def __init__(self, parent, app, model, subtitle, index):
        super().__init__(parent, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        self.app, self.model = app, model
        self.variables, self.entries, self.scales = [], [], []
        self.updating = False
        self.palette_key = None
        self.palette_image = None
        self.axes = (0, 1)

        content = tk.Frame(self, bg=PAPER)
        content.pack(fill="both", expand=True, padx=18, pady=16)
        title_row = tk.Frame(content, bg=PAPER)
        title_row.pack(fill="x")
        tk.Label(title_row, text=model, font=(FONT, 23, "bold"), bg=PAPER, fg=INK).pack(side="left")
        tk.Label(title_row, text=f"0{index}", font=(MONO, 11), bg=PAPER, fg=MUTED).pack(side="right")
        tk.Label(content, text=subtitle, font=(FONT, 11), bg=PAPER, fg=MUTED, anchor="w").pack(fill="x", pady=(0, 10))

        self.canvas = tk.Canvas(content, width=self.WIDTH, height=self.HEIGHT,
                                bg=PAPER, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(anchor="center")
        self.image_item = self.canvas.create_image(0, 0, anchor="nw")
        self.cursor_outer = self.canvas.create_oval(0, 0, 0, 0, outline="#FFFFFF", width=3)
        self.cursor_inner = self.canvas.create_oval(0, 0, 0, 0, outline=INK, width=1)
        self.canvas.bind("<Button-1>", self.on_palette)
        self.canvas.bind("<B1-Motion>", self.on_palette)

        axes_row = tk.Frame(content, bg=PAPER)
        axes_row.pack(fill="x", pady=(8, 2))
        symbols = [channel[0] for channel in CHANNELS[model]]
        self.axis_vars = [tk.StringVar(value=symbols[0]), tk.StringVar(value=symbols[1])]
        for axis, caption in enumerate(("X →", "Y ↑")):
            tk.Label(axes_row, text=caption, bg=PAPER, fg=MUTED, font=(FONT, 10)).pack(side="left", padx=(0 if axis == 0 else 16, 5))
            selector = ttk.Combobox(axes_row, textvariable=self.axis_vars[axis], values=symbols,
                                    width=3, state="readonly", font=(MONO, 10))
            selector.pack(side="left")
            selector.bind("<<ComboboxSelected>>", lambda event, axis=axis: self.on_axis_change(axis))
        self.fixed_label = tk.Label(content, bg=PAPER, fg=MUTED, font=(FONT, 10), anchor="w")
        self.fixed_label.pack(fill="x", pady=(2, 8))

        for i, (symbol, name, maximum) in enumerate(CHANNELS[model]):
            row = tk.Frame(content, bg=PAPER)
            row.pack(fill="x", pady=(0, 2))
            tk.Label(row, text=f"{symbol}  {name}", bg=PAPER, fg=INK,
                     font=(FONT, 11)).pack(side="left")
            unit = "°" if model == "HLS" and i == 0 else "%" if model != "RGB" else ""
            tk.Label(row, text=unit, bg=PAPER, fg=MUTED, width=2, font=(FONT, 10)).pack(side="right")
            variable = tk.StringVar()
            entry = tk.Entry(row, textvariable=variable, width=8, justify="right", font=(MONO, 11),
                             bg=BG, fg=INK, insertbackground=INK, relief="flat", borderwidth=4,
                             highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)
            entry.pack(side="right")
            scale = ttk.Scale(content, from_=0, to=maximum,
                              command=lambda value, i=i: self.on_scale(i, value), takefocus=True)
            scale.pack(fill="x", pady=(0, 6))
            # Клавиатура работает с фиксированным понятным шагом.
            for key, sign in (("Left", -1), ("Down", -1), ("Right", 1), ("Up", 1)):
                scale.bind(f"<{key}>", lambda event, i=i, sign=sign: self.on_scale_key(i, sign))
            variable.trace_add("write", lambda *args, i=i: self.on_entry(i))
            entry.bind("<FocusOut>", lambda event, i=i: self.finish_entry(i))
            entry.bind("<Return>", lambda event, i=i: self.finish_entry(i))
            self.variables.append(variable)
            self.entries.append(entry)
            self.scales.append(scale)

        hint = "0–255 на канал" if model == "RGB" else "0–100% на канал" if model == "CMYK" else "H: 0–360° · L, S: 0–100%"
        self.range_hint = tk.Label(content, text=hint, bg=PAPER, fg=MUTED, font=(FONT, 10), anchor="w")
        self.range_hint.pack(side="bottom", fill="x", pady=(2, 0))

    def on_entry(self, index):
        if self.updating:
            return
        try:
            value = float(self.variables[index].get().replace(",", "."))
            self.app.state.set_component(self.model, index, value)
        except ValueError:
            maximum = CHANNELS[self.model][index][2]
            self.entries[index].configure(highlightbackground=ERROR, highlightcolor=ERROR)
            self.app.set_status(f"{self.model} · {CHANNELS[self.model][index][0]}: введите число от 0 до {maximum}.", error=True)
            return
        self.app.refresh(source=f"{self.model} · числовое поле", editing=(self.model, index))

    def finish_entry(self, index):
        self.updating = True
        self.variables[index].set(number(self.app.state.values[self.model][index]))
        self.updating = False
        self.entries[index].configure(highlightbackground=LINE, highlightcolor=ACCENT)
        self.app.set_status("Все модели синхронизированы. Значения на экране округлены до 2 знаков.")

    def on_scale(self, index, value):
        if self.updating:
            return
        self.app.state.set_component(self.model, index, float(value))
        self.app.refresh(source=f"{self.model} · ползунок")

    def on_scale_key(self, index, sign):
        maximum = CHANNELS[self.model][index][2]
        value = max(0, min(maximum, self.app.state.values[self.model][index] + sign))
        self.on_scale(index, value)
        return "break"

    def on_axis_change(self, changed_axis):
        symbols = [channel[0] for channel in CHANNELS[self.model]]
        new_axes = [symbols.index(var.get()) for var in self.axis_vars]
        if new_axes[0] == new_axes[1]:
            # При выборе занятой оси меняем оси местами.
            other = 1 - changed_axis
            new_axes[other] = self.axes[changed_axis]
            self.axis_vars[other].set(symbols[new_axes[other]])
        self.axes = tuple(new_axes)
        self.render_palette()

    def on_palette(self, event):
        x = max(0, min(1, event.x / (self.WIDTH - 1)))
        y = max(0, min(1, 1 - event.y / (self.HEIGHT - 1)))
        values = list(self.app.state.values[self.model])
        for axis, fraction in zip(self.axes, (x, y)):
            values[axis] = fraction * CHANNELS[self.model][axis][2]
        self.app.state.set_values(self.model, values)
        self.app.refresh(source=f"{self.model} · палитра")

    def sync(self, editing=None):
        self.updating = True
        try:
            for i, value in enumerate(self.app.state.values[self.model]):
                if editing != (self.model, i):
                    self.variables[i].set(number(value))
                self.scales[i].set(value)
                self.entries[i].configure(highlightbackground=LINE, highlightcolor=ACCENT)
        finally:
            self.updating = False
        self.move_cursor()

    def move_cursor(self):
        values = self.app.state.values[self.model]
        x_index, y_index = self.axes
        x = values[x_index] / CHANNELS[self.model][x_index][2] * (self.WIDTH - 1)
        y = (1 - values[y_index] / CHANNELS[self.model][y_index][2]) * (self.HEIGHT - 1)
        # Кольцо остаётся видимым и на границе палитры.
        x, y = max(5, min(self.WIDTH - 6, x)), max(5, min(self.HEIGHT - 6, y))
        self.canvas.coords(self.cursor_outer, x - 5, y - 5, x + 5, y + 5)
        self.canvas.coords(self.cursor_inner, x - 6, y - 6, x + 6, y + 6)

    def render_palette(self):
        values = self.app.state.values[self.model]
        fixed = tuple((i, v) for i, v in enumerate(values) if i not in self.axes)
        key = self.axes, fixed
        if key != self.palette_key:
            # Небольшой PPM-растр рисуется средствами Tk, Pillow не нужен.
            width, height = self.WIDTH // 2, self.HEIGHT // 2
            pixels = bytearray()
            x_index, y_index = self.axes
            components = list(values)
            x_max = CHANNELS[self.model][x_index][2]
            y_max = CHANNELS[self.model][y_index][2]
            for y in range(height):
                components[y_index] = (1 - y / (height - 1)) * y_max
                for x in range(width):
                    components[x_index] = x / (width - 1) * x_max
                    pixels.extend(max(0, min(255, round(v))) for v in to_rgb(self.model, components))
            ppm = f"P6\n{width} {height}\n255\n".encode() + pixels
            self.palette_image = tk.PhotoImage(data=ppm, format="PPM").zoom(2)
            self.canvas.itemconfigure(self.image_item, image=self.palette_image)
            self.palette_key = key
        fixed_text = " · ".join(f"{CHANNELS[self.model][i][0]} = {number(v)}" for i, v in fixed)
        self.fixed_label.configure(text=f"Фиксировано: {fixed_text}")
        self.move_cursor()


class ColorApp:
    def __init__(self, root):
        self.root = root
        self.state = ColorState()
        self.palette_job = None
        self.help_window = None
        root.title("Лаборатория цвета — БГУ · Вариант 13")
        root.configure(bg=BG)
        root.geometry("1140x850")
        root.minsize(1060, 850)
        root.option_add("*Font", (FONT, 11))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TScale", background=PAPER, troughcolor=LINE,
                        bordercolor=PAPER, lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure("TCombobox", padding=3, fieldbackground=BG, background=BG, foreground=INK)
        style.map("TCombobox", fieldbackground=[("readonly", BG)], selectbackground=[("readonly", BG)], selectforeground=[("readonly", INK)])
        style.configure("TButton", padding=(12, 8), background=PAPER, foreground=INK,
                        bordercolor=LINE, font=(FONT, 11))
        style.map("TButton", background=[("active", "#EDE9FA")])

        outer = tk.Frame(root, bg=BG)
        outer.pack(fill="both", expand=True, padx=26, pady=20)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        header = tk.Frame(outer, bg=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        heading = tk.Frame(header, bg=BG)
        heading.pack(side="left")
        tk.Label(heading, text="БГУ  /  КОМПЬЮТЕРНАЯ ГРАФИКА", bg=BG, fg=MUTED,
                 font=(FONT, 10), anchor="w").pack(fill="x")
        tk.Label(heading, text="Лаборатория цвета", bg=BG, fg=INK,
                 font=(FONT, 27, "bold"), anchor="w").pack(fill="x", pady=(4, 0))
        ttk.Button(header, text="Как это работает", command=self.show_help).pack(side="right", padx=(14, 0))
        tk.Label(header, text="ЛАБА 01\nВариант 13 · CMYK / RGB / HLS", bg=BG, fg=MUTED,
                 justify="right", font=(FONT, 10)).pack(side="right")

        preview = tk.Frame(outer, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        preview.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        self.swatch = tk.Canvas(preview, width=256, height=108, highlightthickness=0)
        self.swatch.pack(side="left", padx=10, pady=10)
        self.swatch_caption = self.swatch.create_text(20, 25, text="ТЕКУЩИЙ ЦВЕТ", anchor="w", font=(FONT, 10))
        self.swatch_hex = self.swatch.create_text(20, 64, text="", anchor="w", font=(MONO, 27, "bold"))
        self.swatch_note = self.swatch.create_text(20, 94, text="Один цвет · три представления", anchor="w", font=(FONT, 10))
        tools = tk.Frame(preview, bg=PAPER)
        tools.pack(side="left", fill="both", expand=True, padx=18, pady=14)
        upper = tk.Frame(tools, bg=PAPER)
        upper.pack(fill="x")
        tk.Label(upper, text="HEX", bg=PAPER, fg=MUTED, font=(MONO, 10)).pack(side="left", padx=(0, 10))
        self.hex_var = tk.StringVar()
        self.hex_entry = tk.Entry(upper, textvariable=self.hex_var, width=9, font=(MONO, 13),
                                 bg=BG, fg=INK, relief="flat", borderwidth=7,
                                 highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)
        self.hex_entry.pack(side="left", padx=(0, 8))
        self.hex_entry.bind("<Return>", lambda event: self.apply_hex())
        ttk.Button(upper, text="Применить", command=self.apply_hex).pack(side="left", padx=(0, 8))
        ttk.Button(upper, text="Копировать HEX", command=self.copy_hex).pack(side="left")
        presets = tk.Frame(tools, bg=PAPER)
        presets.pack(fill="x", pady=(14, 0))
        tk.Label(presets, text="Попробовать", bg=PAPER, fg=MUTED, font=(FONT, 10)).pack(side="left", padx=(0, 12))
        for color, name in (("#FF0000", "Красный"), ("#00FF00", "Зелёный"), ("#0000FF", "Синий"),
                            ("#00FFFF", "Голубой"), ("#FF00FF", "Пурпурный"), ("#FFFF00", "Жёлтый"),
                            ("#808080", "Серый"), ("#FFFFFF", "Белый"), ("#000000", "Чёрный")):
            button = tk.Canvas(presets, width=24, height=24, bg=color,
                               highlightthickness=1, highlightbackground=LINE, cursor="hand2", takefocus=True)
            button.pack(side="left", padx=(0, 7))
            button.bind("<Button-1>", lambda event, color=color: self.set_hex(color, "готовый образец"))
            button.bind("<Return>", lambda event, color=color: self.set_hex(color, "готовый образец"))
            button.bind("<space>", lambda event, color=color: self.set_hex(color, "готовый образец"))
            button.bind("<Enter>", lambda event, name=name: self.set_status(f"Готовый образец: {name}"))
            button.bind("<FocusIn>", lambda event, widget=button: widget.configure(highlightbackground=ACCENT, highlightthickness=2))
            button.bind("<FocusOut>", lambda event, widget=button: widget.configure(highlightbackground=LINE, highlightthickness=1))

        cards = tk.Frame(outer, bg=BG)
        cards.grid(row=2, column=0, sticky="nsew")
        self.panels = {}
        for column, (model, subtitle) in enumerate((
            ("CMYK", "Голубой · пурпурный · жёлтый · чёрный"),
            ("RGB", "Красный · зелёный · синий"),
            ("HLS", "Цветовой тон · светлота · насыщенность"),
        )):
            cards.columnconfigure(column, weight=1, uniform="models")
            panel = ModelPanel(cards, self, model, subtitle, column + 1)
            panel.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 7, 0 if column == 2 else 7))
            self.panels[model] = panel
        cards.rowconfigure(0, weight=1)

        footer = tk.Frame(outer, bg=BG)
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.status_label = tk.Label(footer, bg=BG, fg=MUTED, anchor="w", font=(FONT, 10))
        self.status_label.pack(side="left", fill="x", expand=True)
        tk.Label(footer, text="PYTHON + TKINTER", bg=BG, fg=MUTED, font=(MONO, 9)).pack(side="right")
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def set_status(self, text, error=False):
        self.status_label.configure(text=text, fg=ERROR if error else MUTED)

    def refresh(self, source=None, editing=None):
        color = self.state.hex
        self.hex_var.set(color)
        self.hex_entry.configure(highlightbackground=LINE, highlightcolor=ACCENT)
        self.swatch.configure(bg=color)
        r, g, b = self.state.values["RGB"]
        text_color = INK if (0.2126 * r + 0.7152 * g + 0.0722 * b) > 155 else PAPER
        self.swatch.itemconfigure(self.swatch_hex, text=color)
        for item in (self.swatch_caption, self.swatch_hex, self.swatch_note):
            self.swatch.itemconfigure(item, fill=text_color)
        for panel in self.panels.values():
            panel.sync(editing)
        # Сам цвет и поля обновляются сразу; растр палитр — не чаще чем раз в 24 мс.
        if self.palette_job is None:
            self.palette_job = self.root.after(24, self.render_palettes)
        prefix = f"Изменено: {source}. " if source else ""
        self.set_status(prefix + "Поля, ползунки и палитры связаны. Дробные значения допустимы.")

    def render_palettes(self):
        self.palette_job = None
        for panel in self.panels.values():
            panel.render_palette()

    def set_hex(self, value, source="HEX"):
        try:
            self.state.set_values("RGB", hex_to_rgb(value))
        except ValueError as error:
            self.hex_entry.configure(highlightbackground=ERROR, highlightcolor=ERROR)
            self.set_status(str(error), error=True)
            return False
        self.refresh(source)
        return True

    def apply_hex(self):
        return self.set_hex(self.hex_var.get())

    def copy_hex(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.state.hex)
        self.set_status(f"{self.state.hex} скопирован в буфер обмена.")

    def show_help(self):
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.lift()
            return
        window = tk.Toplevel(self.root)
        self.help_window = window
        window.title("Как устроена лаборатория цвета")
        window.geometry("680x580")
        window.configure(bg=PAPER)
        tk.Label(window, text="Один цвет, три языка", font=(FONT, 23, "bold"),
                 bg=PAPER, fg=INK).pack(anchor="w", padx=26, pady=(24, 12))
        text = tk.Text(window, wrap="word", relief="flat", bg=PAPER, fg=INK,
                       font=(FONT, 13), padx=26, pady=10, spacing3=12)
        text.pack(fill="both", expand=True)
        text.insert("1.0", """КАК МЕНЯТЬ ЦВЕТ
В любой панели введите число, передвиньте ползунок или нажмите на палитру. Две другие модели обновятся автоматически. Поля принимают точку или запятую; неверный ввод подсвечивается и не меняет цвет.

КАК ЧИТАТЬ ПАЛИТРУ
X увеличивается слева направо, Y — снизу вверх. В выпадающих списках можно выбрать любые две компоненты. Остальные фиксированы и подписаны под палитрой: меняйте их полями или ползунками.

ЧТО ЗНАЧАТ МОДЕЛИ
RGB — сложение красного, зелёного и синего света. Нули дают чёрный, максимумы — белый.
CMYK — доли голубой, пурпурной, жёлтой и чёрной красок. Здесь используется учебная формула, без цветового профиля принтера.
HLS — тон H по цветовому кругу, светлота L и насыщенность S. При L=0% получается чёрный, при L=100% — белый; при S=0% — серый. HLS и HSL описывают одну модель с разным порядком компонентов. HSV — другая модель.

ТОЧНОСТЬ
Вычисления используют float; только подписи округлены до двух знаков, а HEX и экран — до 8 бит на канал. Введённые CMYK сохраняются: один RGB может соответствовать нескольким сочетаниям красок. Подробнее о формулах — в THEORY.md.
""")
        text.configure(state="disabled")
        ttk.Button(window, text="Понятно", command=window.destroy).pack(anchor="e", padx=26, pady=18)

    def close(self):
        if self.palette_job is not None:
            self.root.after_cancel(self.palette_job)
            self.palette_job = None
        self.root.destroy()


def main():
    root = tk.Tk()
    ColorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
