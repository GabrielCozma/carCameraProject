cwd=`pwd`
src_dir=$cwd/src

records_dir=$cwd/records

if [ ! -d $records_dir ]; then
    mkdir $records_dir
    if [ $? -ne 0 ]; then
        exit -1
    fi
fi

run_script="run.sh"
install_marker="# _DCAM_APP_"
install_line="$cwd/$run_script"
rclocal="/etc/rc.local"

if [ ! -f $rclocal ]; then
    echo "Error: File $rclocal not found!"
    exit -1
fi

# Check if already installed
grep -q "$install_marker" $rclocal
if [ $? -eq 0 ]; then
    echo "Already installed. Replacing startup command in $rclocal"
    cmd="/^${install_marker}/{n;s@.*@${install_line}@;}"
    # echo $cmd
    sudo sed -i.bak "$cmd" ${rclocal}
else
    cmd="s@\(^exit 0\$\)@${install_marker}\n${install_line}\n\n&@"
    # echo $cmd
    sudo sed -i.bak "$cmd" ${rclocal}
fi

if [ $? -ne 0 ]; then
        exit -1
fi

echo "#!/bin/bash" > $run_script
echo "" >> $run_script
echo "# Auto generated." >> $run_script
echo "" >> $run_script
echo "cd $src_dir" >> $run_script
echo "sudo -H -u $USER python3 main.py -r \"$records_dir\" &" >> $run_script
chmod +x $run_script

if [ $? -ne 0 ]; then
        exit -1
fi
