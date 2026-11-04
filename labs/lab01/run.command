#!/bin/zsh
# Запуск двойным щелчком в Finder; путь не зависит от текущей папки.
cd -- "${0:A:h}" || exit 1
if [[ -x /opt/homebrew/bin/python3 ]]; then
    exec /opt/homebrew/bin/python3 app.py
elif [[ -x /usr/local/bin/python3 ]]; then
    exec /usr/local/bin/python3 app.py
else
    exec python3 app.py
fi
