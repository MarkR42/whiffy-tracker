
# Create a msdos floppy disc image, which we will write to the
# flash of the esp8266.

rm -f fs.img

# Micropython uses a dos fs at a hard-coded (?) offset.

# Use a wacky mformat command to initialise the drive.

# -T = total size, in sectors, sectors are 4k.
# -d 1 = number of copies of fat.
# mformat -C -T 256 -i fs.img  -h 255 -s 63 -S 5 -d 1 ::

# Note that we seem to need a 4096 sector size, or Micropython
# won't access the fs.
mkfs.fat -C -f 1 -S 4096 fs.img 1024

mcopy -i fs.img -s fsroot/* :: 

# Create some directories
# mmd -i fs.img data1 data2

minfo -i fs.img :: 
mdir -i fs.img :: 

./truncate_image.py fs.img
