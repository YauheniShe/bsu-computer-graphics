"""Окно лабораторной: сетка, ввод данных и шаги отсечения."""

import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from clipping import SIDES, clip_polygon, cohen_sutherland, parse_polygons, parse_segments


ROOT = Path(__file__).resolve().parent
BG, PAPER, INK, MUTED = '#f3f4f8', '#ffffff', '#202637', '#657086'
BLUE, ORANGE, GRID = '#4263eb', '#c85620', '#e4e8f0'
GREEN, PALE_GREEN, PURPLE = '#178151', '#e8f5ee', '#7950b2'
LINES, POLYGON = 'Сазерленд — Коэн', 'Сазерленд — Ходжман'
PRESETS = {
    LINES: {'Пересечения с окном': 'segments.txt', 'На границе и вне окна': 'segments_boundary.txt'},
    POLYGON: {'Прямоугольное окно': 'polygon.txt', 'Наклонное окно': 'polygon_slanted.txt',
              'Касание в точке': 'polygon_touch.txt'},
}
DESCRIPTIONS = {
    LINES: 'Число отрезков, затем по строке x₁ y₁ x₂ y₂. Последняя строка — xmin ymin xmax ymax.',
    POLYGON: 'Число вершин и строки x y исходного контура, затем число вершин и строки x y окна.',
}


def point_text(point):
    return '(' + ', '.join(f'{float(value):.10g}' for value in point) + ')'


