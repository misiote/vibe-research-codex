#!/bin/zsh
vr_share_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$vr_share_root/install.sh"
vr_status=$?
printf '\n按回车关闭。\n'
read REPLY
exit $vr_status
