#!/bin/zsh
cd -- "${0:A:h}" || exit 1

lab_fail() {
    printf '%s\n' "$1"
    read -r '?Нажми Enter, чтобы закрыть окно.'
    exit 1
}

if [[ ! -x .venv/bin/python ]]; then
    lab_interpreter=''
    for lab_python in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        if "$lab_python" -c 'import sys, tkinter; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
            lab_interpreter="$lab_python"
            break
        fi
    done
    [[ -n "$lab_interpreter" ]] || lab_fail 'Нужен Python 3.10+ с Tkinter.'
    "$lab_interpreter" -m venv .venv || lab_fail 'Не удалось создать окружение Python.'
fi

if ! .venv/bin/python -c 'import numpy, PIL, tkinter' >/dev/null 2>&1; then
    printf 'Первый запуск: установка NumPy и Pillow.\n'
    .venv/bin/python -m pip install -r requirements.txt || lab_fail 'Не удалось установить зависимости.'
fi

.venv/bin/python app.py || lab_fail 'Не удалось запустить программу.'
