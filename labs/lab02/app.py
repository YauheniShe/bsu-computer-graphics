"""Лабораторная 2, вариант 13. Запуск: python app.py."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

from processing import compare, read_image


ROOT = Path(__file__).resolve().parent
BG, PAPER, INK, MUTED, LINE = "#F4F5F8", "#FFFFFF", "#202435", "#697386", "#E2E5ED"
FONT = "Helvetica Neue"
SAMPLES = {
    "Текст с тенью и шумом": ("shadow_text.png", "threshold"),
    "Бледный текст": ("faint_text.png", "threshold"),
    "Размытое изображение": ("blurred_shapes.png", "sharpen"),
    "Изображение с шумом": ("noisy_shapes.png", "sharpen"),
}


class ImagePanel(tk.Frame):
    def __init__(self, parent, app, title, result_index=None):
        super().__init__(parent, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        self.app, self.result_index = app, result_index
        self.image = None
        self.photo = None
        self.render_job = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.title = tk.Label(self, text=title, bg=PAPER, fg=INK, font=(FONT, 16, "bold"), anchor="w")
        self.title.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 3))
        self.details = tk.Label(self, bg=PAPER, fg=MUTED, font=(FONT, 10), anchor="w")
        self.details.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.canvas = tk.Canvas(self, bg="#ECEEF3", highlightthickness=0, width=320, height=330)
        self.canvas.grid(row=2, column=0, sticky="nsew", padx=12)
        self.canvas.bind("<Configure>", self.schedule_render)
        self.canvas.bind("<Button-1>", lambda event: self.open_full_size())
        buttons = tk.Frame(self, bg=PAPER)
        buttons.grid(row=3, column=0, sticky="ew", padx=12, pady=12)
        self.view_button = ttk.Button(buttons, text="Открыть крупно", command=self.open_full_size, state="disabled")
        self.view_button.pack(side="left")
        self.save_button = None
        if result_index is not None:
            self.save_button = ttk.Button(buttons, text="Сохранить…", state="disabled",
                                          command=lambda: app.save_result(result_index))
            self.save_button.pack(side="right")

    def show(self, array, details=""):
        self.image = Image.fromarray(array) if array is not None else None
        self.details.configure(text=details)
        enabled = "normal" if self.image is not None else "disabled"
        self.view_button.configure(state=enabled)
        if self.save_button is not None:
            self.save_button.configure(state=enabled)
        self.render()

    def schedule_render(self, event=None):
        if self.render_job is not None:
            self.after_cancel(self.render_job)
        self.render_job = self.after(40, self.render)

    def render(self):
        if self.render_job is not None:
            self.after_cancel(self.render_job)
            self.render_job = None
        self.canvas.delete("all")
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        if self.image is None:
            self.photo = None
            self.canvas.create_text(width / 2, height / 2, text="Нет результата", fill=MUTED, font=(FONT, 12))
            return
        preview = self.image.copy()
        preview.thumbnail((max(1, width - 16), max(1, height - 16)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(preview)
        self.canvas.create_image(width / 2, height / 2, image=self.photo)

    def open_full_size(self):
        if self.image is None:
            return
        window = tk.Toplevel(self)
        window.title(self.title.cget("text") + " — 100%")
        window.geometry(f"{min(1100, self.image.width + 24)}x{min(800, self.image.height + 24)}")
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)
        canvas = tk.Canvas(window, highlightthickness=0, bg=BG)
        horizontal = ttk.Scrollbar(window, orient="horizontal", command=canvas.xview)
        vertical = ttk.Scrollbar(window, command=canvas.yview)
        canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        horizontal.grid(row=1, column=0, sticky="ew")
        vertical.grid(row=0, column=1, sticky="ns")
        canvas.photo = ImageTk.PhotoImage(self.image)
        canvas.create_image(0, 0, anchor="nw", image=canvas.photo)
        canvas.configure(scrollregion=(0, 0, self.image.width, self.image.height))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"))
        return window


class ImageApp:
    def __init__(self, root, auto_load=True):
        self.root = root
        self.image = None
        self.path = None
        self.results = None
        self.future = None
        self.pending = None
        self.last_mode = "threshold"
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.variables = {}
        self.help_window = None
        root.title("Обработка изображений — Лабораторная 2")
        root.geometry("1220x780")
        root.minsize(1120, 720)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", padding=(10, 7), font=(FONT, 11), background=PAPER, foreground=INK, bordercolor=LINE)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 9), font=(FONT, 11), background=BG)
        style.map("TNotebook.Tab", background=[("selected", PAPER)], foreground=[("selected", INK)])
        style.configure("TFrame", background=PAPER)
        style.configure("TLabel", background=PAPER, foreground=INK, font=(FONT, 11))
        style.configure("TSpinbox", padding=5, font=(FONT, 11))
        style.configure("TCombobox", padding=5, font=(FONT, 11), background=PAPER)
        style.map("TCombobox", fieldbackground=[("readonly", PAPER)], selectbackground=[("readonly", PAPER)], selectforeground=[("readonly", INK)])

        outer = tk.Frame(root, bg=BG)
        outer.pack(fill="both", expand=True, padx=24, pady=20)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)
        header = tk.Frame(outer, bg=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        tk.Label(header, text="Обработка изображений", bg=BG, fg=INK,
                 font=(FONT, 24, "bold")).pack(side="left")
        ttk.Button(header, text="Справка", command=self.show_help).pack(side="right")
        tk.Label(header, text="Лабораторная 2 · Вариант 13", bg=BG, fg=MUTED,
                 font=(FONT, 11)).pack(side="right", padx=20)

        files = tk.Frame(outer, bg=BG)
        files.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        ttk.Button(files, text="Открыть изображение…", command=self.choose_file).pack(side="left")
        tk.Label(files, text="Пример:", bg=BG, fg=MUTED, font=(FONT, 11)).pack(side="left", padx=(22, 8))
        self.sample_var = tk.StringVar(value=next(iter(SAMPLES)))
        selector = ttk.Combobox(files, textvariable=self.sample_var, values=list(SAMPLES), state="readonly", width=26)
        selector.pack(side="left")
        selector.bind("<<ComboboxSelected>>", lambda event: self.load_sample())
        ttk.Button(files, text="Открыть пример", command=self.load_sample).pack(side="left", padx=8)

        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        threshold = ttk.Frame(self.notebook, padding=14)
        sharpen = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(threshold, text="Локальные пороги")
        self.notebook.add(sharpen, text="Повышение резкости")
        self.add_parameter(threshold, "window", "Окно", "31", 3, 151, 2)
        self.add_parameter(threshold, "niblack_k", "k Ниблэка", "0.2", -1, 1, 0.05)
        self.add_parameter(threshold, "sauvola_k", "k Сауволы", "0.2", 0, 1, 0.05)
        self.add_parameter(sharpen, "laplacian_amount", "Лаплас: коэффициент", "0.6", 0, 3, 0.1)
        self.add_parameter(sharpen, "unsharp_amount", "Маска: коэффициент", "1.5", 0, 5, 0.1)
        self.add_parameter(sharpen, "sigma", "Сигма", "1.2", 0.3, 5, 0.1)
        for frame in (threshold, sharpen):
            ttk.Button(frame, text="Обработать", command=self.process).pack(side="right")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_mode_change)

        images = tk.Frame(outer, bg=BG)
        images.grid(row=3, column=0, sticky="nsew")
        images.rowconfigure(0, weight=1)
        self.panels = []
        for i, title in enumerate(("Исходное", "Ниблэк", "Саувола")):
            images.columnconfigure(i, weight=1, uniform="images")
            panel = ImagePanel(images, self, title, i - 1 if i else None)
            panel.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 2 else 6))
            self.panels.append(panel)

        self.status = tk.Label(outer, text="Открой изображение или выбери пример.", bg=BG,
                               fg=MUTED, anchor="w", font=(FONT, 11), wraplength=1060, justify="left")
        self.status.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        self.poll_job = root.after(40, self.poll_result)
        self.load_job = root.after(80, self.load_sample) if auto_load else None
        root.protocol("WM_DELETE_WINDOW", self.close)

    @property
    def mode(self):
        return "threshold" if self.notebook.index(self.notebook.select()) == 0 else "sharpen"

    def add_parameter(self, frame, key, label, value, minimum, maximum, step):
        ttk.Label(frame, text=label).pack(side="left", padx=(0, 7))
        variable = tk.StringVar(value=value)
        spin = ttk.Spinbox(frame, textvariable=variable, from_=minimum, to=maximum,
                           increment=step, width=6)
        spin.pack(side="left", padx=(0, 18))
        spin.bind("<Return>", lambda event: self.process())
        variable.trace_add("write", lambda *args: self.parameters_changed())
        self.variables[key] = variable

    def invalidate_results(self):
        if self.future is not None:
            self.future.cancel()
            self.future = None
        self.results = None
        for panel in self.panels[1:]:
            panel.show(None)

    def parameters_changed(self):
        if self.image is not None:
            self.invalidate_results()
            self.status.configure(text="Параметры изменены. Нажми «Обработать» или Enter.", fg=MUTED)

    def on_mode_change(self, event=None):
        if self.image is not None and self.mode != self.last_mode:
            self.process()

    def choose_file(self):
        path = filedialog.askopenfilename(title="Открыть изображение", filetypes=[
            ("Изображения", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.gif"), ("Все файлы", "*")])
        if path:
            self.load_path(path)

    def load_sample(self):
        self.load_job = None
        filename, mode = SAMPLES[self.sample_var.get()]
        self.notebook.select(0 if mode == "threshold" else 1)
        self.load_path(ROOT / "samples" / filename)

    def load_path(self, path):
        try:
            image = read_image(path)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            self.status.configure(text=f"Не удалось открыть файл: {error}", fg="#B4233A")
            return False
        self.image, self.path = image, Path(path)
        height, width = image.shape[:2]
        self.panels[0].show(image, f"{width} × {height} · {self.path.name}")
        self.process()
        return True

    def parameters(self):
        if self.mode == "threshold":
            return {"window": int(self.variables["window"].get()),
                    "niblack_k": float(self.variables["niblack_k"].get().replace(",", ".")),
                    "sauvola_k": float(self.variables["sauvola_k"].get().replace(",", "."))}
        return {key: float(self.variables[key].get().replace(",", "."))
                for key in ("laplacian_amount", "unsharp_amount", "sigma")}

    def process(self):
        if self.image is None:
            return
        self.invalidate_results()
        self.last_mode = self.mode
        titles = ("Ниблэк", "Саувола") if self.mode == "threshold" else ("Лаплас", "Нерезкое маскирование")
        for panel, title in zip(self.panels[1:], titles):
            panel.title.configure(text=title)
        try:
            parameters = self.parameters()
        except ValueError:
            self.status.configure(text="Проверь параметры: окно — целое нечётное число; остальные поля — числа.", fg="#B4233A")
            return
        self.pending = (self.mode, parameters, perf_counter())
        self.future = self.executor.submit(compare, self.image, self.mode, parameters)
        self.status.configure(text="Обработка…", fg=MUTED)

    def poll_result(self):
        if self.future is not None and self.future.done():
            future, self.future = self.future, None
            try:
                self.results = future.result()
                mode, parameters, started = self.pending
                if mode == "threshold":
                    notes = (f"Окно {parameters['window']} · k = {parameters['niblack_k']:g}",
                             f"Окно {parameters['window']} · k = {parameters['sauvola_k']:g} · R = 128")
                else:
                    notes = (f"Коэффициент {parameters['laplacian_amount']:g}",
                             f"Коэффициент {parameters['unsharp_amount']:g} · σ = {parameters['sigma']:g}")
                for panel, result, note in zip(self.panels[1:], self.results, notes):
                    panel.show(result, note)
                elapsed = perf_counter() - started
                self.status.configure(text=f"Готово за {elapsed:.2f} с. Результаты сохраняются в исходном размере; «Открыть крупно» показывает 100%.", fg=MUTED)
            except Exception as error:
                self.results = None
                self.status.configure(text=f"Ошибка обработки: {error}", fg="#B4233A")
        self.poll_job = self.root.after(40, self.poll_result)

    def save_result(self, index, path=None):
        if self.results is None:
            return False
        if path is None:
            suffixes = ("niblack", "sauvola") if self.last_mode == "threshold" else ("laplacian", "unsharp")
            path = filedialog.asksaveasfilename(title="Сохранить результат", defaultextension=".png",
                initialfile=f"{self.path.stem}_{suffixes[index]}.png", filetypes=[("PNG", "*.png"), ("TIFF", "*.tif"), ("BMP", "*.bmp")])
        if not path:
            return False
        try:
            Image.fromarray(self.results[index]).save(path)
        except (OSError, ValueError) as error:
            self.status.configure(text=f"Не удалось сохранить: {error}", fg="#B4233A")
            return False
        self.status.configure(text=f"Сохранено: {path}", fg=MUTED)
        return True

    def show_help(self):
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.lift()
            return
        window = tk.Toplevel(self.root)
        self.help_window = window
        window.title("Справка")
        window.geometry("680x570")
        text = tk.Text(window, wrap="word", bg=PAPER, fg=INK, font=(FONT, 13),
                       padx=24, pady=22, relief="flat", spacing3=10)
        scroll = ttk.Scrollbar(window, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("1.0", """ЛОКАЛЬНЫЕ ПОРОГИ