class ClippingApp:
    def __init__(self, root):
        self.root = root
        root.title('Алгоритмы отсечения — лабораторная 4')
        root.geometry('1280x850')
        root.minsize(1120, 780)
        root.configure(bg=BG)
        self.algorithm = tk.StringVar(value=LINES)
        self.preset = tk.StringVar()
        self.object_name = tk.StringVar()
        self.status = tk.StringVar()
        self.hover = tk.StringVar(value='Наведите курсор на сетку')
        self.source_visible = tk.BooleanVar(value=True)
        self.scale, self.ox, self.oy = 30.0, 300.0, 300.0
        self.zoom = tk.DoubleVar(value=self.scale)
        self.drag = None
        self.draw_id = self.fit_id = self.play_id = None
        self.data_text, self.valid_text = {}, {}
        self.editor_name = self.active_name = LINES
        self.geometry = self.window = self.result = self.traces = ()
        self.steps = ()
        self.step_index = None
        self._build()
        self.load_preset(fit=False)
        self.fit_id = root.after(150, self.fit)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-Return>', lambda event: self.rebuild(fit=True))

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Arial', 11), background=BG, foreground=INK)
        style.configure('TButton', padding=(10, 6))
        style.configure('Treeview', rowheight=25, background=PAPER, fieldbackground=PAPER)
        style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#dbe4ff')], foreground=[('selected', INK)])

        top = ttk.Frame(self.root, padding=(18, 14, 18, 10))
        top.pack(fill='x')
        ttk.Label(top, text='Алгоритмы отсечения', font=('Arial', 22, 'bold')).pack(side='left')
        ttk.Button(top, text='Справка', command=self.help).pack(side='right')
        ttk.Label(top, text='Компьютерная графика · Лабораторная 4', foreground=MUTED).pack(side='right', padx=18)

        content = ttk.Frame(self.root, padding=(18, 0, 18, 4))
        content.pack(fill='both', expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, minsize=390)
        content.rowconfigure(0, weight=1)
        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        self._build_plot(left)

        right = ttk.Frame(content, width=390)
        right.grid(row=0, column=1, sticky='nsew')
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(8, weight=1)
        self._build_controls(right)
        ttk.Label(self.root, textvariable=self.status, padding=(18, 8, 18, 10), foreground=MUTED,
                  wraplength=1040).pack(fill='x')

    def _build_plot(self, left):
        tools = ttk.Frame(left, padding=(0, 0, 0, 8))
        tools.grid(row=0, column=0, sticky='ew')
        ttk.Label(tools, text='Масштаб').pack(side='left')
        ttk.Scale(tools, from_=0.1, to=80, variable=self.zoom, length=145,
                  command=self.zoom_changed).pack(side='left', padx=8)
        self.zoom_label = ttk.Label(tools, width=8)
        self.zoom_label.pack(side='left')
        ttk.Button(tools, text='Вписать', command=self.fit).pack(side='left', padx=8)
        ttk.Checkbutton(tools, text='Исходные фигуры', variable=self.source_visible,
                        command=self.redraw).pack(side='right')
        self.canvas = tk.Canvas(left, bg=PAPER, highlightthickness=1, highlightbackground=GRID)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', self.schedule_draw)
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-4>', lambda event: self.zoom_at(self.scale * 1.12, event.x, event.y))
        self.canvas.bind('<Button-5>', lambda event: self.zoom_at(self.scale / 1.12, event.x, event.y))
        self.canvas.bind('<ButtonPress-1>', lambda event: setattr(self, 'drag', (event.x, event.y, self.ox, self.oy)))
        self.canvas.bind('<B1-Motion>', self.pan)
        self.canvas.bind('<ButtonRelease-1>', lambda event: setattr(self, 'drag', None))
        self.canvas.bind('<Motion>', self.motion)
        legend = ttk.Frame(left)
        legend.grid(row=2, column=0, sticky='w', pady=(7, 2))
        for text, color in (('Окно', ORANGE), ('Исходные фигуры', BLUE), ('Видимая часть', GREEN)):
            ttk.Label(legend, text=f'━ {text}', foreground=color, font=('Arial', 10)).pack(side='left', padx=(0, 15))
        ttk.Label(left, textvariable=self.hover, foreground=MUTED,
                  font=('Arial', 10)).grid(row=3, column=0, sticky='w')

    def _build_controls(self, right):
        ttk.Label(right, text='Алгоритм', font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky='w')
        combo = ttk.Combobox(right, textvariable=self.algorithm, values=list(PRESETS), state='readonly')
        combo.grid(row=1, column=0, sticky='ew', pady=(5, 10))
        combo.bind('<<ComboboxSelected>>', self.change_algorithm)

        ttk.Label(right, text='Исходные данные', font=('Arial', 12, 'bold')).grid(row=2, column=0, sticky='w')
        self.description = ttk.Label(right, wraplength=380, foreground=MUTED, font=('Arial', 10))
        self.description.grid(row=3, column=0, sticky='ew', pady=(3, 5))
        editor = ttk.Frame(right)
        editor.grid(row=4, column=0, sticky='ew')
        self.input = tk.Text(editor, height=11, width=1, wrap='none', font='TkFixedFont',
                             bg=PAPER, fg=INK, insertbackground=INK, highlightthickness=1,
                             highlightbackground=GRID, highlightcolor=BLUE, padx=7, pady=5, undo=True)
        self.input.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(editor, command=self.input.yview)
        scroll.pack(side='right', fill='y')
        self.input.configure(yscrollcommand=scroll.set)

        controls = ttk.Frame(right)
        controls.grid(row=5, column=0, sticky='ew', pady=(6, 10))
        ttk.Button(controls, text='Отсечь', width=7, command=lambda: self.rebuild(fit=True)).pack(side='left')
        ttk.Button(controls, text='Открыть…', width=10, command=self.open_file).pack(side='left', padx=5)
        self.presets = ttk.Combobox(controls, textvariable=self.preset, state='readonly', width=16)
        self.presets.pack(side='right', fill='x', expand=True)
        self.presets.bind('<<ComboboxSelected>>', self.load_preset)

        steps = ttk.Frame(right)
        steps.grid(row=6, column=0, sticky='ew', pady=(0, 6))
        ttk.Label(steps, text='Шаги', font=('Arial', 12, 'bold')).pack(side='left')
        self.objects = ttk.Combobox(steps, textvariable=self.object_name, state='readonly', width=18)
        self.objects.pack(side='right')
        self.objects.bind('<<ComboboxSelected>>', self.select_object)

        playback = ttk.Frame(right)
        playback.grid(row=7, column=0, sticky='ew', pady=(0, 6))
        ttk.Button(playback, text='Начало', width=6, command=lambda: self.show_step(0)).pack(side='left', padx=(0, 4))
        ttk.Button(playback, text='←', width=4, command=lambda: self.move_step(-1)).pack(side='left', padx=(0, 4))
        self.play_button = ttk.Button(playback, text='Пуск', width=6, command=self.toggle_play)
        self.play_button.pack(side='left', padx=(0, 4))
        ttk.Button(playback, text='→', width=4, command=lambda: self.move_step(1)).pack(side='left', padx=(0, 4))
        ttk.Button(playback, text='Всё', width=6, command=self.show_all).pack(side='left')

        table_frame = ttk.Frame(right)
        table_frame.grid(row=8, column=0, sticky='nsew')
        self.table = ttk.Treeview(table_frame, columns=('step', 'check', 'result'), show='headings', selectmode='browse')
        for key, title, width in (('step', 'Шаг', 48), ('check', 'Проверка', 145), ('result', 'Действие', 150)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=width, anchor='center', stretch=key != 'step')
        self.table.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(table_frame, command=self.table.yview)
        scroll.pack(side='right', fill='y')
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind('<<TreeviewSelect>>', self.select_step)
        self.details = ttk.Label(right, wraplength=380, foreground=MUTED, font=('Arial', 10))
        self.details.grid(row=9, column=0, sticky='ew', pady=(6, 2))

    def set_input(self, text):
        self.input.delete('1.0', 'end')
        self.input.insert('1.0', text.rstrip('\n'))
        self.input.edit_reset()

    def change_algorithm(self, event=None):
        self.data_text[self.editor_name] = self.input.get('1.0', 'end-1c'), self.preset.get()
        name = self.editor_name = self.algorithm.get()
        self.presets.configure(values=list(PRESETS[name]))
        if name in self.data_text:
            text, preset = self.data_text[name]
            self.preset.set(preset)
            self.set_input(text)
            if not self.rebuild(fit=True):
                error = self.status.get()
                self.rebuild(self.valid_text[name], fit=True)
                self.status.set(error)
                self.input.focus_set()
        else:
            self.preset.set('')
            self.load_preset()

    def load_preset(self, event=None, fit=True):
        name = self.algorithm.get()
        presets = PRESETS[name]
        self.presets.configure(values=list(presets))
        if self.preset.get() not in presets:
            self.preset.set(next(iter(presets)))
        self.set_input((ROOT / 'samples' / presets[self.preset.get()]).read_text(encoding='utf-8'))
        self.rebuild(fit=fit)

    def open_file(self):
        path = filedialog.askopenfilename(parent=self.root, title='Открыть исходные данные',
                                          filetypes=[('Текстовые файлы', '*.txt'), ('Все файлы', '*')])
        if path:
            try:
                text = Path(path).read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError) as error:
                self.status.set(f'Не удалось открыть файл. {error}')
            else:
                if self.rebuild(text, fit=True):
                    self.set_input(text)
                    self.preset.set('')

    def rebuild(self, text=None, fit=False):
        name = self.algorithm.get()
        self.description.configure(text=DESCRIPTIONS[name])
        if text is None:
            text = self.input.get('1.0', 'end-1c')
        try:
            if name == LINES:
                geometry, rectangle = parse_segments(text)
                xmin, ymin, xmax, ymax = rectangle
                window = ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax))
                scene, traces = [], []
                for segment in geometry:
                    steps = []
                    scene.append(cohen_sutherland(segment, rectangle, steps))
                    traces.append(steps)
                summary = f'Отрезков: {len(geometry)} · Видимых: {sum(part is not None for part in scene)}'
                objects = [f'Отрезок {i}' for i in range(1, len(geometry) + 1)]
            else:
                polygon, window = parse_polygons(text)
                steps = []
                result = clip_polygon(polygon, window, steps)
                geometry, scene, traces = (polygon,), (result,), (steps,)
                summary = f'Вершин: {len(polygon)} · После отсечения: {len(result)}'
                objects = ['Многоугольник']
        except ValueError as error:
            self.status.set(f'Не отсечено. {error}')
            return False

        self.valid_text[name] = text
        self.active_name = name
        self.geometry, self.window, self.result, self.traces = geometry, window, scene, traces
        self.status.set(f'{name} · {summary}')
        self.objects.configure(values=objects, state='readonly' if len(objects) > 1 else 'disabled')
        self.object_name.set(objects[0] if objects else '')
        self.select_object()
        if fit:
            self.fit()
        return True

    def select_object(self, event=None):
        index = self.objects.current()
        self.steps = self.traces[index] if index >= 0 else ()
        self.table.delete(*self.table.get_children())
        for i, step in enumerate(self.steps):
            if self.active_name == LINES:
                check = ' / '.join(f'{code:04b}' for code in step.codes)
                action = SIDES.get(step.side, step.action)
            else:
                check = f'Ребро {i + 1} окна'
                action = f'Вершин: {len(step.polygon)}'
            self.table.insert('', 'end', iid=str(i), values=(i + 1, check, action))
        self.show_all()

    def show_all(self):
        self.stop_play()
        self.step_index = None
        self.table.selection_remove(*self.table.selection())
        self.details.configure(text='Показан итог. Выберите шаг в таблице.' if self.steps else 'Нет шагов отсечения.')
        self.redraw()

    def select_step(self, event=None):
        selected = self.table.selection()
        if selected and int(selected[0]) != self.step_index:
            self.show_step(int(selected[0]))

    def show_step(self, index, pause=True):
        if not self.steps:
            return
        if pause:
            self.stop_play()
        self.step_index = max(0, min(index, len(self.steps) - 1))
        item = str(self.step_index)
        self.table.selection_set(item)
        self.table.see(item)
        step = self.steps[self.step_index]
        if self.active_name == LINES:
            text = ' → '.join(point_text(p) for p in step.segment) if step.segment else 'Видимых точек нет.'
        else:
            text = 'Ребро ' + ' → '.join(point_text(p) for p in step.edge)
            if step.polygon:
                text += f' · {len(step.polygon)} вершин'
            else:
                text += ' · Видимых точек нет'
        self.details.configure(text=text)
        self.redraw()

    def move_step(self, delta):
        if self.step_index is None:
            self.show_step(0 if delta > 0 else len(self.steps) - 1)
        else:
            self.show_step(self.step_index + delta)

    def stop_play(self):
        if self.play_id:
            self.root.after_cancel(self.play_id)
            self.play_id = None
        self.play_button.configure(text='Пуск')

    def toggle_play(self):
        if self.play_id:
            self.stop_play()
            return
        if not self.steps:
            return
        if self.step_index is None or self.step_index == len(self.steps) - 1:
            self.show_step(0)
        self.play_button.configure(text='Пауза')
        self.play_id = self.root.after(550, self.tick)

    def tick(self):
        self.play_id = None
        if self.step_index < len(self.steps) - 1:
            self.show_step(self.step_index + 1, pause=False)
        if self.step_index < len(self.steps) - 1:
            self.play_id = self.root.after(550, self.tick)
        else:
            self.stop_play()

    def screen(self, x, y):
        return self.ox + float(x) * self.scale, self.oy - float(y) * self.scale

    def world(self, sx, sy):
        return (sx - self.ox) / self.scale, (self.oy - sy) / self.scale

    def fit(self):
        if self.fit_id:
            self.root.after_cancel(self.fit_id)
            self.fit_id = None
        width, height = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        points = ((0, 0),) + self.window + tuple(p for figure in self.geometry for p in figure)
        xs, ys = zip(*points)
        xmin, xmax, ymin, ymax = map(float, (min(xs), max(xs), min(ys), max(ys)))
        self.scale = max(0.1, min(80, (width - 60) / max(xmax - xmin, 1), (height - 60) / max(ymax - ymin, 1)))
        self.ox = width / 2 - (xmin + xmax) * self.scale / 2
        self.oy = height / 2 + (ymin + ymax) * self.scale / 2
        self.zoom.set(self.scale)
        self.redraw()

    def zoom_at(self, scale, sx, sy):
        x, y = self.world(sx, sy)
        self.scale = max(0.1, min(80, scale))
        self.ox, self.oy = sx - x * self.scale, sy + y * self.scale
        self.zoom.set(self.scale)
        self.redraw()

    def zoom_changed(self, value):
        self.zoom_at(float(value), self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)

    def wheel(self, event):
        if event.delta:
            self.zoom_at(self.scale * (1.12 if event.delta > 0 else 1 / 1.12), event.x, event.y)

    def pan(self, event):
        if self.drag:
            x, y, ox, oy = self.drag
            self.ox, self.oy = ox + event.x - x, oy + event.y - y
            self.redraw()

    def motion(self, event):
        x, y = self.world(event.x, event.y)
        self.hover.set(f'Точка ({x:.3f}, {y:.3f}) · Колесо — масштаб · Перетаскивание — сдвиг')

    def schedule_draw(self, event=None):
        if self.draw_id:
            self.root.after_cancel(self.draw_id)
        self.draw_id = self.root.after(30, self.redraw)

    def draw_grid(self, width, height):
        canvas = self.canvas
        xmin, ymax = self.world(0, 0)
        xmax, ymin = self.world(width, height)
        unit = 10 ** math.floor(math.log10(48 / self.scale))
        step = next(factor * unit for factor in (1, 2, 5, 10) if factor * unit >= 48 / self.scale)
        label_y = max(16, min(height - 15, self.oy + 15))
        label_x = max(32, min(width - 20, self.ox - 8))
        for i in range(math.ceil(xmin / step), math.floor(xmax / step) + 1):
            sx, _ = self.screen(i * step, 0)
            canvas.create_line(sx, 0, sx, height, fill=GRID, tags='grid')
            canvas.create_text(sx, label_y, text=f'{i * step:g}', font=('Arial', 9), fill=MUTED)
        for i in range(math.ceil(ymin / step), math.floor(ymax / step) + 1):
            _, sy = self.screen(0, i * step)
            canvas.create_line(0, sy, width, sy, fill=GRID, tags='grid')
            if i:
                canvas.create_text(label_x, sy, text=f'{i * step:g}', anchor='e', font=('Arial', 9), fill=MUTED)
        if 0 <= self.oy <= height:
            canvas.create_line(0, self.oy, width - 5, self.oy, fill=INK, arrow='last', tags='axis')
            canvas.create_text(width - 15, max(13, self.oy - 14), text='X', fill=INK, font=('Arial', 11, 'bold'))
        if 0 <= self.ox <= width:
            canvas.create_line(self.ox, height, self.ox, 5, fill=INK, arrow='last', tags='axis')
            canvas.create_text(min(width - 14, self.ox + 14), 14, text='Y', fill=INK, font=('Arial', 11, 'bold'))

    def draw_figure(self, points, color, width, tag, dash=()):
        if not points:
            return
        if len(points) == 1 or (len(points) == 2 and points[0] == points[1]):
            x, y = self.screen(*points[0])
            self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline=PAPER, tags=tag)
            return
        path = points + points[:1] if len(points) > 2 else points
        coords = [value for point in path for value in self.screen(*point)]
        self.canvas.create_line(*coords, fill=color, width=width, dash=dash, joinstyle='round',
                                capstyle='round', tags=tag)

    def redraw(self):
        if self.draw_id:
            self.root.after_cancel(self.draw_id)
            self.draw_id = None
        canvas = self.canvas
        width, height = canvas.winfo_width(), canvas.winfo_height()
        canvas.delete('all')
        self.zoom_label.configure(text=f'{self.scale:.2g} px')
        step = self.steps[self.step_index] if self.step_index is not None else None
        if self.active_name == POLYGON and step is None and self.result and len(self.result[0]) > 2:
            coords = [value for point in self.result[0] for value in self.screen(*point)]
            canvas.create_polygon(*coords, fill=PALE_GREEN, outline='', tags='visible-fill')
        self.draw_grid(width, height)
        if self.source_visible.get():
            for points in self.geometry:
                self.draw_figure(points, BLUE, 2, 'source', dash=(5, 4))
        self.draw_figure(self.window, ORANGE, 2, 'window')
        if step is not None and self.active_name == LINES:
            color = GREEN if step.action == 'Принят' else PURPLE
            self.draw_figure(step.segment, color, 3, 'step')
        elif step is not None:
            self.draw_figure(step.polygon, PURPLE, 3, 'step')
            self.draw_figure(step.edge, ORANGE, 4, 'edge')
        else:
            for points in self.result:
                self.draw_figure(points, GREEN, 3, 'visible')

    def help(self):
        messagebox.showinfo('Отсечение фигур',
            'Выберите алгоритм, отредактируйте данные или откройте файл .txt. '
            'Нажмите «Отсечь» или Ctrl+Enter. Готовые примеры есть справа.\n\n'
            'Сазерленд — Коэн: число отрезков, строки x₁ y₁ x₂ y₂, строка xmin ymin xmax ymax. '
            'Код конца состоит из битов 1000 (верх), 0100 (низ), 0010 (право), 0001 (лево).\n\n'
            'Сазерленд — Ходжман: сначала исходный контур, затем окно. У каждого — число вершин '
            'и строки x y в порядке обхода. Оба контура выпуклые.\n\n'
            'Оранжевый — окно, синий пунктир — исходные фигуры, зелёный — видимая часть. '
            'Фиолетовый показывает промежуточный результат. Для итогового вида нажмите «Всё».\n\n'
            'Колесо меняет масштаб около курсора, перетаскивание сдвигает сетку. '
            'Координаты от −1000 до 1000, десятичный разделитель — точка.', parent=self.root)

    def close(self):
        for timer in (self.play_id, self.draw_id, self.fit_id):
            if timer:
                self.root.after_cancel(timer)
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = ClippingApp(root)
    root.mainloop()
