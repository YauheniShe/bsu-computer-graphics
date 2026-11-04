"""Окно лабораторной: сетка, шаги алгоритмов и замеры времени."""

from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from benchmark import measure
from raster import ALGORITHMS, bresenham_circle, nearest


ROOT = Path(__file__).resolve().parent
BG, PAPER, INK, MUTED = '#f3f4f8', '#ffffff', '#202637', '#657086'
BLUE, ORANGE, GRID = '#4263eb', '#c85620', '#e4e8f0'
LINE, CIRCLE, WU = 'Брезенхем — отрезок', 'Брезенхем — окружность', 'Ву — сглаживание'
PRESETS = {
    'Отрезок (0, 0) → (13, 8)': (None, (0, 0, 13, 8)),
    'Крутой наклон': (None, (-3, -6, 4, 12)),
    'Отрицательный наклон': (None, (-10, 7, 9, -5)),
    'Вертикальный отрезок': (None, (2, -8, 2, 9)),
    'Одна точка': (None, (3, -2, 3, -2)),
    'Окружность, R = 8': (CIRCLE, (0, 0, 8)),
    'Смещённая окружность': (CIRCLE, (-3, 2, 6)),
    'Сглаженный отрезок': (WU, (0, 0, 13, 8)),
}
DESCRIPTIONS = {
    'Пошаговый': 'Ведущая координата меняется на 1. Вторая считается по уравнению прямой и округляется.',
    'ЦДА': 'К вещественным x и y прибавляются dx/L и dy/L. В таблице показаны значения до округления.',
    LINE: 'd = 2b − a. При d ≥ 0 следующий шаг диагональный, иначе — вдоль ведущей оси.',
    CIRCLE: 'u, v — смещения от центра. d = 3 − 2R. Один шаг добавляет до восьми симметричных пикселей.',
    WU: 'f — дробная часть второй координаты. Два соседних пикселя получают веса 1−f и f; концы полные.',
}


def blend(alpha):
    color = (66, 99, 235)
    return '#' + ''.join(f'{round(255*(1-alpha)+channel*alpha):02x}' for channel in color)


def number(value):
    return f'{value:.4f}'.rstrip('0').rstrip('.') if isinstance(value, float) else str(value)


