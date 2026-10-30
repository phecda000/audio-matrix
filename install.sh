#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
app_dir="$data_home/audio-matrix"
binary="$app_dir/bin/audio-matrix"
bin_dir="$HOME/.local/bin"
applications_dir="$data_home/applications"
icons_dir="$data_home/icons/hicolor/scalable/apps"

install -d "$app_dir" "$bin_dir" "$applications_dir" "$icons_dir"
rm -rf "$app_dir/src" "$app_dir/bin" "$app_dir/assets" "$app_dir/share"
cp -a "$project_dir/src" "$app_dir/"
cp -a "$project_dir/bin" "$app_dir/"
cp -a "$project_dir/assets" "$app_dir/"
cp -a "$project_dir/share" "$app_dir/"
chmod 0755 "$binary"
ln -sfn "$binary" "$bin_dir/audio-matrix"
install -m 0644 "$project_dir/assets/audio-matrix.svg" "$icons_dir/audio-matrix.svg"
sed "s|@EXEC@|$binary|g" \
    "$project_dir/share/audio-matrix.desktop" \
    > "$applications_dir/audio-matrix.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$data_home/icons/hicolor" >/dev/null 2>&1 || true
fi

printf '音频矩阵已安装。\n'
printf '从应用菜单启动，或运行：%s\n' "$bin_dir/audio-matrix"
