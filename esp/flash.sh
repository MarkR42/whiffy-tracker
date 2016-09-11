
# Older versions of Micropython used 561152
FS_OFFSET=589824

esptool.py write_flash $FS_OFFSET fs.img
