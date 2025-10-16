read -p "Введите полный путь к файлу: " filename
if [ -f "$filename" ]; then
        line_count=$(wc -l < "$filename")
        echo "Количество строк: $line_count"
else
        echo "Нет файла"
fi
