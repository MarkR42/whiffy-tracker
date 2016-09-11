
# Older versions of Micropython used 561152
FS_OFFSET=589824

esptool.py read_flash $FS_OFFSET 1048576 fsout.img