class RasterApp:
    def __init__(self, root):
        self.root = root
        root.title('Базовые растровые алгоритмы — лабораторная 3')
        root.geometry('1280x850')
        root.minsize(1120, 780)
        root.configure(bg=BG)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.poll_id = self.play_id = self.draw_id = None
        self.closed = False
        self.scale = 30.0
        self.ox, self.oy = 200.0, 500.0
        self.drag = None
        self.updating = False
        self.trace, self.pixels = [], []
        self.count = 0
        self.geometry = (0, 0, 13, 8)
        self.active_name = LINE
        self.bench_data = None
        self.algorithm = tk.StringVar(value=LINE)
        self.preset = tk.StringVar(value=next(iter(PRESETS)))
        self.status = tk.StringVar(value='')
        self.hover = tk.StringVar(value='Наведите курсор на сетку')
        self.zoom = tk.DoubleVar(value=self.scale)
        self.step_var = tk.DoubleVar(value=0)
        self.ideal = tk.BooleanVar(value=True)
        self.fields = {key: tk.StringVar(value=str(value)) for key, value in
                       zip(('x0', 'y0', 'x1', 'y1', 'cx', 'cy', 'radius'), (0, 0, 13, 8, 0, 0, 8))}
        self._build()
        self._load_saved_benchmark()
        self.rebuild()
        root.after(150, self.fit)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Return>', lambda event: self.rebuild())

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Arial', 11), background=BG, foreground=INK)
        style.configure('TButton', padding=(10, 6))
        style.configure('TNotebook.Tab', padding=(12, 7))
        style.configure('Treeview', rowheight=25, background=PAPER, fieldbackground=PAPER)
        style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#dbe4ff')], foreground=[('selected', INK)])
        top = ttk.Frame(self.root, padding=(18, 14, 18, 10))
        top.pack(fill='x')
        ttk.Label(top, text='Базовые растровые алгоритмы', font=('Arial', 22, 'bold')).pack(side='left')
        ttk.Button(top, text='Справка', command=self.help).pack(side='right')
        ttk.Label(top, text='Компьютерная графика · Лабораторная 3', foreground=MUTED).pack(side='right', padx=18)
        content = ttk.Frame(self.root, padding=(18, 0, 18, 4))
        content.pack(fill='both', expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, minsize=390)
        content.rowconfigure(0, weight=1)
        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        tools = ttk.Frame(left, padding=(0, 0, 0, 8))
        tools.grid(row=0, column=0, sticky='ew')
        ttk.Label(tools, text='Масштаб').pack(side='left')
        self.zoom_slider = ttk.Scale(tools, from_=0.2, to=80, variable=self.zoom, length=145,
                                     command=self.zoom_changed)
        self.zoom_slider.pack(side='left', padx=8)
        self.zoom_label = ttk.Label(tools, width=7)
        self.zoom_label.pack(side='left')
        ttk.Button(tools, text='Вписать', command=self.fit).pack(side='left', padx=8)
        ttk.Checkbutton(tools, text='Идеальная линия', variable=self.ideal, command=self.redraw).pack(side='right')
        self.canvas = tk.Canvas(left, bg=PAPER, highlightthickness=1, highlightbackground=GRID)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', lambda event: self.schedule_draw())
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-4>', lambda event: self.zoom_at(self.scale*1.12, event.x, event.y))
        self.canvas.bind('<Button-5>', lambda event: self.zoom_at(self.scale/1.12, event.x, event.y))
        self.canvas.bind('<ButtonPress-1>', lambda event: setattr(self, 'drag', (event.x, event.y, self.ox, self.oy)))
        self.canvas.bind('<B1-Motion>', self.pan)
        self.canvas.bind('<ButtonRelease-1>', lambda event: setattr(self, 'drag', None))
        self.canvas.bind('<Motion>', self.motion)
        ttk.Label(left, text='Колесо — масштаб · Перетаскивание — сдвиг · Целые координаты — центры клеток',
                  foreground=MUTED, font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=(7, 2))
        ttk.Label(left, textvariable=self.hover, foreground=MUTED, font=('Arial', 10)).grid(row=3, column=0, sticky='w')
        right = ttk.Frame(content, width=390)
        right.grid(row=0, column=1, sticky='nsew')
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(6, weight=1)
        ttk.Label(right, text='Алгоритм', font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky='w')
        combo = ttk.Combobox(right, textvariable=self.algorithm, values=list(ALGORITHMS), state='readonly')
        combo.grid(row=1, column=0, sticky='ew', pady=(5, 10))
        combo.bind('<<ComboboxSelected>>', lambda event: self.rebuild())
        inputs = ttk.Frame(right)
        inputs.grid(row=2, column=0, sticky='ew')
        self.line_fields = ttk.Frame(inputs)
        self.circle_fields = ttk.Frame(inputs)
        for frame, names in ((self.line_fields, ('x0', 'y0', 'x1', 'y1')),
                             (self.circle_fields, ('cx', 'cy', 'radius'))):
            for i, key in enumerate(names):
                ttk.Label(frame, text='R' if key == 'radius' else key).grid(row=0, column=i, sticky='w')
                entry = ttk.Entry(frame, textvariable=self.fields[key], width=7)
                entry.grid(row=1, column=i, sticky='ew', padx=(0, 8), pady=(3, 7))
                frame.columnconfigure(i, weight=1)
        controls = ttk.Frame(right)
        controls.grid(row=3, column=0, sticky='ew', pady=(0, 6))
        ttk.Button(controls, text='Построить', command=lambda: self.rebuild(fit=True)).pack(side='left')
        presets = ttk.Combobox(controls, textvariable=self.preset, values=list(PRESETS), state='readonly', width=24)
        presets.pack(side='right', fill='x', expand=True, padx=(8, 0))
        presets.bind('<<ComboboxSelected>>', self.load_preset)
        self.description = ttk.Label(right, wraplength=380, foreground=MUTED, font=('Arial', 10))
        self.description.grid(row=4, column=0, sticky='ew', pady=(0, 8))
        playback = ttk.Frame(right)
        playback.grid(row=5, column=0, sticky='ew', pady=(0, 8))
        for label, command in [('Начало', lambda: self.show_steps(1)), ('←', lambda: self.show_steps(self.count-1))]:
            ttk.Button(playback, text=label, width=6, command=command).pack(side='left', padx=(0, 4))
        self.play_button = ttk.Button(playback, text='Пуск', width=6, command=self.toggle_play)
        self.play_button.pack(side='left', padx=(0, 4))
        ttk.Button(playback, text='→', width=4, command=lambda: self.show_steps(self.count+1)).pack(side='left', padx=(0, 4))
        ttk.Button(playback, text='Всё', width=6, command=lambda: self.show_steps(len(self.trace))).pack(side='left')
        self.tabs = ttk.Notebook(right)
        self.tabs.grid(row=6, column=0, sticky='nsew')
        steps_tab, time_tab = ttk.Frame(self.tabs, padding=7), ttk.Frame(self.tabs, padding=7)
        self.tabs.add(steps_tab, text='Шаги')
        self.tabs.add(time_tab, text='Время')
        steps_tab.columnconfigure(0, weight=1)
        steps_tab.rowconfigure(2, weight=1)
        self.step_label = ttk.Label(steps_tab)
        self.step_label.grid(row=0, column=0, sticky='w')
        self.step_slider = ttk.Scale(steps_tab, from_=1, to=14, variable=self.step_var,
                                     command=lambda value: None if self.updating else self.show_steps(round(float(value))))
        self.step_slider.grid(row=1, column=0, sticky='ew', pady=(3, 6))
        self.table = ttk.Treeview(steps_tab, columns=('i', 'x', 'y', 'd'), show='headings', selectmode='browse')
        for key, title, width in [('i', 'i', 36), ('x', 'x', 80), ('y', 'y', 80), ('d', 'd / f', 95)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor='center', stretch=True)
        self.table.grid(row=2, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(steps_tab, orient='vertical', command=self.table.yview)
        scroll.grid(row=2, column=1, sticky='ns')
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind('<<TreeviewSelect>>', self.select_step)
        self.step_details = ttk.Label(steps_tab, wraplength=350, font=('Arial', 10))
        self.step_details.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 3))
        time_tab.columnconfigure(0, weight=1)
        time_tab.rowconfigure(1, weight=1)
        self.bench_note = ttk.Label(time_tab, text='Без отрисовки и таблицы шагов.\nМедиана 5 серий; время на один вызов.',
                                   wraplength=350, font=('Arial', 10), foreground=MUTED)
        self.bench_note.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        self.bench_table = ttk.Treeview(time_tab, columns=('method', 'size', 'us'), show='headings')
        for key, title, width in [('method', 'Алгоритм', 170), ('size', 'L / R', 50), ('us', 'мкс', 70)]:
            self.bench_table.heading(key, text=title)
            self.bench_table.column(key, width=width, stretch=True)
        self.bench_table.grid(row=1, column=0, sticky='nsew')
        bench_scroll = ttk.Scrollbar(time_tab, command=self.bench_table.yview)
        bench_scroll.grid(row=1, column=1, sticky='ns')
        self.bench_table.configure(yscrollcommand=bench_scroll.set)
        bench_buttons = ttk.Frame(time_tab)
        bench_buttons.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self.bench_button = ttk.Button(bench_buttons, text='Измерить заново', command=self.start_benchmark)
        self.bench_button.pack(side='left')
        ttk.Button(bench_buttons, text='Сохранить JSON', command=self.save_benchmark).pack(side='right')
        ttk.Label(self.root, textvariable=self.status, padding=(18, 8, 18, 10), foreground=MUTED).pack(fill='x')

    def rebuild(self, fit=False):
        circle = self.algorithm.get() == CIRCLE
        self.line_fields.pack_forget()
        self.circle_fields.pack_forget()
        (self.circle_fields if circle else self.line_fields).pack(fill='x')
        names = ('cx', 'cy', 'radius') if circle else ('x0', 'y0', 'x1', 'y1')
        try:
            values = tuple(int(self.fields[key].get().strip()) for key in names)
            if any(abs(value) > 1000 for value in values):
                raise ValueError('Координаты: от −1000 до 1000')
            if circle and not 0 <= values[2] <= 500:
                raise ValueError('Радиус: целое число от 0 до 500')
            trace = []
            pixels = ALGORITHMS[self.algorithm.get()](*values, trace=trace)
        except ValueError as error:
            self.status.set(f'Не построено: {error}. Исправьте поля и нажмите «Построить».')
            return False
        self.stop_play()
        self.geometry, self.active_name = values, self.algorithm.get()
        self.trace, self.pixels = trace, pixels
        self.description.configure(text=DESCRIPTIONS[self.active_name])
        self.updating = True
        self.table.delete(*self.table.get_children())
        self.table.heading('x', text='u' if circle else 'x')
        self.table.heading('y', text='v' if circle else 'y')
        for i, step in enumerate(trace):
            self.table.insert('', 'end', iid=str(i), values=(i, number(step.x), number(step.y),
                                                           '—' if step.value is None else number(step.value)))
        self.step_slider.configure(to=max(2, len(trace)))
        self.updating = False
        self.show_steps(len(trace))
        self.status.set(f'{self.active_name} · {len(pixels)} пикселей · {len(trace)} шагов. Оранжевый контур — текущий шаг.')
        if fit:
            self.fit()
        return True

    def load_preset(self, event=None):
        algorithm, values = PRESETS[self.preset.get()]
        if algorithm:
            self.algorithm.set(algorithm)
        elif self.algorithm.get() == CIRCLE:
            self.algorithm.set(LINE)
        names = ('cx', 'cy', 'radius') if algorithm == CIRCLE else ('x0', 'y0', 'x1', 'y1')
        for key, value in zip(names, values):
            self.fields[key].set(str(value))
        self.rebuild(fit=True)

    def show_steps(self, count):
        if not self.trace:
            return
        self.count = max(1, min(len(self.trace), count))
        self.updating = True
        self.step_var.set(self.count)
        self.table.selection_set(str(self.count-1))
        self.table.see(str(self.count-1))
        self.updating = False
        step = self.trace[self.count-1]
        self.step_label.configure(text=f'Шаг {self.count} из {len(self.trace)} · индекс i = {self.count-1}')
        details = ', '.join(f'({p.x}, {p.y})' + (f' α={p.alpha:.3f}' if p.alpha < 1 else '') for p in step.pixels)
        self.step_details.configure(text=f'{step.action}\nПиксели: {details}')
        self.redraw()

    def select_step(self, event=None):
        if not self.updating and self.table.selection():
            count = int(self.table.selection()[0])+1
            if count != self.count:
                self.stop_play()
                self.show_steps(count)

    def stop_play(self):
        if self.play_id:
            self.root.after_cancel(self.play_id)
            self.play_id = None
        self.play_button.configure(text='Пуск')

    def toggle_play(self):
        if self.play_id:
            self.stop_play()
            return
        if self.count == len(self.trace):
            self.show_steps(1)
        self.play_button.configure(text='Пауза')
        self.play_id = self.root.after(240, self.tick)

    def tick(self):
        self.play_id = None
        self.show_steps(self.count+1)
        if self.count < len(self.trace):
            self.play_id = self.root.after(240, self.tick)
        else:
            self.play_button.configure(text='Пуск')

    def screen(self, x, y):
        return self.ox + x*self.scale, self.oy - y*self.scale

    def world(self, sx, sy):
        return (sx-self.ox)/self.scale, (self.oy-sy)/self.scale

    def fit(self):
        if not self.pixels:
            return
        width, height = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        xs, ys = [0] + [p.x for p in self.pixels], [0] + [p.y for p in self.pixels]
        xmin, xmax, ymin, ymax = min(xs)-2, max(xs)+2, min(ys)-2, max(ys)+2
        self.scale = max(0.2, min(64, (width-35)/(xmax-xmin), (height-35)/(ymax-ymin)))
        self.ox = width/2 - (xmin+xmax)*self.scale/2
        self.oy = height/2 + (ymin+ymax)*self.scale/2
        self.zoom.set(self.scale)
        self.redraw()

    def zoom_at(self, scale, sx, sy):
        x, y = self.world(sx, sy)
        self.scale = max(0.2, min(80, scale))
        self.ox, self.oy = sx-x*self.scale, sy+y*self.scale
        self.zoom.set(self.scale)
        self.redraw()

    def zoom_changed(self, value):
        if hasattr(self, 'canvas'):
            self.zoom_at(float(value), self.canvas.winfo_width()/2, self.canvas.winfo_height()/2)

    def wheel(self, event):
        if event.delta:
            self.zoom_at(self.scale*(1.12 if event.delta > 0 else 1/1.12), event.x, event.y)

    def pan(self, event):
        if self.drag:
            x, y, ox, oy = self.drag
            self.ox, self.oy = ox+event.x-x, oy+event.y-y
            self.redraw()

    def motion(self, event):
        x, y = self.world(event.x, event.y)
        self.hover.set(f'Пиксель ({nearest(x)}, {nearest(y)}) · точка ({x:.2f}, {y:.2f})')

    def schedule_draw(self):
        if self.draw_id:
            self.root.after_cancel(self.draw_id)
        self.draw_id = self.root.after(30, self.redraw)

    def redraw(self):
        self.draw_id = None
        if self.closed or not hasattr(self, 'canvas'):
            return
        c, s = self.canvas, self.scale
        width, height = c.winfo_width(), c.winfo_height()
        c.delete('all')
        self.zoom_label.configure(text=f'{s:.1f} px' if s < 10 else f'{s:.0f} px')
        xmin, ymax = self.world(0, 0)
        xmax, ymin = self.world(width, height)
        current = self.trace[self.count-1].pixels if self.trace and self.count else ()
        for step in self.trace[:self.count]:
            for p in step.pixels:
                x, y = self.screen(p.x, p.y)
                if -s <= x <= width+s and -s <= y <= height+s:
                    c.create_rectangle(x-s/2, y-s/2, x+s/2, y+s/2, fill=blend(p.alpha), outline='', tags='pixel')
        grid_step = max(1, math.ceil(5/s))
        for x in range(math.floor((xmin-0.5)/grid_step)*grid_step, math.ceil(xmax+0.5), grid_step):
            sx, _ = self.screen(x+0.5, 0)
            c.create_line(sx, 0, sx, height, fill=GRID, tags='grid')
        for y in range(math.floor((ymin-0.5)/grid_step)*grid_step, math.ceil(ymax+0.5), grid_step):
            _, sy = self.screen(0, y+0.5)
            c.create_line(0, sy, width, sy, fill=GRID, tags='grid')
        if self.ideal.get():
            if self.active_name == CIRCLE:
                x, y, radius = self.geometry
                c.create_oval(*self.screen(x-radius, y+radius), *self.screen(x+radius, y-radius),
                              outline=ORANGE, width=1.5, dash=(5, 3), tags='ideal')
            else:
                c.create_line(*self.screen(*self.geometry[:2]), *self.screen(*self.geometry[2:]),
                              fill=ORANGE, width=1.5, dash=(5, 3), tags='ideal')
        # Оси проходят через центры пикселей, линии сетки — между ними.
        c.create_line(0, self.oy, width-5, self.oy, fill=INK, arrow='last', tags='axis')
        c.create_line(self.ox, height, self.ox, 5, fill=INK, arrow='last', tags='axis')
        tick_step = 1 if s >= 24 else (5 if s >= 8 else max(10, 10**math.ceil(math.log10(24/s))))
        label_y = max(18, min(height-15, self.oy+17))
        label_x = max(20, min(width-23, self.ox-10))
        for x in range(math.ceil(xmin/tick_step)*tick_step, math.floor(xmax/tick_step)*tick_step+1, tick_step):
            sx, _ = self.screen(x, 0)
            c.create_text(sx, label_y, text=str(x), font=('Arial', 9), fill=MUTED, tags='coordinate')
        for y in range(math.ceil(ymin/tick_step)*tick_step, math.floor(ymax/tick_step)*tick_step+1, tick_step):
            if y:
                _, sy = self.screen(0, y)
                c.create_text(label_x, sy, text=str(y), anchor='e', font=('Arial', 9), fill=MUTED, tags='coordinate')
        c.create_text(width-15, max(15, min(height-15, self.oy-14)), text='X', fill=INK, font=('Arial', 11, 'bold'))
        c.create_text(max(15, min(width-15, self.ox+15)), 14, text='Y', fill=INK, font=('Arial', 11, 'bold'))
        for p in current:
            x, y = self.screen(p.x, p.y)
            c.create_rectangle(x-s/2+1, y-s/2+1, x+s/2-1, y+s/2-1,
                               outline=ORANGE, width=2, tags='current')
            if s >= 16:
                c.create_oval(x-2, y-2, x+2, y+2, fill=ORANGE, outline='', tags='center')

    def _load_saved_benchmark(self):
        path = ROOT / 'benchmark_results.json'
        if path.exists():
            try:
                self.display_benchmark(json.loads(path.read_text(encoding='utf-8')))
            except (ValueError, KeyError, TypeError, OSError):
                self.bench_note.configure(text='Сохранённый замер не прочитан. Можно выполнить новый.')

    def display_benchmark(self, data):
        self.bench_table.delete(*self.bench_table.get_children())
        for row in data['rows']:
            short = row['algorithm'].replace('Брезенхем — ', 'Брез. ').replace('Ву — сглаживание', 'Ву')
            self.bench_table.insert('', 'end', values=(short, row['size'], f'{row["median_us"]:.2f}'))
        self.bench_note.configure(text=f'{data["cpu"]}, Python {data["python"]}\n'
                                  f'Медиана {data["repeats"]} серий без GUI; мкс/вызов. L — длина по ведущей оси, R — радиус.')
        self.bench_data = data

    def start_benchmark(self):
        if self.future is not None:
            return
        self.stop_play()
        self.bench_button.state(['disabled'])
        self.status.set('Измерение времени: несколько секунд, без отрисовки и записи шагов…')
        self.future = self.executor.submit(measure)
        self.poll_id = self.root.after(100, self.poll_benchmark)

    def poll_benchmark(self):
        self.poll_id = None
        if not self.future.done():
            self.poll_id = self.root.after(100, self.poll_benchmark)
            return
        try:
            self.display_benchmark(self.future.result())
            self.status.set('Замер завершён. Результат можно сохранить в JSON.')
        except Exception as error:
            self.status.set(f'Замер не выполнен: {error}')
        self.future = None
        self.bench_button.state(['!disabled'])

    def save_benchmark(self):
        if self.bench_data is None:
            self.status.set('Сначала выполните замер.')
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                                          initialfile='raster_times.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                Path(path).write_text(json.dumps(self.bench_data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                self.status.set(f'Сохранено: {path}')
            except OSError as error:
                messagebox.showerror('Не удалось сохранить', str(error), parent=self.root)

    def help(self):
        messagebox.showinfo('Как устроена сетка',
            'Целая координата (x, y) — центр пикселя. Его клетка занимает '
            '[x−0.5, x+0.5) × [y−0.5, y+0.5).\n\n'
            'Экран: X = ox + x·s, Y = oy − y·s. Поэтому математическая ось Y направлена вверх. '
            'Размер клетки s задаётся масштабом.\n\n'
            'Синий — найденные пиксели; насыщенность у Ву зависит от веса. '
            'Пунктир — идеальный отрезок или окружность. Оранжевая рамка отмечает текущий шаг.\n\n'
            'Выберите алгоритм, введите целые координаты и нажмите «Построить». '
            'Колесо меняет масштаб около курсора, перетаскивание сдвигает сетку. '
            'Строка таблицы показывает построение до выбранного шага.\n\n'
            'При малом масштабе часть линий сетки и подписей пропускается для читаемости.\n\n'
            'Допустимы координаты −1000…1000, радиус 0…500. '
            'Во вкладке «Время» измеряется генерация списка пикселей без графического интерфейса.', parent=self.root)

    def close(self):
        self.closed = True
        for timer in (self.play_id, self.poll_id, self.draw_id):
            if timer:
                self.root.after_cancel(timer)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = RasterApp(root)
    root.mainloop()
