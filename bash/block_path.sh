#!/bin/bash

show_usage() {
  echo "Использование:"
  echo "  $0 block path1 [path2 ...]         # заблокировать доступ к path1, path2 и т.д."
  echo "  $0 unblock path1 [path2 ...]       # разблокировать доступ"
  echo "  $0 block -f /path/to/file.txt      # заблокировать пути из файла"
  echo "  $0 unblock -f /path/to/file.txt    # разблокировать пути из файла"
  exit 1
}

if [[ $# -lt 2 ]]; then
  show_usage
fi

ACTION=$1
shift

# Читаем пути либо из файла (-f), либо из аргументов
if [[ "$1" == "-f" ]]; then
  FILE_PATH=$2
  if [[ ! -f "$FILE_PATH" ]]; then
    echo "Файл не найден: $FILE_PATH"
    exit 1
  fi
  mapfile -t PATHS < "$FILE_PATH"
else
  PATHS=("$@")
fi

block() {
  for p in "${PATHS[@]}"; do
    if [[ -d "$p" || -f "$p" ]]; then
      chmod -R 000 "$p"
      echo "$(date): Заблокирован доступ к $p" >> ~/work_access_control.log
    else
      echo "Путь не найден или недоступен: $p"
    fi
  done
  osascript -e 'display notification "Доступ к проектам заблокирован. Время отдыха!" with title "Work Blocker"'
}

unblock() {
  for p in "${PATHS[@]}"; do
    if [[ -d "$p" || -f "$p" ]]; then
      chmod -R 755 "$p"
      echo "$(date): Разблокирован доступ к $p" >> ~/work_access_control.log
    else
      echo "Путь не найден или недоступен: $p"
    fi
  done
  osascript -e 'display notification "Доступ к проектам восстановлен. Можно работать." with title "Work Blocker"'
}

case "$ACTION" in
  block)
    block
    ;;
  unblock)
    unblock
    ;;
  *)
    show_usage
    ;;
esac
