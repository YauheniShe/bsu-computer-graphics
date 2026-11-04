"""Таблицы отчёта из сохранённого замера и проверенных трассировок."""

from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))
from raster import bresenham_circle, bresenham_line


def table(path, columns, heading, rows):
    content = [r'\begin{tabular}{' + columns + r'}\toprule',
               heading + r'\\\midrule', *[row + r'\\' for row in rows],
               r'\bottomrule\end{tabular}']
    path.write_text('\n'.join(content)+'\n', encoding='utf-8')


def escape(text):
    return ''.join({'&': r'\&', '_': r'\_', '%': r'\%', '#': r'\#',
                    '{': r'\{', '}': r'\}', '$': r'\$'}.get(c, c) for c in str(text))


def main():
    output = Path(__file__).resolve().parent
    data = json.loads((LAB/'benchmark_results.json').read_text(encoding='utf-8'))
    line_rows = []
    for name in ('Пошаговый', 'ЦДА', 'Брезенхем — отрезок', 'Ву — сглаживание'):
        rows = [r for r in data['rows'] if r['algorithm'] == name]
        line_rows.append(escape(name) + ' & ' + ' & '.join(f'{r["median_us"]:.2f}' for r in rows))
    table(output/'line_times.tex', 'lrrr', r'Алгоритм & $L=100$ & $L=500$ & $L=1000$', line_rows)
    circle_rows = [f'{r["size"]} & {r["pixels_per_call"]} & {r["median_us"]:.2f} & '
                   f'{r["min_us"]:.2f}--{r["max_us"]:.2f}' for r in data['rows'] if r['kind'] == 'radius']
    table(output/'circle_times.tex', 'rrrr', r'$R$ & Пикселей & Медиана, мкс & Мин.--макс., мкс', circle_rows)
    when = datetime.fromisoformat(data['measured_at']).astimezone(ZoneInfo('Europe/Minsk'))
    (output/'environment.tex').write_text(
        f'Замер выполнен {when:%d.%m.%Y} в {when:%H:%M} (Минск): '
        f'{escape(data["cpu"])}, {escape(data["system"])}, {escape(data["machine"])}, '
        f'Python {escape(data["python"])}. Число серий --- {data["repeats"]}; '
        f'повторений набора входов в серии --- {data["loops"]}.\n', encoding='utf-8')

    trace = []
    bresenham_line(0, 0, 13, 8, trace)
    def row(index):
        step = trace[index]
        action = {'конец': '---', 'диагональ': 'Д', 'прямо': 'П'}[step.action]
        return f'{index} & {step.x} & {step.y} & {step.value} & {action}'
    heading = r'$i$ & $x_i$ & $y_i$ & $d_i$ & Шаг'
    table(output/'line_steps.tex', r'rrrrc@{\qquad}rrrrc', heading+' & '+heading,
          [row(i)+' & '+row(i+7) for i in range(7)])
    trace = []
    bresenham_circle(0, 0, 8, trace)
    table(output/'circle_steps.tex', 'rrrrl', r'$i$ & $u_i$ & $v_i$ & $d_i$ & Изменение координат',
          [f'{i} & {s.x} & {s.y} & {s.value} & ' + (r'$u+1,\;v-1$' if s.value >= 0 else r'$u+1$')
           for i, s in enumerate(trace)])
    print('Таблицы отчёта обновлены.')


if __name__ == '__main__':
    main()
