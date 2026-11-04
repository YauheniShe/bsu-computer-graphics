#!/bin/zsh
cd -- "${0:A:h}/labs/lab01" || exit 1

for lab_python in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
    if "$lab_python" -c 'import sys, tkinter; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        "$lab_python" app.py
        lab_exit_code=$?
        if (( lab_exit_code != 0 )); then
            read -r '?Не удалось запустить программу. Нажми Enter, чтобы закрыть окно.'
        fi
        exit "$lab_exit_code"
    fi
done

printf 'Нужен Python 3.10 или новее с Tkinter.\n'
read -r '?Нажми Enter, чтобы закрыть окно.'
exit 1