Для каждого пикселя вычисляются среднее m и стандартное отклонение s в соседнем окне. Ниблэк: T = m − k·s. Саувола: T = m·(1 + k·(s/128 − 1)). Пиксель темнее порога становится чёрным, остальные — белыми.

Размер окна должен быть нечётным. Слишком маленькое окно теряет внутренние части широких штрихов; слишком большое хуже учитывает локальное освещение.

СРАВНЕНИЕ
Открой «Текст с тенью и шумом»: Саувола лучше очищает фон. В примере «Бледный текст» Ниблэк сохраняет слабые штрихи, которые Саувола при k=0.2 теряет. Эти наблюдения относятся к данным примерам и параметрам, а не ко всем изображениям.

ПОВЫШЕНИЕ РЕЗКОСТИ
Лаплас усиливает разницу между пикселем и четырьмя соседями. Нерезкое маскирование прибавляет разность исходного и сглаженного изображения. Коэффициент задаёт усиление, σ — масштаб сглаживания.

На размытом примере становятся заметнее края. На зашумлённом усиливается и шум: увеличение резкости не восстанавливает утраченную информацию и может создавать ореолы.

УПРАВЛЕНИЕ
После изменения параметров нажми «Обработать» или Enter. Нажми на изображение или «Открыть крупно», чтобы рассмотреть пиксели. Кнопки «Сохранить…» записывают результат в полном размере. Формулы и измерения приведены в THEORY.md и samples/RESULTS.md.
""")
        text.configure(state="disabled")

    def close(self):
        self.root.after_cancel(self.poll_job)
        if self.load_job is not None:
            self.root.after_cancel(self.load_job)
        for panel in self.panels:
            if panel.render_job is not None:
                panel.after_cancel(panel.render_job)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ImageApp(root)
    root.mainloop()
