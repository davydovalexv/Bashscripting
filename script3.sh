read -p "Укажите путь до директории и имя архива: " dir_path archive_name
if [[ ! -d "$dir_path" ]]; then
    echo "директория не существует"
    exit 1
fi
current_date=$(date +%F)
tar -czf "${archive_name}_${current_date}.tar.gz" -C "$(dirname "$dir_path")" "$(basename "$dir_path")"
echo "Архив создан"
